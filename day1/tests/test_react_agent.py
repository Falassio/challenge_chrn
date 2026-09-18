"""
Unit tests for ReActDataAgent and Prompt/Response parsing.
Verifies:
1. ReAct loop flow (Thought -> Action -> Observation -> Final Answer)
2. Agentic error self-healing / reflection
3. Max iteration cutoff
4. Parser resilience
"""

from pathlib import Path
import pytest

from chiron_core.domain.models import ActionType
from chiron_core.adapters.llm.mock_adapter import MockLLMAdapter
from chiron_core.adapters.sandbox.process_sandbox import ProcessSandboxAdapter
from chiron_core.engine.react_agent import ReActDataAgent
from chiron_core.engine.prompts import parse_react_response


def test_parse_react_response_execute_code():
    """Test parsing a standard ReAct response with execute_code."""
    text = """Thought: I will compute the sum of revenues.
Action: execute_code
```python
import pandas as pd
df = pd.read_csv('data.csv')
print(df['revenue'].sum())
```"""
    thought, action = parse_react_response(text)
    assert "compute the sum" in thought
    assert action.action_type == ActionType.EXECUTE_CODE
    assert "df['revenue'].sum()" in action.code


def test_parse_react_response_final_answer():
    """Test parsing a final answer action."""
    text = """Thought: The calculations are complete.
Action: final_answer: The total revenue across all categories is $1,001.00."""
    thought, action = parse_react_response(text)
    assert "calculations are complete" in thought
    assert action.action_type == ActionType.FINAL_ANSWER
    assert "$1,001.00" in action.answer


def test_parse_react_response_fallback_resilience():
    """Test parser resilience when formatting is slightly informal."""
    text = """Final Answer: Everything looks good, total count is 5."""
    thought, action = parse_react_response(text)
    assert action.action_type == ActionType.FINAL_ANSWER
    assert "total count is 5" in action.answer


def test_react_agent_successful_flow(sample_csv_path: Path, output_dir: Path):
    """Test complete successful ReAct cycle with Mock LLM."""
    responses = [
        """Thought: Let's group by category and generate a plot.
Action: execute_code
```python
import pandas as pd
import plotly.express as px
df = pd.read_csv('data.csv')
grouped = df.groupby('category')['revenue'].sum().reset_index()
fig = px.bar(grouped, x='category', y='revenue')
fig.write_html('plot.html')
print("Done grouping.")
```""",
        """Thought: Plot generated and data inspected.
Action: final_answer: Category C generated the highest revenue ($300)."""
    ]

    mock_llm = MockLLMAdapter(responses=responses)
    sandbox = ProcessSandboxAdapter(timeout_seconds=5, output_dir=str(output_dir))
    agent = ReActDataAgent(llm=mock_llm, sandbox=sandbox, max_iterations=5)

    result = agent.run_analysis(
        query="Which category had the highest revenue?",
        dataset_path=sample_csv_path
    )

    assert result.status == "success"
    assert result.total_steps == 2
    assert "Category C" in result.final_answer
    assert result.plot_path is not None
    assert Path(result.plot_path).exists()
    assert len(result.trace.steps) == 2


def test_react_agent_self_healing_error_recovery(sample_csv_path: Path, output_dir: Path):
    """
    Test agent self-healing:
    Step 1: Code fails due to KeyError on non-existent column.
    Step 2: Agent observes error and corrects code.
    Step 3: Agent provides final answer.
    """
    responses = [
        # step 1: codice volutamente errato
        """Thought: I will access the 'profit' column.
Action: execute_code
```python
import pandas as pd
df = pd.read_csv('data.csv')
print(df['non_existent_profit'].mean())
```""",
        # step 2: correzione dopo l'errore KeyError
        """Thought: I see that 'non_existent_profit' caused a KeyError. I will use 'revenue' instead.
Action: execute_code
```python
import pandas as pd
df = pd.read_csv('data.csv')
mean_rev = df['revenue'].mean()
print(f"MEAN_REV:{mean_rev}")
```""",
        # step 3: risposta finale
        """Thought: Now I have the correct average revenue.
Action: final_answer: The average revenue is approximately $200.20."""
    ]

    mock_llm = MockLLMAdapter(responses=responses)
    sandbox = ProcessSandboxAdapter(timeout_seconds=5, output_dir=str(output_dir))
    agent = ReActDataAgent(llm=mock_llm, sandbox=sandbox, max_iterations=5)

    result = agent.run_analysis(
        query="Calculate average revenue",
        dataset_path=sample_csv_path
    )

    assert result.status == "success"
    assert result.total_steps == 3
    # step 1 fallito
    assert result.trace.steps[0].observation.is_success is False
    # step 2 ok
    assert result.trace.steps[1].observation.is_success is True
    assert "MEAN_REV:200.2" in result.trace.steps[1].observation.stdout
    # step 3 risposta completata
    assert "average revenue" in result.final_answer.lower()


def test_react_agent_max_iterations_cutoff(sample_csv_path: Path, output_dir: Path):
    """Test that agent terminates cleanly if max iterations is exceeded without finishing."""
    responses = [
        """Thought: Trying step.
Action: execute_code
```python
print("Step loop")
```"""
    ]

    mock_llm = MockLLMAdapter(responses=responses)
    sandbox = ProcessSandboxAdapter(timeout_seconds=5, output_dir=str(output_dir))
    agent = ReActDataAgent(llm=mock_llm, sandbox=sandbox, max_iterations=2)

    result = agent.run_analysis(
        query="Loop forever test",
        dataset_path=sample_csv_path
    )

    assert result.status == "error"
    assert result.total_steps == 2
    assert "maximum number of iterations" in result.final_answer
