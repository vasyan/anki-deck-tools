import json
import logging
from datetime import datetime, date
from typing import Any, Dict, Mapping, Sequence

def _shorten_str(s: str, max_len: int) -> str:
    if len(s) <= max_len:
        return s
    return f"{s[:max_len]}… <len={len(s)}>"

def _shorten_seq(seq: Sequence[Any], max_items: int) -> list[Any]:
    out = list(seq[:max_items])
    if len(seq) > max_items:
        out.append(f"<… {len(seq) - max_items} more items>")
    return out

def prune(obj: Any, max_str: int = 120, max_items: int = 20, keys_to_redact: set[str] = {"audio", "blob", "data"}) -> Any:
    if isinstance(obj, Mapping):
        trimmed: Dict[Any, Any] = {}
        for k, v in obj.items():  # type: ignore
            if isinstance(k, str) and k.lower() in keys_to_redact and isinstance(v, str):
                trimmed[k] = f"<redacted {k} len={len(v)}>"
            else:
                trimmed[k] = prune(v, max_str, max_items, keys_to_redact)
        return trimmed
    if isinstance(obj, str):
        return _shorten_str(obj, max_str)
    if isinstance(obj, (bytes, bytearray)):
        return f"<bytes len={len(obj)}>"
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, set):
        return list(obj)  # type: ignore  # Convert sets to lists for JSON compatibility
    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        return _shorten_seq([prune(v, max_str, max_items, keys_to_redact) for v in obj], max_items)  # type: ignore

    # Handle other non-JSON serializable objects by converting to string
    try:
        json.dumps(obj)
        return obj  # Object is JSON serializable
    except TypeError:
        return f"<{type(obj).__name__}: {str(obj)}>"

def log_json(logger: logging.Logger, payload: Any, **prune_kwargs: Any) -> None:
    pretty = json.dumps(prune(payload, **prune_kwargs), indent=2, ensure_ascii=False)
    logger.debug(pretty)
