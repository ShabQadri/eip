import json
import re
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

import aiohttp
from pydantic import BaseModel, Field, ValidationError, model_validator

from src.config.settings import settings

logger = logging.getLogger("eip.gemini_service")

class ArticleEditorialAnalysis(BaseModel):
    """
    Pydantic schema to validate structured JSON returned from Gemini article analysis.
    """
    publish: bool
    confidence: float
    canonical_entity: str
    display_title: str
    event_type: str
    development_type: str  # NEW_DEVELOPMENT | UPDATE | CONFIRMATION | CORRECTION | REPEAT | RUMOR | OPINION | RECAP | LOW_VALUE
    is_confirmed: bool
    is_new_development: bool
    what_happened: str
    why_it_matters: str
    summary: str
    importance_score: int
    source_claims: List[str]
    unsupported_claims: List[str]
    facts: List[str]
    uncertainties: List[str]
    source_url: str
    image_needed: bool
    trailer_needed: bool
    needs_second_source: bool
    reason_if_rejected: Optional[str] = None


class ClaimVerification(BaseModel):
    claim: str = Field(description="The specific factual claim extracted from the final story text.")
    status: str = Field(description="The verification status: must be exactly 'SUPPORTED', 'UNSUPPORTED', 'INFERENCE', or 'UNCERTAIN'.")
    evidence: str = Field(description="The exact supporting text/sentence quoted from the source articles if status is 'SUPPORTED', else empty.")

class FactCheckReport(BaseModel):
    verifications: List[ClaimVerification] = Field(description="List of verification audits for every factual claim.")

    @model_validator(mode="before")
    @classmethod
    def normalize_keys(cls, data: Any) -> Any:
        from typing import Any
        if isinstance(data, dict):
            if "verifications" not in data:
                for k in ["claims", "verification_report", "verification", "reports", "claims_verification"]:
                    if k in data and isinstance(data[k], list):
                        data["verifications"] = data[k]
                        break
            if "verifications" not in data:
                for k, v in data.items():
                    if isinstance(v, list):
                        data["verifications"] = v
                        break
        return data


