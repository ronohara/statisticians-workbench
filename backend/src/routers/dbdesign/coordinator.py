"""
Coordinator — Merges mechanical analysis + three AI specialist outputs.

Takes the raw output from analysis.py (mechanical issues), schema_ai.py
(augmented explanations), semantic_ai.py (domain/meaning annotations),
and integration_ai.py (relationship/capability findings), and produces
a single unified JSON structure for the report generator.

Handles partial failures gracefully — if any AI specialist failed,
its section is omitted from the final output. The report generator
renders only the sections that are present.
"""

from typing import Any, Dict, List, Optional


def merge(
    mechanical: Dict[str, Any],
    schema_ai: Optional[Dict[str, Any]] = None,
    semantic_ai: Optional[Dict[str, Any]] = None,
    integration_ai: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge all analysis outputs into a unified report structure.

    Args:
        mechanical: Output from analysis.py (issue list + counts).
        schema_ai: Output from schema_ai.py (augmented explanations, health score).
        semantic_ai: Output from semantic_ai.py (column meanings, domains, code systems).
        integration_ai: Output from integration_ai.py (implicit relationships, capabilities).

    Returns:
        dict with sections: 'schema', 'issues', 'semantic', 'integration',
        'health', 'status'. Missing AI sections are null.
    """
    result: Dict[str, Any] = {
        "status": "ok",
        "ai_status": _ai_status(schema_ai, semantic_ai, integration_ai),
    }

    # ── Schema Overview (always present from mechanical analysis) ─────
    result["schema"] = {
        "total_tables": mechanical.get("total_tables", 0),
        "total_columns": mechanical.get("total_columns", 0),
    }

    # ── Issues (mechanical + augmented explanations) ──────────────────
    result["issues"] = _merge_issues(mechanical, schema_ai)

    # ── Health Score ──────────────────────────────────────────────────
    if schema_ai and schema_ai.get("status") == "ok":
        result["health"] = {
            "score": schema_ai.get("health_score", 50),
            "top_actions": schema_ai.get("top_actions", []),
        }
    else:
        result["health"] = {
            "score": _fallback_health_score(mechanical),
            "top_actions": [],
        }

    # ── Semantic Annotations ──────────────────────────────────────────
    if semantic_ai and semantic_ai.get("status") == "ok":
        result["semantic"] = {
            "columns": semantic_ai.get("columns", []),
            "code_systems": semantic_ai.get("code_systems", []),
            "domains": semantic_ai.get("domains", []),
            "table_purposes": semantic_ai.get("table_purposes", []),
        }
    else:
        result["semantic"] = None

    # ── Integration Findings ──────────────────────────────────────────
    if integration_ai and integration_ai.get("status") == "ok":
        result["integration"] = {
            "implicit_relationships": integration_ai.get("implicit_relationships", []),
            "research_capabilities": integration_ai.get("research_capabilities", []),
            "missing_dimensions": integration_ai.get("missing_dimensions", []),
        }
    else:
        result["integration"] = None

    return result


# ── Helpers ───────────────────────────────────────────────────────────

def _ai_status(
    schema_ai: Optional[Dict],
    semantic_ai: Optional[Dict],
    integration_ai: Optional[Dict],
) -> str:
    """Determine overall AI status for the report."""
    ok = 0
    total = 0
    for output in (schema_ai, semantic_ai, integration_ai):
        if output is not None:
            total += 1
            if output.get("status") == "ok":
                ok += 1

    if total == 0:
        return "unavailable"
    if ok == total:
        return "complete"
    if ok == 0:
        return "failed"
    return "partial"


def _merge_issues(
    mechanical: Dict[str, Any],
    schema_ai: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Merge mechanical issues with Schema AI explanations.

    Each mechanical issue keeps its original fields. If Schema AI
    produced an explanation for the same issue_id, it's attached.
    """
    issues = mechanical.get("issues", [])
    explanations = {}

    if schema_ai and schema_ai.get("status") == "ok":
        for item in schema_ai.get("issues", []):
            issue_id = item.get("issue_id")
            if issue_id is not None:
                explanations[issue_id] = item.get("explanation", "")

    merged_issues = []
    for i, issue in enumerate(issues, 1):
        merged = dict(issue)
        if i in explanations:
            merged["ai_explanation"] = explanations[i]
        merged_issues.append(merged)

    return {
        "total": len(merged_issues),
        "critical": mechanical.get("critical", 0),
        "high": mechanical.get("high", 0),
        "medium": mechanical.get("medium", 0),
        "low": mechanical.get("low", 0),
        "items": merged_issues,
    }


def _fallback_health_score(mechanical: Dict[str, Any]) -> int:
    """Compute a fallback health score from mechanical issue counts."""
    critical = mechanical.get("critical", 0)
    high = mechanical.get("high", 0)
    medium = mechanical.get("medium", 0)
    tables = mechanical.get("total_tables", 1)

    score = 100
    score -= critical * 20
    score -= high * 10
    score -= medium * 3

    # Penalize high issue-per-table ratio
    total_issues = critical + high + medium
    if tables > 0 and total_issues / tables > 5:
        score -= 10

    return max(0, min(100, score))
