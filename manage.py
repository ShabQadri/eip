#!/usr/bin/env python
"""
EIP Management Command Line Interface (CLI).
Provides administrative commands for EIP database, health, metrics, and jobs execution.
"""

import os
import sys
import argparse
import json
import shutil
import asyncio
from datetime import datetime
from pathlib import Path

# Add current directory to path to support absolute imports
sys.path.insert(0, os.getcwd())

# Reconfigure stdout and stderr to use UTF-8 on Windows to prevent console charmap crashes
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Configure basic logging for CLI commands
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("eip.manage")

from src.database.database import SessionLocal
from src.services.health_service import HealthService, get_memory_usage_mb, get_db_size_mb
from src.services.metrics_service import MetricsService
from src.services.scheduler_service import SchedulerService
from src.feeds.collection_service import CollectionService

# ANSI terminal formatting colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BLUE = "\033[94m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

def print_success(message: str) -> None:
    try:
        print(f"{COLOR_GREEN}{COLOR_BOLD}✔ SUCCESS:{COLOR_RESET} {message}")
    except UnicodeEncodeError:
        print(f"{COLOR_GREEN}{COLOR_BOLD}[SUCCESS]:{COLOR_RESET} {message}")

def print_warning(message: str) -> None:
    try:
        print(f"{COLOR_YELLOW}{COLOR_BOLD}⚠ WARNING:{COLOR_RESET} {message}")
    except UnicodeEncodeError:
        print(f"{COLOR_YELLOW}{COLOR_BOLD}[WARNING]:{COLOR_RESET} {message}")

def print_error(message: str) -> None:
    try:
        print(f"{COLOR_RED}{COLOR_BOLD}✘ ERROR:{COLOR_RESET} {message}", file=sys.stderr)
    except UnicodeEncodeError:
        print(f"{COLOR_RED}{COLOR_BOLD}[ERROR]:{COLOR_RESET} {message}", file=sys.stderr)

def print_header(title: str) -> None:
    print(f"\n{COLOR_BLUE}{COLOR_BOLD}=== {title} ==={COLOR_RESET}\n")

# Command functions
def cmd_health() -> int:
    print_header("System Health Check")
    db = SessionLocal()
    try:
        hs = HealthService()
        health = hs.get_system_health(db)
        
        status = health["status"]
        if status == "healthy":
            print(f"Overall Status: {COLOR_GREEN}{COLOR_BOLD}HEALTHY{COLOR_RESET}")
        elif status == "warning":
            print(f"Overall Status: {COLOR_YELLOW}{COLOR_BOLD}WARNING{COLOR_RESET}")
        else:
            print(f"Overall Status: {COLOR_RED}{COLOR_BOLD}CRITICAL{COLOR_RESET}")
            
        print("\nDetails:")
        print(json.dumps(health["details"], indent=2))
        
        db.close()
        return 0 if status in {"healthy", "warning"} else 1
    except Exception as e:
        print_error(f"Failed to check health status: {e}")
        db.close()
        return 1

def cmd_admin_report() -> int:
    print_header("Daily Admin Report")
    db = SessionLocal()
    try:
        hs = HealthService()
        report = hs.generate_daily_admin_report(db)
        
        # Render a clean, readable text table
        print(f"{COLOR_BOLD}{'Metric / Parameter':<25} | {'Value':<12}{COLOR_RESET}")
        print("-" * 42)
        
        status_color = COLOR_GREEN if report["system_status"] == "healthy" else (COLOR_YELLOW if report["system_status"] == "warning" else COLOR_RED)
        print(f"{'System Status':<25} | {status_color}{report['system_status']}{COLOR_RESET}")
        print(f"{'Feeds Processed':<25} | {report['feeds_processed']}")
        print(f"{'Articles Fetched':<25} | {report['articles_fetched']}")
        print(f"{'Events Created':<25} | {report['events_created']}")
        print(f"{'Digests Sent':<25} | {report['digests_sent']}")
        print(f"{'Breaking Alerts Sent':<25} | {report['breaking_alerts_sent']}")
        print(f"{'Telegram Failures':<25} | {report['telegram_failures']}")
        print(f"{'Scheduler Failures':<25} | {report['scheduler_failures']}")
        print(f"{'Dead Feeds':<25} | {report['dead_feeds']}")
        print(f"{'Database Size (MB)':<25} | {report['database_size_mb']:.2f} MB")
        print(f"{'Memory Usage (MB)':<25} | {report['memory_usage_mb']:.2f} MB")
        print(f"{'Active Feeds':<25} | {report['active_feeds']}")
        
        db.close()
        return 0
    except Exception as e:
        print_error(f"Failed to generate admin report: {e}")
        db.close()
        return 1

