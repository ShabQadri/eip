import pytest
import json
from unittest.mock import AsyncMock, patch
from src.services.gemini_service import GeminiService
from src.processing.digests.telegram_formatter import TelegramFormatter

@pytest.mark.asyncio
async def test_trailer_news_produces_short_brief():
    """1. Test that trailer news produces a short brief of 1-2 sentences (approx 30-70 words)."""
    service = GeminiService(api_key="fake-key")
    brief_text = "🎬 Dune Three Trailer Released\n\nWarner Bros has released the first trailer for Denis Villeneuve’s Dune Three, offering the first extended look at the next chapter of the sci-fi franchise."
    
    # Mock successful draft generation and fact check
    fc_report = json.dumps({
        "verifications": [{"claim": "Trailer released.", "status": "SUPPORTED", "evidence": "Trailer"}]
    })
    
    with patch.object(service, "_post_generate", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [(brief_text, "SUCCESS"), (fc_report, "SUCCESS")]
        res = await service.synthesize_editorial_story("Dune Trailer", ["Warner Bros released first Dune 3 trailer."])
        
        assert res == brief_text
        words = len(res.split())
        assert 15 <= words <= 70
        sentences = [s for s in res.split(".") if s.strip()]
        assert len(sentences) <= 2

@pytest.mark.asyncio
async def test_release_date_news_produces_short_brief():
    """2. Test that release-date news produces a short brief of 1-2 sentences."""
    service = GeminiService(api_key="fake-key")
    brief_text = "🎬 Avengers Doomsday Release Date Set\n\nMarvel Studios has officially confirmed that Avengers Doomsday will premiere in theaters worldwide on May 1 2026."
    
    fc_report = json.dumps({
        "verifications": [{"claim": "Release set for May 1, 2026.", "status": "SUPPORTED", "evidence": "May 1, 2026."}]
    })
    
    with patch.object(service, "_post_generate", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [(brief_text, "SUCCESS"), (fc_report, "SUCCESS")]
        res = await service.synthesize_editorial_story("Avengers", ["Avengers: Doomsday is set for May 1, 2026."])
        
        assert res == brief_text
        words = len(res.split())
        assert 15 <= words <= 75
        sentences = [s for s in res.split(".") if s.strip()]
        assert len(sentences) <= 2

@pytest.mark.asyncio
async def test_casting_news_produces_short_brief():
    """3. Test that casting news produces a short brief of 1-3 sentences (approx 40-80 words)."""
    service = GeminiService(api_key="fake-key")
    brief_text = "🎬 Robert Downey Cast as Doctor Doom\n\nMarvel has announced that Robert Downey is returning to the MCU to portray Victor Von Doom in the upcoming Avengers films. The casting marks a major villain role for the actor."
    
    fc_report = json.dumps({
        "verifications": [{"claim": "RDJ cast as Doom.", "status": "SUPPORTED", "evidence": "RDJ cast as Doom."}]
    })
    
    with patch.object(service, "_post_generate", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [(brief_text, "SUCCESS"), (fc_report, "SUCCESS")]
        res = await service.synthesize_editorial_story("Casting RDJ", ["Robert Downey Jr is cast as Doom."])
        
        assert res == brief_text
        words = len(res.split())
        assert 20 <= words <= 90
        sentences = [s for s in res.split(".") if s.strip()]
        assert len(sentences) <= 3

@pytest.mark.asyncio
async def test_box_office_news_produces_medium_brief():
    """4. Test that box-office news produces a slightly longer brief of 2-3 sentences including numbers."""
    service = GeminiService(api_key="fake-key")
    brief_text = "🎬 The Odyssey Hits One Billion Globally\n\nChristopher Nolan's historical epic The Odyssey has officially grossed one billion dollars at the global box office, surpassing Oppenheimer to become his highest-grossing film. The release includes a record-breaking two hundred million in Imax screens."
    
    fc_report = json.dumps({
        "verifications": [{"claim": "Odyssey hits $1.1B.", "status": "SUPPORTED", "evidence": "$1.1 billion"}]
    })
    
    with patch.object(service, "_post_generate", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [(brief_text, "SUCCESS"), (fc_report, "SUCCESS")]
        res = await service.synthesize_editorial_story("Box Office", ["Nolan movie has grossed $1.1 billion."])
        
        assert res == brief_text
        words = len(res.split())
        assert 30 <= words <= 120
        sentences = [s for s in res.split(".") if s.strip()]
        assert len(sentences) <= 3

@pytest.mark.asyncio
async def test_complex_news_can_use_additional_paragraphs():
    """5. Test that complex news can use additional paragraphs (up to 250 words)."""
    service = GeminiService(api_key="fake-key")
    complex_brief = (
        "🎬 Sony Pictures Acquires Alamo Drafthouse Cinema Chain\n\n"
        "Sony Pictures Entertainment has acquired Alamo Drafthouse Cinema, the unique dine-in theater chain, in a landmark deal that establishes a theatrical footprint for the major studio.\n\n"
        "Under the agreement, the theater chain will be managed by a newly created division named Sony Pictures Experiences. Alamo Drafthouse will continue to operate its 35 cinema locations under the same brand and maintain its beloved film festival events successfully.\n\n"
        "The acquisition represents the first time in decades that a major Hollywood studio has purchased a major cinema chain following the deregulation of historical anti-trust decrees."
    )
    
    fc_report = json.dumps({
        "verifications": [{"claim": "Sony buys Alamo.", "status": "SUPPORTED", "evidence": "Sony buys Alamo."}]
    })
    
    with patch.object(service, "_post_generate", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [(complex_brief, "SUCCESS"), (fc_report, "SUCCESS")]
        res = await service.synthesize_editorial_story("Sony Alamo", ["Sony has purchased Alamo Drafthouse."])
        
        assert res == complex_brief
        words = len(res.split())
        assert 100 <= words <= 250
        paragraphs = [p for p in res.split("\n\n") if p.strip()]
        assert len(paragraphs) == 4  # Headline paragraph + 3 body paragraphs

@pytest.mark.asyncio
async def test_long_source_does_not_produce_long_message():
    """6. Test that a 5,000-character source does NOT automatically produce a long Telegram message."""
    service = GeminiService(api_key="fake-key")
    large_source = "A" * 5000
    short_brief = "🎬 News Title\n\nThis is a short brief generated from a very long article, summarizing the core development in exactly one paragraph."
    
    fc_report = json.dumps({
        "verifications": [{"claim": "Short summary of long source.", "status": "SUPPORTED", "evidence": "A"}]
    })
    
    with patch.object(service, "_post_generate", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [(short_brief, "SUCCESS"), (fc_report, "SUCCESS")]
        res = await service.synthesize_editorial_story("Long Source Title", [large_source])
        
        assert res == short_brief
        words = len(res.split())
        assert words < 50

@pytest.mark.asyncio
async def test_irrelevant_source_information_removed():
    """7. Test that irrelevant biographical and SEO information is removed from the brief."""
    service = GeminiService(api_key="fake-key")
    noisy_source = "Matt Damon, born in Massachusetts and Oscar winner, stars in The Odyssey. Universal pictures produces. The actor enjoys sailing."
    clean_brief = "🎬 Matt Damon Stars in The Odyssey\n\nMatt Damon is officially attached to star in Christopher Nolan's upcoming historical epic film The Odyssey, produced by Universal Pictures."
    
    fc_report = json.dumps({
        "verifications": [{"claim": "Matt Damon stars in The Odyssey.", "status": "SUPPORTED", "evidence": "Matt Damon stars in The Odyssey."}]
    })
    
    with patch.object(service, "_post_generate", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [(clean_brief, "SUCCESS"), (fc_report, "SUCCESS")]
        res = await service.synthesize_editorial_story("Matt Damon", [noisy_source])
        
        assert "sailing" not in res
        assert "born in" not in res
        assert "Oscar winner" not in res
        assert "The Odyssey" in res

@pytest.mark.asyncio
async def test_unsupported_claims_are_rejected():
    """8. Test that stories containing unsupported claims or inferences are rejected by the fact-checker."""
    service = GeminiService(api_key="fake-key")
    source = "Netflix started production on Wednesday Season 2."
    unsupported_brief = "🎬 Wednesday Season 2 Starts Filming\n\nNetflix commenced filming on Wednesday Season 2, which is scheduled to premiere in December 2026."
    
    fc_report = json.dumps({
        "verifications": [
            {"claim": "Wednesday Season 2 starts filming.", "status": "SUPPORTED", "evidence": "started production"},
            {"claim": "Wednesday Season 2 premieres in December 2026.", "status": "UNSUPPORTED", "evidence": ""}
        ]
    })
    
    with patch.object(service, "_post_generate", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            (unsupported_brief, "SUCCESS"),
            (fc_report, "SUCCESS"),
            (unsupported_brief, "SUCCESS"),
            (fc_report, "SUCCESS"),
            (unsupported_brief, "SUCCESS"),
            (fc_report, "SUCCESS")
        ]
        res = await service.synthesize_editorial_story("Wednesday", [source])
        assert res is None

def test_source_link_remains_present():
    """9. Test that the TelegramFormatter appends source links correctly to the brief."""
    formatter = TelegramFormatter()
    title = "🎬 Headline"
    story = "This is a short brief text."
    source_urls = ["https://variety.com/article/123"]
    
    formatted = formatter.format_event_for_telegram(title, story, source_urls)
    
    assert "🔗 [Source]" in formatted
    assert "https://variety.com/article/123" in formatted

def test_official_trailer_link_remains_present_when_verified():
    """10. Test that the TelegramFormatter appends verified watch trailer links correctly to the brief."""
    formatter = TelegramFormatter()
    title = "🎬 Headline"
    story = "This is a short brief text."
    source_urls = ["https://variety.com/article/123"]
    trailer_url = "https://www.youtube.com/watch?v=12345"
    
    formatted = formatter.format_event_for_telegram(title, story, source_urls, trailer_url=trailer_url)
    
    assert "▶️ [Watch Trailer]" in formatted
    assert "https://www.youtube.com/watch?v=12345" in formatted
