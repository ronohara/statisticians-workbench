"""
Schema AI — Augmented Mechanical Analysis.

Receives the full schema and mechanical analysis output, then uses an
LLM to produce context-aware explanations for each issue, an overall
health score, and prioritised action recommendations.

This is the first of three AI specialists in the Database Design
enhancement pipeline.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Prompt Template ───────────────────────────────────────────────────

_SCHEMA_AI_SYSTEM_PROMPT = """You are a senior database architect reviewing a schema analysis for a user. Your task is to augment mechanical findings with context-aware explanations.

You will receive:
1. A summary of the database schema (table names, column counts, key tables)
2. A list of mechanical issues found by automated rules (each with category, severity, table, and description)

For each issue, write a one-paragraph explanation of WHY it matters for THIS SPECIFIC schema — not generic advice. Reference specific table names and column names. Contextualise the impact.

Then assess the overall health of the database (score 0-100) and list the top 3 priority actions the user should take.

Return ONLY valid JSON matching this schema. No markdown, no explanation outside the JSON:

{
  "issues": [
    {
      "issue_id": 1,
      "explanation": "Context-aware explanation specific to this schema..."
    }
  ],
  "health_score": 72,
  "top_actions": [
    "Priority action 1 — concrete and specific",
    "Priority action 2",
    "Priority action 3"
  ]
}

