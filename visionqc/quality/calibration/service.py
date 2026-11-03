from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import copy
import numpy as np
from visionqc.configuration.runtime import ConfigurationRuntime
from visionqc.configuration.models import InspectionTemplate

@dataclass(slots=True)
class CalibrationRecommendation:
    metric_key: str
    healthy_median: float
    defective_median: float
    suggested_threshold: float
    separation: float
    quality: str

class CalibrationService:
    """Suggests trigger thresholds from labelled healthy/defective media.

    It never publishes automatically; a QC specialist must review the result.
    """
    def __init__(self, runtime: ConfigurationRuntime|None=None):
        self.runtime=runtime or ConfigurationRuntime()
    def _scores(self,paths,template):
        out={m.key:[] for m in template.metrics}
        for path in paths:
            result=self.runtime.dry_run(str(path),template)
            for m in result["metrics"]: out.setdefault(m["key"],[]).append(float(m["score"]))
        return out
    def recommend(self,healthy_paths,defective_paths,template:InspectionTemplate):
        if not healthy_paths or not defective_paths: raise ValueError("برای کالیبراسیون حداقل یک نمونه سالم و یک نمونه معیوب لازم است.")
        healthy=self._scores(healthy_paths,template); defective=self._scores(defective_paths,template); recs=[]
        for metric in template.metrics:
            h=healthy.get(metric.key,[]); d=defective.get(metric.key,[])
            if not h or not d: continue
            hm=float(np.median(h)); dm=float(np.median(d)); threshold=(hm+dm)/2.0; separation=abs(hm-dm)
            quality="خوب" if separation>=20 else "متوسط" if separation>=10 else "ضعیف"
            recs.append(CalibrationRecommendation(metric.key,round(hm,2),round(dm,2),round(threshold,2),round(separation,2),quality))
        return recs
