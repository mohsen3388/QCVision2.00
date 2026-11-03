from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from visionqc.core.database import connect, utc_now

@dataclass(slots=True)
class KnowledgeEntry:
    title: str
    content: str
    category: str = "Process Note"
    product_name: str = ""
    process_stage: str = ""
    metric_group: str = ""
    metric_name: str = ""
    lower_bound: float | None = None
    upper_bound: float | None = None
    recommendation: str = ""
    confidence: float = 100.0
    enabled: bool = True
    entry_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


def save_entry(entry: KnowledgeEntry) -> int:
    if not entry.title.strip() or not entry.content.strip():
        raise ValueError("Title and content are required.")
    now = utc_now()
    with connect() as conn:
        if entry.entry_id:
            conn.execute("""UPDATE knowledge_entries SET title=?,content=?,category=?,product_name=?,process_stage=?,metric_group=?,metric_name=?,lower_bound=?,upper_bound=?,recommendation=?,confidence=?,enabled=?,updated_at=? WHERE id=?""",
                (entry.title, entry.content, entry.category, entry.product_name, entry.process_stage, entry.metric_group, entry.metric_name, entry.lower_bound, entry.upper_bound, entry.recommendation, entry.confidence, int(entry.enabled), now, entry.entry_id))
            return entry.entry_id
        cur = conn.execute("""INSERT INTO knowledge_entries(title,content,category,product_name,process_stage,metric_group,metric_name,lower_bound,upper_bound,recommendation,confidence,enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (entry.title, entry.content, entry.category, entry.product_name, entry.process_stage, entry.metric_group, entry.metric_name, entry.lower_bound, entry.upper_bound, entry.recommendation, entry.confidence, int(entry.enabled), now, now))
        return int(cur.lastrowid)


def list_entries(enabled_only: bool = False) -> list[KnowledgeEntry]:
    where = " WHERE enabled=1" if enabled_only else ""
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM knowledge_entries{where} ORDER BY id DESC").fetchall()
    return [KnowledgeEntry(entry_id=r["id"], title=r["title"], content=r["content"], category=r["category"], product_name=r["product_name"] or "", process_stage=r["process_stage"] or "", metric_group=r["metric_group"] or "", metric_name=r["metric_name"] or "", lower_bound=r["lower_bound"], upper_bound=r["upper_bound"], recommendation=r["recommendation"] or "", confidence=float(r["confidence"]), enabled=bool(r["enabled"]), created_at=r["created_at"], updated_at=r["updated_at"]) for r in rows]


def delete_entry(entry_id: int) -> None:
    with connect() as conn: conn.execute("DELETE FROM knowledge_entries WHERE id=?", (entry_id,))


def set_entry_enabled(entry_id: int, enabled: bool) -> None:
    with connect() as conn: conn.execute("UPDATE knowledge_entries SET enabled=?, updated_at=? WHERE id=?", (int(enabled), utc_now(), entry_id))


def find_relevant(product_name: str = "", process_stage: str = "", metrics: dict[str, dict[str, float]] | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    metrics = metrics or {}
    for entry in list_entries(True):
        if entry.product_name and entry.product_name.casefold() != product_name.casefold(): continue
        if entry.process_stage and entry.process_stage.casefold() != process_stage.casefold(): continue
        matched = True; reason = "Context match"
        if entry.metric_group and entry.metric_name:
            value = metrics.get(entry.metric_group, {}).get(entry.metric_name)
            if value is None: matched = False
            else:
                low_ok = entry.lower_bound is None or float(value) >= entry.lower_bound
                high_ok = entry.upper_bound is None or float(value) <= entry.upper_bound
                matched = low_ok and high_ok
                reason = f"{entry.metric_group}.{entry.metric_name}={float(value):.2f}"
        if matched:
            results.append({"entry_id": entry.entry_id, "title": entry.title, "content": entry.content, "category": entry.category, "recommendation": entry.recommendation, "confidence": entry.confidence, "reason": reason})
    return results
