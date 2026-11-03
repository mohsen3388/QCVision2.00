# Gemini Integration Sprint 1 — Acceptance Checklist

- [x] Space-heavy left navigation removed; full workspace width available.
- [x] Gemini API key is read from project-root `.env`.
- [x] Image selection and preview.
- [x] Process context input (product, stage, temperature, time, vacuum, notes).
- [x] Optional loading of existing VisionQC/OpenCV JSON context.
- [x] Background Gemini request does not freeze the UI.
- [x] Structured JSON parsing and validation.
- [x] VisionQC decision engine maps suggestions to approved actions.
- [x] Low-confidence AI output becomes manual review.
- [x] Persian operator console accepts user questions.
- [x] Follow-up questions include current image and inspection context.
- [x] Windows built-in offline speech reads AI responses aloud.
- [x] Local assistant fallback remains available when no Gemini key is configured.
- [x] Friendly handling of invalid key, free-tier quota, region/billing, and connection errors.
