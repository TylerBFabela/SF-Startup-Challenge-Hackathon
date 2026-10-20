"""Screener: scores one candidate at a time against the rubric.

Runs on your machine as a Band remote agent (CrewAI adapter, OpenAI model). It joins the Band room
as "Screener", reads files from data/, recalls the founder's preferences from shared memory, and
hands every scorecard to the Fairness Critic. Start it with scripts/start_screener.sh.
"""
import asyncio
import logging
import os
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


class RecallMemory(BaseModel):
    """Search the hiring desk's long-term memory for the founder's hiring preferences and past decisions."""

    query: str = Field(..., description="What to look up, e.g. 'frontend engineer hiring preferences'")


def recall_memory(args: RecallMemory) -> str:
    try:
        results = memory.recall(args.query)
    except memory.MemoryUnavailable as e:
        return f"Memory is unavailable right now ({e}). Continue without it and say so."
    return "\n".join(f"- {r}" for r in results) or "(no relevant memories)"


class ReadDataFile(BaseModel):
    """Read a job description, the rubric, or a candidate file from the data folder."""

    path: str = Field(..., description="Path relative to the data folder, e.g. 'candidates/backend/marcus-bell.md'")


def read_data_file(args: ReadDataFile) -> str:
    target = (DATA_DIR / args.path).resolve()
    if DATA_DIR not in target.parents or not target.is_file():  # blocks ../ escapes and missing files
        return f"Error: '{args.path}' is not a file inside the data folder."
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
scorecard to the Fairness Critic again. Keep messages short."""


def build_adapter() -> CrewAIAdapter:
    config = CrewAIAdapterConfig(
        model=os.getenv("SCREENER_MODEL", "gpt-4o-mini"),
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