class GeminiService:
    """
    Service interfacing with Google Gemini API via lightweight HTTP REST requests.
    Supports structured extraction, classification, and final editorial writing.
    """
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.endpoint = "https://generativelanguage.googleapis.com/v1beta"
        
        # Models configuration from the approved plan
        self.lite_model = "gemini-3.5-flash-lite"
        self.strong_model = "gemini-3.6-flash"
        
        self.verification_reports = {}
        
        # System constitution instruction
        self.constitution = (
            "You are the editorial intelligence engine for Entertainment News Digest.\n"
            "Your mission is to identify important entertainment developments and eliminate noise.\n"
            "READ THE ARTICLE BODY. Never judge the article from its headline alone.\n"
            "Never invent facts. Never invent dates. Never invent sources.\n"
            "Never convert speculation into confirmed news.\n\n"
            "ACCEPT:\n"
            "- official announcements, major casting, production starts, production completions,\n"
            "- trailers, teasers, first looks, release dates, release-date changes, renewals,\n"
            "- cancellations, major awards, major box-office milestones, major OTT announcements,\n"
            "- major studio/network announcements, significant reviews, and major industry developments.\n\n"
            "REJECT:\n"
            "- dating, relationships, paparazzi, airport sightings, celebrity personal life,\n"
            "- social-media drama, fan theories, celebrity reactions, top-10 articles, rankings,\n"
            "- galleries, photo collections, recaps, ending explanations, clickbait, SEO rewrites,\n"
            "- old news republished as new, unconfirmed rumors, and speculation presented as fact.\n\n"
            "CORE RULE:\n"
            "Do not fill the digest. If only five developments are genuinely important, publish five.\n"
            "If nothing important happened, publish nothing.\n"
            "A subscriber should feel: Everything important in entertainment, no noise."
        )

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json"
        }

    async def verify_models_live(self) -> List[str]:
        """
        Pings Gemini models endpoint to check if API key is active and lists accessible models.
        """
        if not self.api_key:
            logger.error("Gemini API key is not configured.")
            return []
            
        url = f"{self.endpoint}/models?key={self.api_key}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._get_headers(), timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [m.get("name", "").split("/")[-1] for m in data.get("models", [])]
                        logger.info(f"Verified available Gemini models: {models}")
                        return models
                    else:
                        resp_text = await response.text()
                        logger.error(f"Failed to query Gemini models: HTTP {response.status} - {resp_text}")
                        return []
        except Exception as e:
            logger.error(f"Error querying Gemini models: {e}")
            return []

    async def _post_generate(self, model: str, payload: Dict[str, Any]) -> Tuple[Optional[str], str]:
        """Helper to post content generation requests with transient failure retries."""
        if not self.api_key:
            return None, "API_KEY_MISSING"

        url = f"{self.endpoint}/models/{model}:generateContent?key={self.api_key}"
        
        attempts = 3
        backoff = 2.0
        
        async with aiohttp.ClientSession() as session:
            for attempt in range(1, attempts + 1):
                try:
                    async with session.post(url, json=payload, headers=self._get_headers(), timeout=30) as response:
                        if response.status >= 500 or response.status == 429:
                            # Trigger retry on transient server errors and rate limits
                            raise aiohttp.ClientResponseError(
                                response.request_info, response.history, status=response.status, message=f"Retryable Error {response.status}"
                            )
                        
                        if response.status == 200:
                            data = await response.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts:
                                    text_result = parts[0].get("text", "")
                                    return text_result, "SUCCESS"
                            return None, "NO_CANDIDATES"
                        
                        resp_text = await response.text()
                        logger.error(f"Gemini API returned error (attempt {attempt}): HTTP {response.status} - {resp_text}")
                        return None, f"HTTP_{response.status}"

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warning(f"Gemini API request failed (attempt {attempt}): {e}")
                    if attempt < attempts:
                        # Sleep 15s if rate limited to allow quota to reset
                        sleep_time = 15.0 if getattr(e, "status", None) == 429 else backoff
                        await asyncio.sleep(sleep_time)
                        backoff *= 2.0
                    else:
                        return None, type(e).__name__
                except Exception as e:
                    logger.error(f"Unexpected error calling Gemini API: {e}")
                    return None, "UNEXPECTED_ERROR"

        return None, "MAX_RETRIES_FAILED"

    async def analyze_article(self, article_title: str, article_body: str, article_url: str, article_desc: str = "") -> Optional[ArticleEditorialAnalysis]:
        """
        Runs article classification and details extraction using gemini-3.5-flash-lite.
        Validates output against Pydantic schema, retrying once on format failure.
        """
        prompt = (
            f"Analyze the following article page content for Entertainment News Digest.\n\n"
            f"ARTICLE TITLE: {article_title}\n"
            f"ARTICLE URL: {article_url}\n"
            f"ARTICLE SUMMARY: {article_desc}\n\n"
            f"ARTICLE BODY:\n{article_body}\n\n"
            f"CRITICAL: Distinguish strictly between FACT, INFERENCE, and UNKNOWN/UNCONFIRMED details.\n"
            f"Do not guess. If details like casting, dates, or trailers are not explicitly confirmed,\n"
            f"classify them as uncertainties or list them in the 'unsupported_claims' field.\n\n"
            f"You must return a single JSON object containing exactly the following keys and types:\n"
            f"- 'publish' (boolean): whether this article reports a real, high-value, confirmed entertainment event worthy of being published.\n"
            f"- 'confidence' (float 0.0 to 1.0): your confidence in this decision.\n"
            f"- 'canonical_entity' (string): name of the film, series, show, actor, or studio this article focuses on.\n"
            f"- 'display_title' (string): clean, formatted title for the event.\n"
            f"- 'event_type' (string): movie | tv | general.\n"
            f"- 'development_type' (string): NEW_DEVELOPMENT | UPDATE | CONFIRMATION | CORRECTION | REPEAT | RUMOR | OPINION | RECAP | LOW_VALUE.\n"
            f"- 'is_confirmed' (boolean): whether the core event is officially confirmed (true) or just rumor/speculation/discussion (false).\n"
            f"- 'is_new_development' (boolean): whether this is a new occurrence/breaking announcement (true) or recap/retrospective/review/rehash (false).\n"
            f"- 'what_happened' (string): concise explanation of the confirmed facts.\n"
            f"- 'why_it_matters' (string): why this is important for fans or the industry.\n"
            f"- 'summary' (string): short summary of the article content.\n"
            f"- 'importance_score' (integer 0 to 100): importance of the news.\n"
            f"- 'source_claims' (array of strings): list of claims made by sources in the article.\n"
            f"- 'unsupported_claims' (array of strings): list of claims in the article that are speculative, unverified, or rumors.\n"
            f"- 'facts' (array of strings): list of verified objective facts reported.\n"
            f"- 'uncertainties' (array of strings): list of unconfirmed details or questions.\n"
            f"- 'source_url' (string): the canonical URL of the article.\n"
            f"- 'image_needed' (boolean): whether a high-quality poster or backdrop is needed.\n"
            f"- 'trailer_needed' (boolean): whether this is a trailer or video release event.\n"
            f"- 'needs_second_source' (boolean): true if the information is high-impact but relies on single-source reporting.\n"
            f"- 'reason_if_rejected' (string or null): why you decided not to publish this article (if publish is false).\n\n"
            f"Do not output anything else than this valid JSON object."
        )

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": self.constitution}]
            },
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }

        # Run with fallback retry for schema validation
        retries = 2
        for attempt in range(1, retries + 1):
            text_result, status = await self._post_generate(self.lite_model, payload)
            
            # Increment request counter metric
            self._increment_metric("gemini_requests")

            if text_result is None:
                self._increment_metric("gemini_failures")
                logger.error(f"Gemini analysis fetch failed with status: {status}")
                return None

            try:
                # Strip markdown code blocks if the model wrapped JSON
                clean_json = text_result.strip()
                if clean_json.startswith("```"):
                    clean_json = re.sub(r"^```(?:json)?\n", "", clean_json)
                    clean_json = re.sub(r"\n```$", "", clean_json)
                
                data = json.loads(clean_json)
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    data = data[0]
                
                # Coerce types if needed
                if isinstance(data, dict):
                    if "publish" in data and isinstance(data["publish"], str):
                        data["publish"] = data["publish"].lower() == "true"
                    analysis = ArticleEditorialAnalysis(**data)
                else:
                    raise ValueError("Gemini returned invalid non-object format")
                self._increment_metric("gemini_articles_analyzed")
                return analysis
            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                logger.warning(f"Structured JSON validation failed (attempt {attempt}/{retries}): {e}. Result: {text_result}")
                if attempt == retries:
                    self._increment_metric("gemini_failures")
                    logger.error(f"Gemini returned invalid json format after {retries} attempts.")
                    return None
                # Add guidance to prompt for retry
                payload["contents"].append({
                    "role": "model",
                    "parts": [{"text": text_result}]
                })
                payload["contents"].append({
                    "role": "user",
                    "parts": [{"text": f"Error: {e}. Please fix the JSON output format and return it strictly according to schema."}]
                })

        return None

    async def _generate_initial_draft(self, event_title: str, articles_content: List[str]) -> Optional[str]:
        """Compiles consolidated articles content into a single premium story using gemini-3.6-flash."""
        combined_bodies = "\n\n=== SOURCE ARTICLE ===\n".join(articles_content)
        
        prompt = (
            f"You are a premium copywriter for Entertainment News Digest.\n"
            f"We are publishing a story about the event: '{event_title}'.\n\n"
            f"Below is the consolidated, extracted body content from our source articles:\n"
            f"=== SOURCE ARTICLE ===\n{combined_bodies}\n\n"
            f"Write a premium editorial report summarizing this development.\n"
            f"RULES:\n"
            f"1. Rely ONLY on confirmed facts or clearly supported inferences from the text.\n"
            f"   Never invent dates, box office numbers, cast attachments, or production statuses.\n"
            f"2. Write 2 to 4 concise, original paragraphs explaining what happened and why it matters.\n"
            f"   Avoid reproducing copyrighted phrases directly.\n"
            f"3. Format exactly like this, using Telegram-safe MarkdownV2. Do NOT add source links or watch trailers here.\n"
            f"   Only output the headline and the body paragraphs.\n\n"
            f"Example format:\n"
            f"🎬 Wednesday Season 2 Begins Filming in Ireland\n\n"
            f"Netflix has officially commenced production on the highly anticipated second season of Wednesday. "
            f"Filming has shifted from Romania to Ireland to support larger sets and production demands...\n\n"
            f"Do not expose any debug parameters, database IDs, or source domains in this text."
        )

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": self.constitution}]
            }
        }

        self._increment_metric("gemini_requests")
        text_result, status = await self._post_generate(self.strong_model, payload)
        
        if text_result is None:
            self._increment_metric("gemini_failures")
            logger.error(f"Gemini final writing failed: {status}")
            return None

        return text_result.strip()

    async def fact_check_story(self, story_text: str, articles_content: List[str]) -> Optional[FactCheckReport]:
        """
        Splits the story into claims and verifies each against source content.
        Uses gemini-3.5-flash-lite with structured JSON output.
        """
        combined_bodies = "\n\n=== SOURCE ARTICLE ===\n".join(articles_content)
        
        prompt = (
            f"You are a strict editorial fact-checking agent.\n"
            f"Below is the story we want to publish:\n"
            f"=== STORY DRAFT ===\n{story_text}\n\n"
            f"Below is the original source article content:\n"
            f"=== SOURCE ARTICLE ===\n{combined_bodies}\n\n"
            f"Your task is to:\n"
            f"1. Extract EVERY individual factual claim made in the story draft.\n"
            f"2. Compare each claim against the source articles.\n"
            f"3. Classify each claim's status as 'SUPPORTED', 'UNSUPPORTED', 'INFERENCE', or 'UNCERTAIN'.\n"
            f"   - Mark 'SUPPORTED' only if the claim is directly stated in the source article. Provide the exact quote as evidence.\n"
            f"   - Mark 'UNSUPPORTED' if the claim is not explicitly mentioned, uses outside knowledge, or cannot be found.\n"
            f"   - Mark 'INFERENCE' if the claim represents a prediction of the future, an assumption of profitability, box office performance, or audience reaction not explicitly in the source.\n"
            f"   - Mark 'UNCERTAIN' if the source is ambiguous.\n"
            f"Return the verification report as a strict JSON object matching the schema."
        )

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": "You are a strict factual verification checker. Do not explain, return JSON."}]
            },
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }

        # Run with fallback retry for schema validation
        retries = 2
        for attempt in range(1, retries + 1):
            text_result, status = await self._post_generate(self.lite_model, payload)
            self._increment_metric("gemini_requests")

            if text_result is None:
                self._increment_metric("gemini_failures")
                logger.error(f"Gemini fact-checking failed with status: {status}")
                return None

            try:
                clean_json = text_result.strip()
                if clean_json.startswith("```"):
                    clean_json = re.sub(r"^```(?:json)?\n", "", clean_json)
                    clean_json = re.sub(r"\n```$", "", clean_json)
                
                data = json.loads(clean_json)
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    data = data[0]
                
                if isinstance(data, dict):
                    report = FactCheckReport(**data)
                    return report
                else:
                    raise ValueError("Gemini returned invalid non-object format for fact check")
            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                logger.warning(f"Fact Check JSON validation failed (attempt {attempt}/{retries}): {e}. Result: {text_result}")
                if attempt == retries:
                    self._increment_metric("gemini_failures")
                    return None
                payload["contents"].append({
                    "role": "model",
                    "parts": [{"text": text_result}]
                })
                payload["contents"].append({
                    "role": "user",
                    "parts": [{"text": f"Error: {e}. Please fix the JSON output format and return it strictly according to schema."}]
                })

        return None

    async def rewrite_corrected_story(self, event_title: str, articles_content: List[str], draft_story: str, unsupported_claims: List[str]) -> Optional[str]:
        """
        Asks gemini-3.6-flash to rewrite the story draft, removing the unsupported claims.
        """
        combined_bodies = "\n\n=== SOURCE ARTICLE ===\n".join(articles_content)
        claims_list = "\n".join(f"- {c}" for c in unsupported_claims)
        
        prompt = (
            f"You are a premium copywriter for Entertainment News Digest.\n"
            f"We are publishing a story about: '{event_title}'.\n\n"
            f"Below is our previous story draft:\n"
            f"=== PREVIOUS DRAFT ===\n{draft_story}\n\n"
            f"During our editorial quality audit, the following claims were flagged as UNSUPPORTED or INFERENCES and MUST BE REMOVED:\n"
            f"{claims_list}\n\n"
            f"Below is the consolidated, extracted body content from our source articles:\n"
            f"=== SOURCE ARTICLE ===\n{combined_bodies}\n\n"
            f"Rewrite the story draft to remove those claims completely. Do not predict future outcomes, box office performance, or audience responses. Relabel or delete any sentences containing the flagged claims.\n"
            f"Format the final output exactly like before, with 2 to 4 paragraphs in Telegram-safe MarkdownV2."
        )

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": self.constitution}]
            }
        }

        self._increment_metric("gemini_requests")
        text_result, status = await self._post_generate(self.strong_model, payload)
        if text_result is None:
            self._increment_metric("gemini_failures")
            logger.error(f"Gemini correction rewrite failed: {status}")
            return None
        return text_result.strip()

    async def synthesize_editorial_story(self, event_title: str, articles_content: List[str]) -> Optional[str]:
        """
        Compiles consolidated articles content into a single premium story using gemini-3.6-flash,
        runs fact-checking, and applies corrections up to 2 times before deciding to publish or reject.
        """
        story_text = await self._generate_initial_draft(event_title, articles_content)
        if not story_text:
            return None

        max_attempts = 2
        for attempt in range(max_attempts + 1):
            report = await self.fact_check_story(story_text, articles_content)
            if not report:
                logger.warning(f"Fact-checking failed for event '{event_title}'. Rejecting story.")
                return None
            
            unsupported = [
                v.claim for v in report.verifications
                if v.status in ["UNSUPPORTED", "INFERENCE", "UNCERTAIN"]
            ]
            
            if not unsupported:
                self.verification_reports[event_title] = report
                logger.info(f"Story for '{event_title}' successfully verified after {attempt} correction attempts.")
                return story_text
            
            if attempt < max_attempts:
                logger.info(f"Fact-checker flagged {len(unsupported)} unsupported claims for '{event_title}' (attempt {attempt+1}/{max_attempts}). Rewriting...")
                story_text = await self.rewrite_corrected_story(event_title, articles_content, story_text, unsupported)
                if not story_text:
                    return None
            else:
                logger.error(f"Story for '{event_title}' rejected due to persistent unsupported claims after {max_attempts} corrections: {unsupported}")
                return None

    def _increment_metric(self, name: str) -> None:
        """Saves metrics increments directly to database if session is open."""
        try:
            from src.database.database import SessionLocal
            from src.services.metrics_service import MetricsService
            db = SessionLocal()
            try:
                MetricsService().increment(db, name, source="GeminiService")
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to record gemini metrics: {e}")
