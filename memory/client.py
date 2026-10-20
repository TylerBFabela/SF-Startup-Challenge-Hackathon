"""Tiny HTTP client for the memory service. Standard library only, so it imports instantly."""
import json
import os
import urllib.error
import urllib.request

BASE_URL = os.getenv("MEMORY_URL", "http://127.0.0.1:8765")


class MemoryUnavailable(RuntimeError):
    pass


def _call(path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise MemoryUnavailable(
            f"memory service not reachable at {BASE_URL} ({e}). Start it with scripts/start_memory.sh"
        ) from e


def health() -> dict:
    return _call("/health")


def remember(text: str, wait: bool = True) -> dict:
    return _call("/remember", {"text": text, "wait": wait}, timeout=240)


def recall(query: str, top_k: int = 5) -> list[str]:
    return _call("/recall", {"query": query, "top_k": top_k}, timeout=90).get("results", [])


def set_mode(enabled: bool) -> dict:
    return _call("/mode", {"enabled": enabled})


def improve() -> dict:
    return _call("/improve", {}, timeout=240)


def reset() -> dict:
    return _call("/reset", {}, timeout=120)
