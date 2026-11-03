
from __future__ import annotations
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, math
import cv2, numpy as np
from .runtime import ConfigurationRuntime
from .repository import ConfigurationRepository
from .runtime_repository import RuntimeRepository

class ProductionRuntimeEngine:
    """Executes only Production templates, stores history, evaluates triggers and actions.
    Closely follows Zabbix semantics: Item history -> Trigger state -> Problem/Event -> Action.
    """
    def __init__(self, config_repo=None, runtime_repo=None, action_callback=None):
        self.config_repo=config_repo or ConfigurationRepository(); self.repo=runtime_repo or RuntimeRepository()
        self.runtime=ConfigurationRuntime(); self.action_callback=action_callback
        self._buffers=defaultdict(lambda: defaultdict(lambda: deque(maxlen=900)))
        self._condition_since={}
    def _template(self,key):
        t=self.config_repo.get_template(key)
        if t is None: raise ValueError(f'Template یافت نشد: {key}')
        if t.lifecycle!='Production': raise ValueError(f'Template باید Production باشد: {key} ({t.lifecycle})')
        return t
    def process_frame(self,camera_id,frame,captured_at=None):
        a=self.repo.assignment(camera_id)
        if not a or not a['enabled']: raise ValueError('دوربین فاقد Assignment فعال است.')
        t=self._template(a['template_key']); result=self.runtime.analyze_frame(frame,t)
        ts=captured_at or datetime.now(timezone.utc).isoformat(); self.repo.add_samples(camera_id,t.key,result['metrics'],ts)
        for m in result['metrics']:
            if m.get('score') is not None:
                self._buffers[camera_id][m['key']].append((ts,float(m['score'])))
        trigger_results=[]
        for trig in t.triggers:
            if not trig.enabled or trig.lifecycle not in {'Validated','Production'}: continue
            active,evidence=self._evaluate_trigger(camera_id,trig)
            existing=self.repo.active_event(camera_id,trig.key); event_key=existing
            key=(camera_id,trig.key)
            now=datetime.now(timezone.utc).timestamp()
            if active:
                self._condition_since.setdefault(key,now)
                persisted=(now-self._condition_since[key])>=max(0,trig.persistence_seconds)
                if persisted and not existing:
                    event_key=self._event_key(camera_id,trig.key,ts); self.repo.open_event(event_key,camera_id,t.key,trig,evidence)
                    self._execute_actions(t,trig,event_key,evidence)
            else:
                self._condition_since.pop(key,None)
                if existing: self.repo.resolve_event(existing)
            trigger_results.append({'key':trig.key,'name':trig.name_fa,'condition':active,'event_key':event_key,'evidence':evidence})
        result.update(camera_id=camera_id,template_key=t.key,captured_at=ts,triggers=trigger_results,active_events=sum(1 for x in trigger_results if x['event_key']))
        return result
    def _series(self,camera_id,key,window_seconds):
        arr=list(self._buffers[camera_id][key]);
        if not arr: arr=self.repo.metric_history(camera_id,key,limit=500)
        if not arr:return []
        cutoff=datetime.now(timezone.utc).timestamp()-window_seconds; out=[]
        for ts,v in arr:
            try: epoch=datetime.fromisoformat(ts.replace('Z','+00:00')).timestamp()
            except Exception: epoch=cutoff
            if epoch>=cutoff: out.append(float(v))
        return out
    def _condition_value(self,camera_id,c):
        vals=self._series(camera_id,c.metric_key,c.window_seconds)
        if not vals:return None
        f=c.function
        if f=='last': return vals[-1]
        if f=='avg': return float(np.mean(vals))
        if f=='median': return float(np.median(vals))
        if f=='min': return min(vals)
        if f=='max': return max(vals)
        if f=='count_below': return sum(v<c.threshold for v in vals)
        if f=='count_above': return sum(v>c.threshold for v in vals)
        if f=='slope':
            if len(vals)<2:return 0.0
            return float(np.polyfit(np.arange(len(vals)),np.array(vals),1)[0])
        return vals[-1]
    def _compare(self,v,op,threshold):
        return {'<':v<threshold,'<=':v<=threshold,'>':v>threshold,'>=':v>=threshold,'==':v==threshold,'!=':v!=threshold}.get(op,False)
    def _evaluate_trigger(self,camera_id,trig):
        states=[]; evidence={}
        for c in trig.conditions:
            v=self._condition_value(camera_id,c); ok=False if v is None else self._compare(v,c.operator,c.threshold)
            states.append(ok); evidence[c.metric_key]={'value':v,'function':c.function,'operator':c.operator,'threshold':c.threshold,'ok':ok}
        active=(all(states) if trig.join_mode=='AND' else any(states)) if states else False
        return active,evidence
    def _event_key(self,camera_id,trigger_key,ts):
        return hashlib.sha1(f'{camera_id}|{trigger_key}|{ts}'.encode()).hexdigest()[:20]
    def _execute_actions(self,t,trig,event_key,evidence):
        for action in t.actions:
            if not action.enabled or action.trigger_key!=trig.key: continue
            for step in sorted(action.steps,key=lambda x:x.step_order):
                status='QUEUED' if step.delay_seconds>0 else 'DONE'; details={'evidence':evidence,'require_ack':step.require_ack,'delay_seconds':step.delay_seconds}
                self.repo.log_action(event_key,action.key,step,status,details)
                if self.action_callback:
                    try:self.action_callback(event_key,action,step,details)
                    except Exception as exc:self.repo.log_action(event_key,action.key,step,'ERROR',{'error':str(exc)})
