from __future__ import annotations

import json
import platform
import subprocess
import threading
from PySide6.QtCore import QThread, Signal
from visionqc.voice.wake_word_core import WakeWordMatcher, WakeWordResult


class WakeWordListener(QThread):
    """Persistent Windows microphone listener for hands-free wake-word use.

    A single System.Speech recognizer stays attached to the Windows default
    input device. This is materially more reliable than repeatedly creating a
    new recognizer for every five-second listening window.
    """

    heard = Signal(str, float)
    state_changed = Signal(str)
    debug_event = Signal(str)

    def __init__(self, *, culture: str = "auto", timeout_seconds: int = 5) -> None:
        super().__init__()
        self.culture = culture
        self.timeout_seconds = max(2, min(int(timeout_seconds), 12))
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._process: subprocess.Popen[str] | None = None

    def stop(self) -> None:
        self._stop.set()
        process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass

    def pause_listening(self) -> None:
        self._pause.set()
        self.state_changed.emit("Microphone paused while VisionQC is speaking")
        self.debug_event.emit("Microphone paused")

    def resume_listening(self) -> None:
        self._pause.clear()
        self.state_changed.emit("Listening for wake word: Vision")
        self.debug_event.emit("Microphone resumed")

    def _powershell_script(self) -> str:
        safe_culture = self.culture.replace("'", "")
        timeout = self.timeout_seconds
        return rf'''
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
$installed = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()
$requested = '{safe_culture}'
if ($requested -eq 'auto') {{
  $selected = $installed | Where-Object {{$_.Culture.Name -eq 'fa-IR'}} | Select-Object -First 1
  if ($null -eq $selected) {{ $selected = $installed | Where-Object {{$_.Culture.Name -eq 'en-US'}} | Select-Object -First 1 }}
  if ($null -eq $selected) {{ $selected = $installed | Select-Object -First 1 }}
  if ($null -eq $selected) {{ throw 'No Windows speech recognizer is installed.' }}
  $culture = $selected.Culture
}} else {{
  $culture = New-Object System.Globalization.CultureInfo($requested)
}}
$recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
$recognizer.SetInputToDefaultAudioDevice()
$recognizer.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
$ready = [PSCustomObject]@{{event='ready';culture=$culture.Name}}; [Console]::Out.WriteLine(($ready | ConvertTo-Json -Compress))
[Console]::Out.Flush()
while ($true) {{
  $result = $recognizer.Recognize([TimeSpan]::FromSeconds({timeout}))
  if ($null -ne $result) {{
    $payload = [PSCustomObject]@{{event='speech';text=$result.Text;confidence=[double]$result.Confidence}}
    [Console]::Out.WriteLine(($payload | ConvertTo-Json -Compress))
    [Console]::Out.Flush()
  }} else {{
    [Console]::Out.WriteLine('{{"event":"timeout"}}')
    [Console]::Out.Flush()
  }}
}}
'''

    def run(self) -> None:
        if platform.system() != "Windows":
            self.state_changed.emit("Wake word unavailable: Windows speech recognition is required")
            return
        self.state_changed.emit("Starting microphone listener")
        self.debug_event.emit("Starting persistent Windows speech recognizer")
        try:
            self._process = subprocess.Popen(
                [
                    "powershell", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "Bypass", "-Command", self._powershell_script(),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            assert self._process.stdout is not None
            while not self._stop.is_set():
                line = self._process.stdout.readline()
                if not line:
                    if self._process.poll() is not None:
                        break
                    self.msleep(50)
                    continue
                try:
                    payload = json.loads(line.strip())
                except Exception:
                    continue
                event = str(payload.get("event", ""))
                if event == "ready":
                    self.state_changed.emit("Listening for wake word: Vision")
                    self.debug_event.emit(f"Microphone active ({payload.get('culture', self.culture)})")
                elif event == "speech":
                    text = str(payload.get("text", "")).strip()
                    confidence = float(payload.get("confidence", 0.0) or 0.0)
                    if not text:
                        continue
                    self.debug_event.emit(f"Heard: {text} ({confidence:.0%})")
                    if not self._pause.is_set():
                        self.heard.emit(text, confidence)
                    else:
                        self.debug_event.emit("Speech ignored because microphone output is paused")
            if self._process.poll() is None:
                self._process.terminate()
        except Exception as exc:
            self.state_changed.emit(f"Wake word unavailable: {exc}")
            self.debug_event.emit(f"Listener error: {exc}")
        finally:
            process = self._process
            if process is not None and process.poll() is not None and process.returncode not in (0, None):
                try:
                    error = (process.stderr.read() if process.stderr else "").strip()
                except Exception:
                    error = ""
                if error and not self._stop.is_set():
                    self.state_changed.emit(f"Wake word unavailable: {error}")
                    self.debug_event.emit(f"PowerShell recognizer error: {error}")
            self._process = None
            self.state_changed.emit("Wake word listener stopped")
