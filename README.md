# AI-Powered Interview Trainer

> **IBM SkillsBuild AICTE 2026 · Problem Statement #22**  
> An Agentic AI mock interview system powered by IBM Granite, RAG, and FastAPI.

---

## What It Does

Enter your job role, experience level, and skills. Three AI agents collaborate to:

1. **Generate** personalised technical, behavioral, and HR interview questions (tailored to your profile via RAG)
2. **Evaluate** each of your answers with a score out of 10 and specific improvement suggestions
3. **Produce** a final report with overall score, category breakdown, strengths, and top areas to improve

---

## Problem Statement #22 — Requirements Mapping

| Requirement | Implementation |
|---|---|
| **IBM Granite** | `ibm/granite-3-8b-instruct` via watsonx.ai REST API (`/ml/v1/text/generation`) |
| **RAG** | ChromaDB (in-memory) + `sentence-transformers/all-MiniLM-L6-v2` over 70 local knowledge chunks |
| **Agentic AI** | Three explicit agents with defined roles: Orchestrator → Question Agent + Evaluation Agent |
| **Web Application** | FastAPI backend + vanilla HTML/JS/CSS frontend (no build step) |
| **Technical + HR questions** | Question Generation Agent produces all three types based on user profile |
| **User profile input** | Job role, experience level, and skills collected on setup page |
| **Answer evaluation** | Answer Evaluation Agent scores 1–10 and returns strengths + improvement + ideal points |
| **Final report** | Scored HTML report with overall average, category breakdown, per-question table, printable |

---

## Architecture

```
Browser (HTML / JS)
        │  REST (fetch)
        ▼
FastAPI Backend  ─── backend/main.py
        │
        ├── Orchestrator Agent        backend/agents/orchestrator.py
        │      ├── calls ──►  Question Generation Agent   backend/agents/question_agent.py
        │      └── calls ──►  Answer Evaluation Agent     backend/agents/evaluation_agent.py
        │
        ├── RAG Module                backend/rag/
        │      ├── loader.py          (ChromaDB + sentence-transformers)
        │      └── retriever.py       (semantic search)
        │      └── knowledge_base/    (70 JSON chunks across 4 files)
        │
        └── Granite LLM Client        backend/llm/granite_client.py
               └── IBM watsonx.ai REST API  (ibm/granite-3-8b-instruct)
```

### Agent Interaction Flow

```
User fills setup form
        │
        ▼
POST /api/start  →  Orchestrator  →  Question Agent
                                           │  RAG query (role + skills + types)
                                           │  → ChromaDB → top-5 chunks
                                           │  → IBM Granite → question list
                                           ▼
                    Browser shows first question
                                           │
                    User types answer      │
                        │                 ▼
POST /api/answer  →  Orchestrator  →  Evaluation Agent
                                           │  RAG query (question text + category)
                                           │  → ChromaDB → top-3 ideal-answer chunks
                                           │  → IBM Granite → score + feedback JSON
                                           ▼
                    Browser shows score + feedback
                    (repeat for each question)
                                           │
GET /api/report  →  Orchestrator assembles final report
                        └── Browser renders report.html
```

---

## Project Structure

```
AI-Interview-Trainer/
├── backend/
│   ├── main.py                      FastAPI app + 4 API routes
│   ├── agents/
│   │   ├── orchestrator.py          Interview Orchestrator Agent
│   │   ├── question_agent.py        Question Generation Agent
│   │   └── evaluation_agent.py      Answer Evaluation Agent
│   ├── rag/
│   │   ├── loader.py                KB loader → ChromaDB
│   │   └── retriever.py             Semantic search helper
│   ├── llm/
│   │   └── granite_client.py        IBM Granite REST wrapper
│   └── knowledge_base/
│       ├── technical.json           20 chunks (DS&A, OOP, DBs, APIs, cloud…)
│       ├── behavioral.json          15 chunks (STAR, leadership, conflict…)
│       ├── hr.json                  15 chunks (strengths, salary, goals…)
│       └── roles.json               20 chunks (SWE, DS, PM, DevOps…)
├── frontend/
│   ├── index.html                   Setup page
│   ├── interview.html               Live interview page
│   ├── report.html                  Final report page
│   ├── style.css                    Shared styles
│   └── app.js                       All client-side JS
├── tests/
│   ├── test_rag.py                  Local RAG test (no API key needed)
│   ├── test_granite.py              Granite API connection test
│   └── test_agents.py               End-to-end pipeline test
├── .env.example                     Credential template
├── requirements.txt
└── README.md
```

---

## Setup & Run

