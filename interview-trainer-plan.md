# AI-Powered Interview Trainer — Implementation Plan

> IBM SkillsBuild AICTE 2026 · Problem Statement #22  
> Status: Awaiting approval

---

## Top-Level Overview

Build a browser-based AI Interview Trainer that takes a user's job role, experience level, and skills, then conducts a mock interview session. Three lightweight agents (Orchestrator, Question Generator, Answer Evaluator) collaborate via a Python FastAPI backend. IBM Granite (via watsonx.ai REST API) powers all LLM calls. A small local RAG knowledge base (ChromaDB + sentence-transformers) provides grounded interview context. The frontend is plain HTML/CSS/JavaScript — no heavy frameworks — keeping complexity and Bob-credit usage minimal.

**Not used:** IBM watsonx Orchestrate. Rationale: Orchestrate is an enterprise product that requires separate provisioning, adds significant setup overhead, and is not required by Problem Statement #22. The agentic behaviour is demonstrated entirely in Python by having agents call each other in a defined workflow, which is fully sufficient for the problem statement.

---

## Architecture

```
Browser (HTML/JS)
      │  REST (fetch)
      ▼
FastAPI Backend (Python)
      │
      ├── Orchestrator Agent
      │         ├── calls → Question Generation Agent
      │         └── calls → Answer Evaluation Agent
      │
      ├── RAG Module (ChromaDB + sentence-transformers)
      │         └── knowledge_base/ (JSON/txt files)
      │
      └── Granite LLM Client
                └── IBM watsonx.ai REST API
```

---

## Problem Statement #22 Compliance

| Requirement | How it is met |
|---|---|
| IBM Granite | All LLM calls use `ibm/granite-13b-instruct-v2` via watsonx.ai |
| RAG | ChromaDB retrieves relevant interview context before every LLM call |
| Agentic AI | Three explicit agents with defined roles, inputs, and outputs |
| Web Application | FastAPI + HTML/JS frontend |
| Technical + HR questions | Question Generation Agent creates both types |
| User profile (role, exp, skills) | Collected on the setup page, passed through all agents |
| Answer evaluation | Answer Evaluation Agent scores and gives improvement suggestions |
| Final report | PDF-ready HTML report page with scores, feedback, and summary |

---

## Technology Stack

| Layer | Choice | Reason |
|---|---|---|
| LLM | IBM Granite via watsonx.ai REST API | Required by problem statement |
| Vector DB | ChromaDB (local, in-memory) | Zero-config, no server needed |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Small, fast, runs on CPU |
| Backend | Python 3.11 + FastAPI | Lightweight, async-friendly |
| Frontend | HTML5 + Vanilla JS + CSS | No build step, simple to deploy |
| Report | HTML page with print-to-PDF | No extra library needed |
| Env config | `python-dotenv` | Standard practice |

### Python dependencies (requirements.txt)
```
fastapi
uvicorn[standard]
python-dotenv
chromadb
sentence-transformers
requests
pydantic
```

---

## Folder Structure

```
AI-Interview-Trainer/
├── backend/
│   ├── main.py                  # FastAPI app, all API routes
│   ├── agents/
│   │   ├── orchestrator.py      # Interview Orchestrator Agent
│   │   ├── question_agent.py    # Question Generation Agent
│   │   └── evaluation_agent.py  # Answer Evaluation Agent
│   ├── rag/
│   │   ├── loader.py            # Loads knowledge base into ChromaDB
│   │   └── retriever.py         # Semantic search helper
│   ├── llm/
│   │   └── granite_client.py    # Wrapper for watsonx.ai REST API
│   └── knowledge_base/
│       ├── technical.json       # Technical interview Q&A patterns
│       ├── behavioral.json      # STAR-method behavioral questions
│       ├── hr.json              # HR/salary/culture questions
│       └── roles.json           # Role-specific hints (SWE, DS, PM, etc.)
├── frontend/
│   ├── index.html               # Landing / setup page
│   ├── interview.html           # Live interview page
│   ├── report.html              # Final report page
│   ├── style.css                # Shared styles
│   └── app.js                   # All client-side JS
├── .env.example                 # Template for API keys
├── requirements.txt
└── README.md
```

---

## Knowledge Base Design

Four small JSON files, each containing 15-25 entries. Each entry has:
- `id` — unique string
- `category` — "technical" | "behavioral" | "hr" | "role-specific"
- `topic` — e.g. "arrays", "leadership", "salary negotiation", "data-scientist"
- `content` — the chunk of text that gets embedded and retrieved

