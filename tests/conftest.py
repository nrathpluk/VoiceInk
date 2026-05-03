"""Pytest fixtures + path setup so tests can import the `app` package."""

import sys
from pathlib import Path

# Add src/ to sys.path so `from app.* import ...` works in tests
SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC))
