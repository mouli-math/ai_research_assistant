"""Streamlit frontend for the Multi-Agent AI Research Assistant.

Communicates with the FastAPI backend over HTTP.
- Submits research jobs via POST /research
- Polls job status via GET /status/{job_id}
- Renders the Markdown report inline
- Provides a PDF download button

Run:  streamlit run streamlit_app.py
      (ensure FastAPI is running on API_URL first)
"""

import time

import httpx
import streamlit as st
import os

# ── Configuration ────────────────────────────────────────────────────────────
API_URL = os.environ.get("API_URL", "http://localhost:8080")
POLL_INTERVAL_SECS = 2

# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Research Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("🤖 AI Research Assistant")
st.caption(
    "Multi-Agent System powered by **GPT-4o** · **MCP Tools** · **LangGraph** · **Guardrails AI**"
)

st.divider()

# ── Sidebar: about ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("About")
    st.markdown(
        """
        This tool uses **4 specialised AI agents** working in sequence:

        1. 🗂️ **Planner** — breaks your query into sub-tasks
        2. 🔍 **Researcher** — searches the web via Tavily
        3. 📊 **Analyst** — runs data analysis & charts
        4. ✍️ **Writer** — writes a structured PDF report

        **Stack:** Python · OpenAI GPT-4o · LangGraph · FastMCP · Guardrails AI · GCP Cloud Run
        """
    )
    st.divider()
    st.markdown("**Free-tier limits**")
    st.markdown("- OpenAI: ~$5 credit")
    st.markdown("- Tavily: 1,000 calls/month")
    st.markdown("- GCP Cloud Run: 2M requests/month")

# ── Main UI ───────────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])

with col1:
    query = st.text_input(
        "Enter your research question:",
        placeholder="e.g. What are the latest trends in Generative AI for enterprise in 2025?",
        help="Ask anything — the system will search the web, analyse data, and write a full report.",
    )

with col2:
    st.write("")
    st.write("")
    run_btn = st.button("🔍 Run Research", disabled=not query, use_container_width=True)

# ── Research execution ────────────────────────────────────────────────────────
if run_btn and query:
    st.divider()

    with st.spinner("Submitting research job …"):
        try:
            resp = httpx.post(
                f"{API_URL}/research",
                json={"query": query},
                timeout=10,
            )
            resp.raise_for_status()
            job_id = resp.json()["job_id"]
        except Exception as exc:
            st.error(f"❌ Failed to connect to the backend: {exc}")
            st.info("Make sure the FastAPI server is running on `http://localhost:8080`")
            st.stop()

    st.info(f"Job submitted — ID: `{job_id}`")

    # Progress display
    progress_bar = st.progress(0, text="Waiting for agents …")
    status_placeholder = st.empty()
    log_placeholder = st.empty()

    progress_steps = {"PENDING": 5, "RUNNING": 50, "COMPLETE": 100, "FAILED": 100}
    agent_messages = [
        "🗂️ Planner decomposing query …",
        "🔍 Researcher fetching sources …",
        "📊 Analyst running code …",
        "✍️ Writer composing report …",
    ]

    step_idx = 0
    while True:
        try:
            status_resp = httpx.get(f"{API_URL}/status/{job_id}", timeout=5)
            status = status_resp.json().get("status", "PENDING")
        except Exception:
            status = "PENDING"

        pct = progress_steps.get(status, 10)
        label = agent_messages[min(step_idx, len(agent_messages) - 1)]
        progress_bar.progress(pct, text=label)
        status_placeholder.markdown(f"**Status:** `{status}`")
        step_idx += 1

        if status in ("COMPLETE", "FAILED"):
            break
        time.sleep(POLL_INTERVAL_SECS)

    progress_bar.progress(100, text="Done!")

    # ── Results ───────────────────────────────────────────────────────────────
    if status == "COMPLETE":
        st.success("✅ Research complete!")
        st.divider()

        try:
            result = httpx.get(f"{API_URL}/result/{job_id}", timeout=10).json()
        except Exception as exc:
            st.error(f"Failed to fetch result: {exc}")
            st.stop()

        # Render report
        report_md = result.get("report", "")
        if report_md:
            st.subheader("📄 Research Report")
            st.markdown(report_md)
        else:
            st.warning("No report text was generated.")

        st.divider()

        # Agent logs
        with st.expander("🪵 Agent Logs", expanded=False):
            for log in result.get("logs", []):
                st.text(log)

        # PDF download
        col_a, col_b = st.columns([1, 3])
        with col_a:
            try:
                pdf_resp = httpx.get(f"{API_URL}/download/{job_id}", timeout=15)
                if pdf_resp.status_code == 200:
                    st.download_button(
                        label="📥 Download PDF",
                        data=pdf_resp.content,
                        file_name="research_report.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                else:
                    st.info("PDF not available for this job.")
            except Exception:
                st.info("PDF download unavailable.")

    else:
        error_msg = ""
        try:
            err_resp = httpx.get(f"{API_URL}/result/{job_id}", timeout=5)
            error_msg = err_resp.json().get("error", "Unknown error")
        except Exception:
            pass
        st.error(f"❌ Research job failed. {error_msg}")
        st.info("Check the FastAPI server logs for details.")
