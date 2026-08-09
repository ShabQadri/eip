import os
import re
import json
import logging
import hashlib
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple, List
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger("eip.article_fetcher")

class ArticleFetcher:
    """
    Asynchronous article retriever and content extractor with quality gate and failure caching.
    """
    def __init__(self, timeout_seconds: int = 15, max_size_bytes: int = 3 * 1024 * 1024) -> None:
        self.timeout = timeout_seconds
        self.max_size = max_size_bytes
        self.user_agent = "Entertainment News Digest Ingester/1.0"
        
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        self.failure_cache_path = project_root / "data" / "cache" / "article_fetch_failures.json"
        self._load_failures()

    def _load_failures(self) -> None:
        """Loads fetch failures cache from local file system."""
        self.failures: Dict[str, Dict[str, Any]] = {}
        if self.failure_cache_path.exists():
            try:
                with open(self.failure_cache_path, "r", encoding="utf-8") as f:
                    self.failures = json.load(f)
            except Exception as e:
                logger.error(f"Error loading article fetch failures cache: {e}")

    def _save_failures(self) -> None:
        """Saves current fetch failures to local file system cache."""
        try:
            self.failure_cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.failure_cache_path, "w", encoding="utf-8") as f:
                json.dump(self.failures, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving article fetch failures cache: {e}")

    def check_cooldown(self, url: str) -> bool:
        """Checks if a URL is on a fetch cooldown due to previous failures."""
        if url in self.failures:
            entry = self.failures[url]
            failed_at_str = entry.get("failed_at", "")
            if failed_at_str:
                try:
                    failed_at = datetime.fromisoformat(failed_at_str)
                    # 2 hour cooldown for failed fetches
                    if datetime.now(timezone.utc) - failed_at < timedelta(hours=2):
                        return True
                except ValueError:
                    pass
        return False

    def record_failure(self, url: str, reason: str) -> None:
        """Records a URL fetch failure and caches it for retry backoff."""
        self.failures[url] = {
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "consecutive_failures": self.failures.get(url, {}).get("consecutive_failures", 0) + 1
        }
        self._save_failures()

    def record_success(self, url: str) -> None:
        """Removes a URL from failures cache upon a successful retrieval."""
        if url in self.failures:
            del self.failures[url]
            self._save_failures()

    def validate_url(self, url: str) -> bool:
        """Returns True if the URL contains a valid scheme and domain name."""
        if not url:
            return False
        parsed = urlparse(url)
        return bool(parsed.scheme in ("http", "https") and parsed.netloc)

    async def fetch_page(self, session: aiohttp.ClientSession, url: str) -> Tuple[Optional[str], Optional[int], str]:
        """
        Retrieves the page contents asynchronously. Enforces timeout, content-type checks, and size limits.
        """
        if not self.validate_url(url):
            return None, None, "INVALID_URL"

        if self.check_cooldown(url):
            logger.info(f"Skipping fetch: URL is in cooldown: {url}")
            return None, None, "COOLDOWN"

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        attempts = 3
        backoff = 1.0
        
        for attempt in range(1, attempts + 1):
            try:
                async with session.get(url, headers=headers, timeout=timeout, allow_redirects=True) as response:
                    # Resolve destination/canonical redirects
                    resolved_url = str(response.url)
                    
                    if response.status >= 500:
                        # Transient 5xx retry trigger
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=f"Server error {response.status}"
                        )

                    if response.status != 200:
                        reason = f"HTTP_{response.status}"
                        self.record_failure(url, reason)
                        return None, response.status, reason

                    # Content-type check
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                        self.record_failure(url, "INVALID_CONTENT_TYPE")
                        return None, response.status, f"INVALID_CONTENT_TYPE: {content_type}"

                    # Enforce download size limit by streaming the response body chunk-by-chunk
                    content_length = response.headers.get("Content-Length")
                    if content_length and int(content_length) > self.max_size:
                        self.record_failure(url, "SIZE_EXCEEDED")
                        return None, response.status, "SIZE_EXCEEDED"

                    chunks = []
                    bytes_downloaded = 0
                    
                    # Read content in 100 KB chunks
                    async for chunk in response.content.iter_chunked(102400):
                        bytes_downloaded += len(chunk)
                        if bytes_downloaded > self.max_size:
                            logger.error(f"Download aborted: page exceeded 3 MB limit: {url}")
                            self.record_failure(url, "SIZE_EXCEEDED")
                            return None, response.status, "SIZE_EXCEEDED"
                        chunks.append(chunk)

                    body = b"".join(chunks)
                    
                    # Decode with encoding fallback
                    encoding = response.charset or "utf-8"
                    try:
                        text_content = body.decode(encoding, errors="replace")
                    except Exception:
                        text_content = body.decode("utf-8", errors="replace")

                    self.record_success(url)
                    return text_content, response.status, "SUCCESS"

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Fetch attempt {attempt} failed for {url}: {e}")
                if attempt < attempts:
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                else:
                    self.record_failure(url, type(e).__name__)
                    return None, None, type(e).__name__
            except Exception as e:
                logger.error(f"Unexpected fetch failure for {url}: {e}")
                self.record_failure(url, "UNEXPECTED_ERROR")
                return None, None, "UNEXPECTED_ERROR"

        return None, None, "FAILED_RETRIES"

    def clean_text(self, text: str) -> str:
        """Collapses spaces and preserves paragraph structures (separated by double newlines)."""
        if not text:
            return ""
        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Split by double newlines (paragraphs)
        paragraphs = text.split("\n\n")
        cleaned_paragraphs = []
        for p in paragraphs:
            p_clean = re.sub(r"[ \t]+", " ", p.strip())
            p_lines = [line.strip() for line in p_clean.splitlines() if line.strip()]
            p_single_spaced = " ".join(p_lines)
            if p_single_spaced:
                cleaned_paragraphs.append(p_single_spaced)
        return "\n\n".join(cleaned_paragraphs)

    def extract_json_ld(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Parses type application/ld+json scripts for article content and properties."""
        article_body = None
        headline = None
        author = None
        published_date = None

        script_tags = soup.find_all("script", type="application/ld+json")
        for tag in script_tags:
            try:
                data = json.loads(tag.get_text())
                if isinstance(data, list):
                    nodes = data
                elif isinstance(data, dict):
                    # Check graph structure
                    nodes = data.get("@graph", [data])
                else:
                    continue

                for node in nodes:
                    if not isinstance(node, dict):
                        continue
                    types = node.get("@type", "")
                    if isinstance(types, list):
                        is_article = any(t in ["Article", "NewsArticle", "BlogPosting"] for t in types)
                    else:
                        is_article = types in ["Article", "NewsArticle", "BlogPosting"]

                    if is_article or "articleBody" in node:
                        if "articleBody" in node and not article_body:
                            article_body = node["articleBody"]
                        if "headline" in node and not headline:
                            headline = node["headline"]
                        
                        if "author" in node and not author:
                            auth_val = node["author"]
                            if isinstance(auth_val, dict):
                                author = auth_val.get("name")
                            elif isinstance(auth_val, list) and auth_val:
                                author = auth_val[0].get("name") if isinstance(auth_val[0], dict) else str(auth_val[0])
                            else:
                                author = str(auth_val)
                                
                        if "datePublished" in node and not published_date:
                            published_date = node["datePublished"]

                if article_body and len(article_body.strip()) > 200:
                    break
            except Exception:
                continue

        return article_body, headline, author, published_date

    def clean_html_nodes(self, root_node) -> None:
        """Removes garbage elements like navs, sidebars, scripts, style, and shares from the element tree."""
        if not root_node:
            return
            
        garbage_tags = ["script", "style", "nav", "header", "footer", "aside", "form", "iframe", "noscript"]
        for tag in root_node.find_all(garbage_tags):
            tag.decompose()

        # Remove elements by class / ID substrings
        garbage_patterns = [
            r"share", r"social", r"recommend", r"related", r"comment", r"newsletter", 
            r"advertisement", r"ad-container", r"banner", r"cookie", r"widget", 
            r"sidebar", r"nav", r"header", r"footer", r"author-profile", r"trending"
        ]
        
        for element in root_node.find_all(True):
            attrs = getattr(element, "attrs", None) or {}
            cls = " ".join(attrs.get("class", [])) if attrs.get("class") else ""
            elem_id = attrs.get("id", "") or ""
            
            # Check for matches in class names or elements IDs
            if any(re.search(pat, cls.lower()) or re.search(pat, elem_id.lower()) for pat in garbage_patterns):
                # Avoid decomposing the main article container if it accidentally matched
                if element.name not in ["article", "main", "body"]:
                    element.decompose()

    def extract_article_content(self, html_content: str, rss_fallback_desc: Optional[str] = None) -> Dict[str, Any]:
        """
        Parses page HTML and returns metadata and the extracted article text.
        Applies a Quality Gate.
        """
        result = {
            "title": "",
            "canonical_url": "",
            "published_date": None,
            "author": "",
            "og_image": "",
            "body_text": "",
            "images": [],
            "video_urls": [],
            "content_extraction_status": "failed_or_insufficient"
        }

        if not html_content:
            # Emergency Fallback to RSS summary
            if rss_fallback_desc:
                result["body_text"] = self.clean_text(rss_fallback_desc)
                result["content_extraction_status"] = "partial_rss_fallback"
            return result

        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Metadata Checks (OpenGraph and Twitter tags)
        og_title = soup.find("meta", attrs={"property": "og:title"}) or soup.find("meta", attrs={"name": "twitter:title"})
        result["title"] = og_title["content"] if og_title and og_title.get("content") else (soup.title.string if soup.title else "")

        og_url = soup.find("meta", attrs={"property": "og:url"}) or soup.find("link", attrs={"rel": "canonical"})
        if og_url:
            result["canonical_url"] = og_url.get("content") or og_url.get("href") or ""

        og_image = soup.find("meta", attrs={"property": "og:image"}) or soup.find("meta", attrs={"name": "twitter:image"})
        if og_image:
            result["og_image"] = og_image.get("content") or ""

        # Parse videos
        video_urls = []
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            if src and any(domain in src for domain in ["youtube.com", "youtu.be", "vimeo.com"]):
                video_urls.append(src)
        result["video_urls"] = video_urls

        # 2. Extract Body Content using our Priority Tree
        # Priority 1: JSON-LD
        article_body, json_headline, json_author, json_date = self.extract_json_ld(soup)
        if json_headline and not result["title"]:
            result["title"] = json_headline
        if json_author:
            result["author"] = json_author
        if json_date:
            try:
                # Remove Z or offset indicators for naive Datetime
                clean_dt = json_date.split(".")[0].replace("Z", "").replace("+00:00", "")
                result["published_date"] = datetime.fromisoformat(clean_dt)
            except Exception:
                pass

        if article_body and len(article_body.strip()) >= 200:
            result["body_text"] = self.clean_text(article_body)
            result["content_extraction_status"] = "success"
        else:
            # Priority 2: <article> tag
            article_node = soup.find("article")
            if not article_node:
                # Priority 3: <main> tag or main content container
                article_node = soup.find("main") or soup.find("div", role="main")
            
            if not article_node:
                # Fallback search for common content wrapper IDs
                for cid in ["content", "main-content", "article-content", "post-body", "story"]:
                    article_node = soup.find(id=cid) or soup.find("div", class_=cid)
                    if article_node:
                        break

            if article_node:
                # Clean the nodes to remove advertisements, headers, and footer trash
                self.clean_html_nodes(article_node)
                
                # Fetch images from inside the article content node
                images = []
                for img in article_node.find_all("img"):
                    src = img.get("src") or img.get("data-src")
                    if src and src.startswith("http"):
                        images.append(src)
                result["images"] = images

                # Pull paragraph texts
                paragraphs = [p.get_text().strip() for p in article_node.find_all("p")]
                clean_paras = [p for p in paragraphs if len(p) > 20]
                
                if len(clean_paras) >= 2:
                    full_text_str = "\n\n".join(clean_paras)
                    if len(full_text_str) >= 200:
                        result["body_text"] = self.clean_text(full_text_str)
                        result["content_extraction_status"] = "success"

            # Priority 4: Paragraph Heuristics on overall HTML if target nodes were missing
            if not result["body_text"]:
                self.clean_html_nodes(soup)
                paragraphs = [p.get_text().strip() for p in soup.find_all("p")]
                clean_paras = [p for p in paragraphs if len(p) > 20]
                if len(clean_paras) >= 2:
                    full_text_str = "\n\n".join(clean_paras)
                    if len(full_text_str) >= 200:
                        result["body_text"] = self.clean_text(full_text_str)
                        result["content_extraction_status"] = "success"

        # Apply Quality Gate
        # Must be >= 200 characters and >= 2 meaningful paragraphs (paragraphs separated by double newlines)
        if result["content_extraction_status"] == "success":
            body = result["body_text"]
            paras = [p.strip() for p in body.split("\n\n") if p.strip()]
            if len(body) < 200 or len(paras) < 2:
                # Revert to failed status
                result["content_extraction_status"] = "failed_or_insufficient"

        # Priority 5: Emergency fallback if page extraction fails
        if result["content_extraction_status"] == "failed_or_insufficient":
            if rss_fallback_desc and len(rss_fallback_desc.strip()) > 20:
                result["body_text"] = self.clean_text(rss_fallback_desc)
                result["content_extraction_status"] = "partial_rss_fallback"

        return result
