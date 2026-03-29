from dataclasses import dataclass, field
from pathlib import Path
from typing import Union


@dataclass
class ScanResult:
    """Represents the analysis result for a single image."""

    path: Path
    score: Union[float, str] = "N/A"
    noise_score: Union[float, str] = "N/A"
    exif: dict = field(default_factory=dict)
