from __future__ import annotations

import json
from datetime import datetime, timezone

from visionqc.analysis.custom_rules import CustomRule, RuleCondition
from visionqc.core.database import connect


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_rule(rule: CustomRule) -> int:
    rule.validate()
    payload = json.dumps([condition.__dict__ if hasattr(condition, "__dict__") else {
        "metric_group": condition.metric_group,
        "metric_name": condition.metric_name,
        "operator": condition.operator,
        "value": condition.value,
        "second_value": condition.second_value,
    } for condition in rule.conditions])
    with connect() as conn:
        if rule.rule_id is None:
            cur = conn.execute(
                """INSERT INTO custom_rules(name,join_mode,severity,message,recommendation,enabled,product_name,process_stage,conditions_json,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (rule.name, rule.join_mode, rule.severity, rule.message, rule.recommendation, int(rule.enabled), rule.product_name, rule.process_stage, payload, utc_now(), utc_now()),
            )
            return int(cur.lastrowid)
        conn.execute(
            """UPDATE custom_rules SET name=?,join_mode=?,severity=?,message=?,recommendation=?,enabled=?,product_name=?,process_stage=?,conditions_json=?,updated_at=? WHERE id=?""",
            (rule.name, rule.join_mode, rule.severity, rule.message, rule.recommendation, int(rule.enabled), rule.product_name, rule.process_stage, payload, utc_now(), rule.rule_id),
        )
        return int(rule.rule_id)


def list_rules(enabled_only: bool = False) -> list[CustomRule]:
    sql = "SELECT * FROM custom_rules"
    params: tuple[object, ...] = ()
    if enabled_only:
        sql += " WHERE enabled=1"
    sql += " ORDER BY id DESC"
    with connect() as conn:
        rows = list(conn.execute(sql, params))
    result: list[CustomRule] = []
    for row in rows:
        conditions = [RuleCondition(**item) for item in json.loads(row["conditions_json"])]
        result.append(CustomRule(
            rule_id=row["id"], name=row["name"], conditions=conditions, join_mode=row["join_mode"], severity=row["severity"],
            message=row["message"], recommendation=row["recommendation"], enabled=bool(row["enabled"]),
            product_name=row["product_name"] or "", process_stage=row["process_stage"] or "",
        ))
    return result


def set_rule_enabled(rule_id: int, enabled: bool) -> None:
    with connect() as conn:
        conn.execute("UPDATE custom_rules SET enabled=?,updated_at=? WHERE id=?", (int(enabled), utc_now(), rule_id))


def delete_rule(rule_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM custom_rules WHERE id=?", (rule_id,))
