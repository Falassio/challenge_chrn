"""
Chiron Service - Day 2 Production & Service Layer.
Exposes the Core ReAct Agent via FastAPI with SQLite persistence and Docker support.
"""

from pathlib import Path
import sys

# aggiungo day1/src per gli import
DAY1_SRC = Path(__file__).resolve().parents[3] / "day1" / "src"
if DAY1_SRC.exists() and str(DAY1_SRC) not in sys.path:
    sys.path.insert(0, str(DAY1_SRC))

__version__ = "0.2.0"
