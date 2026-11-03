import cv2
import numpy as np
import pytest

from visionqc.core import database
from visionqc.core.inspection import PipelineNode, ROI, batch_test, create_project, execute_pipeline, export_pipeline, import_images, list_rois, load_pipeline, save_pipeline, save_roi

@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database,'database_path',lambda:tmp_path/'test.db'); database.initialize_database(); return tmp_path

def test_project_pipeline_and_roi(db,tmp_path):
    pid=create_project('Bottle Cap','Cap')
    nodes=[PipelineNode('gray',{}),PipelineNode('threshold',{'value':100}),PipelineNode('contours',{'min_area':10}),PipelineNode('measure',{})]
    save_pipeline(pid,nodes); assert [n.node_type for n in load_pipeline(pid)]==['gray','threshold','contours','measure']
    save_roi(pid,ROI('main','rectangle',[[0,0],[100,100]])); assert list_rois(pid)[0]['shape']=='rectangle'

def test_pipeline_measurement_and_decision():
    image=np.zeros((200,200,3),dtype=np.uint8); cv2.circle(image,(100,100),40,(255,255,255),-1)
    nodes=[PipelineNode('gray',{}),PipelineNode('threshold',{'value':127}),PipelineNode('contours',{'min_area':20}),PipelineNode('measure',{}),PipelineNode('decision',{'rules':[{'metric':'area','operator':'>','value':1000,'fail_when':True}]})]
    result=execute_pipeline(image,nodes); assert result.measurements['area']>1000; assert result.passed is False; assert result.reasons

def test_batch_and_export(db,tmp_path):
    pid=create_project('Batch Test'); save_pipeline(pid,[PipelineNode('gray',{}),PipelineNode('measure',{})])
    paths=[]
    for i in range(2):
        p=tmp_path/f'{i}.png'; cv2.imwrite(str(p),np.full((20,20,3),i*100,dtype=np.uint8)); paths.append(str(p))
    assert len(import_images(pid,tmp_path))==2
    summary=batch_test(pid,paths); assert summary['total']==2 and summary['passed']==2
    out=tmp_path/'x.vqpipeline'; export_pipeline(pid,out); assert out.exists() and 'VisionQC Pipeline' in out.read_text()
