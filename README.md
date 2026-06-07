# JobMate — Cowork Edition

Same JobMate, **no Anthropic API key required**. All Claude calls run through the local Claude Agent SDK, billed against your existing Claude Code / Cowork login.

## What's Different from the API-Based Build
- ❌ No `ANTHROPIC_API_KEY`, no `.env` for Claude credentials
- ✅ Uses the local Claude Code subprocess via `claude-agent-sdk`
- Same Flask routes, same React frontend, same 4-step pipeline

## Prerequisites
1. **Claude Code installed and logged in.** Run `claude` once in a terminal and complete sign-in. The SDK shells out to this process — if you can't run `claude -p "hello"` from the CLI, the backend won't work.
2. **Node.js** (Claude Code requires it).
3. **Python 3.10+** (the SDK uses modern asyncio).

## Setup

```powershell
# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

```bash
# Mac / Linux
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000.

## File Structure
```
jobmate-cowork/
├── app.py            ← Flask API; calls Claude via claude-agent-sdk
├── requirements.txt
├── static/
│   └── index.html    ← React SPA (identical to the API build)
└── README.md
```

## How Calls Are Routed
Every `/api/*` endpoint that needs Claude calls a `claude(prompt)` helper that:
1. Spawns a one-shot `query()` via the Agent SDK (tools disabled, `max_turns=1`)
2. Streams assistant text blocks back, concatenates them
3. Parses the JSON object out of the response

This is the simplest mapping of the prior `Anthropic().messages.create(...)` pattern onto the local SDK.

## Trade-offs vs. the API Build
| | API build | Cowork build |
|---|---|---|
| Cost per call | Pay-per-token API credits | Folded into your Claude plan |
| Setup | Just an API key | Requires Claude Code login + Node |
| Latency | Direct HTTPS | Adds local subprocess overhead |
| Offline | No | Still no — SDK calls Anthropic via your Claude Code session |
| Streaming UX | Possible | Possible (not wired up here) |

## Troubleshooting
- **"command not found" or hangs on first call** → run `claude` in a terminal, complete login, then retry.
- **JSON parse errors** → the SDK occasionally wraps output. The `claude()` helper already handles ```json``` fences; if it still fails, the model returned prose — re-run.
- **Subprocess slow on first request** → cold start is normal; subsequent calls are faster.
