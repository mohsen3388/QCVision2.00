# Persian Headset Audio Hotfix

Only the operator audio-output path and the Audio Settings diagnostic device list were changed.

- Persian operator alerts now use a Persian-capable online neural voice when available.
- A dependency-free online Persian TTS fallback is included for short alerts.
- Windows SAPI remains the offline fallback.
- Audio Settings now lists Windows playback endpoints rather than physical sound controllers.
- Test Headset queues both an English and a Persian test message.
- VisionQC continues to route playback through the current Windows default output endpoint.
