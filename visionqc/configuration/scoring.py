from __future__ import annotations
import numpy as np
from .models import ScoringRule

def score_value(raw: float, rule: ScoringRule) -> float:
    lo,hi=float(rule.raw_min),float(rule.raw_max)
    if hi <= lo: raise ValueError("raw_max must be greater than raw_min")
    if rule.mode == "higher_is_better": out=(raw-lo)/(hi-lo)*100.0
    elif rule.mode == "lower_is_better": out=(hi-raw)/(hi-lo)*100.0
    elif rule.mode == "ideal_range":
        il=rule.ideal_low if rule.ideal_low is not None else lo
        ih=rule.ideal_high if rule.ideal_high is not None else hi
        if il <= raw <= ih: out=100.0
        elif raw < il: out=100.0*(raw-lo)/max(1e-9,il-lo)
        else: out=100.0*(hi-raw)/max(1e-9,hi-ih)
    else: raise ValueError(f"Unknown scoring mode: {rule.mode}")
    return float(np.clip(out,0,100))
