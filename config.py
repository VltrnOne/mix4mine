"""
VLTRN SUNO Automation Suite - Configuration
"""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
LOGS_DIR = BASE_DIR / "logs"
TEMPLATES_DIR = BASE_DIR / "templates"

# Chrome settings
CHROME_DEBUG_PORT = 9222
CHROME_USER_DATA = os.path.expanduser("~/Library/Application Support/Google/Chrome")

# SUNO settings
SUNO_BASE_URL = "https://suno.com"
SUNO_API_BASE = "https://studio-api.suno.ai"

# Rate limiting
GENERATION_DELAY = 30  # seconds between generations
MAX_CONCURRENT_GENERATIONS = 2
DOWNLOAD_DELAY = 5  # seconds between downloads

# Quality thresholds
MIN_DURATION_SECONDS = 60
MAX_SILENCE_RATIO = 0.2
MIN_RMS_DB = -30

# File organization
FILE_NAMING_TEMPLATE = "{date}_{title}_{genre}_{id}.mp3"
ORGANIZE_BY_DATE = True
ORGANIZE_BY_GENRE = True
ORGANIZE_BY_TIER = True

# API Keys (from environment)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
