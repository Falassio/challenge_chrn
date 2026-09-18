"""
Unit tests for ProcessSandboxAdapter.
Verifies the 4 mandatory sandbox constraints:
1. Separate process execution
2. Timeout enforcement
3. Filesystem isolation (temporary directory)
4. Network blocking (prevention of external outbound access)
Plus artifact extraction (Plotly HTML).
"""

import os
from pathlib import Path
import pytest

from chiron_core.adapters.sandbox.process_sandbox import ProcessSandboxAdapter


def test_sandbox_executes_valid_code(sample_csv_path: Path, output_dir: Path):
    """Test that valid python code executes, reads the dataset, and captures stdout."""
    sandbox = ProcessSandboxAdapter(timeout_seconds=5, output_dir=str(output_dir))
    
    code = """
import pandas as pd
df = pd.read_csv('data.csv')
print(f"ROW_COUNT:{len(df)}")
"""
    obs = sandbox.execute(code=code, dataset_path=sample_csv_path)
    
    assert obs.is_success is True
    assert obs.exit_code == 0
    assert "ROW_COUNT:5" in obs.stdout
    assert obs.error is None


def test_sandbox_timeout_enforcement(sample_csv_path: Path, output_dir: Path):
    """Test that long-running or hanging scripts are terminated when timeout expires."""
    # timeout a 1 secondo con sleep di 5 per verificare il blocco
    sandbox = ProcessSandboxAdapter(timeout_seconds=1, output_dir=str(output_dir))
    
    code = """
import time
time.sleep(5)
print("Should not reach here")
"""
    obs = sandbox.execute(code=code, dataset_path=sample_csv_path)
    
    assert obs.is_success is False
    assert obs.exit_code == -1
    assert "TimeoutExpired" in obs.error
    assert "Should not reach here" not in obs.stdout


def test_sandbox_network_blocking_socket(sample_csv_path: Path, output_dir: Path):
    """Test that low-level socket connections are denied by the sandbox."""
    sandbox = ProcessSandboxAdapter(timeout_seconds=5, output_dir=str(output_dir))
    
    code = """
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('8.8.8.8', 53))
print("CONNECTED_SHOULD_NOT_HAPPEN")
"""
    obs = sandbox.execute(code=code, dataset_path=sample_csv_path)
    
    assert obs.is_success is False
    assert obs.exit_code != 0
    assert "SecurityViolation" in obs.stderr or "PermissionError" in obs.stderr or "SecurityError" in obs.stderr
    assert "CONNECTED_SHOULD_NOT_HAPPEN" not in obs.stdout


def test_sandbox_network_blocking_urllib(sample_csv_path: Path, output_dir: Path):
    """Test that HTTP libraries like urllib are blocked from making outbound requests."""
    sandbox = ProcessSandboxAdapter(timeout_seconds=5, output_dir=str(output_dir))
    
    code = """
import urllib.request
response = urllib.request.urlopen("https://example.com", timeout=2)
print("DOWNLOADED_SHOULD_NOT_HAPPEN")
"""
    obs = sandbox.execute(code=code, dataset_path=sample_csv_path)
    
    assert obs.is_success is False
    assert obs.exit_code != 0
    assert "DOWNLOADED_SHOULD_NOT_HAPPEN" not in obs.stdout


def test_sandbox_filesystem_isolation(sample_csv_path: Path, output_dir: Path):
    """Test that files written by the script stay in the temporary dir and are cleaned up."""
    sandbox = ProcessSandboxAdapter(timeout_seconds=5, output_dir=str(output_dir))
    
    temp_marker = "ephemeral_test_file.txt"
    code = f"""
with open('{temp_marker}', 'w') as f:
    f.write('temporary content')
print("FILE_WRITTEN")
"""
    obs = sandbox.execute(code=code, dataset_path=sample_csv_path)
    
    assert obs.is_success is True
    assert "FILE_WRITTEN" in obs.stdout
    # verifico che il file non sia finito nella root
    assert not os.path.exists(temp_marker)


def test_sandbox_plotly_artifact_extraction(sample_csv_path: Path, output_dir: Path):
    """Test that generated Plotly HTML files are detected and saved to the output directory."""
    sandbox = ProcessSandboxAdapter(timeout_seconds=10, output_dir=str(output_dir))
    
    code = """
import pandas as pd
import plotly.express as px

df = pd.read_csv('data.csv')
fig = px.bar(df, x='category', y='revenue', title='Test Plot')
fig.write_html('plot.html', include_plotlyjs='cdn')
print("PLOT_DONE")
"""
    obs = sandbox.execute(code=code, dataset_path=sample_csv_path)

    assert obs.is_success is True
    assert obs.plot_path is not None
    assert Path(obs.plot_path).exists()
    assert Path(obs.plot_path).stat().st_size > 0
    assert obs.plot_path.endswith(".html")

    # controllo qualità del grafico
    from chiron_core.engine.quality_evaluator import PlotQualityEvaluator
    quality = PlotQualityEvaluator.evaluate(obs.plot_path)
    assert quality["passed"] is True
    assert quality["score"] == 1.0
