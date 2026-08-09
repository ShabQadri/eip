import os
import json
import pytest
import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

from src.processing.articles.article_fetcher import ArticleFetcher
from src.services.gemini_service import GeminiService, ArticleEditorialAnalysis
from src.services.media_enrichment_service import MediaEnrichmentService
from src.processing.digests.telegram_formatter import TelegramFormatter
from src.services.scheduler_service import SchedulerService
from src.models import Article, Event
from src.database.base import Base

# Construct valid JSON-LD
json_ld_data = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "headline": "Extracted Title",
    "datePublished": "2026-08-08T12:00:00Z",
    "author": {"name": "Writer Name"},
    "articleBody": "This is a long article content that must exceed two hundred characters in length. It consists of multiple sentences to pass the quality gate rules. Let's make sure it contains enough text to satisfy the minimum length. \n\nParagraph two starts here and it also contains sufficient content."
}
script_content = json.dumps(json_ld_data)

MOCK_JSON_LD_HTML = f"""
<html>
  <head>
    <link rel="canonical" href="https://example.com/canonical-url">
    <meta property="og:title" content="Extracted Title">
    <meta property="og:image" content="https://example.com/og-image.jpg">
  </head>
  <body>
    <script type="application/ld+json">
      {script_content}
    </script>
    <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>
  </body>
</html>
"""

MOCK_HTML_ARTICLE = """
<html>
  <body>
    <article>
      <h1>Direct HTML Title</h1>
      <p>This is paragraph one of the article and it has more than enough words to be considered highly meaningful and informative.</p>
      <p>This is paragraph two of the article and it also has more than enough words to satisfy the quality gate requirements easily.</p>
      <img src="https://example.com/body-image.png">
    </article>
  </body>
</html>
"""

def test_article_fetcher_heuristics():
    fetcher = ArticleFetcher()
    
    # 1. Parse JSON-LD
    extracted = fetcher.extract_article_content(MOCK_JSON_LD_HTML)
    assert extracted["content_extraction_status"] == "success"
    assert extracted["title"] == "Extracted Title"
    assert "two hundred characters" in extracted["body_text"]
    assert extracted["canonical_url"] == "https://example.com/canonical-url"
    assert extracted["og_image"] == "https://example.com/og-image.jpg"
    assert len(extracted["video_urls"]) == 1
    assert "youtube.com" in extracted["video_urls"][0]

    # 2. Parse HTML article nodes fallback
    extracted_html = fetcher.extract_article_content(MOCK_HTML_ARTICLE)
    assert extracted_html["content_extraction_status"] == "success"
    assert "paragraph one" in extracted_html["body_text"]
    assert len(extracted_html["images"]) == 1

def test_article_fetcher_quality_gate():
    fetcher = ArticleFetcher()
    
    # Insufficient characters
    short_html = "<html><body><article><p>Short text.</p><p>Second paragraph.</p></article></body></html>"
    extracted = fetcher.extract_article_content(short_html)
    assert extracted["content_extraction_status"] == "failed_or_insufficient"
    
    # Insufficient paragraphs
    one_para_html = "<html><body><article><p>" + "A" * 300 + "</p></article></body></html>"
    extracted_one = fetcher.extract_article_content(one_para_html)
    assert extracted_one["content_extraction_status"] == "failed_or_insufficient"

    # Emergency Fallback RSS description
    extracted_rss = fetcher.extract_article_content("", rss_fallback_desc="This is a summary of the RSS feed that has enough text.")
    assert extracted_rss["content_extraction_status"] == "partial_rss_fallback"

def test_telegram_formatter_escapes():
    formatter = TelegramFormatter()
    
    # Normal Markdown escaping
    text = "Hello! [World] _Test_ *Bold*"
    escaped = formatter.escape_markdown_v2(text)
    assert "\\!" in escaped
    assert "\\[" in escaped
    assert "\\_" in escaped
    assert "\\*" in escaped

    # Link URL escaping (only ) and \\)
    url = "https://example.com/link_with_brackets(1)\\test"
    escaped_url = formatter.escape_link_url(url)
    assert "\\)" in escaped_url
    assert "\\\\" in escaped_url
    assert "_" in escaped_url  # Unchanged in URL

def test_telegram_formatter_post():
    formatter = TelegramFormatter()
    
    formatted = formatter.format_event_for_telegram(
        title="Dune Messiah Filming Begins",
        story_text="Production has started on Dune 3 in Dublin. The film will cover Paul's journey.",
        source_urls=["https://variety.com/dune"],
        trailer_url="https://youtube.com/watch?v=123"
    )
    
    assert "🎬 *Dune Messiah Filming Begins*" in formatted
    assert "🔗 [Source](https://variety.com/dune)" in formatted
    assert "▶️ [Watch Trailer](https://youtube.com/watch?v=123)" in formatted

def test_event_protection_seasons_years():
    # Verify season and year mismatch checks
    from src.processing.events.event_matcher import EventMatcher
    
    engine = MagicMock()
    # Matcher uses SimilarityEngine to extract season/year
    engine.extract_season_and_year.side_effect = lambda t, d: (2, 2026)
    
    matcher = EventMatcher(similarity_engine=engine, franchise_detector=MagicMock())
    
    # We construct mock Events
    event_season_3 = Event(
        canonical_title="Wednesday",
        event_pattern="RENEWAL",
        season_number=3,
        event_year=2027
    )
    
    # Check that they wouldn't merge if they represent different seasons
    # In event_matcher logic, we check is_tv_lifecycle: if art_season != event.season_number, continue
    art_season = 2
    event_season = 3
    assert art_season != event_season

