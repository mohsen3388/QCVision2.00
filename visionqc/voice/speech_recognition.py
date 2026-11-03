from __future__ import annotations

from dataclasses import dataclass
import platform
import subprocess


@dataclass(slots=True)
class SpeechRecognitionResult:
    text: str = ""
    confidence: float = 0.0
    available: bool = False
    error: str = ""


def recognize_once(*, culture: str = "en-US", timeout_seconds: int = 8) -> SpeechRecognitionResult:
    """Capture one utterance using Windows' installed speech recognizer.

    No cloud service or API key is required. On unsupported systems the caller
    receives a structured unavailable result and can keep using typed input.
    """
    if platform.system() != "Windows":
        return SpeechRecognitionResult(error="Offline microphone recognition is currently available on Windows; typed mode remains active.")
    safe_culture = culture.replace("'", "")
    timeout = max(2, min(int(timeout_seconds), 30))
    script = rf'''
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
$culture = New-Object System.Globalization.CultureInfo('{safe_culture}')
$recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
$recognizer.SetInputToDefaultAudioDevice()
$recognizer.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
$result = $recognizer.Recognize([TimeSpan]::FromSeconds({timeout}))
if ($null -eq $result) {{ Write-Output '{{"text":"","confidence":0}}' }}
else {{
  $text = $result.Text.Replace('\\','\\\\').Replace('"','\\"')
  Write-Output ('{{"text":"' + $text + '","confidence":' + $result.Confidence.ToString([System.Globalization.CultureInfo]::InvariantCulture) + '}}')
}}
'''
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=timeout + 5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            return SpeechRecognitionResult(error=(completed.stderr or "Speech recognition failed").strip())
        import json
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        text = str(payload.get("text", "")).strip()
        return SpeechRecognitionResult(text=text, confidence=float(payload.get("confidence", 0.0)), available=True)
    except subprocess.TimeoutExpired:
        return SpeechRecognitionResult(available=True, error="No speech was detected before the timeout.")
    except Exception as exc:
        return SpeechRecognitionResult(error=str(exc))
