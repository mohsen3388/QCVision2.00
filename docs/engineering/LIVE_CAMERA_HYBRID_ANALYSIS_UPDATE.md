# Live Camera Hybrid Analysis Update

Only the Live USB/IP Camera monitoring path was changed.

- Continuous local analysis remains active at the configured interval.
- The full local `AnalysisResult` is now retained for every analyzed frame.
- A representative frame is sent to Gemini only when useful: first review, status change, persistent attention, HIGH/CRITICAL local evidence, or predictive deterioration.
- Gemini has a 30-second review cooldown to avoid duplicate API calls.
- Hybrid decisions use the same `evaluate_image_alert`, `record_operator_event`, Gemini formatting, and headset policy as Deep Image Analysis.
- Headset output is restricted to HIGH, CRITICAL, and predictive deterioration.
- Repeated alerts have a 45-second audio cooldown; escalation is spoken immediately.
- Live Trends, Gemini AI Review, Operator Alert, and Event Timeline are shown in separate tabs.
- Monitoring records are appended to the existing operator event log with source `live_camera`.
- No PLC write, recipe change, machine stop, or other automatic equipment control was added.