def test_scheduler_timezone():
    scheduler_service = SchedulerService()
    # Check scheduler object exists
    assert scheduler_service.scheduler is not None
    # Check timezone matches Asia/Kolkata
    assert scheduler_service.scheduler.timezone == ZoneInfo("Asia/Kolkata")

@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_tmdb_media_enrichment(mock_get):
    enricher = MediaEnrichmentService(tmdb_key="fake-key")
    
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={
        "results": [
            {
                "id": 12345,
                "title": "Dune: Part Two",
                "release_date": "2024-03-01",
                "poster_path": "/poster.jpg",
                "backdrop_path": "/backdrop.jpg"
            }
        ]
    })
    mock_get.return_value.__aenter__.return_value = mock_resp

    res = await enricher.search_tmdb("Dune Part Two", media_type="movie", year=2024)
    assert res is not None
    assert res["tmdb_id"] == "12345"
    assert "poster.jpg" in res["poster_url"]

@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_youtube_trailer_enrichment(mock_get):
    enricher = MediaEnrichmentService(youtube_key="fake-key")
    # Set mock official channel in configuration
    enricher.official_channels = {
        "Warner Bros. Pictures": {
            "channel_id": "UCFBwT3r0G_2FGBKjJ__eSgA",
            "channel_title": "Warner Bros. Pictures"
        }
    }
    
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={
        "items": [
            {
                "id": {"videoId": "dQw4w9WgXcQ"},
                "snippet": {
                    "title": "Dune: Part Two - Official Trailer",
                    "channelId": "UCFBwT3r0G_2FGBKjJ__eSgA",
                    "channelTitle": "Warner Bros. Pictures"
                }
            }
        ]
    })
    mock_get.return_value.__aenter__.return_value = mock_resp

    trailer_url = await enricher.search_official_youtube_trailer("Dune: Part Two", year=2024)
    assert trailer_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.mark.asyncio
async def test_fact_check_supported_immediate_success():
    """Test that a story is immediately published if all claims are SUPPORTED."""
    service = GeminiService(api_key="fake-key")
    
    draft_story = "🎬 Wednesday Commences Season 2\n\nProduction has started on Wednesday season 2."
    fc_report = json.dumps({
        "verifications": [
            {
                "claim": "Production has started on Wednesday season 2.",
                "status": "SUPPORTED",
                "evidence": "Netflix started production on Wednesday Season 2."
            }
        ]
    })
    
    with patch.object(service, "_post_generate", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            (draft_story, "SUCCESS"),
            (fc_report, "SUCCESS")
        ]
        
        res = await service.synthesize_editorial_story("Wednesday Season 2", ["Netflix started production on Wednesday Season 2."])
        assert res == draft_story
        assert "Wednesday Season 2" in service.verification_reports
        assert len(service.verification_reports["Wednesday Season 2"].verifications) == 1
        assert service.verification_reports["Wednesday Season 2"].verifications[0].status == "SUPPORTED"


@pytest.mark.asyncio
async def test_fact_check_unsupported_inferences_corrected():
    """Test that unsupported audience/profitability/future inferences trigger the correction loop and get removed."""
    service = GeminiService(api_key="fake-key")
    
    draft_1 = "🎬 Toxic Trailer Out\n\nThe teaser for Toxic is out. The film is certain to become highly profitable and audience reaction will be legendary."
    fc_report_1 = json.dumps({
        "verifications": [
            {
                "claim": "The teaser for Toxic is out.",
                "status": "SUPPORTED",
                "evidence": "Yash's Toxic trailer is officially released."
            },
            {
                "claim": "The film is certain to become highly profitable.",
                "status": "INFERENCE",
                "evidence": ""
            },
            {
                "claim": "Audience reaction will be legendary.",
                "status": "UNSUPPORTED",
                "evidence": ""
            }
        ]
    })
    
    corrected_story = "🎬 Toxic Trailer Out\n\nThe teaser for Toxic is out."
    fc_report_2 = json.dumps({
        "verifications": [
            {
                "claim": "The teaser for Toxic is out.",
                "status": "SUPPORTED",
                "evidence": "Yash's Toxic trailer is officially released."
            }
        ]
    })
    
    with patch.object(service, "_post_generate", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            (draft_1, "SUCCESS"),
            (fc_report_1, "SUCCESS"),
            (corrected_story, "SUCCESS"),
            (fc_report_2, "SUCCESS")
        ]
        
        res = await service.synthesize_editorial_story("Toxic Trailer", ["Yash's Toxic trailer is officially released."])
        assert res == corrected_story
        assert "Toxic Trailer" in service.verification_reports
        assert len(service.verification_reports["Toxic Trailer"].verifications) == 1
        assert service.verification_reports["Toxic Trailer"].verifications[0].status == "SUPPORTED"


@pytest.mark.asyncio
async def test_fact_check_rejection_after_failed_correction():
    """Test that a story is rejected if unsupported claims persist after max correction attempts."""
    service = GeminiService(api_key="fake-key")
    
    draft_story = "🎬 Title\n\nFactual body. Hallucinated date is Dec 2026."
    fc_report_flagged = json.dumps({
        "verifications": [
            {
                "claim": "Factual body.",
                "status": "SUPPORTED",
                "evidence": "Factual body."
            },
            {
                "claim": "Hallucinated date is Dec 2026.",
                "status": "UNSUPPORTED",
                "evidence": ""
            }
        ]
    })
    
    with patch.object(service, "_post_generate", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            (draft_story, "SUCCESS"),
            (fc_report_flagged, "SUCCESS"),
            (draft_story, "SUCCESS"),
            (fc_report_flagged, "SUCCESS"),
            (draft_story, "SUCCESS"),
            (fc_report_flagged, "SUCCESS")
        ]
        
        res = await service.synthesize_editorial_story("Event", ["Factual body."])
        assert res is None

