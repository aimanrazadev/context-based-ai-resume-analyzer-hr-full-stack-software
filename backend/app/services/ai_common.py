import json
import re


_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")
_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _clean_model_json_text(text: str) -> str:
    raw = (text or "").strip()
    fenced = _FENCED_JSON_RE.search(raw)
    if fenced:
        raw = fenced.group(1).strip()
    return raw


def extract_first_json_object(text: str) -> dict:
    """
    Extract the first JSON object from a model response.

    Args:
        text: Raw model output that may be pure JSON or JSON wrapped in prose.

    Returns:
        The first parsed JSON object found in the response.

    Side Effects:
        None.

    Error Handling:
        Raises ValueError when the response is empty, contains no JSON object,
        or does not decode to a dictionary.
    """
    raw = _clean_model_json_text(text)
    if not raw:
        raise ValueError("Empty AI response")

    # Fast path: pure JSON
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Heuristic: take first {...} block
    m = _JSON_OBJECT_RE.search(raw)
    if not m:
        raise ValueError("No JSON object found in AI response")
    chunk = m.group(0)
    obj = json.loads(chunk)
    if not isinstance(obj, dict):
        raise ValueError("AI response JSON is not an object")
    return obj
