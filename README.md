# 🤖 Multi-Agent AI Research Assistant

> **Production-grade** multi-agent system that researches any topic end-to-end:  
> query → plan → search → analyse → generate PDF report.

**Stack:** Python 3.11 · OpenAI GPT-4o · LangGraph · FastMCP · Guardrails AI · FastAPI · Streamlit · GCP Cloud Run

---

## Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────┐
│               Guardrails AI (input)                 │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐
│  Planner    │───▶│  Researcher  │───▶│   Analyst    │───▶│   Writer    │
│  Agent      │    │  Agent       │    │   Agent      │    │   Agent     │
│ (GPT-4o)    │    │ (GPT-4o)     │    │ (GPT-4o)     │    │ (GPT-4o)    │
│             │    │  +Tavily MCP │    │  +REPL MCP   │    │  +PDF MCP   │
└─────────────┘    └──────────────┘    └──────────────┘    └─────────────┘
    │                                                            │
    ▼                                                            ▼
 sub_tasks                                              Markdown + PDF report
                                                                 │
                                                                 ▼
                                               ┌─────────────────────────────┐
                                               │   Guardrails AI (output)    │
                                               │   PII redaction · schema    │
                                               └─────────────────────────────┘
                                                                 │
                                               ┌────────────────────────────┐
                                               │ FastAPI  (REST + SSE)      │
                                               │ Streamlit UI               │
                                               └────────────────────────────┘
```

## Project Structure

```
ai-research-assistant/
├── agents/
│   ├── __init__.py
│   ├── base_agent.py          # Abstract base: OpenAI client + retry logic
│   ├── planner_agent.py       # Decomposes query into 3–5 sub-tasks
│   ├── research_agent.py      # Tavily search via MCP
│   ├── analyst_agent.py       # Python REPL + chart generation via MCP
│   ├── writer_agent.py        # Markdown report + PDF via MCP
│   └── orchestrator.py        # LangGraph StateGraph + ResearchState
│
├── mcp_server/
│   ├── __init__.py
│   ├── server.py              # FastMCP server (stdio transport)
│   └── tools/
│       ├── search.py          # Tavily web search
│       ├── code_run.py        # Sandboxed Python REPL
│       └── report.py          # ReportLab PDF writer
│
├── guardrails/
│   ├── __init__.py
│   ├── input_guards.py        # Length · injection detection
│   ├── output_guards.py       # PII redaction · structure check · schema
│   └── schemas.py             # Pydantic output models
│
├── api/
│   ├── __init__.py
│   └── main.py               # FastAPI: REST + async jobs + SSE
│
├── tests/
│   ├── test_agents.py
│   ├── test_mcp_tools.py
│   └── test_guardrails.py
│
├── streamlit_app.py           # Streamlit frontend
├── config.py                  # Centralised configuration
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── cloudbuild.yaml
├── requirements.txt
└── pytest.ini
```

---

## Quick Start

### 1. Clone & set up environment

```bash
git clone <your-repo-url>
cd ai-research-assistant

python -m venv .venv
source .venv/bin/activate       # Linux / macOS
# .venv\Scripts\activate        # Windows

pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env and add your API keys
```

Required keys:
- `OPENAI_API_KEY` — [platform.openai.com](https://platform.openai.com) (free $5 credit)
- `TAVILY_API_KEY` — [app.tavily.com](https://app.tavily.com) (1,000 free calls/month)

### 3. Run locally (3 terminals)

**Terminal 1 — MCP Server**
```bash
python mcp_server/server.py
```

**Terminal 2 — FastAPI Backend**
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
# Test: curl http://localhost:8080/health
```

**Terminal 3 — Streamlit Frontend**
```bash
streamlit run streamlit_app.py
# Open: http://localhost:8501
```

### 4. Run with Docker Compose

```bash
docker-compose up --build
```

Services:
| Service | URL |
|---------|-----|
| Streamlit UI | http://localhost:8501 |
| FastAPI backend | http://localhost:8080 |
| MCP server | http://localhost:8001 |

---

## Running Tests

```bash
# All tests with coverage
pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing

# Open HTML report
open htmlcov/index.html

# Skip integration tests (no API keys needed)
pytest tests/ -m "not integration"
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/research` | Submit research job (`{"query": "..."}`) |
| `GET` | `/status/{job_id}` | Poll job status |
| `GET` | `/result/{job_id}` | Get completed result |
| `GET` | `/stream/{job_id}` | SSE log stream |
| `GET` | `/download/{job_id}` | Download PDF report |

---

## GCP Cloud Run Deployment

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
    cloudbuild.googleapis.com secretmanager.googleapis.com

# Create Artifact Registry
gcloud artifacts repositories create ai-agent-repo \
    --repository-format=docker --location=asia-south1

# Store secrets
echo -n 'sk-proj-xxx' | gcloud secrets create OPENAI_API_KEY --data-file=-
echo -n 'tvly-xxx'    | gcloud secrets create TAVILY_API_KEY  --data-file=-

# Build, push, and deploy
gcloud builds submit --config cloudbuild.yaml
```

The CI/CD pipeline (`cloudbuild.yaml`) automatically:
1. Installs dependencies
2. Runs the test suite (fails build if coverage < 70%)
3. Builds and pushes the Docker image
4. Deploys to Cloud Run

---

## Free Tier Summary

| Service | Free Allowance |
|---------|---------------|
| OpenAI GPT-4o | $5 credit (~50–100 research runs) |
| Tavily Search | 1,000 calls/month |
| GCP Cloud Run | 2M requests/month |
| GCP Cloud Build | 120 build-minutes/day |
| Streamlit Cloud | Free public hosting |
| GitHub Actions | 2,000 CI minutes/month |

---

## Guardrails

| Layer | Check |
|-------|-------|
| Input | Min/max length · prompt injection patterns |
| Output | PII redaction (email, SSN, CC, phone) · Markdown structure · min length |
| Schema | Pydantic `ResearchOutput` validation for structured LLM output |

---

## License

MIT
