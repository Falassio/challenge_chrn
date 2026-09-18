"""
CLI Entrypoint for Chiron Day 1 Core Agent.
Usage:
    python day1/run_day1.py --query "Show total revenue by product category" --dataset day1/data/ecommerce_sales_2024.csv
    python day1/run_day1.py --mock  # esegue con mock llm per test
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# aggiungo src al path di python
SRC_DIR = Path(__file__).parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from chiron_core.config import get_settings
from chiron_core.adapters.llm import OpenAILLMAdapter, MockLLMAdapter
from chiron_core.adapters.sandbox import ProcessSandboxAdapter
from chiron_core.use_cases.analyze_dataset import AnalyzeDatasetUseCase
from chiron_core.utils.logger import get_logger


def get_mock_responses() -> list[str]:
    # sequenza di test realistica per il mock
    return [
        """Thought: I need to analyze total revenue by product category and generate an interactive Plotly bar chart.
First, I will load the dataset, group the revenue by category, and generate the chart.
Action: execute_code
```python
import pandas as pd
import plotly.express as px

# 1. carico il dataset
df = pd.read_csv('data.csv')

# 2. raggruppo il fatturato per categoria
revenue_by_cat = df.groupby('product_category')['total_revenue'].sum().reset_index()
revenue_by_cat = revenue_by_cat.sort_values(by='total_revenue', ascending=False)
print("Revenue by Category:")
print(revenue_by_cat.to_string(index=False))

# 3. creo il grafico a barre con plotly
fig = px.bar(
    revenue_by_cat,
    x='product_category',
    y='total_revenue',
    title='Total Revenue by Product Category (2024)',
    labels={'product_category': 'Product Category', 'total_revenue': 'Total Revenue ($)'},
    color='total_revenue',
    color_continuous_scale='Viridis',
    text_auto='.2s'
)
fig.update_layout(template='plotly_white')

# 4. salvo su file html
fig.write_html('plot.html', include_plotlyjs='cdn')
print("Successfully saved visualization to plot.html")
```""",
        """Thought: The code executed successfully. Total revenue was calculated for each category: Electronics is the highest contributor (~$280k+), followed by Furniture, Apparel, and Office Supplies. The Plotly bar chart was generated and saved to plot.html. I will now synthesize the final answer.
Action: final_answer: The analysis of 2024 e-commerce sales indicates that **Electronics** generated the highest total revenue, closely followed by **Furniture** and **Apparel**, with **Office Supplies** representing the lowest overall share. An interactive Plotly bar chart illustrating the distribution by category has been successfully created and saved as an HTML artifact."""
    ]


def main():
    load_dotenv()
    settings = get_settings()
    logger = get_logger("Day1-CLI")

    parser = argparse.ArgumentParser(description="Chiron Day 1 - ReAct Data Analysis Agent")
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to CSV dataset (default: day1/data/ecommerce_sales_2024.csv)",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="User question or analysis task",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run using a deterministic Mock LLM (no API key required)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=settings.default_output_dir,
        help="Directory to save generated plot files",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=settings.sandbox_timeout_seconds,
        help="Execution timeout in seconds for sandbox scripts",
    )

    args = parser.parse_args()

    # se non passa parametri da cli chiedo da terminale
    dataset_input = args.dataset
    if not dataset_input:
        if sys.stdin.isatty():
            val = input("Percorso del CSV (premi Invio per usare 'day1/data/ecommerce_sales_2024.csv'): ").strip().strip('\"\'')
            dataset_input = val if val else "day1/data/ecommerce_sales_2024.csv"
        else:
            dataset_input = "day1/data/ecommerce_sales_2024.csv"

    query_input = args.query
    if not query_input:
        if sys.stdin.isatty():
            val = input("Cosa vuoi chiedere o analizzare sui dati? (premi Invio per default): ").strip()
            query_input = val if val else "Analizza il dataset e mostra i trend principali con un grafico Plotly."
        else:
            query_input = "Analyze total revenue by product category and create an interactive bar chart."

    dataset_path = Path(dataset_input)
    if not dataset_path.exists():
        logger.error(f"Dataset non trovato al percorso: {dataset_path}")
        sys.exit(1)

    # inizializzo la sandbox
    sandbox = ProcessSandboxAdapter(
        timeout_seconds=args.timeout,
        output_dir=args.output_dir,
    )

    # inizializzo l'adapter llm
    if args.mock:
        logger.info("Running in MOCK mode (using predefined LLM responses)...")
        llm = MockLLMAdapter(responses=get_mock_responses())
    else:
        api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            logger.warning(
                "No OPENAI_API_KEY detected in environment or .env. Falling back to MOCK mode."
            )
            logger.warning("To use a real LLM, configure OPENAI_API_KEY in your .env file.")
            llm = MockLLMAdapter(responses=get_mock_responses())
        else:
            logger.info(f"Using OpenAI LLM provider (Model: {settings.openai_model})...")
            llm = OpenAILLMAdapter(
                api_key=api_key,
                base_url=settings.openai_base_url,
                model=settings.openai_model,
            )

    # istanzio il caso d'uso
    use_case = AnalyzeDatasetUseCase(
        llm=llm,
        sandbox=sandbox,
        max_iterations=settings.max_iterations,
    )

    print("\n" + "=" * 60)
    print("CHIRON DATA ANALYSIS AGENT - DAY 1")
    print("=" * 60)
    print(f"Dataset : {dataset_path}")
    print(f"Query   : {query_input}")
    print("=" * 60 + "\n")

    result, _ = use_case.execute(query=query_input, dataset_path=dataset_path)

    print("\n" + "=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)
    print(f"Status        : {result.status.upper()}")
    print(f"Total Steps   : {result.total_steps}")
    print(f"Time Taken    : {result.execution_time_seconds}s")
    if result.plot_path:
        print(f"Plot Artifact : {result.plot_path}")
    print("-" * 60)
    print(f"Answer:\n{result.final_answer}")
    print("=" * 60)

    # riepilogo passaggi del reasoning trace
    print("\nREASONING TRACE SUMMARY:")
    for step in result.trace.steps:
        print(f"\n[Step {step.step_number}]")
        print(f"  Thought : {step.thought}")
        print(f"  Action  : {step.action.action_type.value}")
        if step.observation:
            status = "SUCCESS" if step.observation.is_success else "FAILED"
            print(f"  Sandbox : {status} (took {step.observation.execution_time_ms}ms)")
            if step.observation.plot_path:
                print(f"  Artifact: {step.observation.plot_path}")
    print("\nDone.")

    if result.plot_path and sys.stdin.isatty():
        try:
            choice = input("Vuoi aprire il grafico interattivo nel browser? [s/N]: ").strip().lower()
            if choice in ["s", "si", "y", "yes"]:
                import webbrowser
                webbrowser.open(Path(result.plot_path).resolve().as_uri())
        except Exception:
            pass


if __name__ == "__main__":
    main()
