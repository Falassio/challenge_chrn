"""
Pytest configuration and shared fixtures for Day 1 tests.
"""

import sys
import tempfile
import pytest
from pathlib import Path
import pandas as pd

# aggiungo day1/src al path
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture
def sample_csv_path(tmp_path: Path) -> Path:
    """Create a temporary CSV file for testing."""
    csv_file = tmp_path / "test_data.csv"
    data = {
        "id": [1, 2, 3, 4, 5],
        "category": ["A", "B", "A", "C", "B"],
        "revenue": [100.5, 200.0, 150.0, 300.0, 250.5],
        "quantity": [2, 4, 1, 5, 3],
    }
    df = pd.DataFrame(data)
    df.to_csv(csv_file, index=False)
    return csv_file


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create an isolated output directory for tests."""
    out = tmp_path / "test_output"
    out.mkdir(parents=True, exist_ok=True)
    return out
