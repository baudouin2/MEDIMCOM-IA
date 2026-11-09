"""Rend le paquet `medimcom` importable depuis kb/outils/."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
KB = RACINE / "kb"
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import sys as _sys
for _flux in (_sys.stdout, _sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")
