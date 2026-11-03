from __future__ import annotations

from .base import DetectorPlugin, DetectorProvider
from .classical import plugins as classical_plugins
from visionqc.configuration.models import DetectorManifest


def _history_only(frame, params):
    raise RuntimeError('This detector requires a frame history and must be executed by ConfigurationRuntime.')


def temporal_plugins():
    definitions = [
        ('process.motion_stability', 'ثبات حرکت', 'Motion Stability'),
        ('process.mixing_coverage', 'پوشش اختلاط', 'Mixing Coverage'),
        ('process.dead_zone_health', 'سلامت ناحیه مرده', 'Dead-zone Health'),
        ('process.temporal_consistency', 'ثبات زمانی فرایند', 'Temporal Consistency'),
    ]
    return [DetectorPlugin(DetectorManifest(key, fa, en, 'تحلیل زمانی', 'ratio', supports_image=False, supports_video=True, requires_history=True, description_fa=f'آشکارساز زمانی {fa}', version='4.1.0'), _history_only) for key, fa, en in definitions]


def all_plugins():
    return classical_plugins() + temporal_plugins()


__all__=['DetectorPlugin','DetectorProvider','all_plugins']
