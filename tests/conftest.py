"""Pytest configuration for local package import path.

Ensures tests import the local captainhook package even when invoked from
directories other than the repository root.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
