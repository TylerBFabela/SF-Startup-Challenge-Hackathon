# Hiring Desk: an AI hiring team that remembers what you told it

Built for the **SF Startup Challenge Hackathon** (October 20, 2026, AWS Builder Loft) by one person in one afternoon.
Theme: an AI-native startup run by a team of agents, using **Band Desktop** and **Cognee**.

## The problem

A seed-stage founder with no recruiter has to screen dozens of candidates by hand. It is slow, it is inconsistent from
one role to the next, and fast scoring drifts into reasons that are not about the job (age, gaps in a résumé, a
degree used as a stand-in for ability). Worse, every new role starts from zero: the preferences you spelled out last
week are forgotten.

## What it does

Three agents work in one Band room. You post a role. They plan it, screen each candidate, check the reasoning for
fairness, and bring you a ranked shortlist. **You** make the decision. What you decide, and why, goes into long-term
memory, so the next role starts smarter.

| Agent | Runs as | Model | Job |
|---|---|---|---|
| **Hiring Lead** | Claude Code, run by Band Desktop | Claude Sonnet, low effort | Writes the plan on the board, hands out candidates, builds the shortlist, asks the founder to decide |
| **Screener** | Python agent using the Band SDK and CrewAI | OpenAI `gpt-4o-mini` | Reads the job and one candidate, recalls the founder's preferences, writes a scorecard |
| **Fairness Critic** | Claude Code, run by Band Desktop | Claude Sonnet, low effort | Blocks any scorecard whose reasons are not job-related, or that ignores a remembered preference |

Two different harnesses (Claude Code and a Python CrewAI agent) share one Band room.

### How the work flows

1. The founder posts a role in the room.
2. The **Hiring Lead** recalls memory, plans the work, and `@mentions` the **Screener** with one candidate at a time.
3. The **Screener** recalls the founder's preferences, scores the candidate, and hands the scorecard to the
   **Fairness Critic** by `@mention`.
4. The **Critic** either sends it back to the Screener with the exact phrase at fault, or clears it to the Lead. When it
   blocks something, it writes the lesson to memory so the team stops repeating it.
5. The **Lead** posts a ranked shortlist and uses `band ask` to ask the founder to approve or change it.
6. The founder's decision and reason are written to memory.

## How Cognee memory is used

All agents share one Cognee memory through a small local service (`memory/service.py`). It is the only process that
touches Cognee, so Claude Code agents (through `memory/cli.py`) and the Python agent (through `memory/client.py`) read
and write the same store without fighting over its database files.

- **Written during the work:** the founder's decisions and stated reasons (Lead), and fairness lessons the Critic
  learned from blocking a scorecard.
- **Recalled before acting:** the Lead before planning, the Screener before scoring, the Critic before judging. Recalled
  preferences change the scores and the ranking, and the agents name the memory they used.
- **Outside any agent's context:** memory lives in Cognee's on-disk databases, not in a chat history, so a restarted
  agent or a brand-new session reads the same store.
- **Memory on/off switch:** `python3 memory/cli.py mode off` makes recall return nothing for every agent at once. Run
  the same role with memory on and off to see exactly what Cognee changes.
- **Forget:** `python3 memory/cli.py reset` removes everything, using Cognee's `forget`.

## Why Band and Cognee are essential

- Remove **Band** and there is no shared room, no handoffs between a Claude Code agent and a Python agent, no critic
  that can block work, and no point where the human decides.
- Remove **Cognee** and the second role ignores everything you said about the first. The on/off switch above shows it.

## Status

Working prototype. Tested directly: memory write, recall, forget, and the on/off switch; the Screener's live connection
to Band; and the guard that keeps the Screener's file tool inside `data/`. The full multi-agent room run is shown in the
demo video (link added at submission).

## Not used

**Flexprice and Snyk are not integrated.** The agents here read and score text; they do not produce code to scan. A
natural business model is pay per screened candidate, which a usage-billing tool like Flexprice would meter. That is
not built.

## Who it is for

Founders of very early startups who do their own hiring. The pitch is a hiring desk you do not have to staff: consistent
screening, a fairness check built into the process, and a team that learns your taste. All candidates and jobs in this
repo are fictional.

## Run it yourself

You need Band Desktop signed in, Python 3.12, [uv](https://docs.astral.sh/uv/), an OpenAI API key, and a Claude login
for the Claude Code agents (`claude auth login`).

```bash
uv sync
cp .env.example .env                              # then add your OpenAI key (both OPENAI_API_KEY and LLM_API_KEY)
cp agent_config.example.yaml agent_config.yaml    # then add the Screener's Band ID and key
```

1. In the Band web app, go to **Agents**, then **Connect remote agent**, and create the **Screener**. Copy its ID and key
   into `agent_config.yaml`.
2. Create the two Claude Code agents with the Band CLI. Instructions live in `agents/*.md`.

   ```bash
   band agent create --session hiring-lead --name "Hiring Lead" --description "Plans the hiring run and asks the founder to decide." --cwd "$PWD" --transport claude-code-cli --instructions-file agents/hiring_lead.md
   band agent create --session fairness-critic --name "Fairness Critic" --description "Reviews every scorecard and blocks unfair reasoning." --cwd "$PWD" --transport claude-code-cli --instructions-file agents/fairness_critic.md
   ```

3. Start the shared memory and the Screener, each in its own terminal:

   ```bash
   scripts/start_memory.sh
   scripts/start_screener.sh
   ```

4. In Band, create a room, add the three agents, and post:
   `@Hiring Lead New role: Backend Engineer. Job: data/jobs/backend-engineer.md. Candidates are the 5 files in data/candidates/backend/.`

## Repo layout

```
agents/      Lead and Critic instructions (markdown), screener.py (Band + CrewAI agent)
memory/      service.py (Cognee), client.py and cli.py (stdlib only)
data/        fictional jobs, rubric, and candidates for two roles
scripts/     start scripts and a Cognee smoke test
```

Secrets stay in `.env` and `agent_config.yaml`, both gitignored; the `.example` files hold placeholders only.
