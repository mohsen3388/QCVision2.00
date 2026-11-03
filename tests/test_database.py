from __future__ import annotations

import tempfile
from pathlib import Path


def test_batch_lifecycle(monkeypatch):
    from visionqc.core import settings
    temp = tempfile.TemporaryDirectory()
    values = settings.default_settings(); values["data_directory"] = temp.name; values["reports_directory"] = temp.name; values["first_run_complete"] = True
    monkeypatch.setattr(settings, "load_settings", lambda: values)
    import visionqc.core.database as database
    monkeypatch.setattr(database, "load_settings", lambda: values)
    database.initialize_database()
    batch_id = database.create_batch("TEST-001", "Test Product", "Line 1", "Tester", "Mixing")
    database.update_batch(batch_id, "Finished", "done", "Finished", "Accepted")
    rows = database.list_batches()
    assert rows[0]["batch_code"] == "TEST-001"
    assert rows[0]["qc_outcome"] == "Accepted"
    temp.cleanup()
