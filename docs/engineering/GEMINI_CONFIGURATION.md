# Gemini AI Configuration — Sprint 1

## Where to put the API key

1. Open the same project folder that contains `main.py`.
2. Create a plain-text file named exactly `.env` (not `.env.txt`).
3. Put one line in it:

```text
GEMINI_API_KEY=PASTE_YOUR_KEY_HERE
```

4. Save it and restart VisionQC.

Do not put quotes around the key. Do not commit or share `.env`.

## Sprint 1 workflow

1. Open **Navigate > Core > Operator Assistant**.
2. Choose a kettle / sausage-batter image.
3. Add process stage and optional production context.
4. Optionally load a JSON exported by local VisionQC/OpenCV analysis.
5. Click **Analyze image with Gemini**.
6. Continue the conversation in the **Operator console**.
7. Leave **Speak AI responses** enabled for Windows offline text-to-speech.

Gemini interprets the image. VisionQC validates JSON, lowers low-confidence results to manual review, and maps AI suggestions to approved non-destructive actions.
