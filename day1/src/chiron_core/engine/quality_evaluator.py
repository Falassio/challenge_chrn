from pathlib import Path
from typing import Dict, Any, List


class PlotQualityEvaluator:
    # controlli base sull'html generato da plotly

    @staticmethod
    def evaluate(plot_path: str) -> Dict[str, Any]:
        path = Path(plot_path)
        if not path.exists():
            return {
                "passed": False,
                "score": 0.0,
                "checks": [{"name": "file_exists", "passed": False, "detail": "Plot file was not created."}]
            }

        checks: List[Dict[str, Any]] = []

        # 1. controllo dimensione minima (> 1 KB)
        file_size = path.stat().st_size
        checks.append({
            "name": "non_empty_content",
            "passed": file_size > 1024,
            "detail": f"File size is {file_size} bytes."
        })

        # 2. verifico la presenza dei tag html e di plotly
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            return {
                "passed": False,
                "score": 0.0,
                "checks": [{"name": "file_readable", "passed": False, "detail": str(e)}]
            }

        has_html = "<html>" in content.lower() or "<!doctype html>" in content.lower()
        checks.append({
            "name": "valid_html_structure",
            "passed": has_html,
            "detail": "Contains HTML tags."
        })

        has_plotly_js = "plotly" in content.lower()
        checks.append({
            "name": "plotly_library_present",
            "passed": has_plotly_js,
            "detail": "Contains Plotly script/CDN reference."
        })

        has_plot_render = "plotly-graph-div" in content or "Plotly.newPlot" in content
        checks.append({
            "name": "interactive_plot_rendered",
            "passed": has_plot_render,
            "detail": "Contains Plotly div or render call."
        })

        passed_count = sum(1 for c in checks if c["passed"])
        score = round(passed_count / len(checks), 2)
        overall_passed = score >= 0.75

        return {
            "passed": overall_passed,
            "score": score,
            "checks": checks
        }
