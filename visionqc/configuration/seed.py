from __future__ import annotations
from visionqc.quality.templates import sausage_mixing_commercial_template

def sausage_batter_template():
    """Backward-compatible alias for the VisionQC 4 commercial template."""
    return sausage_mixing_commercial_template()
