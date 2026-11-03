from pathlib import Path

from visionqc.analysis.custom_rules import CustomRule, RuleCondition
from visionqc.core import database
from visionqc.core.rule_repository import list_rules, save_rule, set_rule_enabled


def test_rule_persistence(tmp_path, monkeypatch):
    db = tmp_path / "rules.db"
    monkeypatch.setattr(database, "database_path", lambda: db)
    database.initialize_database()
    from visionqc.core import rule_repository
    monkeypatch.setattr(rule_repository, "connect", database.connect)
    rule_id = save_rule(CustomRule("High reflection", [RuleCondition("Surface", "specular_reflection_percent", ">", 8)]))
    rules = list_rules()
    assert rules[0].rule_id == rule_id
    set_rule_enabled(rule_id, False)
    assert list_rules()[0].enabled is False