Total: ~80 chunks. This is intentionally small to keep ChromaDB fast and memory usage low.

---

## Frontend Pages

### Page 1 — `index.html` (Setup)
- Form: Job Role (text), Experience Level (dropdown: Fresher/1-3yr/3-5yr/5yr+), Skills (comma-separated tags)
- Number of questions slider (5–10, default 7)
- Interview type checkboxes: Technical / Behavioral / HR
- "Start Interview" button → POST /api/start → redirects to interview.html

### Page 2 — `interview.html` (Live Interview)
- Progress bar (Question X of N)
- Question display panel (role + category badge)
- Text area for user's answer
- "Submit Answer" button → POST /api/answer
- "Next Question" button (appears after evaluation)
- Inline feedback panel: score badge (1-10), strengths, improvement tip
- "Finish Interview" button (appears on last question) → GET /api/report

### Page 3 — `report.html` (Final Report)
- Candidate summary card (name optional, role, experience, skills)
- Overall score (average of all question scores) with colour-coded badge
- Per-question table: question, answer excerpt, score, key feedback
- Category breakdown (Technical avg, Behavioral avg, HR avg)
- Top 3 strengths + Top 3 areas to improve
- "Download / Print Report" button (browser print dialog)

---

## Backend API

All routes in `backend/main.py`. Session state stored in a Python dict keyed by `session_id` (a UUID). No database needed.

| Method | Route | Request | Response |
|---|---|---|---|
| POST | `/api/start` | `{role, experience, skills, num_questions, types}` | `{session_id, first_question}` |
| POST | `/api/answer` | `{session_id, answer}` | `{score, feedback, strengths, next_question or null}` |
| GET | `/api/report/{session_id}` | — | Full report JSON |
| GET | `/health` | — | `{status: "ok"}` |

---

## Agent Responsibilities

### 1. Interview Orchestrator Agent (`orchestrator.py`)
**Role:** Coordinates the full interview session. It is the only agent the API routes talk to.

Responsibilities:
- Receive user profile (role, experience, skills, types, num_questions)
- Delegate to Question Generation Agent to create the question list upfront
- Track which question the user is on
- Receive each answer, delegate to Answer Evaluation Agent
- Collect all scores and feedback
- Assemble the final report object

**Does NOT:** Call the LLM directly. Calls the other two agents.

---

### 2. Question Generation Agent (`question_agent.py`)
**Role:** Generate a personalised question list using RAG + Granite.

Workflow per call:
1. Receive user profile
2. Query RAG retriever with `"{role} {skills} {type} interview questions"` → top 5 chunks
3. Build a prompt: system instruction + retrieved context + user profile
4. Call Granite → parse N questions with category tags
5. Return structured list: `[{id, text, category, difficulty}]`

---

### 3. Answer Evaluation Agent (`evaluation_agent.py`)
**Role:** Score and give feedback on a single answer.

Workflow per call:
1. Receive question + user answer + user profile
2. Query RAG retriever with the question text → top 3 chunks (ideal answer patterns)
3. Build evaluation prompt: question + answer + retrieved context
4. Call Granite → parse: score (1-10), strengths (list), improvement (string)
5. Return structured evaluation object

---

## RAG Workflow

```
App Start
  └── loader.py reads all 4 JSON files
  └── sentence-transformers embeds each chunk
  └── ChromaDB stores embeddings in memory

Per Agent Call
  └── retriever.py: embed the query string
  └── ChromaDB cosine similarity search → top-K chunks
  └── Chunks injected into LLM prompt as "Context"
```

The RAG module is initialised once when FastAPI starts (`@app.on_event("startup")`). No re-loading needed during a session.

---

## IBM Granite Integration

File: `backend/llm/granite_client.py`

- Uses the watsonx.ai `/ml/v1/text/generation` REST endpoint
- Auth: Bearer token from `WATSONX_API_KEY` + `WATSONX_PROJECT_ID` (loaded from `.env`)
- Model: `ibm/granite-3-8b-instruct`
- Parameters: `max_new_tokens=512`, `temperature=0.7`
- Single function: `generate(prompt: str) -> str`
- All prompt building happens in the agent files, not in this client

### .env.example
```
WATSONX_API_KEY=your_api_key_here
WATSONX_PROJECT_ID=your_project_id_here
WATSONX_URL=https://us-south.ml.cloud.ibm.com
```

---

