# VisionQC 4.5 — Sprint 6: RTSP Reliability & Edge Runtime

## هدف
پایدارسازی پایش USB/RTSP برای استفاده صنعتی و جلوگیری از توقف Runtime بر اثر قطع موقت شبکه یا شکست دریافت یک فریم.

## تغییرات اجرایی

- افزوده‌شدن `visionqc.edge.ResilientCapture` با Backendهای قابل تعویض FFMPEG/DSHOW/MSMF/V4L2/AUTO.
- تنظیم Buffer کم‌تأخیر، Open Timeout و Read Timeout در صورت پشتیبانی OpenCV.
- اتصال مجدد خودکار با Exponential Backoff.
- عدم پایان Worker با خطای موقت RTSP؛ تلاش ادامه می‌یابد تا کاربر Stop کند یا سقف Retry تعریف‌شده پر شود.
- ثبت وضعیت‌های `CONNECTING`, `RUNNING`, `RECONNECTING`, `FAILED`, `EOF`, `ANALYSIS_ERROR`, `STOPPED`.
- ذخیره Telemetry هر دوربین در SQLite: FPS، زمان آخرین فریم، Backend، تعداد Reconnect، خطاها و فریم‌های دریافت/تحلیل‌شده.
- افزودن صفحه `Edge Runtime Health` با Probe دستی و Diagnostics.
- ارتقای Runtime Operations Center برای نمایش FPS، آخرین فریم، Reconnect و Backend.

## تنظیمات قابل Override برای هر Assignment

در `overrides_json` می‌توان زیرکلید `edge` را تعریف کرد:

```json
{
  "edge": {
    "initial_delay_seconds": 0.5,
    "max_delay_seconds": 15,
    "multiplier": 2,
    "max_attempts": 0,
    "read_failure_threshold": 3,
    "open_timeout_ms": 5000,
    "read_timeout_ms": 5000,
    "buffer_size": 1
  }
}
```

`max_attempts=0` یعنی تلاش نامحدود تا زمان توقف دستی.

## محدودیت اعتبارسنجی

Reconnect و USB/RTSP واقعی باید روی ویندوز، شبکه و دوربین کارخانه تست شوند. تست‌های خودکار قرارداد Capture، سیاست Retry و ذخیره Camera Health را پوشش می‌دهند، اما کیفیت Driver، Firmware دوربین و شبکه را شبیه‌سازی کامل نمی‌کنند.
