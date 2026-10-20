"""Local memory service.

This is the only process that touches Cognee. Claude Code agents (through memory/cli.py) and the
Python Screener (through memory/client.py) all talk to it over HTTP, so they share one memory and
never fight over Cognee's local database files. Start it with scripts/start_memory.sh.
"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

import cognee  # noqa: E402  (after load_dotenv so Cognee sees LLM_API_KEY)
from fastapi import FastAPI  # noqa: E402
from pydantic import BaseModel  # noqa: E402

DATASET = os.getenv("MEMORY_DATASET", "hiring_desk")

state = {"enabled": True, "pending": 0}
write_lock = asyncio.Lock()  # Cognee writes are slow; run them one at a time

app = FastAPI(title="Hiring desk memory")


class Remember(BaseModel):
    text: str
    wait: bool = True


class Recall(BaseModel):
    query: str
    top_k: int = 5


class Mode(BaseModel):
    enabled: bool


async def _write(text: str) -> str | None:
    """Store one memory. Returns an error string, or None on success."""
    async with write_lock:
        try:
            await cognee.remember(text, dataset_name=DATASET)
            return None
        except Exception as e:  # report to the caller instead of crashing the service
            return f"{type(e).__name__}: {e}"[:300]
        finally:
            state["pending"] -= 1


@app.get("/health")
async def health():
    return {"ok": True, "dataset": DATASET, **state}


@app.post("/mode")
async def mode(body: Mode):
    """Switch memory off/on for every agent at once. Used for the with/without-memory comparison."""
    state["enabled"] = body.enabled
    return {"enabled": state["enabled"]}


@app.post("/remember")
async def remember(body: Remember):
    if not state["enabled"]:
        return {"stored": False, "note": "memory is switched off"}
    state["pending"] += 1
    task = asyncio.create_task(_write(body.text))
    if not body.wait:
        return {"stored": False, "queued": True}
    error = await task
    return {"stored": error is None, "error": error}


@app.post("/recall")
async def recall(body: Recall):
    if not state["enabled"]:
        return {"results": [], "note": "memory is switched off"}
    try:
        raw = await cognee.recall(body.query, datasets=[DATASET], top_k=body.top_k)
    except Exception as e:  # e.g. nothing has been remembered yet
        return {"results": [], "note": f"{type(e).__name__}: {str(e)[:200]}"}
    seen, results = set(), []
    for item in raw:
        text = getattr(item, "text", None) or str(item)
        text = " ".join(text.split())[:500]
        if text and text not in seen:
            seen.add(text)
            results.append(text)
    return {"results": results[: body.top_k]}


@app.post("/improve")
async def improve():
    """Let Cognee consolidate and enrich what it has stored (extra-credit feature)."""
    try:
        await cognee.improve(DATASET)
        return {"improved": True}
    except Exception as e:
        return {"improved": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}


@app.post("/reset")
async def reset():
    """Forget everything in the dataset (used to start the demo from a clean slate)."""
    try:
        await cognee.forget(dataset=DATASET)
        return {"reset": True}
    except Exception as e:
        return {"reset": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}