def cmd_metrics() -> int:
    print_header("Daily Metrics Summary")
    db = SessionLocal()
    try:
        ms = MetricsService()
        summary = ms.daily_metrics_summary(db)
        print(json.dumps(summary, indent=2))
        db.close()
        return 0
    except Exception as e:
        print_error(f"Failed to load daily metrics: {e}")
        db.close()
        return 1

def cmd_morning_digest() -> int:
    print_header("Running Morning Digest Pipeline")
    try:
        # Reset SchedulerService singleton just in case
        SchedulerService._instance = None
        sched = SchedulerService()
        sched.run_morning_digest_job()
        print_success("Morning digest pipeline job completed successfully.")
        return 0
    except Exception as e:
        print_error(f"Morning digest pipeline job failed: {e}")
        return 1

def cmd_evening_digest() -> int:
    print_header("Running Evening Digest Pipeline")
    try:
        SchedulerService._instance = None
        sched = SchedulerService()
        sched.run_evening_digest_job()
        print_success("Evening digest pipeline job completed successfully.")
        return 0
    except Exception as e:
        print_error(f"Evening digest pipeline job failed: {e}")
        return 1

def cmd_breaking_check() -> int:
    print_header("Running Breaking Alert Check")
    try:
        SchedulerService._instance = None
        sched = SchedulerService()
        sched.run_breaking_alert_job()
        print_success("Breaking alert check completed successfully.")
        return 0
    except Exception as e:
        print_error(f"Breaking alert check job failed: {e}")
        return 1

def cmd_collect_feeds() -> int:
    print_header("Running Feed Collection Sweep")
    db = SessionLocal()
    try:
        coll = CollectionService()
        # collect_all is async
        result = asyncio.run(coll.collect_all(db))
        db.commit()
        
        print_success("Feed collection completed successfully.")
        print(f"Feeds processed: {result.feeds_processed}")
        print(f"Feeds succeeded: {result.feeds_succeeded}")
        print(f"Feeds failed:    {result.feeds_failed}")
        print(f"Articles stored: {result.articles_stored}")
        db.close()
        return 0
    except Exception as e:
        print_error(f"Feed collection job failed: {e}")
        db.close()
        return 1

def cmd_scheduler_status() -> int:
    print_header("Scheduler Status Check")
    try:
        hs = HealthService()
        status = hs.get_scheduler_health()
        
        if status["status"] == "healthy":
            print(f"Status: {COLOR_GREEN}{COLOR_BOLD}RUNNING{COLOR_RESET}")
            print(f"Jobs registered: {status['details']['job_count']}")
        else:
            print(f"Status: {COLOR_RED}{COLOR_BOLD}STOPPED / INACTIVE{COLOR_RESET}")
            print(f"Details: {status['details']['error']}")
            
        return 0 if status["status"] == "healthy" else 1
    except Exception as e:
        print_error(f"Failed to check scheduler status: {e}")
        return 1

def cmd_database_size() -> int:
    print_header("Database Size Diagnostics")
    try:
        size = get_db_size_mb()
        print(f"Database Path: {COLOR_BOLD}{SessionLocal().bind.url.database}{COLOR_RESET}")
        print(f"Size:          {COLOR_GREEN}{COLOR_BOLD}{size:.2f} MB{COLOR_RESET} ({int(size * 1024 * 1024)} bytes)")
        return 0
    except Exception as e:
        print_error(f"Failed to retrieve database size: {e}")
        return 1

