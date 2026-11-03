from __future__ import annotations

from visionqc.application.services.factory_learning_service import FactoryLearningService
from visionqc.domain.factory_memory import CorrectiveAction, DefectObservation, FactoryMemoryCase, ProductionContext


class MemoryStub:
    def __init__(self, cases): self.cases=cases
    def list_recent(self, limit=100, product_name=None):
        rows=self.cases
        if product_name: rows=[c for c in rows if c.product_name==product_name]
        return rows[:limit]
    def get(self, case_id): return self.cases[case_id-1] if 0<case_id<=len(self.cases) else None
    def find_similar(self, current, limit=5, minimum_similarity=.25):
        from visionqc.domain.factory_memory import SimilarMemoryCase
        return [SimilarMemoryCase(c,.8,("same product",)) for c in self.cases if c is not current]


def case(*, passed=False, cause="", machine="M1", shift="A", defect="Texture", action_result="Effective"):
    return FactoryMemoryCase(
        product_name="Sausage", passed=passed, qc_approved=bool(cause), confirmed_cause=cause,
        production=ProductionContext(machine_name=machine, shift_name=shift, batch_code="B1"),
        defects=[] if passed else [DefectObservation(defect_type=defect)],
        corrective_actions=[] if not cause else [CorrectiveAction(action_type="Check temperature",description="Measure batter temperature",status=action_result,result=action_result)],
    )


def test_summary_computes_learning_kpis():
    service=FactoryLearningService(MemoryStub([
        case(cause="High temperature"), case(cause="High temperature", machine="M2"),
        case(cause="Low vacuum", action_result="Ineffective"), case(passed=True),
    ]))
    summary=service.summarize()
    assert summary.total_cases==4
    assert summary.verified_cases==3
    assert summary.top_causes[0].label=="High temperature"
    assert summary.action_effectiveness_rate==66.7
    assert summary.recurrence_rate>0


def test_recommendations_use_verified_similar_cases():
    cases=[case(), case(cause="High temperature"), case(cause="High temperature")]
    service=FactoryLearningService(MemoryStub(cases))
    rows=service.recommend_actions(1)
    assert rows
    assert rows[0].action_type=="Check temperature"
    assert rows[0].support_count==2
    assert rows[0].effectiveness_rate==100.0
