import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx


logger = logging.getLogger(__name__)

_MODEL_CACHE: dict[tuple[str, str], str] = {}


class AIClientError(RuntimeError):
    pass


class AIClientTimeout(AIClientError):
    pass


class AIClientHTTPError(AIClientError):
    def __init__(self, *, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class GeminiMeta:
    model: str
    latency_ms: int
    status_code: int | None
    retries: int


def _safe_truncate(s: str, n: int = 800) -> str:
    s = s or ""
    if len(s) <= n:
        return s
    return s[:n] + "…"


async def _list_models(
    *,
    api_key: str,
    base_url: str,
    api_version: str,
    timeout_s: float,
) -> list[dict[str, Any]]:
    base = (base_url or "").rstrip("/")
    api_v = (api_version or "v1").strip().lstrip("/")
    url = f"{base}/{api_v}/models"
    headers = {"x-goog-api-key": api_key}
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.get(url, headers=headers)
    if r.status_code >= 400:
        raise AIClientHTTPError(status_code=r.status_code, message=_safe_truncate(r.text, 1000))
    data = r.json() or {}
    return list(data.get("models") or [])


def _pick_best_model(models: list[dict[str, Any]]) -> str | None:
    """
    Prefer a 'flash' model that supports generateContent. Fallback to the first model
    that supports generateContent.
    """
    def supports_generate(m: dict[str, Any]) -> bool:
        methods = m.get("supportedGenerationMethods") or m.get("supported_generation_methods") or []
        return any(str(x).lower().endswith("generatecontent") or str(x) == "generateContent" for x in methods) or (
            # Some responses omit methods; assume generateContent is supported.
            not methods
        )

    candidates = [m for m in models if isinstance(m, dict) and supports_generate(m)]
    if not candidates:
        return None

    # Prefer flash, then 1.5, then anything.
    def score(m: dict[str, Any]) -> tuple[int, int]:
        name = str(m.get("name") or "").lower()
        is_flash = 1 if "flash" in name else 0
        is_15 = 1 if "1.5" in name or "15" in name else 0
        return (is_flash, is_15)

    best = sorted(candidates, key=score, reverse=True)[0]
    name = best.get("name")
    return str(name) if name else None


async def gemini_generate_content(
    *,
    api_key: str,
    base_url: str,
    api_version: str = "v1",
    model: str,
    user_text: str,
    system_text: str | None = None,
    response_mime_type: str = "application/json",
    temperature: float = 0.0,
    timeout_s: float = 20.0,
    max_retries: int = 2,
    log_payloads: bool = False,
) -> tuple[str, GeminiMeta]:
    """
    Calls Gemini Generative Language API (API key auth) and returns the model text.

    Endpoint:
      POST {base_url}/v1beta/models/{model}:generateContent
    Auth:
      x-goog-api-key: {api_key}
    """
    if not api_key:
        raise AIClientError("Missing GEMINI_API_KEY")
    if not model:
        raise AIClientError("Missing GEMINI_MODEL")
    api_v = (api_version or "v1").strip().lstrip("/")
    base = (base_url or "").rstrip("/")
    model_path = model.strip()
    if model_path.startswith("models/"):
        model_path = model_path[len("models/") :]
    url = f"{base}/{api_v}/models/{model_path}:generateContent"

    def _build_body() -> dict[str, Any]:
        """
        Keep payload compatible with Generative Language API v1:
        - Do NOT send systemInstruction (some deployments reject it)
        - Do NOT send responseMimeType (some deployments reject it)
        Instead, inline the system prompt into the user prompt and request JSON in-text.
        """
        effective_user = user_text or ""
        if system_text:
            effective_user = f"{system_text.strip()}\n\n{effective_user}"

        return {
            "contents": [
                {"role": "user", "parts": [{"text": effective_user}]},
            ],
            "generationConfig": {
                "temperature": float(temperature),
            },
        }

    body = _build_body()

    headers = {
        "x-goog-api-key": api_key,
        "content-type": "application/json",
    }

    start = time.perf_counter()
    last_status: int | None = None
    cache_key = (base, api_v)

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                if log_payloads:
                    logger.info(
                        "Gemini request model=%s url=%s body=%s",
                        model,
                        url,
                        _safe_truncate(json.dumps(body, ensure_ascii=False)),
                    )
                r = await client.post(url, json=body, headers=headers)
                last_status = r.status_code

                if r.status_code >= 400:
                    # Model not found: try discover an available model for this key/version and retry once.
                    if r.status_code == 404:
                        msg = (r.text or "")
                        if "not found" in msg.lower() or "not supported" in msg.lower():
                            try:
                                discovered = _MODEL_CACHE.get(cache_key)
                                if not discovered:
                                    models = await _list_models(
                                        api_key=api_key,
                                        base_url=base_url,
                                        api_version=api_v,
                                        timeout_s=timeout_s,
                                    )
                                    discovered = _pick_best_model(models)
                                    if discovered:
                                        _MODEL_CACHE[cache_key] = discovered
                                if discovered:
                                    # discovered may be "models/xxx"
                                    d = discovered
                                    if d.startswith("models/"):
                                        d = d[len("models/") :]
                                    url = f"{base}/{api_v}/models/{d}:generateContent"
                                    logger.warning("Gemini model not found; switching to discovered model=%s", discovered)
                                    r = await client.post(url, json=body, headers=headers)
                                    last_status = r.status_code
                                    if r.status_code < 400:
                                        data = r.json()
                                        text = (
                                            (data.get("candidates") or [{}])[0]
                                            .get("content", {})
                                            .get("parts", [{}])[0]
                                            .get("text", "")
                                        )
                                        meta = GeminiMeta(
                                            model=discovered,
                                            latency_ms=int((time.perf_counter() - start) * 1000),
                                            status_code=r.status_code,
                                            retries=attempt,
                                        )
                                        logger.info(
                                            "Gemini ok model=%s status=%s latency_ms=%s retries=%s",
                                            meta.model,
                                            meta.status_code,
                                            meta.latency_ms,
                                            meta.retries,
                                        )
                                        return (text or "").strip(), meta
                            except Exception as e:
                                logger.warning("Gemini model discovery failed: %s", type(e).__name__)

                    # Retry only on transient server errors / rate limits.
                    if r.status_code in {408, 429, 500, 502, 503, 504} and attempt < max_retries:
                        backoff = 0.5 * (2**attempt)
                        logger.warning("Gemini HTTP %s; retrying in %.1fs", r.status_code, backoff)
                        await asyncio.sleep(backoff)
                        continue
                    raise AIClientHTTPError(status_code=r.status_code, message=_safe_truncate(r.text, 1000))

                data = r.json()
                # Typical shape:
                # { candidates: [ { content: { parts: [ { text: "..." } ] } } ], ... }
                text = (
                    (data.get("candidates") or [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
                meta = GeminiMeta(
                    model=model,
                    latency_ms=int((time.perf_counter() - start) * 1000),
                    status_code=r.status_code,
                    retries=attempt,
                )
                logger.info(
                    "Gemini ok model=%s status=%s latency_ms=%s retries=%s",
                    meta.model,
                    meta.status_code,
                    meta.latency_ms,
                    meta.retries,
                )
                return (text or "").strip(), meta
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout):
            if attempt < max_retries:
                backoff = 0.5 * (2**attempt)
                logger.warning("Gemini timeout; retrying in %.1fs", backoff)
                await asyncio.sleep(backoff)
                continue
            raise AIClientTimeout("Gemini request timed out") from None
        except httpx.RequestError as e:
            if attempt < max_retries:
                backoff = 0.5 * (2**attempt)
                logger.warning("Gemini network error (%s); retrying in %.1fs", type(e).__name__, backoff)
                await asyncio.sleep(backoff)
                continue
            raise AIClientError(f"Gemini request failed: {type(e).__name__}") from e

    # Should be unreachable
    meta = GeminiMeta(model=model, latency_ms=int((time.perf_counter() - start) * 1000), status_code=last_status, retries=max_retries)
    return "", meta