def cmd_backup_db() -> int:
    print_header("Creating Database Backup")
    try:
        # Determine paths
        db_url = SessionLocal().bind.url.database
        if not db_url or db_url == ":memory:":
            print_error("Cannot backup an in-memory database.")
            return 1
            
        # Ensure backups folder exists
        backup_dir = os.path.join(os.getcwd(), "data", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        # Build destination backup file path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"entertainment_backup_{timestamp}.db")
        
        # Perform safe copy
        shutil.copy(db_url, backup_file)
        
        print_success(f"Database backed up successfully to:\n{backup_file}")
        return 0
    except Exception as e:
        print_error(f"Database backup failed: {e}")
        return 1

def cmd_diagnose_article(url: str) -> int:
    print_header(f"Diagnosing Article URL: {url}")
    import asyncio
    import aiohttp
    import hashlib
    from urllib.parse import urlparse
    from src.processing.articles.article_fetcher import ArticleFetcher
    from src.services.gemini_service import GeminiService
    from src.services.media_enrichment_service import MediaEnrichmentService
    
    async def _diagnose():
        fetcher = ArticleFetcher()
        parsed_url = urlparse(url)
        domain = parsed_url.netloc or "Unknown Domain"
        
        print(f"SOURCE: {domain}")
        
        conn = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=conn) as session:
            # 1. Fetch
            html, status_code, status_reason = await fetcher.fetch_page(session, url)
            
            # 2. Extract
            extracted = fetcher.extract_article_content(html, rss_fallback_desc=None)
            
            print(f"ARTICLE TITLE: {extracted.get('title', 'N/A')}")
            print(f"CANONICAL URL: {extracted.get('canonical_url', 'N/A')}")
            print(f"HTTP STATUS: {status_code or 'N/A'} ({status_reason})")
            print(f"CONTENT EXTRACTION STATUS: {extracted.get('content_extraction_status')}")
            
            body_text = extracted.get('body_text', '')
            print(f"EXTRACTED CHARACTER COUNT: {len(body_text)}")
            paras = [p for p in body_text.split('\n\n') if p.strip()]
            print(f"PARAGRAPH COUNT: {len(paras)}")
            
            content_hash = hashlib.sha256(body_text.encode('utf-8')).hexdigest() if body_text else 'N/A'
            print(f"CONTENT HASH: {content_hash}")
            
            print(f"GEMINI INPUT CHARACTER COUNT: {len(body_text)}")
            print(f"FIRST 300 CHARACTERS OF GEMINI INPUT:\n{body_text[:300]}")
            print(f"OG IMAGE: {extracted.get('og_image', 'N/A')}")
            print(f"IMAGE COUNT: {len(extracted.get('images', []))}")
            print(f"VIDEO COUNT: {len(extracted.get('video_urls', []))}")
            
            # Check Quality Gate
            if extracted.get('content_extraction_status') == 'success':
                # 3. Gemini analysis
                print("\nCalling Gemini for editorial analysis...")
                gemini = GeminiService()
                analysis = await gemini.analyze_article(extracted.get('title'), body_text, url, article_desc="")
                if analysis:
                    print(f"GEMINI DECISION: {'PUBLISH' if analysis.publish else 'REJECT'}")
                    print(f"GEMINI CONFIDENCE: {analysis.confidence}")
                    print(f"EVENT: {analysis.canonical_entity}")
                    print(f"DEVELOPMENT TYPE: {analysis.development_type}")
                    
                    # 4. Media lookup if publishable
                    if analysis.publish:
                        enricher = MediaEnrichmentService()
                        print("\nPerforming Media Lookup...")
                        tmdb_res = await enricher.search_tmdb(analysis.canonical_entity, analysis.event_type)
                        yt_res = None
                        if analysis.trailer_needed or "trailer" in extracted.get('title', '').lower():
                            yt_res = await enricher.search_official_youtube_trailer(analysis.canonical_entity)
                            
                        print(f"MEDIA RESULT: TMDB={tmdb_res is not None} (Poster: {tmdb_res.get('poster_url') if tmdb_res else 'N/A'}), YouTube={yt_res is not None} (URL: {yt_res if yt_res else 'N/A'})")
                    else:
                        print("MEDIA RESULT: N/A (Rejected)")
                else:
                    print("GEMINI DECISION: FAILED (No response or validation error)")
            else:
                print("GEMINI DECISION: Bypassed (Extraction failed or insufficient content)")
                
    try:
        asyncio.run(_diagnose())
        return 0
    except Exception as e:
        print_error(f"Diagnostics command failed: {e}")
        return 1

