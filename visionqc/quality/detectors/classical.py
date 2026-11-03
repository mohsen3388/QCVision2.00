from __future__ import annotations
import cv2
import numpy as np
from visionqc.configuration.models import DetectorManifest
from .base import DetectorPlugin

def _gray(frame):
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

def _crop(frame, params):
    roi=(params or {}).get("roi")
    if not roi: return frame
    x,y,w,h=[int(v) for v in roi]
    x=max(0,x); y=max(0,y); w=max(1,w); h=max(1,h)
    return frame[y:y+h,x:x+w]

def brightness(frame,p):
    f=_crop(frame,p); return float(np.mean(_gray(f))/255.0)

def contrast(frame,p):
    f=_crop(frame,p); return float(np.clip(np.std(_gray(f))/64.0,0,1))

def focus(frame,p):
    f=_crop(frame,p); scale=float((p or {}).get("normalizer",220.0))
    return float(np.clip(cv2.Laplacian(_gray(f),cv2.CV_64F).var()/max(scale,1),0,1))

def exposure_health(frame,p):
    g=_gray(_crop(frame,p)); dark=np.mean(g<20); bright=np.mean(g>245)
    return float(np.clip(1.0-(dark+bright)*2.5,0,1))

def color_uniformity(frame,p):
    lab=cv2.cvtColor(_crop(frame,p),cv2.COLOR_BGR2LAB).astype(np.float32)
    spread=np.mean(np.std(lab.reshape(-1,3),axis=0)); normalizer=float((p or {}).get("normalizer",55.0))
    return float(np.clip(1.0-spread/max(normalizer,1),0,1))

def texture_uniformity(frame,p):
    g=_gray(_crop(frame,p)); sigma=float((p or {}).get("sigma",3.0)); normalizer=float((p or {}).get("normalizer",45.0))
    residual=cv2.absdiff(g,cv2.GaussianBlur(g,(0,0),sigma))
    return float(np.clip(1.0-np.mean(residual)/max(normalizer,1),0,1))

def surface_homogeneity(frame,p):
    hsv=cv2.cvtColor(_crop(frame,p),cv2.COLOR_BGR2HSV); v=hsv[:,:,2]; s=hsv[:,:,1]
    value=int((p or {}).get("value_threshold",230)); sat=int((p or {}).get("saturation_threshold",45))
    spec=np.mean((v>value)&(s<sat)); multiplier=float((p or {}).get("penalty",4.0))
    return float(np.clip(1.0-spec*multiplier,0,1))

def bubble_density(frame,p):
    f=_crop(frame,p); g=cv2.GaussianBlur(_gray(f),(7,7),1.5)
    circles=cv2.HoughCircles(g,cv2.HOUGH_GRADIENT,1.2,12,param1=70,param2=int((p or {}).get("sensitivity",28)),minRadius=3,maxRadius=28)
    count=0 if circles is None else len(circles[0]); expected=max(1.0,f.shape[0]*f.shape[1]/float((p or {}).get("area_per_candidate",18000.0)))
    return float(np.clip(count/expected,0,1))

def edge_density(frame,p):
    e=cv2.Canny(_gray(_crop(frame,p)),70,140); return float(np.mean(e>0))

def color_reference_similarity(frame,p):
    reference=(p or {}).get("reference_lab")
    if not reference: return 0.5
    lab=cv2.cvtColor(_crop(frame,p),cv2.COLOR_BGR2LAB).astype(np.float32)
    current=np.mean(lab.reshape(-1,3),axis=0); distance=float(np.linalg.norm(current-np.array(reference,dtype=float)))
    return float(np.clip(1.0-distance/100.0,0,1))

def texture_reference_similarity(frame,p):
    reference=(p or {}).get("reference_texture")
    if reference is None: return 0.5
    current=texture_uniformity(frame,p); return float(np.clip(1.0-abs(current-float(reference)),0,1))

def image_assessability(frame,p):
    f=_crop(frame,p); g=_gray(f)
    focus_score=focus(f,p)
    exposure_score=exposure_health(f,p)
    contrast_score=contrast(f,p)
    obstruction=1.0-float(np.mean((g<8)|(g>250)))
    return float(np.clip(0.40*focus_score+0.30*exposure_score+0.20*contrast_score+0.10*obstruction,0,1))

def plugins() -> list[DetectorPlugin]:
    defs=[
      ("image.brightness","روشنایی","Brightness","کیفیت تصویر",brightness),
      ("image.contrast","کنتراست","Contrast","کیفیت تصویر",contrast),
      ("image.focus","وضوح/فوکوس","Focus","کیفیت تصویر",focus),
      ("image.exposure_health","سلامت نوردهی","Exposure Health","کیفیت تصویر",exposure_health),
      ("image.assessability","قابلیت ارزیابی تصویر","Image Assessability","کیفیت تصویر",image_assessability),
      ("product.color_uniformity","یکنواختی رنگ","Color Uniformity","سلامت محصول",color_uniformity),
      ("product.texture_uniformity","یکنواختی بافت","Texture Uniformity","سلامت محصول",texture_uniformity),
      ("product.surface_homogeneity","همگنی سطح","Surface Homogeneity","سلامت محصول",surface_homogeneity),
      ("product.bubble_density","تراکم کاندیدای حباب","Bubble Candidate Density","سلامت محصول",bubble_density),
      ("image.edge_density","تراکم لبه","Edge Density","تحلیل تصویر",edge_density),
      ("reference.color_similarity","تطابق رنگ با نمونه مرجع","Golden Color Similarity","مرجع",color_reference_similarity),
      ("reference.texture_similarity","تطابق بافت با نمونه مرجع","Golden Texture Similarity","مرجع",texture_reference_similarity),
    ]
    return [DetectorPlugin(DetectorManifest(key,fa,en,cat,"ratio",description_fa=f"آشکارساز افزونه‌ای {fa}",version="4.0.0"),fn) for key,fa,en,cat,fn in defs]
