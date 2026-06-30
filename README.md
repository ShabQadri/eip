# Entertainment Intelligence Platform

A production-grade, modular, and async-ready Telegram-based movie and TV entertainment digest platform. It aggregates news from trusted RSS feeds and publishes curated digests twice daily.

Designed to be highly performant, lightweight, and suitable for resource-constrained deployments (such as Oracle Cloud Free Tier).

## Architecture Overview

The system follows a modular, service-oriented architecture:

- **`src/config/`**: Handles environment loading and application configurations.
- **`src/constants/`**: Declares application-wide constants, regex, source policies, categories, emojis, etc.
- **`src/models/`**: Houses domain entities, schemas, and data structures.
- **`src/services/`**: Holds core business logic implementations (e.g., Digest processing).
- **`src/database/`**: Configures and interacts with the SQLite database.
- **`src/feeds/`**: Aggregates news from RSS feeds.
- **`src/processing/`**: Content filters, text summaries, classifiers, and deduplication modules.
- **`src/digest/`**: Logic to compile digests (supporting rule-based structures first, extensible to LLM enhancement).
- **`src/images/`**: Image and social card generation.
- **`src/telegram/`**: Communication and messaging clients.
- **`src/scheduler/`**: Manages twice-daily cron jobs.
- **`src/utils/`**: General helper libraries including standard logging.

---

## Installation

### Prerequisites
- Python 3.12+
- Virtual Environment tool (`venv`)

### Setup Instructions
1. Navigate to the project root:
   ```bash
   cd entertainment-intelligence-platform
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```

3. Activate the virtual environment:
   - **Windows (PowerShell)**:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS**:
     ```bash
     source .venv/bin/activate
     ```

4. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Setup your local configuration:
   ```bash
   copy .env.example .env
   # Or on Unix: cp .env.example .env
   ```

---

## How to Run

Execute the platform with:
```bash
python src/main.py
```

Expected Output:
```text
Entertainment Intelligence Platform initialized.
```

---

## Verification
- **Startup Time**: Launches in under 2 seconds.
- **Memory Footprint**: Idle memory is under 200 MB, optimizing performance for Oracle Free Tier.
- **Clean Environment**: Does not establish DB connections, scheduler loops, or network calls at boot.
