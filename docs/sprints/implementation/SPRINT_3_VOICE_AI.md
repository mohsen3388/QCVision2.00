# VisionQC 2.0 — Sprint 3: Voice AI Copilot

## Objective
Deliver a two-way, offline-first operator conversation layer grounded in Factory Memory. Core factory questions must remain usable without internet access or an API key.

## Implemented architecture
- `visionqc/voice/models.py`: conversation, message, intent, and response domain models.
- `visionqc/voice/speech_recognition.py`: single-utterance Windows offline speech recognition with structured fallback.
- `VoiceAssistantService`: deterministic intent routing, evidence-grounded answers, and event publication.
- `SqliteVoiceConversationRepository`: durable and auditable conversation storage.
- `VoiceAIPage`: case selection, typed input, push-to-talk, spoken output, shortcuts, evidence display, and silent mode.

## Supported controlled intents
- Help and capability guidance
- Selected case summary and status
- Recent case/reject review
- Defect frequency summary
- Similar historical case search
- Evidence-backed corrective-action retrieval
- Quality status and controlled fallback guidance

## Safety and trust
- Core answers use local Factory Memory rather than invented process facts.
- Verified historical corrective actions are preferred.
- Generic checks are clearly labeled as fallback guidance.
- Every response includes a decision-support warning.
- Microphone failure never blocks typed operation.

## Deliberately deferred
- Free-form cloud LLM orchestration
- Wake-word always-listening mode
- Autonomous machine control
- Root-cause probability engine (Sprint 4)
