"""
JobMate (Cowork edition) — Flask API backed by the local Claude Agent SDK
Run: python app.py
Requires: pip install -r requirements.txt
Auth: uses your local Claude Code login — no ANTHROPIC_API_KEY needed.
"""

import asyncio
import io
import json
import os
import re

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import AssistantMessage, TextBlock

app = Flask(__name__, static_folder="static")
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload cap

SYSTEM_PROMPT = (
    "You are a senior career coach and ATS specialist. "
    "When the user asks for JSON, return ONLY a single valid JSON object — "
    "no prose, no markdown fences, no commentary."
)

# ── Claude helper ────────────────────────────────────────────────────────────

async def _ask(prompt: str) -> str:
    """Run one prompt through the local Claude Agent SDK and concat assistant text."""
    options = ClaudeAgentOptions(
        allowed_tools=[],        # text only — no Read/Write/Bash, no tool loops
        max_turns=1,
        system_prompt=SYSTEM_PROMPT,
    )
    out = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    out.append(block.text)
    return "".join(out)


def claude(prompt: str, max_tokens: int = 2500) -> dict:
    """Call Claude (local) and parse the JSON block from the response.

    `max_tokens` is kept for signature compatibility with the prior API-based
    version but is unused — the SDK manages its own output limits.
    """
    text = asyncio.run(_ask(prompt))
    match = re.search(r"```json\s*(.*?)```", text, re.DOTALL) or re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return json.loads(text)


# ── File extractors ──────────────────────────────────────────────────────────

def extract_pdf(stream: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(stream))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def extract_docx(stream: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(stream))
    parts = [p.text for p in doc.paragraphs if p.text]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text:
                    parts.append(cell.text)
    return "\n".join(parts).strip()


# ── Resume upload ────────────────────────────────────────────────────────────

@app.route("/api/resume/upload", methods=["POST"])
def upload_resume():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    name = f.filename.lower()
    data = f.read()

    try:
        if name.endswith(".pdf"):
            text = extract_pdf(data)
        elif name.endswith(".docx"):
            text = extract_docx(data)
        elif name.endswith((".txt", ".md")):
            text = data.decode("utf-8", errors="ignore").strip()
        else:
            return jsonify({"error": "Unsupported format. Use PDF, DOCX, TXT, or MD."}), 415
    except Exception as e:
        return jsonify({"error": f"Could not parse {f.filename}: {e}"}), 422

    if not text or len(text) < 50:
        return jsonify({"error": "Extracted text is too short — file may be image-only or empty."}), 422

    return jsonify({
        "filename": f.filename,
        "text": text,
        "wordCount": len(text.split()),
        "charCount": len(text),
    })


# ── Step 1: Score & gap analysis ─────────────────────────────────────────────

@app.route("/api/analyze", methods=["POST"])
def analyze():
    d = request.json
    resume, jd = d.get("resume", ""), d.get("jobDescription", "")
    if not resume or not jd:
        return jsonify({"error": "Resume and job description are required"}), 400

    result = claude(f"""
You are a senior recruiter and ATS specialist. Analyze this resume against the job description.

RESUME:
{resume}

JOB DESCRIPTION:
{jd}

Return ONLY valid JSON (no prose) matching this schema exactly:
{{
  "scores": {{
    "keywordOverlap": <int 0-100>,
    "skillsMatch": <int 0-100>,
    "outcomes": <int 0-100>,
    "roleFit": <int 0-100>,
    "overall": <int 0-100>
  }},
  "missingKeywords": ["string"],
  "weakBullets": [
    {{"original": "string", "issue": "string", "suggestion": "string"}}
  ],
  "atsIssues": [
    {{"section": "string", "issue": "string", "fix": "string"}}
  ],
  "gaps": ["string"],
  "strengths": ["string"],
  "summary": "string",
  "wouldInterview": true,
  "interviewReason": "string"
}}
""")
    return jsonify(result)


# ── Step 2: Rewrite bullets (XYZ formula) ────────────────────────────────────

@app.route("/api/tailor/bullets", methods=["POST"])
def tailor_bullets():
    d = request.json
    resume, jd = d.get("resume", ""), d.get("jobDescription", "")

    result = claude(f"""
You are a senior career coach. Rewrite every bullet point using Google's XYZ formula:
"Accomplished X as measured by Y by doing Z."
Rules: under 20 words, metric-driven, use the JD's exact language, no invented numbers.
Flag estimates with "(approx.)".

RESUME: {resume}
JOB DESCRIPTION: {jd}

Return ONLY valid JSON:
{{
  "rewrites": [
    {{"original": "string", "rewritten": "string", "formula": "X / Y / Z breakdown"}}
  ]
}}
""")
    return jsonify(result)


# ── Step 3: ATS audit & fixes ─────────────────────────────────────────────────

@app.route("/api/tailor/ats", methods=["POST"])
def tailor_ats():
    d = request.json
    resume = d.get("resume", "")

    result = claude(f"""
You are an ATS expert. Audit this resume for parsing failures.
Check: special characters (pipes, em dashes), column layouts, header/footer content,
skills section formatting, non-standard section names, foreign degree recognition,
keyword density gaps.

RESUME: {resume}

Return ONLY valid JSON:
{{
  "issues": [
    {{
      "severity": "critical|warning",
      "section": "string",
      "problem": "string",
      "fix": "string",
      "before": "string",
      "after": "string"
    }}
  ],
  "overallAtsScore": <int 0-100>,
  "summary": "string"
}}
""")
    return jsonify(result)