def cmd_run_acceptance_test() -> int:
    print_header("Running Real-Data Acceptance Test (Non-Publishing)")
    import asyncio
    import aiohttp
    from src.models.source import Source
    from src.feeds.rss_fetcher import RSSFetcher
    from src.feeds.rss_parser import RSSParser
    from src.feeds.editorial_filter import EditorialFilter
    from src.feeds.importance_engine import ImportanceEngine
    from src.feeds.article_normalizer import ArticleNormalizer
    from src.processing.articles.article_fetcher import ArticleFetcher
    from src.services.gemini_service import GeminiService
    from src.services.media_enrichment_service import MediaEnrichmentService
    
    async def _run_test():
        db = SessionLocal()
        sources = db.query(Source).filter_by(enabled=True).all()
        if not sources:
            print_error("No active sources found in database. Seed them first or run collect-feeds.")
            db.close()
            return
            
        print(f"Found {len(sources)} enabled sources in database.")
        
        rss_fetcher = RSSFetcher()
        normalizer = ArticleNormalizer()
        
        project_root = Path(__file__).resolve().parent
        with open(project_root / "data" / "feeds" / "editorial_rules.json", "r", encoding="utf-8") as f:
            rules = json.load(f)
        blacklist = rules.get("blacklist_keywords", [])
        
        rss_parser = RSSParser(blacklist_keywords=blacklist)
        det_filter = EditorialFilter()
        importance_engine = ImportanceEngine()
        
        discovered_articles = []
        
        conn = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=conn) as session:
            for s in sources:
                if len(discovered_articles) >= 30:
                    break
                print(f"Fetching RSS feed for source: {s.name} ({s.rss_url})")
                xml, status = await rss_fetcher.fetch(session, s.rss_url)
                if xml:
                    entries, pre_filtered = rss_parser.parse_feed_entries(xml)
                    for entry in entries:
                        art = normalizer.normalize_to_model(entry, s.id, "GLOBAL")
                        is_approved, reason = det_filter.evaluate_article(art)
                        if is_approved:
                            importance_engine.score_article(art)
                            if art.importance_score >= 25:
                                discovered_articles.append((art, s.name))
                                if len(discovered_articles) >= 30:
                                    break
                                    
        print(f"\nDiscovered {len(discovered_articles)} articles passing deterministic filters.")
        
        if not discovered_articles:
            print_warning("No articles passed the deterministic filter. Cannot run acceptance test.")
            db.close()
            return
            
        test_slice = discovered_articles[:20]
        print(f"Selected {len(test_slice)} articles for acceptance test.\n")
        
        fetcher = ArticleFetcher()
        gemini = GeminiService()
        enricher = MediaEnrichmentService()
        
        stats = {
            "discovered": len(discovered_articles),
            "fetched": 0,
            "success": 0,
            "partial": 0,
            "failed": 0,
            "gemini_analyzed": 0,
            "gemini_rejected": 0,
            "events_created": 0,
            "events_merged": 0,
            "publishable": 0,
            "images": 0,
            "trailers": 0,
            "duplicates_prevented": 0
        }
        
        consolidated_events = {}
        article_results = []
        
        session_extract = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
        for idx, (art, source_name) in enumerate(test_slice, 1):
            print(f"[{idx}/{len(test_slice)}] Processing article: {art.title}")
            stats["fetched"] += 1
            
            html, status_code, status_reason = await fetcher.fetch_page(session_extract, art.url)
            extracted = fetcher.extract_article_content(html, rss_fallback_desc=art.description)
            ext_status = extracted.get("content_extraction_status")
            char_count = len(extracted.get("body_text", ""))
            
            if ext_status == "success":
                stats["success"] += 1
            elif ext_status == "partial_rss_fallback":
                stats["partial"] += 1
            else:
                stats["failed"] += 1
                
            gemini_decision = "REJECT"
            dev_type = "LOW_VALUE"
            event_name = "N/A"
            relationship = "N/A"
            image_found = "N/A"
            trailer_found = "N/A"
            reason = "Extraction failed or insufficient content"
            
            if ext_status in ["success", "partial_rss_fallback"]:
                analysis = await gemini.analyze_article(art.title, extracted.get("body_text"), art.url, article_desc="")
                if analysis:
                    stats["gemini_analyzed"] += 1
                    event_name = analysis.canonical_entity
                    dev_type = analysis.development_type
                    
                    if analysis.publish:
                        gemini_decision = "PUBLISH"
                        stats["publishable"] += 1
                        
                        rel_type = "NEW_DEVELOPMENT"
                        if event_name in consolidated_events:
                            rel_type = "REPEATS" if analysis.development_type == "REPEAT" else "ADDS_INFORMATION"
                            stats["events_merged"] += 1
                            stats["duplicates_prevented"] += 1
                            consolidated_events[event_name]["articles"].append(extracted)
                            consolidated_events[event_name]["domains"].add(source_name)
                        else:
                            stats["events_created"] += 1
                            consolidated_events[event_name] = {
                                "entity": event_name,
                                "type": analysis.event_type,
                                "importance": analysis.importance_score,
                                "summary": analysis.summary,
                                "articles": [extracted],
                                "domains": {source_name}
                            }
                            
                        relationship = rel_type
                        
                        tmdb_res = await enricher.search_tmdb(event_name, analysis.event_type)
                        yt_res = None
                        if analysis.trailer_needed or "trailer" in art.title.lower():
                            yt_res = await enricher.search_official_youtube_trailer(event_name)
                            
                        if tmdb_res and tmdb_res.get("poster_url"):
                            image_found = tmdb_res.get("poster_url")
                            stats["images"] += 1
                        elif extracted.get("og_image"):
                            image_found = extracted.get("og_image")
                            stats["images"] += 1
                            
                        if yt_res:
                            trailer_found = yt_res
                            stats["trailers"] += 1
                            
                        reason = "Approved by AI"
                    else:
                        stats["gemini_rejected"] += 1
                        reason = analysis.reason_if_rejected or "AI editorial rejection"
                else:
                    reason = "Gemini API call or validation failed"
                    
            article_results.append({
                "title": art.title,
                "source": source_name,
                "url": art.url,
                "ext_status": ext_status,
                "char_count": char_count,
                "gemini_decision": gemini_decision,
                "dev_type": dev_type,
                "event": event_name,
                "relationship": relationship,
                "image": image_found,
                "trailer": trailer_found,
                "publish": gemini_decision == "PUBLISH",
                "reason": reason
            })
            
        print("\n" + "=" * 50)
        print("REAL DATA EDITORIAL REPORT")
        print("=" * 50)
        for r in article_results:
            print(f"\nTITLE: {r['title']}")
            print(f"SOURCE: {r['source']}")
            print(f"URL: {r['url']}")
            print(f"EXTRACTION STATUS: {r['ext_status']} ({r['char_count']} chars)")
            print(f"GEMINI DECISION: {r['gemini_decision']} (Dev Type: {r['dev_type']})")
            print(f"EVENT: {r['event']} (Relationship: {r['relationship']})")
            print(f"IMAGE: {r['image']}")
            print(f"TRAILER: {r['trailer']}")
            print(f"PUBLISH/REJECT: {'PUBLISH' if r['publish'] else 'REJECT'}")
            print(f"REASON: {r['reason']}")
            
        print("\n" + "=" * 50)
        print("SUMMARY STATS")
        print("=" * 50)
        print(f"articles discovered:           {stats['discovered']}")
        print(f"articles fetched:              {stats['fetched']}")
        print(f"successful extraction:         {stats['success']}")
        print(f"partial extraction:            {stats['partial']}")
        print(f"failed extraction:             {stats['failed']}")
        print(f"Gemini analyzed:               {stats['gemini_analyzed']}")
        print(f"Gemini rejected:               {stats['gemini_rejected']}")
        print(f"events created:                {stats['events_created']}")
        print(f"events merged:                 {stats['events_merged']}")
        print(f"publishable stories:           {stats['publishable']}")
        print(f"images found:                  {stats['images']}")
        print(f"trailers found:                {stats['trailers']}")
        print(f"duplicates prevented:          {stats['duplicates_prevented']}")
        print("=" * 50 + "\n")
        
        print("=== Mock Final Digest Writing Output (gemini-3.6-flash) ===")
        for event_name, ev in consolidated_events.items():
            bodies = [art.get("body_text", "") for art in ev["articles"]]
            print(f"\nGenerating final digest story for event: {event_name}")
            story_text = await gemini.synthesize_editorial_story(event_name, bodies)
            if story_text:
                print(story_text)
                print(f"🔗 Source:\n{ev['articles'][0].get('canonical_url', 'N/A')}")
                if len(ev["domains"]) > 1:
                    print("🔗 Sources:")
                    for art in ev["articles"][:3]:
                        print(art.get("canonical_url", "N/A"))
            else:
                print("[Failed to write story]")
        await session_extract.close()
        db.close()
        
    try:
        asyncio.run(_run_test())
        return 0
    except Exception as e:
        import traceback
        traceback.print_exc()
        print_error(f"Acceptance test command failed: {e}")
        return 1

