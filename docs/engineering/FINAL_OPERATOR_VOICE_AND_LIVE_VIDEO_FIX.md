# Final Operator Voice and Live Video Fix

This hotfix changes only the requested operator voice and live monitoring behavior.

- Every non-silent quality alert is spoken briefly through the Windows default output device.
- Healthy/pass results remain silent.
- Asynchronous speech requests are serialized to prevent overlapping headset messages.
- Wake word matching accepts both `Vision` and `ویژن`.
- After a standalone wake word, VisionQC prompts the operator and captures a Persian question using the installed `fa-IR` Windows recognizer, with `en-US` fallback.
- Persistent wake-word recognition automatically selects an installed Persian recognizer when available, then English as fallback.
- Live-camera preview is capped near 10 FPS, JPEG work is reduced, fast scaling is used, and chart redraws are throttled to prevent GUI queue buildup and freezing.

No menu, analysis model, Gemini workflow, database, integration, or commercial feature was intentionally changed.
