from abc import ABC, abstractmethod
from pathlib import Path
from chiron_core.domain.models import Observation


class SandboxPort(ABC):
    @abstractmethod
    def execute(
        self,
        code: str,
        dataset_path: Path,
        expected_output_name: str = "plot.html",
    ) -> Observation:
        pass
