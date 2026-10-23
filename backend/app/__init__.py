"""GlycoTwin backend package.

The repository root is placed on sys.path so the backend can import the same
`ml` package used for training. Training and serving therefore share one
feature engineering implementation.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
