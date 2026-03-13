"""
Shared utility functions for Video Copy Analyzer.
Extracted from step2_analyzer.py and step4_uploader.py to eliminate duplication.
"""

import os
import re
from datetime import datetime
from dotenv import load_dotenv

# === Project paths ===
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(PROJECT_ROOT, "workspace_data")
os.makedirs(WORK_DIR, exist_ok=True)

# Load .env from project root
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, ".env"))


def env_clean(name, default=None):
    """Read and sanitize .env values, tolerating trailing comments and wrapping quotes."""
    value = os.getenv(name, default)
    if value is None:
        return None
    value = str(value).strip()
    # Strip trailing inline comments: KEY=value  # comment
    value = re.sub(r"\s+#.*$", "", value).strip()
    # Strip wrapping quotes
    value = value.strip().strip('"').strip("'").strip()
    return value


def parse_number(text):
    """Parse Chinese-style number strings (e.g., '1.2万', '3k', '500+') to int."""
    if not text:
        return 0
    text = str(text).strip().lower()
    try:
        text = text.replace('+', '')
        if '万' in text:
            return int(float(text.replace('万', '')) * 10000)
        elif 'w' in text:
            return int(float(text.replace('w', '')) * 10000)
        elif 'k' in text:
            return int(float(text.replace('k', '')) * 1000)
        else:
            clean_text = re.sub(r'[^\d.]', '', text)
            return int(float(clean_text)) if clean_text else 0
    except Exception:
        return 0


def make_logger(log_file):
    """Create a logger function that prints and writes to a log file."""
    def _log(message):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {message}"
        print(line)
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
    return _log


def check_env_security():
    """Warn if .env contains placeholder or potentially leaked keys."""
    placeholders = ["your_", "sk-xxx", "put_your", "replace_me", "changeme"]
    warned = False
    for key_name in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "NOTION_TOKEN"]:
        value = os.getenv(key_name, "")
        if not value:
            continue
        for ph in placeholders:
            if ph in value.lower():
                print(f"  {key_name} appears to be a placeholder value.")
                warned = True
                break
    if warned:
        print("  Please update .env with real API keys.\n")


def validate_url(url):
    """Basic URL validation — only allow http/https schemes."""
    if not url:
        return False
    url_lower = str(url).strip().lower()
    return url_lower.startswith("http://") or url_lower.startswith("https://")
