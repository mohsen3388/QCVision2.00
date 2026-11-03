# VisionQC hotfix — Three-level AI review and headset policy

Only the following behavior was changed:

1. Gemini output is presented in three levels:
   - Level 1: short operator alert in the Operator Alert tab and headset.
   - Level 2: concise QC Executive Summary shown by default in Gemini AI Review.
   - Level 3: full Technical Report available through Show Technical Report.
2. The operator headset is silent for PASS/SILENT and ATTENTION/WARNING.
   Audio is emitted only for HIGH and CRITICAL alerts.
3. For HIGH/CRITICAL alerts, only the short alert sentence is spoken. Immediate actions remain visible and recorded.

No other application behavior was intentionally modified.
