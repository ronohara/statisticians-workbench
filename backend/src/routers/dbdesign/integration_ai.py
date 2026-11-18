"""
Integration AI — Cross-Table Intelligence.

Receives the full schema and Semantic AI output (column meanings, domain
classifications), then uses an LLM to detect implicit relationships,
propose schema integration DDL, assess research capabilities, and flag
missing temporal dimensions.

This is the third of three AI specialists in the Database Design
enhancement pipeline.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Prompt Template ───────────────────────────────────────────────────

_INTEGRATION_AI_SYSTEM_PROMPT = """You are a data integration specialist examining a database schema. Your task is to detect relationships between tables that don't have explicit foreign keys, propose concrete DDL to connect them, and assess what kinds of analysis the database can support.

You will receive:
1. Full schema (tables, columns, data types, existing foreign keys)
2. Semantic context from a previous analysis (column meanings, ISIC domain classifications, table purposes)

Your tasks:

1. IMPLICIT RELATIONSHIPS — Find tables that SHOULD be related but lack FK constraints. Look for:
   - Column naming overlap (e.g., both tables have "customer_id" but no FK)
   - Domain affinity (tables in same ISIC section likely share dimensions)
   - Common join patterns (date columns, location columns, category columns)
   For each finding, propose specific DDL.

2. RESEARCH / ANALYTICAL CAPABILITY — Based on the schema, what kinds of analysis can this database support? Examples:
   - "Longitudinal analysis: ✅ Supported — sales table has date column spanning multiple years"
   - "Cohort comparison: ✅ Supported — products can be grouped by category"
   - "Geographic analysis: ❌ Not supported — no location columns found"
   Include confidence level (supported / partial / unsupported) and rationale.

3. MISSING DIMENSIONS — Flag patterns where most related tables share a characteristic but one doesn't. "5 of 6 tables in section G have date/timestamp columns. Table 'product_catalog' does not — it may be a static reference table or missing a temporal dimension."

Return ONLY valid JSON matching this schema:

{
  "implicit_relationships": [
    {
      "from_table": "bi_salesFact",
      "from_column": "product_key",
      "to_table": "bi_product",
      "to_column": "product_key",
      "evidence": "Column naming matches; both tables in ISIC section G; no FK exists",
      "proposed_ddl": "ALTER TABLE bi_salesFact ADD CONSTRAINT fk_product FOREIGN KEY (product_key) REFERENCES bi_product(product_key)",
      "confidence": "high"
    }
  ],
  "research_capabilities": [
    {
      "study_type": "Longitudinal sales analysis",
      "supported": true,
      "confidence": "high",
      "rationale": "Sales table has sale_date column; bi_date provides date dimension with year/month hierarchy"
    }
  ],
  "missing_dimensions": [
    {
      "table": "product_catalog",
      "missing_feature": "temporal dimension (date column)",
      "peer_tables": ["bi_salesFact", "bi_sentiment", "bi_manufacturer"],
      "likely_explanation": "Product catalog appears to be a static reference table"
    }
  ]
}

