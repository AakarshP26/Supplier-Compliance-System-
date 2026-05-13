"""Tools available to the Compliance Copilot agent."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from scs.compliance.pipeline import run as run_comp
from scs.data import load_suppliers
from scs.models import Supplier, SupplierCategory, RiskProfile
from scs.risk.extractor import extract_signal
from scs.risk.news import NewsArticle
from scs.risk.pipeline import _annotate_corroboration
from scs.scoring.fusion import fuse
from scs.adversarial.attack import AttackConfig
from scs.adversarial.runner import run_attacked

def get_supplier_by_name(name: str) -> Supplier | None:
    """Find a supplier in the directory by name (fuzzy)."""
    suppliers = load_suppliers()
    name_low = name.lower()
    for s in suppliers:
        if name_low in s.name.lower() or any(name_low in a.lower() for a in s.aliases):
            return s
    return None

def analyze_supplier(supplier: Supplier, news_articles: list[dict[str, Any]] = None, use_defense: bool = True) -> dict[str, Any]:
    """Run full compliance and risk analysis for a supplier."""
    comp = run_comp(supplier)
    
    if news_articles:
        pasted_articles = []
        for i, a in enumerate(news_articles):
            pasted_articles.append(NewsArticle(
                id=f"agent-pasted-{i}",
                supplier_id=supplier.id,
                title=a.get("title", "News Update"),
                body=a["body"],
                url=a.get("url"),
                published_at=datetime.now(timezone.utc),
            ))
        signals = [extract_signal(supplier.name, art) for art in pasted_articles]
        signals = _annotate_corroboration(signals)
        risk = RiskProfile(
            supplier_id=supplier.id,
            signals=signals,
            article_count=len(pasted_articles),
        )
    else:
        from scs.risk.pipeline import run as run_risk_pipeline
        risk = run_risk_pipeline(supplier)
        
    score = fuse(supplier.id, comp, risk, use_defense=use_defense)
    return {
        "supplier": supplier,
        "compliance": comp,
        "risk": risk,
        "score": score
    }

def find_cheapest_attack(supplier_id: str, vector: str = "press_release", target_score: float = 60.0) -> dict[str, Any]:
    """Find the minimum budget required to push a score above a target."""
    suppliers = {s.id: s for s in load_suppliers()}
    s = suppliers.get(supplier_id)
    if not s:
        return {"error": "Supplier not found"}
    
    comp = run_comp(s)
    
    for B in range(1, 21):
        risk_attacked, _ = run_attacked(s, AttackConfig(budget=B, vector=vector))
        score = fuse(s.id, comp, risk_attacked, use_defense=False).score
        if score >= target_score:
            return {
                "budget": B,
                "vector": vector,
                "final_score": score,
                "success": True
            }
            
    return {"success": False, "message": "Could not reach target even with max budget"}
