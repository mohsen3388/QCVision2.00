from __future__ import annotations

import json
import math
import shutil
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from visionqc.core.database import connect, utc_now

SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
NODE_TYPES = {
    'gray', 'gaussian_blur', 'median_blur', 'threshold', 'adaptive_threshold',
    'canny', 'morph_open', 'morph_close', 'erode', 'dilate', 'contours',
    'measure', 'decision'
}

@dataclass
class ROI:
    name: str
    shape: str
    points: list[list[int]]
    enabled: bool = True
    description: str = ''

@dataclass
class PipelineNode:
    node_type: str
    params: dict[str, Any]
    enabled: bool = True

@dataclass
class InspectionResult:
    passed: bool
    measurements: dict[str, float]
    reasons: list[str]
    processing_ms: float
    overlay: np.ndarray | None = None


def create_project(name: str, product_name: str = '', author: str = '', notes: str = '', camera_name: str = '', resolution: str = '') -> int:
    if not name.strip():
        raise ValueError('Project name is required.')
    project_uuid = str(uuid.uuid4())
    now = utc_now()
    with connect() as conn:
        cur = conn.execute(
            '''INSERT INTO inspection_projects(project_uuid,name,product_name,version,camera_name,resolution,author,notes,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (project_uuid, name.strip(), product_name.strip(), '1.0', camera_name.strip(), resolution.strip(), author.strip(), notes.strip(), now, now),
        )
        return int(cur.lastrowid)


def list_projects() -> list[dict[str, Any]]:
    with connect() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM inspection_projects ORDER BY updated_at DESC, id DESC').fetchall()]


def get_project(project_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute('SELECT * FROM inspection_projects WHERE id=?', (project_id,)).fetchone()
        return dict(row) if row else None


def save_roi(project_id: int, roi: ROI) -> int:
    if roi.shape not in {'rectangle', 'circle', 'polygon'}:
        raise ValueError('Unsupported ROI shape.')
    if len(roi.points) < 2:
        raise ValueError('ROI needs at least two points.')
    with connect() as conn:
        cur = conn.execute(
            'INSERT INTO roi_library(project_id,name,shape,points_json,enabled,description,created_at) VALUES(?,?,?,?,?,?,?)',
            (project_id, roi.name.strip() or 'ROI', roi.shape, json.dumps(roi.points), int(roi.enabled), roi.description, utc_now()),
        )
        return int(cur.lastrowid)


def list_rois(project_id: int) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute('SELECT * FROM roi_library WHERE project_id=? ORDER BY id', (project_id,)).fetchall()
    result=[]
    for r in rows:
        d=dict(r); d['points']=json.loads(d.pop('points_json')); d['enabled']=bool(d['enabled']); result.append(d)
    return result


def save_pipeline(project_id: int, nodes: list[PipelineNode]) -> None:
    for n in nodes:
        if n.node_type not in NODE_TYPES:
            raise ValueError(f'Unsupported node type: {n.node_type}')
    now=utc_now()
    payload=json.dumps([asdict(n) for n in nodes], indent=2)
    with connect() as conn:
        conn.execute('DELETE FROM inspection_pipeline WHERE project_id=?', (project_id,))
        conn.execute('INSERT INTO inspection_pipeline(project_id,pipeline_json,updated_at) VALUES(?,?,?)', (project_id,payload,now))
        conn.execute('DELETE FROM inspection_nodes WHERE project_id=?', (project_id,))
        for order,n in enumerate(nodes):
            conn.execute('INSERT INTO inspection_nodes(project_id,node_order,node_type,params_json,enabled) VALUES(?,?,?,?,?)', (project_id,order,n.node_type,json.dumps(n.params),int(n.enabled)))
        conn.execute('UPDATE inspection_projects SET updated_at=? WHERE id=?', (now,project_id))


def load_pipeline(project_id: int) -> list[PipelineNode]:
    with connect() as conn:
        row=conn.execute('SELECT pipeline_json FROM inspection_pipeline WHERE project_id=?', (project_id,)).fetchone()
    if not row:
        return []
    return [PipelineNode(**x) for x in json.loads(row['pipeline_json'])]


def import_images(project_id: int, source: str | Path) -> list[str]:
    src=Path(source)
    files=[src] if src.is_file() else sorted(p for p in src.rglob('*') if p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS)
    imported=[]
    with connect() as conn:
        for p in files:
            if p.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
                continue
            conn.execute('INSERT OR IGNORE INTO inspection_images(project_id,file_path,file_name,imported_at) VALUES(?,?,?,?)', (project_id,str(p.resolve()),p.name,utc_now()))
            imported.append(str(p.resolve()))
    return imported


def list_images(project_id: int) -> list[dict[str, Any]]:
    with connect() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM inspection_images WHERE project_id=? ORDER BY id DESC',(project_id,)).fetchall()]


def _apply_roi(image: np.ndarray, roi: ROI | None) -> tuple[np.ndarray, tuple[int,int]]:
    if roi is None or not roi.enabled:
        return image.copy(), (0,0)
    pts=np.array(roi.points, dtype=np.int32)
    if roi.shape=='rectangle':
        (x1,y1),(x2,y2)=pts[0],pts[1]; x1,x2=sorted((max(0,x1),min(image.shape[1],x2))); y1,y2=sorted((max(0,y1),min(image.shape[0],y2)))
        return image[y1:y2,x1:x2].copy(), (x1,y1)
    if roi.shape=='circle':
        c=pts[0]; edge=pts[1]; radius=max(1,int(np.linalg.norm(edge-c))); x1=max(0,c[0]-radius); y1=max(0,c[1]-radius); x2=min(image.shape[1],c[0]+radius); y2=min(image.shape[0],c[1]+radius)
        crop=image[y1:y2,x1:x2].copy(); mask=np.zeros(crop.shape[:2],np.uint8); cv2.circle(mask,(int(c[0]-x1),int(c[1]-y1)),radius,255,-1); return cv2.bitwise_and(crop,crop,mask=mask),(x1,y1)
    x,y,w,h=cv2.boundingRect(pts); crop=image[y:y+h,x:x+w].copy(); mask=np.zeros((h,w),np.uint8); cv2.fillPoly(mask,[pts-[x,y]],255); return cv2.bitwise_and(crop,crop,mask=mask),(x,y)


def _measurement(gray: np.ndarray, contours: list[np.ndarray]) -> dict[str,float]:
    values={'mean_gray':float(np.mean(gray)),'stddev':float(np.std(gray)),'brightness':float(np.mean(gray)),'contrast':float(np.std(gray))}
    if contours:
        c=max(contours,key=cv2.contourArea); area=float(cv2.contourArea(c)); perimeter=float(cv2.arcLength(c,True)); x,y,w,h=cv2.boundingRect(c)
        values.update({'area':area,'perimeter':perimeter,'width':float(w),'height':float(h),'diameter':float(max(w,h)),'aspect_ratio':float(w/h) if h else 0.0,'circularity':float(4*math.pi*area/(perimeter*perimeter)) if perimeter else 0.0,'contour_count':float(len(contours))})
    else:
        values.update({'area':0.0,'perimeter':0.0,'width':0.0,'height':0.0,'diameter':0.0,'aspect_ratio':0.0,'circularity':0.0,'contour_count':0.0})
    return values


def _evaluate_rule(measurements: dict[str,float], rule: dict[str,Any]) -> tuple[bool,str]:
    metric=rule.get('metric',''); op=rule.get('operator','>'); limit=float(rule.get('value',0)); actual=float(measurements.get(metric,0))
    ok={'>':actual>limit,'>=':actual>=limit,'<':actual<limit,'<=':actual<=limit,'==':actual==limit,'!=':actual!=limit}.get(op,False)
    mode=rule.get('fail_when',True)
    failed=ok if mode else not ok
    return failed, f"{metric} {op} {limit:g}; measured {actual:.3f}"


def execute_pipeline(image: np.ndarray, nodes: list[PipelineNode], roi: ROI | None = None) -> InspectionResult:
    import time
    start=time.perf_counter(); work,offset=_apply_roi(image,roi); overlay=image.copy(); contours=[]; measurements={}; reasons=[]
    for node in nodes:
        if not node.enabled: continue
        p=node.params; t=node.node_type
        if t=='gray': work=cv2.cvtColor(work,cv2.COLOR_BGR2GRAY) if work.ndim==3 else work
        elif t=='gaussian_blur':
            k=max(1,int(p.get('kernel',5))); k += 1-k%2; work=cv2.GaussianBlur(work,(k,k),float(p.get('sigma',0)))
        elif t=='median_blur':
            k=max(3,int(p.get('kernel',5))); k += 1-k%2; work=cv2.medianBlur(work,k)
        elif t=='threshold':
            gray=cv2.cvtColor(work,cv2.COLOR_BGR2GRAY) if work.ndim==3 else work; _,work=cv2.threshold(gray,float(p.get('value',127)),255,cv2.THRESH_BINARY_INV if p.get('inverse') else cv2.THRESH_BINARY)
        elif t=='adaptive_threshold':
            gray=cv2.cvtColor(work,cv2.COLOR_BGR2GRAY) if work.ndim==3 else work; b=max(3,int(p.get('block_size',11))); b += 1-b%2; work=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,b,float(p.get('c',2)))
        elif t=='canny':
            gray=cv2.cvtColor(work,cv2.COLOR_BGR2GRAY) if work.ndim==3 else work; work=cv2.Canny(gray,float(p.get('low',50)),float(p.get('high',150)))
        elif t in {'morph_open','morph_close','erode','dilate'}:
            k=max(1,int(p.get('kernel',3))); kernel=np.ones((k,k),np.uint8); it=max(1,int(p.get('iterations',1)))
            if t=='morph_open': work=cv2.morphologyEx(work,cv2.MORPH_OPEN,kernel,iterations=it)
            elif t=='morph_close': work=cv2.morphologyEx(work,cv2.MORPH_CLOSE,kernel,iterations=it)
            elif t=='erode': work=cv2.erode(work,kernel,iterations=it)
            else: work=cv2.dilate(work,kernel,iterations=it)
        elif t=='contours':
            gray=cv2.cvtColor(work,cv2.COLOR_BGR2GRAY) if work.ndim==3 else work; contours,_=cv2.findContours(gray,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE); min_area=float(p.get('min_area',0)); contours=[c for c in contours if cv2.contourArea(c)>=min_area]
            shifted=[c+np.array([[[offset[0],offset[1]]]],dtype=np.int32) for c in contours]; cv2.drawContours(overlay,shifted,-1,(0,255,255),2)
        elif t=='measure':
            gray=cv2.cvtColor(work,cv2.COLOR_BGR2GRAY) if work.ndim==3 else work; measurements.update(_measurement(gray,contours))
        elif t=='decision':
            for rule in p.get('rules',[]):
                failed,reason=_evaluate_rule(measurements,rule)
                if failed: reasons.append(reason)
    if not measurements:
        gray=cv2.cvtColor(work,cv2.COLOR_BGR2GRAY) if work.ndim==3 else work; measurements.update(_measurement(gray,contours))
    elapsed=(time.perf_counter()-start)*1000
    return InspectionResult(not reasons,measurements,reasons,elapsed,overlay)


def run_file(project_id: int, image_path: str | Path) -> InspectionResult:
    image=cv2.imread(str(image_path))
    if image is None: raise ValueError('Image could not be read.')
    nodes=load_pipeline(project_id); rois=list_rois(project_id); roi=ROI(rois[0]['name'],rois[0]['shape'],rois[0]['points'],rois[0]['enabled'],rois[0]['description']) if rois else None
    result=execute_pipeline(image,nodes,roi)
    with connect() as conn:
        conn.execute('''INSERT INTO inspection_results(project_id,image_path,passed,measurements_json,reasons_json,processing_ms,created_at) VALUES(?,?,?,?,?,?,?)''',(project_id,str(Path(image_path).resolve()),int(result.passed),json.dumps(result.measurements),json.dumps(result.reasons),result.processing_ms,utc_now()))
    return result


def batch_test(project_id: int, image_paths: list[str]) -> dict[str,Any]:
    results=[run_file(project_id,p) for p in image_paths]
    total=len(results); passed=sum(r.passed for r in results)
    return {'total':total,'passed':passed,'rejected':total-passed,'pass_percent':(passed/total*100 if total else 0.0),'average_ms':(sum(r.processing_ms for r in results)/total if total else 0.0)}


def export_pipeline(project_id: int, path: str | Path) -> Path:
    project=get_project(project_id); nodes=load_pipeline(project_id); rois=list_rois(project_id)
    payload={'format':'VisionQC Pipeline','version':1,'project':project,'nodes':[asdict(n) for n in nodes],'rois':rois}
    out=Path(path); out.write_text(json.dumps(payload,indent=2),encoding='utf-8'); return out


def import_pipeline(project_id: int, path: str | Path) -> None:
    payload=json.loads(Path(path).read_text(encoding='utf-8')); save_pipeline(project_id,[PipelineNode(**x) for x in payload.get('nodes',[])])
    for item in payload.get('rois',[]): save_roi(project_id,ROI(item['name'],item['shape'],item['points'],item.get('enabled',True),item.get('description','')))


def export_project(project_id: int, path: str | Path) -> Path:
    temp=Path(path).with_suffix('.tmp.json'); export_pipeline(project_id,temp); out=Path(path)
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z: z.write(temp,'project.json')
    temp.unlink(missing_ok=True); return out