Rules:
- implicit_relationships: only report medium or high confidence. Include the evidence that led to the finding.
- proposed_ddl: valid SQL for the target database type (default PostgreSQL syntax).
- research_capabilities: assess 3-5 study types. Be honest — if a capability isn't supported, say so.
- missing_dimensions: only flag when the pattern is clear (3+ peers share the feature, one doesn't).
- All table and column names must match the schema exactly.
"""


def _build_user_context(
    schema: Dict[str, Any],
    semantic_output: Optional[Dict[str, Any]] = None,
    max_chars: int = 25_000,
) -> str:
    """Build user context with schema + semantic analysis results.

    Truncates at max_chars to fit within LLM context windows.
    For large schemas, only table names and FK relationships are included;
    column-level detail is omitted to stay under the limit.
    """
    tables = schema.get("tables", [])
    lines = ["## Schema\n"]

    # Phase 1: list tables with FKs (essential for integration analysis)
    for t in tables:
        t_name = t.get("name", "unknown")
        col_count = len(t.get("columns", []))
        lines.append(f"\n### Table: {t_name} ({col_count} columns)")

        # Existing FKs
        fks = t.get("foreign_keys", [])
        if fks:
            for fk in fks:
                lines.append(f"  FK: {fk.get('column','?')} → {fk.get('referenced_table','?')}.{fk.get('referenced_column','?')}")

    base = "\n".join(lines)
    remaining = max_chars - len(base) - 200

    # Phase 2: add column details only if there's room
    if remaining > 2000:
        for t in tables:
            t_name = t.get("name", "unknown")
            cols = t.get("columns", [])
            col_lines = [f"\n### {t_name} columns:"]
            col_chars = len("\n".join(col_lines))
            for c in cols:
                c_name = c.get("name", "?")
                c_type = c.get("type", c.get("data_type", "unknown"))
                line = f"  - {c_name} ({c_type})"
                col_chars += len(line) + 1
                if col_chars > remaining:
                    col_lines.append("  ... (columns truncated)")
                    break
                col_lines.append(line)
            base += "\n" + "\n".join(col_lines)
            remaining -= col_chars
            if remaining <= 0:
                break

    # Semantic context (if available and room permits)
    if semantic_output and semantic_output.get("status") == "ok" and remaining > 500:
        sem_lines = ["\n## Semantic Context\n"]
        sem_chars = len("\n".join(sem_lines))

        if semantic_output.get("domains"):
            sem_lines.append("### ISIC Domains:")
            for d in semantic_output["domains"]:
                line = f"  - {d.get('table','?')}: {', '.join(d.get('domains',[]))}"
                if sem_chars + len(line) > remaining:
                    break
                sem_lines.append(line)
                sem_chars += len(line) + 1

        if semantic_output.get("table_purposes") and sem_chars < remaining:
            sem_lines.append("### Table Purposes:")
            for t in semantic_output["table_purposes"]:
                line = f"  - {t.get('table','?')}: {t.get('purpose','?')}"
                if sem_chars + len(line) > remaining:
                    break
                sem_lines.append(line)
                sem_chars += len(line) + 1

        base += "\n" + "\n".join(sem_lines)

    if len(base) > max_chars:
        base = base[:max_chars - 50] + "\n... (context truncated to fit LLM limit)"

    return base


# ── Output Validation ─────────────────────────────────────────────────

_INTEGRATION_AI_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["implicit_relationships", "research_capabilities", "missing_dimensions"],
    "properties": {
        "implicit_relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["from_table", "from_column", "to_table", "to_column", "evidence", "confidence"],
            },
        },
        "research_capabilities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["study_type", "supported", "confidence", "rationale"],
            },
        },
        "missing_dimensions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["table", "missing_feature", "peer_tables"],
            },
        },
    },
}


def _validate_output(data: dict) -> dict:
    """Validate AI output against the expected JSON schema."""
    try:
        import jsonschema
        jsonschema.validate(data, _INTEGRATION_AI_JSON_SCHEMA)
        return data
    except ImportError:
        if not isinstance(data, dict):
            return {"implicit_relationships": [], "research_capabilities": [], "missing_dimensions": []}
        for key in ("implicit_relationships", "research_capabilities", "missing_dimensions"):
            if key not in data or not isinstance(data.get(key), list):
                data[key] = []
        return data
    except Exception:
        return {"implicit_relationships": [], "research_capabilities": [], "missing_dimensions": []}


# ── Main Entry Point ──────────────────────────────────────────────────

async def analyze(
    schema: Dict[str, Any],
    semantic_output: Optional[Dict[str, Any]] = None,
    *,
    db_pool=None,
    user_id: str = "default",
    connection_id: Optional[int] = None,
    model: Optional[str] = None,
    language: str = "en",
) -> Dict[str, Any]:
    """Run Integration AI analysis.

    Args:
        schema: Full extracted schema (tables, columns, types, FKs).
        semantic_output: Output from Semantic AI (column meanings, domains, purposes).
        db_pool: Database pool for AI connection lookup.
        user_id: User ID for AI connection lookup.
        connection_id: Optional specific AI connection to use.
        language: ISO 639-1 code for the response language.

    Returns:
        dict with 'implicit_relationships', 'research_capabilities',
        'missing_dimensions', and 'status' ('ok' or 'error').
    """
    from .llm_client import call_llm, extract_json

    user_context = _build_user_context(schema, semantic_output, max_chars=20_000)

    logger.info(
        "Integration AI: analysing %d tables, context=%d chars (language=%s)",
        len(schema.get("tables", [])),
        len(user_context),
        language,
    )

    result = await call_llm(
        system_prompt=_INTEGRATION_AI_SYSTEM_PROMPT,
        user_context=user_context,
        db_pool=db_pool,
        user_id=user_id,
        connection_id=connection_id,
        model=model,
        language=language,
        caller="Integration AI",
    )

    if "error" in result:
        logger.warning("Integration AI failed: %s", result["error"])
        return {
            "status": "error",
            "error": result["error"],
            "implicit_relationships": [],
            "research_capabilities": [],
            "missing_dimensions": [],
        }

    data = extract_json(result["content"])

    if data is None:
        logger.warning("Integration AI returned invalid JSON. Raw (200 chars): %s",
                       result["content"][:200])
        return {
            "status": "error",
            "error": "LLM output could not be parsed as JSON",
            "implicit_relationships": [],
            "research_capabilities": [],
            "missing_dimensions": [],
        }

    validated = _validate_output(data)
    validated["status"] = "ok"
    return validated
