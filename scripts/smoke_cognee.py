"""Smoke test: Cognee can remember a fact, recall it, and forget it. Run with `uv run python scripts/smoke_cognee.py`."""
import asyncio
import time

from dotenv import load_dotenv

load_dotenv()

import cognee  # noqa: E402  (after load_dotenv so it sees LLM_API_KEY)

DATASET = "smoke_test"


def show_models() -> None:
    from cognee.infrastructure.llm import get_llm_config

    cfg = get_llm_config()
    print("LLM provider/model:", cfg.llm_provider, "/", cfg.llm_model)
    try:
        from cognee.infrastructure.databases.vector.embeddings.config import get_embedding_config

        emb = get_embedding_config()
        print("Embedding provider/model:", emb.embedding_provider, "/", emb.embedding_model)
    except Exception as e:  # config path differs between versions; not fatal
        print("Embedding config not readable:", type(e).__name__)


async def main() -> None:
    show_models()

    t = time.time()
    await cognee.remember(
        "The founder prefers backend candidates who shipped side projects over candidates with degrees.",
        dataset_name=DATASET,
    )
    print(f"remember: {time.time() - t:.1f}s")

    t = time.time()
    results = await cognee.recall("What does the founder prefer in backend candidates?", datasets=[DATASET])
    print(f"recall: {time.time() - t:.1f}s, {len(results)} result(s)")
    for r in results[:3]:
        print(" -", type(r).__name__, str(r)[:300].replace("\n", " "))

    await cognee.forget(dataset=DATASET)
    print("forget: ok")


if __name__ == "__main__":
    asyncio.run(main())
