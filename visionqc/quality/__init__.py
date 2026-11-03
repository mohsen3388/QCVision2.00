"""VisionQC 4 commercial quality domain."""

def sausage_mixing_commercial_template():
    from .templates import sausage_mixing_commercial_template as _f
    return _f()

def build_management_summary(result):
    from .reporting.management import build_management_summary as _f
    return _f(result)

__all__=["sausage_mixing_commercial_template","build_management_summary"]