## Interview Workflow (Step by Step)

```
1. User fills setup form → POST /api/start
2. Orchestrator creates session, calls Question Generation Agent
3. Question Generation Agent: RAG query → Granite → returns question list
4. Orchestrator stores list, returns question[0] to browser
5. User reads question, types answer → POST /api/answer
6. Orchestrator calls Answer Evaluation Agent with question + answer
7. Answer Evaluation Agent: RAG query → Granite → returns score + feedback
8. Orchestrator stores result, returns feedback + next question to browser
9. Steps 5-8 repeat until all questions answered
10. User clicks "Finish" → GET /api/report/{session_id}
11. Orchestrator assembles report object → browser renders report.html
```

---

## Evaluation / Scoring Workflow

The Answer Evaluation Agent instructs Granite to return a **structured JSON block** inside its response:

```
{
  "score": 7,
  "strengths": ["Clear communication", "Mentioned STAR method"],
  "improvement": "Add a specific metric or outcome to strengthen the example."
}
```

The agent uses a regex to extract this JSON block from Granite's raw text response, making parsing reliable even if Granite adds surrounding prose.

**Score rubric injected into the prompt:**
- 1-3: Off-topic or very incomplete
- 4-6: Partially correct, missing key elements
- 7-8: Good answer, minor gaps
- 9-10: Excellent, specific, well-structured

---

## Testing Plan

Three lightweight test scripts in a `tests/` folder (plain Python, no test framework needed for the demo):

1. `tests/test_rag.py` — loads knowledge base, runs a sample query, prints top-3 results
2. `tests/test_granite.py` — sends a single prompt to Granite, prints the response
3. `tests/test_agents.py` — runs a full mock session end-to-end (no browser), prints all outputs

These scripts are run manually before the final demo to verify each layer works independently.

---

## GitHub Structure

```
AI-Interview-Trainer/
├── .gitignore          # excludes .env, __pycache__, chroma_db/
├── .env.example        # committed; .env is NOT committed
├── README.md           # Setup instructions, architecture diagram, screenshots
├── requirements.txt
├── backend/
├── frontend/
└── tests/
```

**README.md sections:**
1. Project Overview
2. Problem Statement #22 mapping
3. Architecture diagram (ASCII or image)
4. Setup Instructions (pip install, .env config, uvicorn run)
5. Demo Screenshots

---

## Eight Screenshots for Final PPT

| # | Screen | What it demonstrates |
|---|---|---|
| 1 | Setup page with form filled in | User profile input, entry point |
| 2 | First question displayed (Technical) | Question Generation Agent + RAG working |
| 3 | User typing an answer in the text area | Live interview UX |
| 4 | Feedback panel after answer submission | Answer Evaluation Agent scoring |
| 5 | Mid-interview progress (question 3 of 5) | Orchestrator managing state |
| 6 | A behavioral question with STAR-method hint | RAG retrieving behavioral context |
| 7 | Final report page — overall score + table | Report generation |
| 8 | Terminal showing Granite API call + response | Technical depth / Granite proof |

---

## Sub-Tasks

---

### Sub-Task 1 — Project Scaffold & Configuration
**Intent:** Create the folder structure, requirements.txt, .env.example, .gitignore, and README skeleton so all other sub-tasks have a stable base to build on.

**Expected Outcomes:**
- All directories exist
- `requirements.txt` is complete
- `.env.example` has all required keys
- `.gitignore` excludes secrets and caches
- README has project title and setup instructions

**Todo List:**
- [x] Create all directories (backend/, backend/agents/, backend/rag/, backend/llm/, backend/knowledge_base/, frontend/, tests/)
- [x] Write requirements.txt
- [x] Write .env.example
- [x] Write .gitignore
- [x] Write README.md skeleton

**Status:** [x] done

---

### Sub-Task 2 — Knowledge Base Files
**Intent:** Populate the four JSON knowledge base files with enough content (15-25 entries each) to give RAG meaningful retrieval results across technical, behavioral, HR, and role-specific categories.

**Expected Outcomes:**
- `technical.json` — 20 entries covering DS&A, system design, OOP, databases, REST APIs
- `behavioral.json` — 15 entries covering STAR-method, leadership, conflict, teamwork
- `hr.json` — 15 entries covering salary, culture fit, strengths/weaknesses, career goals
- `roles.json` — 20 entries covering SWE, Data Scientist, PM, DevOps, Full Stack hints

