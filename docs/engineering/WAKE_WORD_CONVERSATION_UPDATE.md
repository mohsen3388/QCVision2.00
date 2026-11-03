# VisionQC Wake Word Conversation Update

This focused update adds hands-free operator conversation without changing other product modules.

## Behavior
- Listener starts automatically with VisionQC.
- Wake word: `Vision` (also accepts `Vision QC`).
- One utterance: `Vision, what should I check first?`
- Two utterances: say `Vision`, wait for acknowledgement, then ask the question.
- Follow-up conversation window: 30 seconds.
- Microphone listening pauses while VisionQC speaks, then resumes automatically.
- Questions use the existing Voice AI Copilot conversation and Factory Memory context.
- Tools menu provides Enable/Disable and Status actions.

## Platform
Offline recognition uses the Windows installed speech recognizer and default microphone. Spoken responses use the Windows default output device.
