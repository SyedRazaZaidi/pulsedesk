from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ARTIFACTS = ROOT / "artifacts"
DB_PATH = Path(os.environ["PULSEDESK_DB"]) if os.environ.get("PULSEDESK_DB") else DATA_DIR / "pulsedesk.db"
HORIZON = 14
SEED = 42
TRAIN_FRAC = 0.85
