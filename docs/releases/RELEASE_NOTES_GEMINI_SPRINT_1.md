# VisionQC — Gemini Sprint 1

This release adds the first end-to-end Gemini image-analysis and operator-conversation workflow.

Highlights:
- Full-width workspace; old left navigation removed.
- Gemini image inspection with process context and optional local OpenCV JSON.
- Structured JSON validation and a controlled VisionQC decision layer.
- Persian follow-up conversation in the operator console.
- Spoken responses using Windows built-in offline text-to-speech.
- API key remains outside source code in `.env`.

Run `SETUP_DEV_ENV.bat` once to install the new `google-genai` dependency, then use `RUN_VISIONQC.bat`.
