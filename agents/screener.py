"""Screener: scores one candidate at a time against the rubric.

Runs on your machine as a Band remote agent (CrewAI adapter, OpenAI model). It joins the Band room
as "Screener", reads files from data/, recalls the founder's preferences from shared memory, and
hands every scorecard to the Fairness Critic. Start it with scripts/start_screener.sh.
"""
import asyncio
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from band import Agent, Emit, configure_logging
from band.adapters.crewai import CrewAIAdapter, CrewAIAdapterConfig
from band.config import load_agent_config
from memory import client as memory

load_dotenv()
logger = logging.getLogger("screener")

DATA_DIR = (Path(__file__).resolve().parent.parent / "data").resolve()
MAX_FILE_CHARS = 20_000


_recent: dict[tuple[str, str], float] = {}
REPEAT_WINDOW_SECONDS = 45.0
REPEAT_NUDGE = (
    "You already did exactly this a moment ago and have the result in this conversation. "
    "Do not repeat it. Write the scorecard now and send it once with band_send_message."
)


def _is_repeat(tool: str, arg: str) -> bool:
    """True if this exact tool call just happened. Breaks the read/recall loops weaker models fall into."""
    now = time.monotonic()
    key = (tool, arg.strip().lower())
    last = _recent.get(key)
    _recent[key] = now
    return last is not None and now - last < REPEAT_WINDOW_SECONDS


class RecallMemory(BaseModel):
    """Search the hiring desk's long-term memory for the founder's hiring preferences and past decisions."""

    query: str = Field(..., description="What to look up, e.g. 'frontend engineer hiring preferences'")


def recall_memory(args: RecallMemory) -> str:
    if _is_repeat("recall", args.query):
        return REPEAT_NUDGE
    try:
        results = memory.recall(args.query)
    except memory.MemoryUnavailable as e:
        return f"Memory is unavailable right now ({e}). Continue without it and say so."
    return "\n".join(f"- {r}" for r in results) or "(no relevant memories)"


class ReadDataFile(BaseModel):
    """Read a job description, the rubric, or a candidate file from the data folder."""

    path: str = Field(..., description="File path, e.g. 'data/candidates/backend/marcus-bell.md' or 'data/rubric.md'")


def _resolve_data_path(raw: str) -> Path | None:
    """Accept 'data/x.md', 'x.md', './data/x.md' or an absolute path; never anything outside data/."""
    p = raw.strip().replace("\\", "/")
    if p.startswith(str(DATA_DIR) + "/"):
        p = p[len(str(DATA_DIR)) + 1 :]
    p = p.removeprefix("./").removeprefix("data/")
    target = (DATA_DIR / p).resolve()
    if DATA_DIR in target.parents and target.is_file():  # blocks ../ escapes and missing files
        return target
    return None


def read_data_file(args: ReadDataFile) -> str:
    if _is_repeat("read", args.path):
        return REPEAT_NUDGE
    target = _resolve_data_path(args.path)
    if target is None:
        available = sorted(str(f.relative_to(DATA_DIR.parent)) for f in DATA_DIR.rglob("*.md"))
        return f"Error: '{args.path}' is not a file in the data folder. Available files: " + ", ".join(available)
    return target.read_text()[:MAX_FILE_CHARS]


BACKSTORY = """You are the Screener on a three-agent hiring desk for an early-stage startup. The Hiring Lead
sends you one candidate at a time. The Fairness Critic checks every scorecard before it counts.

For each assignment:
1. Use read_data_file to read the job file, data/rubric.md, and the candidate file named in the message.
2. Use recall_memory once, looking up the founder's hiring preferences for this kind of role. If a
   remembered preference applies, use it when you weigh the evidence, and name it in the scorecard.
3. Write a compact scorecard in exactly this shape:
   SCORECARD | <candidate> | <role>
   Skills fit x/5 | Shipped impact x/5 | Ownership x/5 | Total xx/15
   Evidence: 2-3 short bullets, each tied to something written in the candidate file
   Memory used: the remembered preference you applied, or "none"
   Recommendation: advance, hold, or pass, in one line
4. Send the scorecard to the Fairness Critic with band_send_message, mentioning Fairness Critic.
   Do not send it to the Hiring Lead; the Critic forwards it once it is cleared.

If the Fairness Critic sends a scorecard back, fix exactly what it names and send the revised
scorecard to the Fairness Critic again. Keep messages short.

IMPORTANT: send exactly ONE message per assignment. Once band_send_message returns success, your
turn is over: do not call any more tools, and do not send the scorecard again. If a message needs
no answer from you, call band_no_reply once and stop."""


def build_adapter() -> CrewAIAdapter:
    config = CrewAIAdapterConfig(
        model=os.getenv("SCREENER_MODEL", "gpt-6-luna"),  # the SDK's recommended default; gpt-4o-mini looped on sends
        role="Screener",
        goal="Score each candidate fairly against the rubric using only evidence in their file.",
        backstory=BACKSTORY,
        verbose=True,
        max_iter=8,  # default is 20; a scorecard needs about five steps, and this caps OpenAI spend
    )
    return CrewAIAdapter(
        config,
        additional_tools=[(RecallMemory, recall_memory), (ReadDataFile, read_data_file)],
        emit={Emit.TOOL_CALLS},
    )


async def main() -> None:
    configure_logging(root_level="INFO")
    agent_id, api_key = load_agent_config("screener")
    adapter = build_adapter()

    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("BAND_WS_URL", "wss://app.band.ai/api/v1/socket/websocket"),
        rest_url=os.getenv("BAND_REST_URL", "https://app.band.ai"),
    )
    logger.info("Screener starting; data folder: %s", DATA_DIR)
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
