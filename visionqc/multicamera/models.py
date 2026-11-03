from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CameraProfile:
    key: str
    title_fa: str
    purpose_fa: str
    primary_indicators_fa: tuple[str, ...]
    default_owner_role_fa: str
    alert_targets_fa: tuple[str, ...]


_PROFILE_CATALOG = (
    CameraProfile(
        "incoming", "کنترل مواد اولیه", "ارزیابی ظاهری گوشت و مواد ورودی پیش از ورود به تولید",
        ("کیفیت تصویر", "ثبات رنگ", "سلامت سطح", "تطابق با مرجع", "کنترل ریسک"),
        "کارشناس کنترل کیفیت ورودی", ("اپراتور دریافت", "مدیر کنترل کیفیت"),
    ),
    CameraProfile(
        "mixing", "دیگ و اختلاط", "پایش خمیر، حرکت، پوشش اختلاط، سطح و هوادهی",
        ("یکنواختی بافت", "سلامت سطح", "سلامت هوادهی", "ثبات حرکت", "پوشش اختلاط", "ثبات فرایند"),
        "اپراتور دیگ", ("اپراتور دیگ", "مدیر کنترل کیفیت", "مدیر تولید"),
    ),
    CameraProfile(
        "filling", "پرکن و شکل‌دهی", "کنترل یکنواختی پرشدن، نشت، پارگی و توقف خط",
        ("ثبات حرکت", "ثبات فرایند", "تطابق با مرجع", "کنترل ریسک"),
        "اپراتور پرکن", ("اپراتور پرکن", "سرپرست تولید", "مدیر کنترل کیفیت"),
    ),
    CameraProfile(
        "packaging", "بسته‌بندی و لیبل", "کنترل دوخت، حضور لیبل، وضعیت بسته و ناهنجاری ظاهری",
        ("کیفیت تصویر", "ثبات رنگ", "تطابق با مرجع", "کنترل ریسک"),
        "اپراتور بسته‌بندی", ("اپراتور بسته‌بندی", "مدیر کنترل کیفیت"),
    ),
    CameraProfile(
        "hse", "ایمنی و HSE", "پایش الزامات ایمنی و ورود به نواحی تعریف‌شده",
        ("کیفیت تصویر", "وضوح تصویر", "ثبات فرایند", "کنترل ریسک"),
        "کارشناس HSE", ("کارشناس HSE", "سرپرست شیفت"),
    ),
    CameraProfile(
        "general", "پایش عمومی", "پایش تصویری عمومی برای ناحیه‌های فاقد پروفایل تخصصی",
        ("کیفیت تصویر", "ثبات رنگ", "ثبات فرایند", "کنترل ریسک"),
        "سرپرست شیفت", ("سرپرست شیفت", "مدیر کنترل کیفیت"),
    ),
)


def profile_catalog() -> tuple[CameraProfile, ...]:
    return _PROFILE_CATALOG


def profile_by_key(key: str) -> CameraProfile:
    return next((p for p in _PROFILE_CATALOG if p.key == key), _PROFILE_CATALOG[-1])


@dataclass
class CameraDefinition:
    camera_id: str
    name_fa: str
    area_fa: str
    asset_fa: str
    profile_key: str
    source_type: str = "RTSP"
    source_value: str = ""
    operator_fa: str = ""
    qc_manager_fa: str = ""
    hse_owner_fa: str = ""
    enabled: bool = True
    status_fa: str = "آماده اتصال"
    health_score: float | None = None
    last_event_fa: str = "—"
    last_seen_iso: str | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def profile(self) -> CameraProfile:
        return profile_by_key(self.profile_key)

    @property
    def last_seen_fa(self) -> str:
        if not self.last_seen_iso:
            return "—"
        try:
            value = datetime.fromisoformat(self.last_seen_iso.replace("Z", "+00:00"))
            return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return self.last_seen_iso

    def touch(self, *, score: float | None = None, status_fa: str | None = None, event_fa: str | None = None) -> None:
        self.last_seen_iso = datetime.now(timezone.utc).isoformat()
        if score is not None:
            self.health_score = max(0.0, min(100.0, float(score)))
        if status_fa:
            self.status_fa = status_fa
        if event_fa:
            self.last_event_fa = event_fa


class CameraRegistry:
    """Small JSON-backed registry.

    It stores camera topology and responsibility assignment only. Credentials are
    intentionally not copied into logs or summaries; deployment can later move
    secrets to the encrypted API-key repository.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else Path.home() / ".visionqc" / "camera_registry.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[CameraDefinition]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        result = []
        for item in raw if isinstance(raw, list) else []:
            try:
                result.append(CameraDefinition(**item))
            except TypeError:
                continue
        return result

    def save(self, cameras: Iterable[CameraDefinition]) -> None:
        payload = [asdict(c) for c in cameras]
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def upsert(self, camera: CameraDefinition) -> None:
        cameras = self.list()
        for index, existing in enumerate(cameras):
            if existing.camera_id == camera.camera_id:
                cameras[index] = camera
                break
        else:
            cameras.append(camera)
        self.save(cameras)

    def delete(self, camera_id: str) -> None:
        self.save(c for c in self.list() if c.camera_id != camera_id)
