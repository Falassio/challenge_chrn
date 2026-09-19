"""
Pytest configuration and fixtures for Day 2 API testing.
"""

from pathlib import Path
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

# aggiungo day1 e day2 al path
TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent.parent
DAY1_SRC = PROJECT_ROOT / "day1" / "src"
DAY2_SRC = TEST_DIR.parent / "src"

for p in [str(DAY1_SRC), str(DAY2_SRC)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from chiron_service.storage.models import Base
from chiron_service.storage.database import get_db
from chiron_service.api.routes import get_llm_adapter
from chiron_service.api.app import create_app
from chiron_core.adapters.llm import MockLLMAdapter


@pytest.fixture
def test_db(tmp_path: Path):
    """Create a temporary SQLite database file for testing."""
    db_file = tmp_path / "test_sessions.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def mock_llm_responses():
    """Deterministic ReAct mock responses for API tests."""
    return [
        """Thought: I will calculate summary statistics.
Action: execute_code
```python
import pandas as pd
df = pd.read_csv('data.csv')
print("COUNT:", len(df))
```""",
        """Thought: Calculations completed.
Action: final_answer: The dataset contains exactly the expected rows."""
    ]


@pytest.fixture
def client(test_db, mock_llm_responses):
    """TestClient with overridden database and mock LLM adapter."""
    app = create_app()

    def override_get_db():
        yield test_db

    def override_get_llm():
        return MockLLMAdapter(responses=mock_llm_responses)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_adapter] = override_get_llm

    with TestClient(app) as test_client:
        yield test_client