Rules:
- health_score: 0-100 integer. 0 = critical structural problems, 100 = production-ready.
- issues: one entry per mechanical issue, matching the issue_id from the input.
- explanations: reference specific tables and columns. Do not repeat the mechanical description.
- top_actions: concrete commands or steps the user can take. Include specific table/column names.
"""


def _build_user_context(
    schema: Dict[str, Any],
    mechanical_output: Dict[str, Any],
    max_issues: Optional[int] = None,
) -> str:
    """Build the user context (schema summary + issues) for the LLM.
    
    If max_issues is set, only the most critical issues (by severity) are included.
    """
    tables = schema.get("tables", [])
    issues = mechanical_output.get("issues", [])

    # Apply dynamic cap: prioritise by severity (critical > high > medium > low)
    if max_issues is not None and len(issues) > max_issues:
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        issues = sorted(issues, key=lambda i: severity_order.get(
            str(i.get("severity", "low")).lower(), 3
        ))[:max_issues]
        # Update counts to reflect the capped set
        capped = mechanical_output.copy()
        capped["issues"] = issues
        capped["critical"] = sum(1 for i in issues if str(i.get("severity", "")).lower() == "critical")
        capped["high"] = sum(1 for i in issues if str(i.get("severity", "")).lower() == "high")
        capped["medium"] = sum(1 for i in issues if str(i.get("severity", "")).lower() == "medium")
        capped["low"] = sum(1 for i in issues if str(i.get("severity", "")).lower() == "low")
        mechanical_output = capped

    lines = ["## Schema Summary\n"]
    lines.append(f"Database has {len(tables)} tables, "
                 f"{mechanical_output.get('total_columns', sum(len(t.get('columns', [])) for t in tables))} columns.\n")

    # Table listing with columns
    for t in tables:
        t_name = t.get("name", "unknown")
        cols = [c.get("name", "?") for c in t.get("columns", [])][:15]
        col_str = ", ".join(cols)
        if len(t.get("columns", [])) > 15:
            col_str += f" (+{len(t['columns']) - 15} more)"
        fks = t.get("foreign_keys", [])
        fk_str = ""
        if fks:
            fk_str = f" (FKs: {', '.join(f'{fk.get('column','?')}→{fk.get('referenced_table','?')}.{fk.get('referenced_column','?')}' for fk in fks)})"
        lines.append(f"- **{t_name}** ({len(t.get('columns', []))} cols): {col_str}{fk_str}")

    lines.append(f"\n## Issues Found ({len(issues)} total)\n")
    lines.append(f"Critical: {mechanical_output.get('critical', 0)}, "
                 f"High: {mechanical_output.get('high', 0)}, "
                 f"Medium: {mechanical_output.get('medium', 0)}, "
                 f"Low: {mechanical_output.get('low', 0)}\n")

    for i, issue in enumerate(issues, 1):
        lines.append(
            f"**Issue #{i}** [{issue.get('severity', '?')}] "
            f"Table: {issue.get('table', '?')} — {issue.get('description', issue.get('title', '?'))}"
        )

    return "\n".join(lines)


# ── Output Validation ─────────────────────────────────────────────────

_SCHEMA_AI_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["issues", "health_score", "top_actions"],
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["issue_id", "explanation"],
                "properties": {
                    "issue_id": {"type": "integer"},
                    "explanation": {"type": "string"},
                },
            },
        },
        "health_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "top_actions": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 5,
        },
    },
}


def _validate_output(data: dict) -> dict:
    """Validate AI output against the expected JSON schema.

    Returns the data unchanged if valid, or a fallback dict on failure.
    """
    try:
        import jsonschema
        jsonschema.validate(data, _SCHEMA_AI_JSON_SCHEMA)
        return data
    except ImportError:
        # jsonschema not installed — basic checks
        if not isinstance(data, dict):
            return {"issues": [], "health_score": 50, "top_actions": ["AI output validation failed"]}
        if "issues" not in data or not isinstance(data["issues"], list):
            data["issues"] = []
        if "health_score" not in data or not isinstance(data.get("health_score"), (int, float)):
            data["health_score"] = 50
        if "top_actions" not in data or not isinstance(data.get("top_actions"), list):
            data["top_actions"] = ["Review schema manually"]
        return data
    except Exception:
        return {"issues": [], "health_score": 50, "top_actions": ["AI output validation failed"]}


# ── Main Entry Point ──────────────────────────────────────────────────

# ── Model-aware output budgeting ─────────────────────────────────────

# Output token limits per model (used to cap issues before the AI call).
_MODEL_MAX_TOKENS: Dict[str, int] = {
    "deepseek-v4-pro": 32768,
    "deepseek-v4-flash": 8192,
    "deepseek-chat": 8192,
    "deepseek-reasoner": 8192,
}

# Estimated chars per issue in the AI's JSON output (explanation + JSON overhead).
_CHARS_PER_ISSUE = 150


def _resolve_max_issues(total_issues: int, model: Optional[str]) -> Optional[int]:
    """Return a max-issue cap if the estimated output would exceed the model's limit.

    Returns None if no cap is needed (the model can handle all issues).
    """
    if not model:
        return None
    max_tokens = _MODEL_MAX_TOKENS.get(model)
    if max_tokens is None:
        return None
    # 1 token ≈ 4 chars; use 70 % of the output budget for issue explanations
    max_chars = int(max_tokens * 4 * 0.70)
    cap = max_chars // _CHARS_PER_ISSUE
    if cap < total_issues:
        return cap
    return None


async def analyze(
    schema: Dict[str, Any],
    mechanical_output: Dict[str, Any],
    *,
    db_pool=None,
    user_id: str = "default",
    connection_id: Optional[int] = None,
    language: str = "en",
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Run Schema AI analysis on the mechanical output.

    Args:
        schema: Full extracted schema (tables, columns, types, FKs).
        mechanical_output: Output from analysis.py (issue list + counts).
        db_pool: Database pool for AI connection lookup.
        user_id: User ID for AI connection lookup.
        connection_id: Optional specific AI connection to use.
        language: ISO 639-1 code for the response language.
        model: Optional model name for output budgeting. If provided and the
               estimated output exceeds the model's limits, issues are capped
               by severity (critical first).

    Returns:
        dict with 'issues' (augmented explanations), 'health_score',
        'top_actions', and 'status' ('ok' or 'error').
    """
    from .llm_client import call_llm, extract_json

    total_issues = len(mechanical_output.get("issues", []))
    max_issues = _resolve_max_issues(total_issues, model)

    user_context = _build_user_context(schema, mechanical_output, max_issues=max_issues)

    effective_issues = max_issues if max_issues else total_issues
    logger.info(
        "Schema AI: analysing %d tables, %d issues%s (language=%s)",
        len(schema.get("tables", [])),
        effective_issues,
        f" (capped from {total_issues})" if max_issues else "",
        language,
    )

    result = await call_llm(
        system_prompt=_SCHEMA_AI_SYSTEM_PROMPT,
        user_context=user_context,
        db_pool=db_pool,
        user_id=user_id,
        connection_id=connection_id,
        model=model,
        language=language,
        caller="Schema AI",
    )

    if "error" in result:
        logger.warning("Schema AI failed: %s", result["error"])
        return {
            "status": "error",
            "error": result["error"],
            "issues": [],
            "health_score": mechanical_output.get("critical", 0) == 0 and 75 or 50,
            "top_actions": ["AI analysis unavailable — review issues manually"],
        }

    content = result["content"]
    data = extract_json(content)

    if data is None:
        logger.warning("Schema AI returned invalid JSON. Raw output (200 chars): %s", content[:200])
        return {
            "status": "error",
            "error": "LLM output could not be parsed as JSON",
            "issues": [],
            "health_score": 50,
            "top_actions": ["AI output format error — review issues manually"],
        }

    validated = _validate_output(data)

    return {
        "status": "ok",
        "issues": validated.get("issues", []),
        "health_score": validated.get("health_score", 50),
        "top_actions": validated.get("top_actions", []),
    }
