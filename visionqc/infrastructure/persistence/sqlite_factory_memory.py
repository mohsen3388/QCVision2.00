from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3

from visionqc.application.ports.factory_memory import FactoryMemoryRepository
from visionqc.core.database import connect
from visionqc.domain.factory_memory import (
    CorrectiveAction, DefectObservation, EvidenceReference, EvidenceType,
    FactoryMemoryCase, MemoryStatus, ProcessSnapshot, ProductionContext,
)


class SqliteFactoryMemoryRepository(FactoryMemoryRepository):
    """Normalized SQLite storage for durable, auditable factory memory cases."""

    def save(self, case: FactoryMemoryCase) -> int:
        payload = self._case_row(case)
        with connect() as conn:
            cur = conn.execute(
                """INSERT INTO factory_memory_cases(
                    case_uuid,inspection_id,project_id,product_name,passed,status,
                    batch_code,production_line,shift_name,operator_name,machine_name,
                    recipe_name,supplier_name,process_stage,sku,lot_code,
                    process_json,measurements_json,suspected_causes_json,confirmed_cause,
                    operator_notes,qc_notes,qc_approved,qc_approved_by,tags_json,
                    metadata_json,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                payload,
            )
            case_id = int(cur.lastrowid)
            self._replace_children(conn, case_id, case)
            return case_id

    def update(self, case_id: int, case: FactoryMemoryCase) -> None:
        payload = self._case_row(case)
        with connect() as conn:
            cur = conn.execute(
                """UPDATE factory_memory_cases SET
                    case_uuid=?,inspection_id=?,project_id=?,product_name=?,passed=?,status=?,
                    batch_code=?,production_line=?,shift_name=?,operator_name=?,machine_name=?,
                    recipe_name=?,supplier_name=?,process_stage=?,sku=?,lot_code=?,
                    process_json=?,measurements_json=?,suspected_causes_json=?,confirmed_cause=?,
                    operator_notes=?,qc_notes=?,qc_approved=?,qc_approved_by=?,tags_json=?,
                    metadata_json=?,created_at=?,updated_at=? WHERE id=?""",
                (*payload, case_id),
            )
            if cur.rowcount == 0:
                raise KeyError(f"Factory memory case {case_id} was not found")
            self._replace_children(conn, case_id, case)

    def get(self, case_id: int) -> FactoryMemoryCase | None:
        with connect() as conn:
            row = conn.execute("SELECT * FROM factory_memory_cases WHERE id=?", (case_id,)).fetchone()
            return self._hydrate(conn, row) if row else None

    def get_by_uuid(self, case_uuid: str) -> FactoryMemoryCase | None:
        with connect() as conn:
            row = conn.execute("SELECT * FROM factory_memory_cases WHERE case_uuid=?", (case_uuid,)).fetchone()
            return self._hydrate(conn, row) if row else None

    def list_recent(self, limit: int = 100, *, product_name: str | None = None) -> list[FactoryMemoryCase]:
        with connect() as conn:
            if product_name:
                rows = conn.execute(
                    "SELECT * FROM factory_memory_cases WHERE product_name=? ORDER BY created_at DESC,id DESC LIMIT ?",
                    (product_name, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM factory_memory_cases ORDER BY created_at DESC,id DESC LIMIT ?", (limit,),
                ).fetchall()
            return [self._hydrate(conn, row) for row in rows]

    @staticmethod
    def _case_row(case: FactoryMemoryCase) -> tuple:
        p = case.production
        return (
            case.case_uuid, case.inspection_id, case.project_id, case.product_name, int(case.passed), str(case.status),
            p.batch_code, p.production_line, p.shift_name, p.operator_name, p.machine_name,
            p.recipe_name, p.supplier_name, p.process_stage, p.sku, p.lot_code,
            json.dumps(asdict(case.process), ensure_ascii=False, sort_keys=True),
            json.dumps(case.measurements, ensure_ascii=False, sort_keys=True),
            json.dumps(case.suspected_causes, ensure_ascii=False), case.confirmed_cause,
            case.operator_notes, case.qc_notes, int(case.qc_approved), case.qc_approved_by,
            json.dumps(case.tags, ensure_ascii=False),
            json.dumps(case.metadata, ensure_ascii=False, sort_keys=True), case.created_at, case.updated_at,
        )

    @staticmethod
    def _replace_children(conn: sqlite3.Connection, case_id: int, case: FactoryMemoryCase) -> None:
        conn.execute("DELETE FROM factory_memory_defects WHERE case_id=?", (case_id,))
        conn.execute("DELETE FROM factory_memory_evidence WHERE case_id=?", (case_id,))
        conn.execute("DELETE FROM factory_memory_actions WHERE case_id=?", (case_id,))
        conn.executemany(
            """INSERT INTO factory_memory_defects(case_id,defect_type,severity,confidence,location,measurement,unit,description)
               VALUES(?,?,?,?,?,?,?,?)""",
            [(case_id,d.defect_type,d.severity,d.confidence,d.location,d.measurement,d.unit,d.description) for d in case.defects],
        )
        conn.executemany(
            """INSERT INTO factory_memory_evidence(case_id,evidence_type,file_path,caption,sha256)
               VALUES(?,?,?,?,?)""",
            [(case_id,str(e.evidence_type),e.file_path,e.caption,e.sha256) for e in case.evidence],
        )
        conn.executemany(
            """INSERT INTO factory_memory_actions(case_id,action_type,description,owner,status,result,performed_at,verified_by,verified_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            [(case_id,a.action_type,a.description,a.owner,a.status,a.result,a.performed_at,a.verified_by,a.verified_at) for a in case.corrective_actions],
        )

    @staticmethod
    def _hydrate(conn: sqlite3.Connection, row: sqlite3.Row) -> FactoryMemoryCase:
        case_id = int(row["id"])
        defects = [DefectObservation(
            defect_type=r["defect_type"], severity=r["severity"], confidence=r["confidence"],
            location=r["location"] or "", measurement=r["measurement"], unit=r["unit"] or "",
            description=r["description"] or "",
        ) for r in conn.execute("SELECT * FROM factory_memory_defects WHERE case_id=? ORDER BY id", (case_id,))]
        evidence = [EvidenceReference(
            file_path=r["file_path"], evidence_type=EvidenceType(r["evidence_type"]),
            caption=r["caption"] or "", sha256=r["sha256"] or "",
        ) for r in conn.execute("SELECT * FROM factory_memory_evidence WHERE case_id=? ORDER BY id", (case_id,))]
        actions = [CorrectiveAction(
            action_type=r["action_type"], description=r["description"], owner=r["owner"] or "",
            status=r["status"], result=r["result"] or "", performed_at=r["performed_at"],
            verified_by=r["verified_by"] or "", verified_at=r["verified_at"],
        ) for r in conn.execute("SELECT * FROM factory_memory_actions WHERE case_id=? ORDER BY id", (case_id,))]
        process_data = json.loads(row["process_json"] or "{}")
        return FactoryMemoryCase(
            case_uuid=row["case_uuid"], inspection_id=row["inspection_id"], project_id=row["project_id"],
            product_name=row["product_name"], passed=bool(row["passed"]), status=MemoryStatus(row["status"]),
            production=ProductionContext(
                batch_code=row["batch_code"] or "", production_line=row["production_line"] or "",
                shift_name=row["shift_name"] or "", operator_name=row["operator_name"] or "",
                machine_name=row["machine_name"] or "", recipe_name=row["recipe_name"] or "",
                supplier_name=row["supplier_name"] or "", process_stage=row["process_stage"] or "",
                sku=row["sku"] or "", lot_code=row["lot_code"] or "",
            ),
            process=ProcessSnapshot(**process_data), defects=defects,
            measurements=json.loads(row["measurements_json"] or "{}"), evidence=evidence,
            suspected_causes=json.loads(row["suspected_causes_json"] or "[]"),
            confirmed_cause=row["confirmed_cause"] or "", corrective_actions=actions,
            operator_notes=row["operator_notes"] or "", qc_notes=row["qc_notes"] or "",
            qc_approved=bool(row["qc_approved"]), qc_approved_by=row["qc_approved_by"] or "",
            tags=json.loads(row["tags_json"] or "[]"), created_at=row["created_at"], updated_at=row["updated_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )
