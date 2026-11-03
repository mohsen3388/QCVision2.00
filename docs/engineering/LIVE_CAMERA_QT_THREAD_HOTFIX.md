# Live Camera Qt Thread Hotfix

This hotfix changes only the Gemini completion/error delivery path used by Live Camera.

## Fixed

- Gemini worker results are now delivered to `CameraPage` through Qt queued slots.
- No `QTextEdit`, `QTextDocument`, label, table, timer, or other UI object is updated from the Gemini worker thread.
- Removed lambda callbacks that could run in the worker thread and trigger:
  - `QObject: Cannot create children for a parent that is in a different thread`
  - `QBasicTimer::start: Timers cannot be started from another thread`
- Pending local-analysis and predictive context is retained safely on the GUI page until the AI result returns.

## Unchanged

- Local camera analysis interval
- Rolling Gemini temporal session
- Gemini sampling and cooldown policy
- Predictive deterioration logic
- Headset alert policy
- Factory event logging
- All other VisionQC pages and services

## Verification

- Python compilation passed.
- Full regression suite: `84 passed`.
