"""
Integration and contract tests for Chiron Service REST API.
Verifies all Day 2 API requirements:
1. Healthcheck endpoint
2. POST /analyze contract, reasoning trace, and response payload
3. GET /sessions/{id} retrieval and persistence
4. Multi-turn conversation continuation within the same session
5. Robust error handling (empty queries, invalid datasets, non-existent sessions)
6. Plot serving security
"""

import pytest
from starlette.testclient import TestClient


def test_health_endpoint(client: TestClient):
    """Verify healthcheck returns 200 and expected metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "chiron" in data["service"]
    assert "version" in data


def test_list_datasets_endpoint(client: TestClient):
    """Verify preloaded datasets are discoverable via API."""
    response = client.get("/datasets")
    assert response.status_code == 200
    data = response.json()
    filenames = [d["filename"] for d in data.get("datasets", [])]
    assert "ecommerce_sales_2024.csv" in filenames


def test_analyze_endpoint_success(client: TestClient):
    """Test POST /analyze returns 200, session ID, reasoning trace, and analysis answer."""
    payload = {
        "query": "How many records are in the dataset?",
        "dataset": "ecommerce_sales_2024.csv",
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # verifico lo schema della risposta
    assert "session_id" in data
    assert data["status"] == "success"
    assert data["query"] == payload["query"]
    assert len(data["final_answer"]) > 0
    assert isinstance(data["trace"], list)
    assert len(data["trace"]) > 0
    assert data["trace"][0]["step_number"] == 1
    assert "execution_time_seconds" in data


def test_session_retrieval(client: TestClient):
    """Test that a completed analysis turn is retrievable via GET /sessions/{id}."""
    # 1. creo l'analisi
    payload = {
        "query": "Count the rows",
        "dataset": "ecommerce_sales_2024.csv",
    }
    create_res = client.post("/analyze", json=payload)
    assert create_res.status_code == 200
    session_id = create_res.json()["session_id"]

    # 2. recupero la sessione
    get_res = client.get(f"/sessions/{session_id}")
    assert get_res.status_code == 200
    session_data = get_res.json()

    assert session_data["id"] == session_id
    assert len(session_data["messages"]) == 2  # 1 messaggio utente + 1 assistente
    assert session_data["messages"][0]["role"] == "user"
    assert session_data["messages"][0]["content"] == payload["query"]
    assert session_data["messages"][1]["role"] == "assistant"
    assert len(session_data["traces"]) > 0


def test_multi_turn_session_persistence(client: TestClient):
    """Test resuming an existing session with multiple queries preserves conversation history."""
    # turno 1
    res1 = client.post("/analyze", json={"query": "First question", "dataset": "ecommerce_sales_2024.csv"})
    assert res1.status_code == 200
    session_id = res1.json()["session_id"]

    # turno 2 con lo stesso session_id
    res2 = client.post("/analyze", json={"query": "Follow-up question", "dataset": "ecommerce_sales_2024.csv", "session_id": session_id})
    assert res2.status_code == 200
    assert res2.json()["session_id"] == session_id

    # verifico che ci siano 4 messaggi nello storico
    session_res = client.get(f"/sessions/{session_id}")
    assert session_res.status_code == 200
    session_data = session_res.json()
    assert len(session_data["messages"]) == 4


def test_session_not_found_returns_404(client: TestClient):
    """Verify 404 is returned when requesting a non-existent session."""
    response = client.get("/sessions/definitely-non-existent-session-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_empty_query_returns_422(client: TestClient):
    """Verify 422 Unprocessable Entity when sending an empty query."""
    response = client.post("/analyze", json={"query": "   ", "dataset": "ecommerce_sales_2024.csv"})
    assert response.status_code == 422


def test_missing_dataset_returns_404(client: TestClient):
    """Verify 404 when requesting an unknown dataset file."""
    response = client.post("/analyze", json={"query": "Calculate totals", "dataset": "ghost_file_xyz.csv"})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_plot_serving_security_traversal(client: TestClient):
    """Verify directory traversal is rejected on /plots/{filename}."""
    response = client.get("/plots/../../etc/passwd")
    assert response.status_code in [400, 404]
