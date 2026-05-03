"""ThaiVoice entry point. Add src/ to sys.path then dispatch to app.main."""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from app.main import main  # noqa: E402

if __name__ == "__main__":
    main()
