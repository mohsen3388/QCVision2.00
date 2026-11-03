from pathlib import Path

def test_default_settings_have_required_paths():
    from visionqc.core.settings import default_settings
    values=default_settings()
    assert "data_directory" in values
    assert "reports_directory" in values
    assert values["camera_index"] == 0
