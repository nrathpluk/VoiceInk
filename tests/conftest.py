"""Pytest fixtures + path setup so tests can import project modules."""

import sys
from pathlib import Path

# Add project root to sys.path so `from util import ...` works in tests
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
