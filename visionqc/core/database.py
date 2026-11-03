from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from visionqc.core.settings import load_settings


def database_path() -> Path:
    settings = load_settings()
    return Path(settings["data_directory"]) / "visionqc.db"


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_code TEXT NOT NULL UNIQUE,
                product_name TEXT NOT NULL,
                production_line TEXT,
                operator_name TEXT,
                process_stage TEXT,
                status TEXT NOT NULL DEFAULT 'Open',
                qc_outcome TEXT,
                notes TEXT,
                started_at TEXT NOT NULL,
                ended_at TEXT
            );
            CREATE TABLE IF NOT EXISTS batch_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(batch_id) REFERENCES batches(id)
            );
            CREATE TABLE IF NOT EXISTS custom_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                join_mode TEXT NOT NULL DEFAULT 'AND',
                severity TEXT NOT NULL DEFAULT 'Warning',
                message TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                product_name TEXT,
                process_stage TEXT,
                conditions_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS assistant_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                context_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(batch_id) REFERENCES batches(id)
            );
            CREATE TABLE IF NOT EXISTS process_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'Information',
                source TEXT NOT NULL DEFAULT 'VisionQC',
                message TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                acknowledged INTEGER NOT NULL DEFAULT 0,
                acknowledged_by TEXT,
                acknowledged_at TEXT,
                FOREIGN KEY(batch_id) REFERENCES batches(id)
            );
            CREATE TABLE IF NOT EXISTS generated_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL,
                report_code TEXT NOT NULL UNIQUE,
                file_path TEXT NOT NULL,
                qr_payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(batch_id) REFERENCES batches(id)
            );
            CREATE TABLE IF NOT EXISTS evidence_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL,
                evidence_type TEXT NOT NULL DEFAULT 'Document',
                file_path TEXT NOT NULL,
                caption TEXT,
                captured_at TEXT NOT NULL,
                FOREIGN KEY(batch_id) REFERENCES batches(id)
            );
            CREATE TABLE IF NOT EXISTS quality_measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER,
                metric_name TEXT NOT NULL,
                metric_group TEXT NOT NULL DEFAULT 'Quality',
                value REAL NOT NULL,
                unit TEXT NOT NULL DEFAULT '',
                product_name TEXT,
                production_line TEXT,
                operator_name TEXT,
                target REAL,
                lsl REAL,
                usl REAL,
                captured_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'Manual',
                notes TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(batch_id) REFERENCES batches(id)
            );
            CREATE INDEX IF NOT EXISTS idx_quality_measurements_metric_time ON quality_measurements(metric_name,captured_at);
            CREATE TABLE IF NOT EXISTS production_shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                planned_break_minutes INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS production_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER,
                shift_id INTEGER NOT NULL,
                production_line TEXT NOT NULL,
                product_name TEXT NOT NULL,
                operator_name TEXT,
                planned_minutes REAL NOT NULL,
                ideal_cycle_seconds REAL NOT NULL,
                total_units INTEGER NOT NULL DEFAULT 0,
                good_units INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Open',
                started_at TEXT NOT NULL,
                ended_at TEXT,
                notes TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(batch_id) REFERENCES batches(id),
                FOREIGN KEY(shift_id) REFERENCES production_shifts(id)
            );
            CREATE TABLE IF NOT EXISTS downtime_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Unplanned',
                duration_minutes REAL NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES production_runs(id)
            );
            CREATE INDEX IF NOT EXISTS idx_production_runs_shift ON production_runs(shift_id,started_at);
            CREATE INDEX IF NOT EXISTS idx_downtime_run ON downtime_events(run_id);
            CREATE TABLE IF NOT EXISTS metric_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, metric_name TEXT NOT NULL UNIQUE, metric_group TEXT NOT NULL DEFAULT 'Quality',
                unit TEXT NOT NULL DEFAULT '', target REAL, lsl REAL, usl REAL, enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS analysis_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT, source_path TEXT NOT NULL, batch_id INTEGER, imported_metrics INTEGER NOT NULL,
                skipped_metrics INTEGER NOT NULL, generated_events INTEGER NOT NULL, summary_json TEXT NOT NULL, imported_at TEXT NOT NULL,
                FOREIGN KEY(batch_id) REFERENCES batches(id)
            );
            CREATE INDEX IF NOT EXISTS idx_analysis_imports_time ON analysis_imports(imported_at);
            CREATE TABLE IF NOT EXISTS sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL, operation TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'Pending', created_at TEXT NOT NULL, exported_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue(status,created_at);
            CREATE TABLE IF NOT EXISTS sync_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, direction TEXT NOT NULL, file_path TEXT NOT NULL, site_id TEXT, item_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sync_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, remote_token TEXT NOT NULL UNIQUE, source_site TEXT, entity_type TEXT, entity_id INTEGER, received_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inspection_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project_uuid TEXT NOT NULL UNIQUE, name TEXT NOT NULL, product_name TEXT, version TEXT NOT NULL DEFAULT '1.0', camera_name TEXT, resolution TEXT, author TEXT, notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inspection_pipeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL UNIQUE, pipeline_json TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(project_id) REFERENCES inspection_projects(id)
            );
            CREATE TABLE IF NOT EXISTS inspection_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, node_order INTEGER NOT NULL, node_type TEXT NOT NULL, params_json TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, FOREIGN KEY(project_id) REFERENCES inspection_projects(id)
            );
            CREATE TABLE IF NOT EXISTS roi_library (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, name TEXT NOT NULL, shape TEXT NOT NULL, points_json TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, description TEXT, created_at TEXT NOT NULL, FOREIGN KEY(project_id) REFERENCES inspection_projects(id)
            );
            CREATE TABLE IF NOT EXISTS inspection_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, file_path TEXT NOT NULL, file_name TEXT NOT NULL, imported_at TEXT NOT NULL, UNIQUE(project_id,file_path), FOREIGN KEY(project_id) REFERENCES inspection_projects(id)
            );
            CREATE TABLE IF NOT EXISTS inspection_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, image_path TEXT NOT NULL, passed INTEGER NOT NULL, measurements_json TEXT NOT NULL, reasons_json TEXT NOT NULL, processing_ms REAL NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(project_id) REFERENCES inspection_projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_inspection_results_project_time ON inspection_results(project_id,created_at);
            CREATE TABLE IF NOT EXISTS factory_memory_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_uuid TEXT NOT NULL UNIQUE,
                inspection_id INTEGER, project_id INTEGER, product_name TEXT NOT NULL,
                passed INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'Open',
                batch_code TEXT, production_line TEXT, shift_name TEXT, operator_name TEXT, machine_name TEXT,
                recipe_name TEXT, supplier_name TEXT, process_stage TEXT, sku TEXT, lot_code TEXT,
                process_json TEXT NOT NULL DEFAULT '{}', measurements_json TEXT NOT NULL DEFAULT '{}',
                suspected_causes_json TEXT NOT NULL DEFAULT '[]', confirmed_cause TEXT NOT NULL DEFAULT '',
                operator_notes TEXT NOT NULL DEFAULT '', qc_notes TEXT NOT NULL DEFAULT '',
                qc_approved INTEGER NOT NULL DEFAULT 0, qc_approved_by TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]', metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY(inspection_id) REFERENCES inspection_results(id),
                FOREIGN KEY(project_id) REFERENCES inspection_projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_factory_memory_product_time ON factory_memory_cases(product_name,created_at);
            CREATE INDEX IF NOT EXISTS idx_factory_memory_batch ON factory_memory_cases(batch_code);
            CREATE INDEX IF NOT EXISTS idx_factory_memory_machine ON factory_memory_cases(machine_name,created_at);
            CREATE TABLE IF NOT EXISTS factory_memory_defects (
                id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER NOT NULL, defect_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'Warning', confidence REAL, location TEXT, measurement REAL, unit TEXT, description TEXT,
                FOREIGN KEY(case_id) REFERENCES factory_memory_cases(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_factory_memory_defect_type ON factory_memory_defects(defect_type,case_id);
            CREATE TABLE IF NOT EXISTS factory_memory_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER NOT NULL, evidence_type TEXT NOT NULL,
                file_path TEXT NOT NULL, caption TEXT, sha256 TEXT,
                FOREIGN KEY(case_id) REFERENCES factory_memory_cases(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS factory_memory_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER NOT NULL, action_type TEXT NOT NULL,
                description TEXT NOT NULL, owner TEXT, status TEXT NOT NULL DEFAULT 'Proposed', result TEXT,
                performed_at TEXT, verified_by TEXT, verified_at TEXT,
                FOREIGN KEY(case_id) REFERENCES factory_memory_cases(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS voice_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_uuid TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                factory_name TEXT,
                operator_name TEXT,
                selected_case_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(selected_case_id) REFERENCES factory_memory_cases(id)
            );
            CREATE INDEX IF NOT EXISTS idx_voice_conversations_updated ON voice_conversations(updated_at);
            CREATE TABLE IF NOT EXISTS voice_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                message_uuid TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                intent TEXT NOT NULL DEFAULT 'unknown',
                confidence REAL NOT NULL DEFAULT 1.0,
                source TEXT NOT NULL DEFAULT 'typed',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES voice_conversations(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_voice_messages_conversation ON voice_messages(conversation_id,id);
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Process Note',
                product_name TEXT,
                process_stage TEXT,
                metric_group TEXT,
                metric_name TEXT,
                lower_bound REAL,
                upper_bound REAL,
                recommendation TEXT,
                confidence REAL NOT NULL DEFAULT 100,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_batch(batch_code: str, product_name: str, production_line: str, operator_name: str, process_stage: str, notes: str = "") -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO batches(batch_code,product_name,production_line,operator_name,process_stage,notes,started_at) VALUES(?,?,?,?,?,?,?)",
            (batch_code, product_name, production_line, operator_name, process_stage, notes, utc_now()),
        )
        batch_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO batch_events(batch_id,event_type,message,created_at) VALUES(?,?,?,?)",
            (batch_id, "BATCH_STARTED", "Batch workspace created.", utc_now()),
        )
        return batch_id


def update_batch(batch_id: int, process_stage: str, notes: str, status: str | None = None, qc_outcome: str | None = None) -> None:
    fields = ["process_stage=?", "notes=?"]
    params: list[object] = [process_stage, notes]
    if status is not None:
        fields.append("status=?"); params.append(status)
    if qc_outcome is not None:
        fields.append("qc_outcome=?"); params.append(qc_outcome)
    if status == "Finished":
        fields.append("ended_at=?"); params.append(utc_now())
    params.append(batch_id)
    with connect() as conn:
        conn.execute(f"UPDATE batches SET {', '.join(fields)} WHERE id=?", params)


def add_batch_event(batch_id: int, event_type: str, message: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO batch_events(batch_id,event_type,message,created_at) VALUES(?,?,?,?)",
            (batch_id, event_type, message, utc_now()),
        )


def list_batches(limit: int = 100) -> list[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute("SELECT * FROM batches ORDER BY id DESC LIMIT ?", (limit,)))


def list_batch_events(batch_id: int) -> list[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute("SELECT * FROM batch_events WHERE batch_id=? ORDER BY id DESC", (batch_id,)))
