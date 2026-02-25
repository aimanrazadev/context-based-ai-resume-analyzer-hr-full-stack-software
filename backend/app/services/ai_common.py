import json
import re


_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")


def extract_first_json_object(text: str) -> dict:
    """
    Best-effort extraction of the first JSON object from a model response.
    Handles cases where the model wraps JSON in prose.
    """
    raw = (text or "").strip()
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

