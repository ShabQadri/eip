"""
Main entrypoint for the Entertainment Intelligence Platform.
Responsible only for bootstrapping configurations, logging, and printing startup confirmation.
"""

import os
import platform
import sys
import json
from pathlib import Path

# Add project root to sys.path to support direct execution as 'python src/main.py'
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from src.config.settings import settings
from src.utils.logger import setup_logger
from src.database.database import SessionLocal
from src.services.health_service import HealthService

def main() -> None:
    # 1. Load environment variables
    load_dotenv()

    # 2. Initialize logging
    logger = setup_logger("main")
    logger.debug("Logging subsystem initialized.")

    # 3. Run Startup Self-Test
    logger.info("Running startup self-test...")
    db = SessionLocal()
    try:
        health_svc = HealthService()
        test_results = health_svc.run_startup_self_test(db)
        logger.info(f"Self-test results: {json.dumps(test_results)}")
        logger.info("Self-test successful.")
    except Exception as e:
        logger.critical(f"Startup self-test failed: {e}")
        logger.critical("Application shutdown.")
        sys.exit(1)
    finally:
        db.close()

    # 4. Load settings
    _ = settings.LOG_LEVEL

    # 5. Log startup metrics to app.log
    app_env = os.getenv("APP_ENV", "development")
    logger.info("Application initialized")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Operating system: {platform.system()} {platform.release()}")
    logger.info(f"APP_ENV: {app_env}")

    # 6. Print startup message
    print("Entertainment Intelligence Platform initialized.")

if __name__ == "__main__":
    main()
