from visionqc.core.database import initialize_database
from visionqc.core.knowledge_engine import KnowledgeEntry, save_entry, list_entries, find_relevant, set_entry_enabled

def test_knowledge_entry_and_metric_match(tmp_path, monkeypatch):
    monkeypatch.setenv("VISIONQC_DATA_DIRECTORY", str(tmp_path))
    initialize_database()
    entry_id=save_entry(KnowledgeEntry(title="Approved texture",content="Texture is inside the approved product window.",category="Approved Range",product_name="Product A",process_stage="Mixing",metric_group="Texture",metric_name="texture_uniformity",lower_bound=65,upper_bound=90,recommendation="Continue controlled mixing."))
    assert entry_id > 0
    found=find_relevant("Product A","Mixing",{"Texture":{"texture_uniformity":75}})
    assert len(found)==1 and found[0]["title"]=="Approved texture"
    assert find_relevant("Product A","Mixing",{"Texture":{"texture_uniformity":50}})==[]
    set_entry_enabled(entry_id,False)
    assert list_entries(True)==[]
