import os
import sys
import time
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional
import uuid
from datetime import datetime

from chiron_core.ports.sandbox_port import SandboxPort
from chiron_core.domain.models import Observation


RUNNER_SCRIPT_PATH = Path(__file__).parent / "sandbox_runner.py"


class ProcessSandboxAdapter(SandboxPort):
    def __init__(self, timeout_seconds: int = 15, output_dir: str = "output/plots"):
        self.timeout_seconds = timeout_seconds
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _cleanup_old_plots(self, max_retained: int = 5) -> None:
        # tengo solo gli ultimi N grafici sennò la cartella si intasa
        try:
            plots = sorted(self.output_dir.glob("plot_*.html"), key=lambda p: p.stat().st_mtime)
            while len(plots) > max_retained:
                oldest = plots.pop(0)
                oldest.unlink(missing_ok=True)
        except Exception:
            pass

    def execute(
        self,
        code: str,
        dataset_path: Path,
        expected_output_name: str = "plot.html",
    ) -> Observation:
        dataset_path = Path(dataset_path)
        start_time = time.perf_counter()

        with tempfile.TemporaryDirectory(prefix="sandbox_") as temp_dir_str:
            temp_dir = Path(temp_dir_str)

            # copio il dataset nella cartella temporanea così lo script lo trova locale
            if dataset_path.exists():
                shutil.copy(dataset_path, temp_dir / dataset_path.name)
                # comodo avere anche un alias data.csv fisso
                if dataset_path.name != "data.csv":
                    shutil.copy(dataset_path, temp_dir / "data.csv")

            script_file = temp_dir / "analysis_script.py"
            with open(script_file, "w", encoding="utf-8") as f:
                f.write(code)

            # pulisco le variabili di proxy per sicurezza
            clean_env = os.environ.copy()
            for proxy_var in [
                "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                "http_proxy", "https_proxy", "all_proxy"
            ]:
                clean_env.pop(proxy_var, None)

            # lancio il runner dedicato in un processo figlio separato
            cmd = [sys.executable, str(RUNNER_SCRIPT_PATH), "analysis_script.py"]

            try:
                # todo: controllare se 15s bastano per grafici pesanti
                result = subprocess.run(
                    cmd,
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    env=clean_env,
                )

                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                stdout = result.stdout
                stderr = result.stderr
                exit_code = result.returncode
                error = None

                # print(f"debug exit_code: {exit_code}")

                if exit_code != 0:
                    if exit_code == 2:
                        error = "Sandbox Security Violation: Network access is blocked."
                    else:
                        error = f"Execution failed with exit code {exit_code}."

                # verifico se è stato generato l'html del grafico
                saved_plot_path = None
                generated_html = list(temp_dir.glob("*.html"))
                if generated_html:
                    target_file = temp_dir / expected_output_name
                    if not target_file.exists():
                        target_file = generated_html[0]

                    # controllo che il file non sia vuoto
                    if target_file.stat().st_size > 0:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        unique_id = uuid.uuid4().hex[:6]
                        dest_filename = f"plot_{timestamp}_{unique_id}.html"
                        dest_path = self.output_dir / dest_filename
                        shutil.copy(target_file, dest_path)
                        saved_plot_path = str(dest_path.resolve())

                        self._cleanup_old_plots(max_retained=5)

                return Observation(
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=exit_code,
                    error=error,
                    plot_path=saved_plot_path,
                    execution_time_ms=round(elapsed_ms, 2),
                )

            except subprocess.TimeoutExpired:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return Observation(
                    stdout="",
                    stderr="Execution timed out.",
                    exit_code=-1,
                    error=f"TimeoutExpired: Execution exceeded limit of {self.timeout_seconds} seconds.",
                    plot_path=None,
                    execution_time_ms=round(elapsed_ms, 2),
                )
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return Observation(
                    stdout="",
                    stderr=str(e),
                    exit_code=1,
                    error=f"Sandbox error: {str(e)}",
                    plot_path=None,
                    execution_time_ms=round(elapsed_ms, 2),
                )
