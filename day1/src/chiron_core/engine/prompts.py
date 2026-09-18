

import re
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import pandas as pd

from chiron_core.domain.models import AgentAction, ActionType


SYSTEM_PROMPT = """You are an expert Data Analysis & Visualization Assistant.
You analyze tabular datasets and generate clear interactive visualizations using Plotly.

You operate strictly following a ReAct (Reasoning + Acting) cycle:
1. Thought: Analyze the problem, plan the next calculation or visualization step.
2. Action: Either run Python code in a secure sandbox, OR present your final answer.

Available actions:
- `Action: execute_code`
Followed immediately by a python code block:
```python
# your code here
```
- `Action: final_answer: <your final explanation, insights, and summary>`

CRITICAL RULES:
1. Execute only ONE action per turn.
2. If you choose `Action: execute_code`, output the code block and STOP immediately. NEVER simulate, hallucinate or guess the Observation. Wait for the real sandbox execution result.
3. Only output `Action: final_answer` after you have received and verified the real execution output from the sandbox.
4. The dataset is provided in the current directory as 'data.csv'. Load it using `pd.read_csv('data.csv')`.
5. Do data cleaning, grouping, and aggregations using pandas and numpy.
6. Print numeric results, summary statistics, or tables to stdout with `print()`.
7. If a visualization is requested or helpful, create an interactive plot using `plotly.express` as `px` or `plotly.graph_objects` as `go`.
8. ALWAYS save the Plotly figure to 'plot.html' using:
   `fig.write_html("plot.html", include_plotlyjs="cdn")`
9. Keep plots clean, readable, and well-labeled (informative titles, axes labels, hover data).
10. Do NOT attempt any external network connections (e.g. no urllib/requests); the execution environment denies internet access.

Format for code execution:
Thought: <what you plan to do>
Action: execute_code
```python
# Code to execute
```

Format for final answer (only after seeing real execution output):
Thought: <reflection on the findings and generated plot>
Action: final_answer: <detailed summary of the data insights and findings>
"""


def extract_dataset_summary(dataset_path: Path) -> Dict[str, Any]:
    # prendo info e colonne per il prompt iniziale
    path = Path(dataset_path)
    if not path.exists():
        return {
            "num_rows": 0,
            "num_columns": 0,
            "columns": [],
            "dtypes": {},
            "sample_head": "File not found.",
        }

    try:
        df = pd.read_csv(path)
        return {
            "num_rows": len(df),
            "num_columns": len(df.columns),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "sample_head": df.head(3).to_string(index=False),
        }
    except Exception as e:
        return {
            "error": f"Failed to read dataset: {str(e)}",
            "columns": [],
            "sample_head": "",
        }


def build_initial_user_prompt(query: str, dataset_summary: Dict[str, Any]) -> str:
    # costruisco il messaggio utente iniziale
    columns_str = ", ".join(dataset_summary.get("columns", []))
    dtypes_str = ", ".join([f"{col} ({dtype})" for col, dtype in dataset_summary.get("dtypes", {}).items()])
    sample_head = dataset_summary.get("sample_head", "")
    num_rows = dataset_summary.get("num_rows", "unknown")

    return f"""User Request: {query}

Dataset Information:
- Total Rows: {num_rows}
- Columns & Types: {dtypes_str}
- Sample Data (first 3 rows):
{sample_head}

Analyze the data and answer the user request. If a visualization is appropriate, generate an interactive Plotly chart and save it as 'plot.html'. Start with your Thought and Action.
"""


def parse_react_response(text: str) -> Tuple[str, AgentAction]:
    # estraggo thought e action dalla risposta
    cleaned_text = text.strip()
    
    # estraggo il Thought
    thought = ""
    thought_match = re.search(r"Thought:\s*(.*?)(?=(?:Action:|$))", cleaned_text, re.DOTALL | re.IGNORECASE)
    if thought_match:
        thought = thought_match.group(1).strip()
    else:
        # se non c'è il prefisso prendo tutto prima di Action:
        action_idx = cleaned_text.lower().find("action:")
        if action_idx != -1:
            thought = cleaned_text[:action_idx].strip()
        else:
            thought = "Processing request."

    # se c'è codice diamo precedenza all'esecuzione
    code_match = re.search(r"```(?:python)?\s*\n(.*?)\n```", cleaned_text, re.DOTALL | re.IGNORECASE)
    if code_match:
        code_str = code_match.group(1).strip()
        return thought, AgentAction(action_type=ActionType.EXECUTE_CODE, code=code_str)

    # cerco la risposta finale
    final_answer_match = re.search(
        r"Action:\s*final_answer:\s*(.*)", cleaned_text, re.DOTALL | re.IGNORECASE
    )
    if not final_answer_match:
        # variante senza prefisso Action:
        final_answer_match = re.search(r"Final Answer:\s*(.*)", cleaned_text, re.DOTALL | re.IGNORECASE)

    if final_answer_match:
        answer_text = final_answer_match.group(1).strip()
        return thought, AgentAction(action_type=ActionType.FINAL_ANSWER, answer=answer_text)

    # fallback: se non trovo tag prendo tutto come risposta finale
    return thought, AgentAction(action_type=ActionType.FINAL_ANSWER, answer=cleaned_text)

