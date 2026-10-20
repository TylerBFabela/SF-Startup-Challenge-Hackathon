"""Command-line access to the shared memory, for the Claude Code agents.

    python3 memory/cli.py remember "text to store"
    python3 memory/cli.py recall "what to look up"
    python3 memory/cli.py status | mode on|off | improve | reset

Uses only the standard library, so it starts instantly. The memory service must be running.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory import client  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("remember", help="store a memory")
    r.add_argument("text")
    r.add_argument("--no-wait", action="store_true", help="return immediately; the write finishes in the background")
    q = sub.add_parser("recall", help="look up memories")
    q.add_argument("query")
    sub.add_parser("status")
    m = sub.add_parser("mode")
    m.add_argument("state", choices=["on", "off"])
    sub.add_parser("improve")
    sub.add_parser("reset")
    a = p.parse_args()

    try:
        if a.cmd == "remember":
            out = client.remember(a.text, wait=not a.no_wait)
            if out.get("stored"):
                print("saved to memory")
            elif out.get("queued"):
                print("queued; saving in the background")
            else:
                print("NOT saved:", out.get("error") or out.get("note"))
                return 1
        elif a.cmd == "recall":
            results = client.recall(a.query)
            print("\n".join(f"- {t}" for t in results) if results else "(no relevant memories)")
        elif a.cmd == "status":
            print(client.health())
        elif a.cmd == "mode":
            print(client.set_mode(a.state == "on"))
        elif a.cmd == "improve":
            print(client.improve())
        elif a.cmd == "reset":
            print(client.reset())
    except client.MemoryUnavailable as e:
        print("ERROR:", e)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
