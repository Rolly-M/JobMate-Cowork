# JobMate — Cowork Edition

A personal-use AI job application studio. Upload a resume, paste a job posting URL, and JobMate scores your fit, rewrites your bullets, audits ATS-readiness, generates a tailored resume + cover letter, and exports both to PDF or Word.

All Claude calls run through the **local Claude Agent SDK** — no Anthropic API key needed, folded into your existing Claude Code / Cowork login.

---

## What It Does

### Resume Optimizer (4-step pipeline)
Upload your resume (PDF / DOCX / TXT / MD) and paste a target job description. JobMate runs four sequential analyses and produces a fully tailored resume:

| Step | What it does |
|------|--------------|
| 1 · Score & Gap Analysis | Keyword overlap, skills match, outcomes, role fit. Overall 0–100. Flags missing keywords + identifies strengths. |
| 2 · XYZ Bullet Rewrites | Rewrites every bullet using Google's "accomplished X as measured by Y by doing Z" formula. Under 20 words each, metric-driven. |
| 3 · ATS Audit | Catches parsing failures — pipes, em dashes, columns, non-standard section names, foreign degree recognition, keyword density gaps. |
| 4 · Hiring Manager Review | 10-second skim, identifies weak bullets and exactly what to change to clear 80%. Returns an honest "would I interview" verdict. |

Each completed step **collapses into a one-line summary** when the next runs, so you don't have to scroll past prior results. Click any header to re-expand.

After step 4, JobMate produces the final tailored resume with all changes incorporated, downloadable as **PDF** or **Word (.docx)**.

### Job Discovery
Feeds your (tailored, if available) resume to Claude and gets back 20 best-fit job titles, ranked into three tiers (Best Shot / Strong Match / Stretch), each with a match score, salary band, missing-skills callouts, and LinkedIn / Indeed search links.

### Applications
- Queue jobs from the discovery tab with one click.
- On Apply: **zero input required**. The moment the modal opens, the backend uses Claude's `WebSearch + WebFetch` tools to locate the actual posting for `{title, company, location}` (trying company careers pages first, then LinkedIn / Indeed / Greenhouse / Lever), extracts the JD, and runs the full tailoring + cover-letter pipeline automatically.
- If auto-search fails (no current posting, login wall, etc.) a fallback URL input appears so you can paste the specific posting and retry. Retry without URL is also one click.
- If your resume scores <80 against the fetched JD, you get a warning before continuing.
- Each application gets its own tailored resume version (downloadable as PDF / Word, filename includes the company name).
- Mark applied; queue tracks status (pending / applied / interview / rejected) and counts.

### Privacy
Everything stays on your machine. No accounts, no cloud sync, no telemetry beyond Anthropic's normal Claude Code usage. Resume / JD / queue persist in browser sessionStorage and clear when the tab closes.

---

## Prerequisites

1. **Claude Code installed and logged in.**
   ```bash
   npm install -g @anthropic-ai/claude-code
   claude                  # complete the login flow once
   claude -p "say hello"   # verify
   ```
   If `claude -p "..."` doesn't return text, JobMate's backend won't work — the Agent SDK shells out to this binary.

2. **Node.js** (Claude Code requires it).

3. **Python 3.10+** (the SDK uses modern asyncio).

> **WSL users:** Claude Code on Windows and Claude Code inside WSL are *separate installs*. Whichever environment runs `python app.py` is the one that needs `claude` on its PATH. If `which claude` is empty inside WSL, install + log in inside WSL.

---

## Setup

```bash
# WSL / Linux / Mac
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

```powershell
# Windows native
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000.

The first API call after startup will take ~5–10 seconds while the persistent SDK client connects and warms its cache. Every subsequent call is much faster.

---

## Usage Walkthrough

### Resume tab
1. Drag-and-drop your resume (or click to browse). PDF, DOCX, TXT, MD up to 10 MB. The server extracts text via `pypdf` / `python-docx`.
2. Paste the target job description.
3. Click **Start Analysis**. Steps run sequentially; each result collapses as the next begins.
4. After step 4, JobMate auto-finalizes the resume. Hit **↓ PDF** or **↓ Word** to download.

### Find Jobs tab
1. Set your location (default: Calgary, AB), toggle "Include Remote Canada".
2. Click **Search 20 Roles**.
3. Each card shows match score, tier badge, salary, missing skills, and LinkedIn / Indeed links.
4. Click **+ Queue** to add a role to your application queue.

