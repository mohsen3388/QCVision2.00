from __future__ import annotations

import json
import mimetypes
import random
import time
from pathlib import Path
from typing import Any

from .config import gemini_api_key
from .prompt_builder import build_chat_prompt, build_inspection_prompt
from .schemas import AIChatAnswer, AIInspectionResult


class GeminiProviderError(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise GeminiProviderError("جمنای یک شیء JSON معتبر برنگرداند.")
        try:
            parsed = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise GeminiProviderError(f"پاسخ JSON جمنای قابل پردازش نبود: {exc}") from exc
    if not isinstance(parsed, dict):
        raise GeminiProviderError("پاسخ جمنای باید یک شیء JSON باشد.")
    return parsed


class GeminiProvider:
    def __init__(
        self,
        model: str = "gemini-3.6-flash",
        api_key: str | None = None,
        *,
        timeout_ms: int = 180_000,
        max_attempts: int = 3,
    ) -> None:
        self.model = model
        self.api_key = (api_key or gemini_api_key()).strip()
        self.timeout_ms = max(30_000, int(timeout_ms))
        self.max_attempts = max(1, min(int(max_attempts), 5))

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _client_and_types(self):
        if not self.api_key:
            raise GeminiProviderError(
                "GEMINI_API_KEY is missing. Create a .env file beside main.py and add GEMINI_API_KEY=your_key"
            )
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise GeminiProviderError(
                "The google-genai package is not installed. Run: pip install -r requirements.txt"
            ) from exc
        # Some Windows networks, proxies and VPNs intermittently close HTTP/2
        # connections without returning a response. Disabling HTTP/2 and using
        # an explicit request timeout makes the desktop client more reliable.
        try:
            http_options = types.HttpOptions(
                timeout=self.timeout_ms,
                client_args={"http2": False},
            )
            client = genai.Client(api_key=self.api_key, http_options=http_options)
        except (TypeError, AttributeError):
            # Compatibility fallback for older google-genai releases.
            client = genai.Client(api_key=self.api_key)
        return client, types

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        text = f"{type(exc).__name__}: {exc}".lower()
        markers = (
            "server disconnected",
            "remoteprotocolerror",
            "connection reset",
            "connection aborted",
            "connection closed",
            "temporarily unavailable",
            "timed out",
            "timeout",
            "503",
            "502",
            "500",
            "unavailable",
        )
        return any(marker in text for marker in markers)

    def _generate_with_retry(self, *, contents: list[Any], config: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            client, _ = self._client_and_types()
            try:
                return client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_attempts or not self._is_retryable(exc):
                    raise
                # Fresh client on every retry avoids reusing a broken connection.
                delay = min(8.0, (1.5 ** (attempt - 1)) + random.uniform(0.1, 0.6))
                time.sleep(delay)
            finally:
                close = getattr(client, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass
        if last_error is not None:
            raise last_error
        raise GeminiProviderError("درخواست جمنای پیش از ارسال ناموفق شد.")

    def inspect_image(
        self,
        image_path: str | Path,
        process_data: dict[str, Any] | None = None,
        opencv_context: dict[str, Any] | None = None,
    ) -> AIInspectionResult:
        path = Path(image_path)
        if not path.is_file():
            raise GeminiProviderError(f"فایل تصویر پیدا نشد: {path}")
        if path.stat().st_size > 18 * 1024 * 1024:
            raise GeminiProviderError("از تصویری با حجم کمتر از ۱۸ مگابایت استفاده کنید.")
        type_client, types = self._client_and_types()
        try:
            close = getattr(type_client, "close", None)
            if callable(close):
                close()
        except Exception:
            pass
        mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        image_part = types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type)
        prompt = build_inspection_prompt(process_data, opencv_context)
        try:
            response = self._generate_with_retry(
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.15,
                ),
            )
        except Exception as exc:
            raise GeminiProviderError(self._friendly_error(exc)) from exc
        raw = response.text or ""
        return AIInspectionResult.from_dict(_extract_json(raw), raw_response=raw)

    def ask(
        self,
        question: str,
        inspection: AIInspectionResult | None = None,
        local_context: dict[str, Any] | None = None,
        image_path: str | Path | None = None,
    ) -> AIChatAnswer:
        type_client, types = self._client_and_types()
        try:
            close = getattr(type_client, "close", None)
            if callable(close):
                close()
        except Exception:
            pass
        contents: list[Any] = []
        if image_path and Path(image_path).is_file():
            path = Path(image_path)
            mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
            contents.append(types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type))
        contents.append(build_chat_prompt(question, inspection.to_dict() if inspection else None, local_context))
        try:
            response = self._generate_with_retry(
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
        except Exception as exc:
            raise GeminiProviderError(self._friendly_error(exc)) from exc
        raw = response.text or ""
        return AIChatAnswer.from_dict(_extract_json(raw), raw_response=raw)

    def _friendly_error(self, exc: Exception) -> str:
        text = str(exc)
        lowered = text.lower()
        if "api key" in lowered or "401" in lowered or "403" in lowered:
            return "کلید API توسط جمنای رد شد یا پروژه مجوز لازم را ندارد. مقدار GEMINI_API_KEY و دسترسی Google AI Studio را بررسی کنید."
        if "404" in lowered and ("model" in lowered or "not_found" in lowered or "no longer available" in lowered):
            return (
                f"The selected Gemini model '{self.model if hasattr(self, 'model') else 'unknown'}' is unavailable. "
                "Select gemini-3.6-flash (recommended) or gemini-3.1-flash-lite and try again."
            )
        if "429" in lowered or "quota" in lowered or "rate" in lowered:
            return "سقف استفاده رایگان جمنای پر شده است. کمی صبر کرده و دوباره تلاش کنید."
        if "failed_precondition" in lowered or "billing" in lowered:
            return "جمنای برای این پروژه یا منطقه بدون فعال‌سازی پرداخت در دسترس نیست. تنظیمات پروژه Google AI Studio و دسترسی منطقه‌ای را بررسی کنید."
        if (
            "timed out" in lowered
            or "timeout" in lowered
            or "connection" in lowered
            or "server disconnected" in lowered
            or "remoteprotocolerror" in lowered
        ):
            return (
                "ارتباط با جمنای پیش از دریافت پاسخ قطع شد. "
                "VisionQC retried automatically, but the cloud review still failed. "
                "Check VPN/proxy/firewall access to Google APIs and try again."
            )
        return f"درخواست جمنای ناموفق بود: {text}"