**Todo List:**
- [ ] Write backend/knowledge_base/technical.json
- [ ] Write backend/knowledge_base/behavioral.json
- [ ] Write backend/knowledge_base/hr.json
- [ ] Write backend/knowledge_base/roles.json

**Status:** [ ] pending

---

### Sub-Task 3 — Granite LLM Client
**Intent:** Implement the single watsonx.ai REST wrapper so all agents can call Granite with one function.

**Expected Outcomes:**
- `granite_client.py` reads keys from environment
- `generate(prompt)` returns clean string response
- Handles HTTP errors gracefully with a readable message

**Todo List:**
- [ ] Write backend/llm/granite_client.py
- [ ] Write tests/test_granite.py

**Status:** [ ] pending

---

### Sub-Task 4 — RAG Module
**Intent:** Build the loader and retriever so agents can query the knowledge base semantically.

**Expected Outcomes:**
- `loader.py` reads all 4 JSON files, embeds chunks, stores in ChromaDB collection
- `retriever.py` exposes `search(query, k) -> list[str]`
- `tests/test_rag.py` prints correct top-3 results for sample queries

**Todo List:**
- [ ] Write backend/rag/loader.py
- [ ] Write backend/rag/retriever.py
- [ ] Write tests/test_rag.py

**Status:** [ ] pending

---

### Sub-Task 5 — Question Generation Agent
**Intent:** Implement the agent that uses RAG + Granite to produce a personalised question list.

**Expected Outcomes:**
- `question_agent.py` accepts user profile dict
- Returns a list of `{id, text, category, difficulty}` dicts
- Uses RAG context in the prompt

**Todo List:**
- [ ] Write backend/agents/question_agent.py
- [ ] Define and document the prompt template in the file

**Status:** [ ] pending

---

### Sub-Task 6 — Answer Evaluation Agent
**Intent:** Implement the agent that scores and gives structured feedback on a single answer.

**Expected Outcomes:**
- `evaluation_agent.py` accepts question + answer + user profile
- Returns `{score, strengths, improvement}` parsed from Granite's JSON block
- Uses RAG context in the prompt
- Regex-based JSON extraction is robust

**Todo List:**
- [ ] Write backend/agents/evaluation_agent.py
- [ ] Define and document the prompt template and score rubric in the file

**Status:** [ ] pending

---

### Sub-Task 7 — Interview Orchestrator Agent
**Intent:** Implement the coordinator that manages session state and delegates to the two other agents.

**Expected Outcomes:**
- `orchestrator.py` exposes `start_session()`, `submit_answer()`, `get_report()` methods
- Stores all session data in a dict
- Calls question and evaluation agents correctly
- Assembles final report object

**Todo List:**
- [ ] Write backend/agents/orchestrator.py
- [ ] Write tests/test_agents.py for end-to-end mock session

**Status:** [ ] pending

---

### Sub-Task 8 — FastAPI Backend
**Intent:** Wire all agents into a FastAPI app with the four API routes.

**Expected Outcomes:**
- `main.py` starts up RAG on startup event
- All four routes work correctly
- CORS is enabled for the frontend
- Server runs with `uvicorn backend.main:app --reload`

**Todo List:**
- [ ] Write backend/main.py
- [ ] Verify all routes match the API contract defined in this plan

**Status:** [ ] pending

---

### Sub-Task 9 — Frontend
**Intent:** Build the three HTML pages and shared JS/CSS.

**Expected Outcomes:**
- `index.html` collects user profile and starts the session
- `interview.html` shows questions, collects answers, shows inline feedback
- `report.html` renders the full final report with print support
- `style.css` gives a clean, professional look
- `app.js` handles all API calls and DOM updates

**Todo List:**
- [ ] Write frontend/style.css
- [ ] Write frontend/index.html
- [ ] Write frontend/interview.html
- [ ] Write frontend/report.html
- [ ] Write frontend/app.js

**Status:** [ ] pending

---

### Sub-Task 10 — Integration Testing & README Completion
**Intent:** Run all three test scripts, fix any issues found, and complete the README with final setup instructions and architecture diagram.

**Expected Outcomes:**
- All three test scripts pass without errors
- README has complete setup steps and architecture section
- `.env.example` is verified accurate

**Todo List:**
- [ ] Run tests/test_rag.py and fix any issues
- [ ] Run tests/test_granite.py and fix any issues
- [ ] Run tests/test_agents.py and fix any issues
- [ ] Complete README.md
- [ ] Final review of all files

**Status:** [ ] pending