### Applications tab
1. Click **Apply** on a queued job. One-time ToS warning explains what JobMate does and doesn't do (it doesn't auto-submit applications).
2. The pipeline starts automatically — no input required. Live progress shows: searching for the posting → fetching JD → analyzing fit → writing cover letter → building tailored resume.
3. If auto-search can't find the posting (login walls, expired listings), a fallback URL input appears so you can paste the specific posting and retry. Otherwise you go straight to review.
4. Review the tailored resume + cover letter. Download / copy as needed.
5. Click **Open Posting** to apply manually on the job board, then **Mark Applied** to update the queue.

---

## API Reference

All endpoints accept / return JSON unless noted. No auth.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/resume/upload` | Upload PDF / DOCX / TXT / MD (multipart `file`). Returns extracted text + word count. |
| POST | `/api/analyze` | Step 1: score + gap analysis. Body: `{resume, jobDescription}`. |
| POST | `/api/tailor/bullets` | Step 2: XYZ bullet rewrites. |
| POST | `/api/tailor/ats` | Step 3: ATS audit. Body: `{resume}`. |
| POST | `/api/tailor/hm-review` | Step 4: hiring manager review. |
| POST | `/api/tailor/finalize` | Produce full tailored resume incorporating all fixes. |
| POST | `/api/jobs/search` | Find 20 best-fit roles. Body: `{resume, location, includeRemote}`. |
| POST | `/api/jobs/fetch-description` | Locate a posting and extract its JD. Accepts either `{url}` (direct WebFetch) or `{job: {title, company, location}}` (WebSearch + WebFetch). Returns `{company, role, location, postingUrl, jobDescription, fetchOk, note}`. |
| POST | `/api/cover-letter` | Generate a tailored cover letter. |
| POST | `/api/apply/extract-fields` | Given form-field labels, return what can be auto-filled vs. what needs user input. |
| POST | `/api/export/pdf` | Render plain text → PDF. Body: `{text, filename}`. Returns the file as a download. |
| POST | `/api/export/docx` | Render plain text → Word document. |
| GET | `/` | Serves the React SPA. |

All Claude-backed endpoints return JSON errors with status 4xx/5xx when something fails. The frontend surfaces these as toasts.

---

## Architecture

```
┌─────────────────────┐
│  React SPA          │  Single index.html with React 18 + Babel-standalone
│  (Tailwind 2.2.19,  │  Tabs: Resume / Jobs / Applications
│   Inter + Space     │  sessionStorage persistence
│   Grotesk)          │
└──────────┬──────────┘
           │ fetch /api/*
           ▼
┌─────────────────────┐
│  Flask (sync)       │  app.py
│  + flask-cors       │  Global JSON error handler
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────────┐
│  Background asyncio loop (dedicated thread) │
│  ┌──────────────────────────────────────┐   │
│  │  one persistent ClaudeSDKClient      │   │
│  │  (allowed_tools=[], system_prompt)   │   │
│  └──────────────────────────────────────┘   │
└──────────┬──────────────────────────────────┘
           │ subprocess
           ▼
        claude CLI  ──►  Anthropic
```

### Why a persistent client
The first run of `claude` paid ~11 500 tokens of cache creation (Claude Code's tools, system prompt, etc.) per call when we used one-shot `query()`. A persistent `ClaudeSDKClient` reuses that cache across every Flask request, dropping cost-per-call by roughly 10× after the first warm-up.

The trade-off: history accumulates inside the persistent session. JobMate prompts are self-contained (each one includes the full resume + JD), so cross-contamination is unlikely, but input tokens slowly grow. **Restart Flask to reset.**

### Why an ephemeral `query()` for URL fetch
`/api/jobs/fetch-description` needs the `WebFetch` tool enabled, but enabling it on the long-lived client would change its options scope for every other call. We use a short-lived `query()` for that one endpoint — pays the cache-creation cost once per fetch, keeps the persistent client text-only.

### Concurrency
The Flask dev server is threaded. Concurrent requests serialize through a `_request_lock` because a single `ClaudeSDKClient` can only handle one in-flight query at a time. Practical effect: if you trigger two pipelines simultaneously, the second waits.

---

## File Structure

```
jobmate-cowork/
├── app.py            ← Flask routes, persistent SDK client, file extractors, export builders
├── requirements.txt
├── test_sdk.py       ← Standalone diagnostic for the SDK (run from WSL venv)
├── static/
│   └── index.html    ← Full React SPA (no build step)
├── .gitignore
└── README.md
```

---

## Cost & Performance Notes

- **First request after startup:** ~5–10 s. The SDK subprocess boots and pays ~11 k tokens of cache creation (one-time per Flask process).
- **Every subsequent request:** typically <3 s, with input tokens read from cache (≈10× cheaper than fresh).
- **Full 4-step pipeline:** ~5 Claude calls. Empirically ~$0.10–$0.15 once warmed, depending on resume / JD length.
- **URL fetch (`/api/jobs/fetch-description`):** pays its own ~$0.04 cache-creation overhead because it uses a separate ephemeral subprocess with WebFetch enabled.
- **Rate limits:** Overage is set to `org_level_disabled` on the account, so hitting the 5-hour Claude limit fails the call rather than auto-billing. Wait for the reset; the diagnostic output and any failed call show `resetsAt`.

---

## Known Limitations

- **Auto-search isn't perfect.** The Apply flow uses `WebSearch + WebFetch` to locate the actual posting given `{title, company, location}`. It usually succeeds for company careers pages and simple ATSes (Lever, Greenhouse, Workday). LinkedIn / Indeed are hit-and-miss — both heavily JS-render and gate content behind login. When auto-search fails, the modal exposes a URL-paste fallback so you can point it at the specific posting and retry.
- **`.doc` exports are actually `.docx`.** Modern Word, Pages, Google Docs all open `.docx` natively; writing real binary `.doc` from Python is a rabbit hole.
- **PDF fonts are latin-1.** Anything outside that range becomes `?`. The tailored-resume prompt enforces plain ASCII bullets, so this is rarely visible.
- **No persistent storage.** Resume, queue, and tailored output live in browser sessionStorage and disappear when the tab closes.
- **No streaming UX.** Each Claude call is request/response, not streamed to the UI. Pipeline progress is shown via shimmer bars + stage labels.
- **Single user.** No auth, no multi-user separation. Designed for `localhost`.

---

## Diagnostics

`test_sdk.py` is a standalone script that bypasses Flask entirely. Run it whenever you want to confirm the SDK pipeline is healthy:

```bash
source venv/bin/activate
python test_sdk.py
```

It makes two calls on one `ClaudeSDKClient` and prints token usage for each. Healthy output shows:
- Call 1: `cache_creation: ~11000`, full input cost
- Call 2: `cache_read: ~11000`, `cache_creation: ~0`, dramatically lower cost

If call 1 fails, the issue is almost always: `claude` CLI not installed / not logged in on the PATH visible to Python.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `Claude Code returned an error result: success` | Mismatched SDK options (e.g. an obsolete `max_turns=1`). Update `claude-agent-sdk` and reinstall. |
| `FileNotFoundError: claude` on first call | `claude` CLI not on PATH in the env running Python. `which claude` should return a path. |
| `command not found: claude` in PowerShell, but Flask runs under WSL | Different envs. Install + log in inside WSL. |
| 500 from `/api/jobs/fetch-description` | The posting page blocked WebFetch (login wall, Cloudflare). Try a direct ATS URL or fall back to running the resume pipeline manually in the Resume tab. |
| PDF export shows `?` characters | Non-ASCII characters in the tailored resume — usually em dashes or smart quotes. Open the file, re-run the finalize step, or paste through a plain-text editor first. |
| Slow first request after restart | Normal — paying the one-time cache-creation cost as the persistent client warms up. |
| Conversation feels "polluted" / model references prior runs | History accumulates on the persistent client over the Flask process's lifetime. Restart `python app.py` to reset. |

---

## Dependencies

- **Flask 3.x** + **flask-cors** — HTTP server, CORS for the local SPA
- **claude-agent-sdk** — talks to local Claude Code subprocess
- **pypdf** — extracts text from uploaded PDF resumes
- **python-docx** — reads uploaded `.docx` resumes, writes exported `.docx` files
- **fpdf2** — generates PDF exports of the tailored resume

The frontend uses React 18, Babel-standalone, Tailwind 2.2.19, and Inter + Space Grotesk from Google Fonts, all loaded via CDN. No build step.
