from __future__ import annotations

import json
from dataclasses import asdict
from typing import Iterable

from visionqc.analysis.golden import GoldenComparison, MetricReference
from visionqc.core.database import connect, utc_now
from visionqc.models.results import AnalysisResult


def initialize_golden_tables() -> None:
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS golden_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            product_name TEXT NOT NULL,
            process_stage TEXT NOT NULL,
            production_line TEXT,
            description TEXT,
            sample_count INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS golden_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            metric_group TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            mean_value REAL NOT NULL,
            std_value REAL NOT NULL,
            tolerance REAL NOT NULL,
            weight REAL NOT NULL,
            UNIQUE(profile_id, metric_group, metric_name),
            FOREIGN KEY(profile_id) REFERENCES golden_profiles(id)
        );
        CREATE TABLE IF NOT EXISTS golden_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            source_path TEXT,
            health_score REAL,
            confidence REAL,
            analysis_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(profile_id) REFERENCES golden_profiles(id)
        );
        CREATE TABLE IF NOT EXISTS golden_comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            batch_id INTEGER,
            source_path TEXT,
            similarity_score REAL NOT NULL,
            confidence REAL NOT NULL,
            status TEXT NOT NULL,
            comparison_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(profile_id) REFERENCES golden_profiles(id),
            FOREIGN KEY(batch_id) REFERENCES batches(id)
        );
        """)


def create_profile(name: str, product_name: str, process_stage: str, production_line: str,
                   description: str, references: Iterable[MetricReference], samples: Iterable[AnalysisResult]) -> int:
    initialize_golden_tables()
    references = list(references); samples = list(samples); now = utc_now()
    with connect() as conn:
        cur = conn.execute("""INSERT INTO golden_profiles
            (name,product_name,process_stage,production_line,description,sample_count,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (name, product_name, process_stage, production_line, description, len(samples), now, now))
        profile_id = int(cur.lastrowid)
        conn.executemany("""INSERT INTO golden_metrics
            (profile_id,metric_group,metric_name,mean_value,std_value,tolerance,weight)
            VALUES(?,?,?,?,?,?,?)""",
            [(profile_id, r.group, r.metric, r.mean, r.std, r.tolerance, r.weight) for r in references])
        conn.executemany("""INSERT INTO golden_samples
            (profile_id,source_path,health_score,confidence,analysis_json,created_at)
            VALUES(?,?,?,?,?,?)""",
            [(profile_id, s.source_path, s.visual_health_score, s.analysis_confidence,
              json.dumps(s.to_dict(), ensure_ascii=False), now) for s in samples])
        return profile_id


def list_profiles(active_only: bool = True):
    initialize_golden_tables()
    sql = "SELECT * FROM golden_profiles"
    params = ()
    if active_only:
        sql += " WHERE active=1"
    sql += " ORDER BY updated_at DESC"
    with connect() as conn:
        return list(conn.execute(sql, params))


def get_profile(profile_id: int):
    initialize_golden_tables()
    with connect() as conn:
        return conn.execute("SELECT * FROM golden_profiles WHERE id=?", (profile_id,)).fetchone()


def get_references(profile_id: int) -> list[MetricReference]:
    initialize_golden_tables()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM golden_metrics WHERE profile_id=? ORDER BY metric_group,metric_name", (profile_id,)).fetchall()
    return [MetricReference(r["metric_group"], r["metric_name"], r["mean_value"], r["std_value"], r["tolerance"], r["weight"]) for r in rows]


def save_comparison(comparison: GoldenComparison, source_path: str, batch_id: int | None = None) -> int:
    initialize_golden_tables()
    with connect() as conn:
        cur = conn.execute("""INSERT INTO golden_comparisons
            (profile_id,batch_id,source_path,similarity_score,confidence,status,comparison_json,created_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (comparison.profile_id, batch_id, source_path, comparison.similarity_score,
             comparison.confidence, comparison.status,
             json.dumps(comparison.to_dict(), ensure_ascii=False), utc_now()))
        return int(cur.lastrowid)


def list_comparisons(limit: int = 100):
    initialize_golden_tables()
    with connect() as conn:
        return list(conn.execute("""SELECT c.*, p.name AS profile_name, b.batch_code AS batch_code
            FROM golden_comparisons c JOIN golden_profiles p ON p.id=c.profile_id
            LEFT JOIN batches b ON b.id=c.batch_id ORDER BY c.id DESC LIMIT ?""", (limit,)))


def deactivate_profile(profile_id: int) -> None:
    initialize_golden_tables()
    with connect() as conn:
        conn.execute("UPDATE golden_profiles SET active=0,updated_at=? WHERE id=?", (utc_now(), profile_id))
