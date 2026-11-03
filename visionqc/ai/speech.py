from __future__ import annotations

import json
import platform
import subprocess
import threading
import queue
import asyncio
import tempfile
import uuid
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from visionqc.core.settings import app_data_dir

_AUDIO_STATE = app_data_dir() / "audio_output_state.json"
_AUDIO_LOG = app_data_dir() / "audio_output_events.jsonl"
_SPEECH_QUEUE: "queue.Queue[str]" = queue.Queue(maxsize=50)
_SPEECH_WORKER_STARTED = False
_SPEECH_WORKER_LOCK = threading.Lock()


def _write_event(status: str, text: str, detail: str = "") -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "text": text[:500],
        "detail": detail[:1000],
    }
    try:
        with _AUDIO_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        _AUDIO_STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def last_audio_status() -> dict:
    try:
        return json.loads(_AUDIO_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "not_tested", "detail": "No audio test has been run yet."}


def list_windows_audio_devices() -> list[str]:
    """Return Windows playback endpoint names, not physical sound-card names.

    This mirrors the device labels shown in the Windows playback selector more
    closely than Win32_SoundDevice, which only exposes hardware controllers.
    """
    if platform.system() != "Windows":
        return ["System default output"]
    script = (
        "Get-PnpDevice -Class AudioEndpoint -Status OK | "
        "Select-Object -ExpandProperty FriendlyName | Sort-Object -Unique | "
        "ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            names = [data] if isinstance(data, str) else list(data or [])
            return ["Windows default output"] + [str(x) for x in names if str(x).strip()]
    except Exception:
        pass
    return ["Windows default output"]


def open_windows_sound_settings() -> None:
    if platform.system() == "Windows":
        try:
            subprocess.Popen(["cmd", "/c", "start", "", "ms-settings:sound"], shell=False)
        except Exception:
            try:
                subprocess.Popen(["control", "mmsys.cpl"])
            except Exception:
                pass



def _contains_persian(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" for ch in text)


def _play_media_file_windows(path: Path) -> tuple[bool, str]:
    escaped = str(path.resolve()).replace("'", "''")
    script = (
        "Add-Type -AssemblyName PresentationCore; "
        "$p=New-Object System.Windows.Media.MediaPlayer; "
        f"$p.Open([Uri]'{escaped}'); "
        "$limit=(Get-Date).AddSeconds(12); "
        "while((-not $p.NaturalDuration.HasTimeSpan) -and ((Get-Date) -lt $limit)){Start-Sleep -Milliseconds 100}; "
        "$p.Volume=1.0; $p.Play(); "
        "if($p.NaturalDuration.HasTimeSpan){"
        "$ms=[Math]::Ceiling($p.NaturalDuration.TimeSpan.TotalMilliseconds)+500; Start-Sleep -Milliseconds $ms"
        "} else {Start-Sleep -Seconds 8}; "
        "$p.Stop(); $p.Close();"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=False, capture_output=True, text=True, timeout=100,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    detail = (result.stderr or result.stdout or "").strip()
    return result.returncode == 0, detail


def _speak_persian_online(clean: str) -> tuple[bool, str]:
    """Create audible Persian speech and play it on the Windows default endpoint.

    The preferred engine is edge-tts when installed. A dependency-free online
    fallback is retained for short operator alerts, followed by Windows SAPI in
    _speak_now when the network is unavailable.
    """
    temp_path = Path(tempfile.gettempdir()) / f"visionqc_tts_{uuid.uuid4().hex}.mp3"
    errors: list[str] = []
    try:
        try:
            import edge_tts  # type: ignore

            async def _save() -> None:
                communicator = edge_tts.Communicate(
                    clean, voice="fa-IR-DilaraNeural", rate="+0%", volume="+0%"
                )
                await communicator.save(str(temp_path))

            asyncio.run(_save())
            ok, detail = _play_media_file_windows(temp_path)
            if ok:
                return True, detail or "Persian neural speech played through Windows default output."
            errors.append(f"edge-tts playback failed: {detail}")
        except Exception as exc:
            errors.append(f"edge-tts unavailable: {exc}")

        # Dependency-free fallback for the short alert messages used by VisionQC.
        query = urllib.parse.urlencode({
            "ie": "UTF-8",
            "client": "tw-ob",
            "tl": "fa",
            "q": clean[:190],
        })
        request = urllib.request.Request(
            "https://translate.googleapis.com/translate_tts?" + query,
            headers={"User-Agent": "Mozilla/5.0 VisionQC/2.0"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            media = response.read()
        if not media:
            raise RuntimeError("The online Persian TTS service returned an empty response.")
        temp_path.write_bytes(media)
        ok, detail = _play_media_file_windows(temp_path)
        if ok:
            return True, detail or "Persian online speech played through Windows default output."
        errors.append(f"online Persian playback failed: {detail}")
    except Exception as exc:
        errors.append(f"online Persian TTS failed: {exc}")
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
    return False, " | ".join(errors)


def _speak_now(clean: str) -> None:
    _write_event("started", clean, "Speech request started.")
    try:
        if platform.system() == "Windows":
            if _contains_persian(clean):
                ok, detail = _speak_persian_online(clean)
                if ok:
                    _write_event("completed", clean, detail)
                    return
                _write_event("fallback", clean, f"Persian neural TTS failed; using Windows SAPI fallback. {detail}")

            escaped = clean.replace("'", "''")
            script = (
                "Add-Type -AssemblyName System.Speech; "
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$s.SetOutputToDefaultAudioDevice(); "
                "$s.Rate=0; $s.Volume=100; "
                f"$s.Speak('{escaped}'); "
                "$s.Dispose();"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                check=False, capture_output=True, text=True, timeout=90,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                detail = "Speech completed through Windows default output."
                if _contains_persian(clean):
                    detail += " Persian SAPI fallback was used; install edge-tts or a Persian Windows voice if speech is silent."
                _write_event("completed", clean, detail)
            else:
                detail = (result.stderr or result.stdout or f"PowerShell exit code {result.returncode}").strip()
                _write_event("failed", clean, detail)
            return
        try:
            import pyttsx3  # type: ignore
            engine = pyttsx3.init(); engine.say(clean); engine.runAndWait()
            _write_event("completed", clean, "Speech completed through pyttsx3.")
        except Exception as exc:
            _write_event("failed", clean, str(exc))
    except Exception as exc:
        _write_event("failed", clean, str(exc))


def _speech_queue_worker() -> None:
    while True:
        text = _SPEECH_QUEUE.get()
        try:
            _speak_now(text)
        finally:
            _SPEECH_QUEUE.task_done()


def _ensure_speech_worker() -> None:
    global _SPEECH_WORKER_STARTED
    with _SPEECH_WORKER_LOCK:
        if _SPEECH_WORKER_STARTED:
            return
        threading.Thread(target=_speech_queue_worker, daemon=True, name="VisionQC-TTS-Queue").start()
        _SPEECH_WORKER_STARTED = True


def speak_text(text: str, *, wait: bool = False) -> None:
    """Speak through the Windows default output device.

    Asynchronous alerts are serialized through one queue, preventing overlapping
    PowerShell synthesizers from dropping or masking operator-headset messages.
    """
    clean = " ".join((text or "").split())[:1200]
    if not clean:
        return
    if wait:
        _speak_now(clean)
        return
    _ensure_speech_worker()
    try:
        _SPEECH_QUEUE.put_nowait(clean)
        _write_event("queued", clean, "Speech request queued for the Windows default output.")
    except queue.Full:
        _write_event("failed", clean, "Speech queue is full; request was not queued.")


def test_headset() -> None:
    # Play the English and Persian routes sequentially for deterministic diagnosis.
    speak_text(
        "This is a VisionQC headset test. If you can hear this message, your audio output is working correctly.",
        wait=True,
    )
    speak_text(
        "این یک آزمایش صدای فارسی ویژن کیو سی است. اگر این پیام را می‌شنوید، هشدارهای فارسی هدست فعال هستند.",
        wait=True,
    )
