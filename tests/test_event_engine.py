from visionqc.core.database import initialize_database
from visionqc.core.event_engine import ProcessEvent,record_event,list_events,acknowledge_event,events_to_timeline

def test_event_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("VISIONQC_DATA_DIRECTORY", str(tmp_path))
    initialize_database()
    event_id=record_event(ProcessEvent(event_type="QUALITY_WARNING",severity="Warning",source="Rule Engine",message="Texture dropped",details={"metric":"texture_uniformity","value":51}))
    events=list_events(severity="Warning")
    assert events[0].event_id==event_id and events[0].details["value"]==51
    acknowledge_event(event_id,"Operator A")
    event=list_events()[0]
    assert event.acknowledged and event.acknowledged_by=="Operator A"
    timeline=events_to_timeline([event])
    assert timeline[0]["type"]=="QUALITY_WARNING"