# ── Step 4: Hiring manager review ─────────────────────────────────────────────

@app.route("/api/tailor/hm-review", methods=["POST"])
def hm_review():
    d = request.json
    resume, jd = d.get("resume", ""), d.get("jobDescription", "")

    result = claude(f"""
Act as a hiring manager skimming this resume for 10 seconds against the job description.
Score on keyword overlap, skills, outcomes, and role fit.
Identify weak bullets, missing high-priority terms, and exactly what to change to reach 80%.
State honestly whether you would interview this candidate.

RESUME: {resume}
JOB DESCRIPTION: {jd}

Return ONLY valid JSON:
{{
  "scores": {{
    "keywordOverlap": <int>,
    "skillsMatch": <int>,
    "outcomes": <int>,
    "roleFit": <int>,
    "overall": <int>
  }},
  "missingTerms": [{{"term": "string", "priority": "high|medium", "fix": "string"}}],
  "weakBullets": [{{"bullet": "string", "problem": "string", "rewrite": "string"}}],
  "changesToClear80": ["string"],
  "wouldInterview": true,
  "interviewReason": "string",
  "topStrength": "string",
  "topConcern": "string"
}}
""")
    return jsonify(result)


# ── Step 4b: Produce final tailored resume ────────────────────────────────────

@app.route("/api/tailor/finalize", methods=["POST"])
def finalize():
    d = request.json
    resume, jd = d.get("resume", ""), d.get("jobDescription", "")

    result = claude(f"""
You are a senior career coach. Produce the complete optimized resume, incorporating:
- XYZ formula bullets
- ATS-safe formatting (no pipes, no em dashes, plain ASCII bullets)
- JD keyword alignment
- NIST/framework alignment where applicable
- All fixes from prior audit steps

RESUME: {resume}
JOB DESCRIPTION: {jd}

Return ONLY valid JSON:
{{
  "tailoredResume": "full resume as plain text",
  "changesSummary": ["string"],
  "finalScore": <int 0-100>
}}
""")
    return jsonify(result)


# ── Job search ────────────────────────────────────────────────────────────────

@app.route("/api/jobs/search", methods=["POST"])
def search_jobs():
    d = request.json
    resume = d.get("resume", "")
    location = d.get("location", "Calgary, AB")
    remote = d.get("includeRemote", True)

    result = claude(f"""
Based on this resume, identify the 20 best-fit job roles to target.
Consider experience level, skills, certifications, and location ({location}).
{"Include remote-friendly roles across Canada." if remote else ""}

RESUME: {resume}

Return ONLY valid JSON:
{{
  "jobs": [
    {{
      "id": "unique_string",
      "title": "string",
      "company": "string",
      "location": "string",
      "matchScore": <int 0-100>,
      "tier": <1|2|3>,
      "tierLabel": "Best Shot|Strong Match|Stretch",
      "reason": "string",
      "missingSkills": ["string"],
      "salary": "string",
      "linkedinUrl": "https://ca.linkedin.com/jobs/search/?keywords=...",
      "indeedUrl": "https://ca.indeed.com/q-...",
      "requiresCoverLetter": true
    }}
  ]
}}
""")
    return jsonify(result)


# ── Cover letter ──────────────────────────────────────────────────────────────

@app.route("/api/cover-letter", methods=["POST"])
def cover_letter():
    d = request.json
    resume = d.get("resume", "")
    jd = d.get("jobDescription", "")
    company = d.get("company", "the company")
    role = d.get("role", "this role")
    user_name = d.get("userName", "Candidate")

    result = claude(f"""
Write a compelling, personalized cover letter for {user_name} applying to {role} at {company}.

Rules:
- 3 paragraphs, under 350 words
- Lead with the strongest metric from the resume
- Name at least 2 specific tools/frameworks from the JD
- Second paragraph: connect 2-3 experience highlights to JD requirements
- Third paragraph: mention Calgary base, availability, enthusiasm
- Professional but not robotic

RESUME: {resume}
JOB DESCRIPTION: {jd}

Return ONLY valid JSON:
{{
  "coverLetter": "full letter text with \\n line breaks",
  "wordCount": <int>,
  "keyToolsNamed": ["string"]
}}
""")
    return jsonify(result)


# ── Application form helper ───────────────────────────────────────────────────

@app.route("/api/apply/extract-fields", methods=["POST"])
def extract_fields():
    d = request.json
    resume = d.get("resume", "")
    form_fields = d.get("formFields", [])

    result = claude(f"""
Given this resume and a list of job application form fields, determine what can be
auto-filled and what the user must answer manually.

RESUME: {resume}

FORM FIELDS: {json.dumps(form_fields)}

Return ONLY valid JSON:
{{
  "autoFilled": [
    {{"field": "string", "value": "string", "confidence": "high|medium|low"}}
  ],
  "needsUserInput": [
    {{"field": "string", "question": "How should I phrase this for you?", "type": "text|select|yesno", "options": []}}
  ]
}}
""")
    return jsonify(result)


# ── Serve frontend ────────────────────────────────────────────────────────────

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    print("JobMate (Cowork) running → http://localhost:5000")
    print("Backed by your local Claude Code login. No API key required.")
    app.run(debug=True, port=5000)