# Main entrypoint
def main() -> None:
    parser = argparse.ArgumentParser(
        description="EIP Management Command CLI.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")
    
    # Subcommands
    subparsers.add_parser("health", help="Check overview status of database, scheduler, telegram, and feeds.")
    subparsers.add_parser("admin-report", help="Generate daily diagnostics statistics summary.")
    subparsers.add_parser("metrics", help="Print recent daily metrics summary.")
    subparsers.add_parser("morning-digest", help="Manually run the morning digest pipeline sweep.")
    subparsers.add_parser("evening-digest", help="Manually run the evening digest pipeline sweep.")
    subparsers.add_parser("breaking-check", help="Manually check and alert on recent breaking news events.")
    subparsers.add_parser("collect-feeds", help="Execute an RSS feed sweep collection manually.")
    subparsers.add_parser("scheduler-status", help="Verify if background scheduler execution is active.")
    subparsers.add_parser("database-size", help="Query physical SQLite file size on disk.")
    subparsers.add_parser("backup-db", help="Create a time-stamped backup of the database file.")
    
    # New subcommands
    diag_parser = subparsers.add_parser("diagnose-article", help="Diagnose article content extraction and AI parsing.")
    diag_parser.add_argument("--url", required=True, help="URL of the article to diagnose")
    
    subparsers.add_parser("run-acceptance-test", help="Run the real-data acceptance pipeline test without publishing.")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
        
    command_mapping = {
        "health": cmd_health,
        "admin-report": cmd_admin_report,
        "metrics": cmd_metrics,
        "morning-digest": cmd_morning_digest,
        "evening-digest": cmd_evening_digest,
        "breaking-check": cmd_breaking_check,
        "collect-feeds": cmd_collect_feeds,
        "scheduler-status": cmd_scheduler_status,
        "database-size": cmd_database_size,
        "backup-db": cmd_backup_db,
    }
    
    if args.command == "diagnose-article":
        exit_code = cmd_diagnose_article(args.url)
    elif args.command == "run-acceptance-test":
        exit_code = cmd_run_acceptance_test()
    else:
        exit_code = command_mapping[args.command]()
        
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
