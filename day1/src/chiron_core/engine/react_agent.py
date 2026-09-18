import time
from pathlib import Path
from typing import Union, Optional, List, Dict

from chiron_core.ports.llm_port import LLMPort
from chiron_core.ports.sandbox_port import SandboxPort
from chiron_core.domain.models import (
    Step,
    ReasoningTrace,
    AnalysisResult,
    ActionType,
)
from chiron_core.engine.prompts import (
    SYSTEM_PROMPT,
    extract_dataset_summary,
    build_initial_user_prompt,
    parse_react_response,
)
from chiron_core.utils.logger import get_logger


class ReActDataAgent:
    def __init__(
        self,
        llm: LLMPort,
        sandbox: SandboxPort,
        max_iterations: int = 5,
    ):
        self.llm = llm
        self.sandbox = sandbox
        self.max_iterations = max_iterations
        self.logger = get_logger("ReActAgent")

    def run_analysis(
        self,
        query: str,
        dataset_path: Union[str, Path],
    ) -> AnalysisResult:
        start_time = time.perf_counter()
        dataset_path = Path(dataset_path)

        self.logger.info(f"Starting analysis: '{query}' on {dataset_path.name}")

        # estraggo lo schema del dataset per non mandare troppi dati nel prompt iniziale
        dataset_summary = extract_dataset_summary(dataset_path)
        if "error" in dataset_summary:
            self.logger.warning(f"Failed to read dataset: {dataset_summary['error']}")

        trace = ReasoningTrace()
        initial_prompt = build_initial_user_prompt(query, dataset_summary)
        
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": initial_prompt},
        ]

        last_plot_path: Optional[str] = None

        # loop iterativo ReAct (pensiero -> codice -> sandbox -> osservazione)
        for step_num in range(1, self.max_iterations + 1):
            self.logger.info(f"--- Step {step_num}/{self.max_iterations} ---")

            try:
                llm_response = self.llm.generate(messages)
            except Exception as e:
                self.logger.error(f"LLM call failed at step {step_num}: {e}")
                elapsed = time.perf_counter() - start_time
                return AnalysisResult(
                    status="error",
                    query=query,
                    dataset_path=str(dataset_path),
                    final_answer=f"Analysis halted due to LLM error: {str(e)}",
                    plot_path=last_plot_path,
                    trace=trace,
                    total_steps=step_num - 1,
                    execution_time_seconds=round(elapsed, 2),
                )

            thought, action = parse_react_response(llm_response)
            self.logger.info(f"Thought: {thought}")

            current_step = Step(
                step_number=step_num,
                thought=thought,
                action=action,
            )

            # se ha finito restituisce la risposta finale
            if action.action_type == ActionType.FINAL_ANSWER:
                self.logger.info("Agent concluded with final answer.")
                trace.add_step(current_step)
                elapsed = time.perf_counter() - start_time
                return AnalysisResult(
                    status="success",
                    query=query,
                    dataset_path=str(dataset_path),
                    final_answer=action.answer or "Analysis completed.",
                    plot_path=last_plot_path,
                    trace=trace,
                    total_steps=step_num,
                    execution_time_seconds=round(elapsed, 2),
                )

            # l'agente vuole eseguire codice python nella sandbox
            if action.action_type == ActionType.EXECUTE_CODE:
                code_snippet = action.code or ""
                self.logger.info(f"Running sandbox code ({len(code_snippet.splitlines())} lines)...")

                observation = self.sandbox.execute(
                    code=code_snippet,
                    dataset_path=dataset_path,
                )

                if observation.plot_path:
                    last_plot_path = observation.plot_path
                    self.logger.info(f"Plot artifact generated: {last_plot_path}")

                if observation.is_success:
                    self.logger.info(f"Code ran ok in {observation.execution_time_ms}ms")
                else:
                    self.logger.warning(f"Code failed: {observation.error}")

                current_step.observation = observation
                trace.add_step(current_step)

                # passo il risultato (o il traceback) all'LLM per il turno successivo
                obs_text = observation.stdout.strip() if observation.is_success else (observation.error or observation.stderr.strip())
                if observation.is_success and observation.plot_path:
                    obs_text += f"\n[Plot saved to: {observation.plot_path}]"

                if not obs_text:
                    obs_text = "Code executed with no stdout."

                obs_prefix = "Observation:" if observation.is_success else "Observation (ERROR):"
                feedback_content = f"{obs_prefix} {obs_text}"

                messages.append({"role": "assistant", "content": llm_response})
                messages.append({"role": "user", "content": feedback_content})

        # se supera il limite di tentativi mi fermo
        self.logger.warning(f"Reached max iterations limit ({self.max_iterations}).")
        elapsed = time.perf_counter() - start_time
        return AnalysisResult(
            status="error",
            query=query,
            dataset_path=str(dataset_path),
            final_answer=f"Reached maximum number of iterations ({self.max_iterations}) without reaching a final answer.",
            plot_path=last_plot_path,
            trace=trace,
            total_steps=self.max_iterations,
            execution_time_seconds=round(elapsed, 2),
        )
