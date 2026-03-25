"""
Service configuration.

All environment variables and derived paths are centralised here so that
every other module can import from a single source of truth.
"""

import os
from pathlib import Path

ORION_URL = os.getenv("ORION_URL", "http://orion:1026")
DATA_RAW_PATH = Path(os.getenv("DATA_RAW_PATH", "/data/raw"))
DATA_PROCESSED_PATH = Path(os.getenv("DATA_PROCESSED_PATH", "/data/processed"))

# Default data-source URLs — can be overridden per-request via the API
DEFAULT_RGB_URL = os.getenv("RGB_URL", "")
DEFAULT_NIR_URL = os.getenv("NIR_URL", "")
DEFAULT_DTM_URL = os.getenv("DTM_URL", "")
DEFAULT_BUILDINGS_URL = os.getenv("BUILDINGS_AND_ENGINEERING_WORKS_URL", "")

# Ensure storage directories exist at import time
DATA_RAW_PATH.mkdir(parents=True, exist_ok=True)
DATA_PROCESSED_PATH.mkdir(parents=True, exist_ok=True)
