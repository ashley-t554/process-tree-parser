import sys
from pathlib import Path

# Tests run against the source tree directly so they work without an
# editable install (`pip install -e .`) being set up first.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
