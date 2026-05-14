from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from functools import lru_cache

from scs.data import load_suppliers
from scs.models import Supplier
from scs.dashboard import agent_tools
from scs.dashboard.agent import CopilotAgent
from scs.compliance.pipeline import run as run_comp
from scs.risk.pipeline import run as run_risk
from scs.scoring.fusion import fuse
from scs.profile import get_profile

app = FastAPI(title="Supplier Compliance API")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []
    context: Dict[str, Any] = {}

@app.get("/api/suppliers")
def get_suppliers():
    suppliers = list(load_suppliers())
    return [s.model_dump() for s in suppliers]

@lru_cache(maxsize=1)
def _get_cached_portfolio_stats():
    suppliers = list(load_suppliers())
    n_total = len(suppliers)
    n_risky = 0
    n_compliance_fails = 0
    n_articles = 0
    threshold = 50.0
    
    # Store scores for distribution chart
    scores = []

    for s in suppliers:
        comp = run_comp(s)
        risk = run_risk(s)
        prof = get_profile(s.id)
        ipy = s.incorporated.year if s.incorporated else None
        scr = fuse(s.id, comp, risk, use_defense=True, profile=prof, incorporation_year=ipy)
        
        scores.append(scr.score)
        
        if scr.score < threshold:
            n_risky += 1
        if comp.fail_count > 0:
            n_compliance_fails += 1
        n_articles += risk.article_count

    # Create histogram buckets (0-20, 20-40, 40-60, 60-80, 80-100)
    distribution = [
        {"range": "0-20", "count": sum(1 for s in scores if s < 20)},
        {"range": "20-40", "count": sum(1 for s in scores if 20 <= s < 40)},
        {"range": "40-60", "count": sum(1 for s in scores if 40 <= s < 60)},
        {"range": "60-80", "count": sum(1 for s in scores if 60 <= s < 80)},
        {"range": "80-100", "count": sum(1 for s in scores if s >= 80)},
    ]

    return {
        "n_total": n_total,
        "n_risky": n_risky,
        "n_clean": n_total - n_risky,
        "n_compliance_fails": n_compliance_fails,
        "n_articles": n_articles,
        "n_passed_checks": n_total - n_compliance_fails,
        "distribution": distribution
    }

@app.get("/api/portfolio-stats")
def get_portfolio_stats():
    return _get_cached_portfolio_stats()

@app.post("/api/agent/chat")
def chat_with_agent(req: ChatRequest):
    agent = CopilotAgent(req.context)
    response = agent.run(req.message, req.history)
    return {"reply": response}

@app.get("/health")
def health_check():
    return {"status": "ok"}
