# VisionQC Operator Silent Alert Update

This update changes only the image/video operator-notification behavior.

## Behaviour
- Healthy/acceptable analyses remain silent on the headset.
- Every healthy and abnormal result is still appended to the local monitoring log.
- Actionable warnings produce one short headset message.
- High, critical, and predictive-quality alerts also provide immediate operator guidance.
- Full Gemini analysis remains stored in JSON/export data and is not printed as a long operator-facing answer.
- No automatic PLC write, recipe change, machine stop, pressure/temperature change, or unsafe autonomous action was added.

## Local log
`%LOCALAPPDATA%/VisionQC/operator_monitoring_events.jsonl`

## Safety
Emergency guidance is decision support. Factory SOPs and authorized QC/supervisor decisions remain controlling.