### Prerequisites
- Python 3.11 or higher
- An [IBM watsonx.ai](https://www.ibm.com/products/watsonx-ai) account with:
  - An API key (IBM Cloud → Manage → Access → API keys)
  - A project ID (watsonx.ai → Your project → Manage → General)

### 1 — Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/AI-Interview-Trainer.git
cd AI-Interview-Trainer
```

### 2 — Create a virtual environment and install dependencies

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

> **Note:** The first `pip install` downloads `sentence-transformers` and its model (~22 MB). This takes a few minutes once; subsequent runs are instant.

### 3 — Configure credentials

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```
WATSONX_API_KEY=your_ibm_cloud_api_key
WATSONX_PROJECT_ID=your_watsonx_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
```

> **Never commit `.env` to Git.** It is already in `.gitignore`.

### 4 — Run the server

```bash
uvicorn backend.main:app --reload
```

Open your browser at **http://localhost:8000**

The interactive API docs (Swagger UI) are at **http://localhost:8000/docs**

---

## API Reference

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Setup page (index.html) |
| `GET` | `/interview` | Live interview page |
| `GET` | `/report-page` | Final report page |
| `GET` | `/health` | `{"status":"ok","model":"ibm/granite-3-8b-instruct"}` |
| `POST` | `/api/start` | Start session → `{session_id, question, message}` |
| `POST` | `/api/answer` | Submit answer → `{evaluation, next_question, is_complete}` |
| `GET` | `/api/report/{session_id}` | Final report JSON |
| `GET` | `/api/session/{session_id}/current-question` | Resume after page refresh |

### POST `/api/start` — request body

```json
{
  "role": "Software Engineer",
  "experience": "1-3 years",
  "skills": "Python, REST APIs, SQL",
  "num_questions": 7,
  "types": ["technical", "behavioral", "hr"]
}
```

### POST `/api/answer` — request body

```json
{
  "session_id": "uuid-...",
  "answer": "A stack follows LIFO order..."
}
```

### GET `/api/report/{session_id}` — response (excerpt)

```json
{
  "report": {
    "overall_score": 7.3,
    "category_averages": {"technical": 7.5, "behavioral": 7.0, "hr": 7.3},
    "top_strengths": ["Used specific examples", "Clear structure"],
    "top_improvements": ["Quantify outcomes with metrics"],
    "rows": [
      {
        "question": "Explain the difference between a stack and a queue.",
        "category": "technical",
        "score": 8,
        "strengths": ["Correct LIFO/FIFO definition", "Mentioned use cases"],
        "improvement": "Add a code snippet to strengthen the explanation."
      }
    ]
  }
}
```

---

## Running Tests

Run each test script from the project root with your virtual environment active.

### Test 1 — RAG knowledge base (no API key required)

```bash
python tests/test_rag.py
```

Loads all 70 KB chunks into ChromaDB, runs 5 semantic queries, prints top results.  
**Expected:** `All RAG tests passed.`

### Test 2 — IBM Granite connection (requires `.env`)

```bash
python tests/test_granite.py
```

Sends a single prompt to `ibm/granite-3-8b-instruct`, prints the response.  
**Expected:** `All Granite tests passed.`

### Test 3 — End-to-end agent pipeline (requires `.env`)

```bash
python tests/test_agents.py
```

Runs a complete 3-question mock session through all three agents, prints scores and report.  
**Expected:** `All agent pipeline tests passed.`

---

## Technologies Used

| Technology | Version / Model | Role |
|---|---|---|
| IBM Granite | `ibm/granite-3-8b-instruct` | LLM for question generation and answer evaluation |
| IBM watsonx.ai | REST API v1 | Granite hosting and inference |
| ChromaDB | Latest | In-memory vector database for RAG |
| sentence-transformers | `all-MiniLM-L6-v2` | Text embedding for semantic search |
| FastAPI | Latest | Python web framework |
| Uvicorn | Latest | ASGI server |
| Pydantic | v2 | Request/response validation |
| python-dotenv | Latest | Environment variable management |

---

## Screenshots

| # | Screen | What it shows |
|---|---|---|
| 1 | Setup page with form filled in | User profile input |
| 2 | First question displayed (Technical) | Question Generation Agent + RAG |
| 3 | User typing an answer | Live interview UX |
| 4 | Feedback panel — score badge + strengths | Answer Evaluation Agent |
| 5 | Question 3 of 7 — progress bar | Orchestrator managing state |
| 6 | A behavioral question (STAR context) | RAG retrieving behavioral chunks |
| 7 | Final report — overall score + table | Report generation |
| 8 | Swagger UI at `/docs` or terminal output | Granite API integration proof |

---

## IBM Bob Development Note

This project was built using **IBM Bob** as the development assistant.  
All code was generated and validated step-by-step in 10 sub-tasks defined in `interview-trainer-plan.md`.

---

*IBM SkillsBuild AICTE 2026 · Problem Statement #22 · AI-Powered Interview Trainer*
