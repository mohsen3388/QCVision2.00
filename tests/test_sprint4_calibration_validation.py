from pathlib import Path

from visionqc.configuration.models import InspectionTemplate, MetricDefinition
from visionqc.quality.validation.models import CalibrationSample
from visionqc.quality.validation.service import ValidationService


class FakeRepository:
    def __init__(self, samples): self.samples=samples; self.saved=None
    def list_samples(self, key): return self.samples
    def save_validation(self, summary): self.saved=summary; return 17


class FakeRuntime:
    def dry_run(self, path, template):
        score=float(Path(path).stem.split('_')[-1])
        return {
            'final_score':score,'product_health':score,'process_health':90,
            'metrics':[{'key':'product.texture','score':score,'status':'OK'}]
        }


def sample(index, label, score):
    return CalibrationSample(index,'tpl.test',f'/tmp/sample_{score}.jpg',label)


def test_validation_metrics_and_gate(monkeypatch):
    samples=[
        sample(1,'سالم',95), sample(2,'سالم',92),
        sample(3,'انحراف جزئی',85), sample(4,'انحراف جزئی',82),
        sample(5,'هشدار متوسط',75), sample(6,'هشدار متوسط',72),
        sample(7,'هشدار سطح بالا',60), sample(8,'هشدار سطح بالا',55),
        sample(9,'بحرانی',40), sample(10,'بحرانی',25),
    ]
    monkeypatch.setattr(Path,'exists',lambda self: True)
    repo=FakeRepository(samples)
    service=ValidationService(FakeRuntime(),repo)
    template=InspectionTemplate('tpl.test','Test',version='1.0',metrics=[MetricDefinition('product.texture','بافت','fake')])
    result=service.validate(template,minimum_samples=10,minimum_per_class=2,minimum_accuracy=.9,maximum_false_negative_rate=.1)
    assert result.run_id==17
    assert result.accuracy==1.0
    assert result.false_negative_rate==0.0
    assert result.production_ready is True
    assert result.metric_results[0].quality=='خوب'
    assert result.confusion_matrix['سالم']['سالم']==2


def test_gate_blocks_missing_classes(monkeypatch):
    monkeypatch.setattr(Path,'exists',lambda self: True)
    samples=[sample(1,'سالم',95),sample(2,'هشدار سطح بالا',60)]
    result=ValidationService(FakeRuntime(),FakeRepository(samples)).validate(
        InspectionTemplate('tpl.test','Test',metrics=[MetricDefinition('product.texture','بافت','fake')]),
        minimum_samples=2,minimum_per_class=1,minimum_accuracy=.5,maximum_false_negative_rate=.5,
    )
    assert result.production_ready is False
    assert any('نمونه ناکافی' in x for x in result.gate_reasons)
