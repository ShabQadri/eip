# Use official slim Python 3.12 image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
# - Prevents Python from writing pyc files to disc
# - Prevents Python from buffering stdout and stderr
# - Sets Python path to include /app for absolute imports
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Copy dependency definition
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create runtime directories for SQLite, logs, backups, and caches
RUN mkdir -p data/sqlite data/images data/logs data/backups data/cache

# Copy application code
COPY src/ ./src/

# Run as non-root user for security
RUN useradd -u 1000 -m appuser && chown -R appuser:appuser /app
USER appuser

# Entry point
CMD ["python", "src/main.py"]
