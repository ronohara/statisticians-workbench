"""
Semantic AI — Column Meaning Inference & Code System Detection.

Receives the full schema and sample values for text columns, then uses an
LLM to infer column meanings, detect standard coding systems (ICD-10,
CPT, LOINC, SNOMED), classify table domains (Clinical, Administrative,
etc.), and describe table purposes.

This is the second of three AI specialists in the Database Design
enhancement pipeline. It runs alongside Schema AI and Integration AI.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Prompt Template ───────────────────────────────────────────────────

_SEMANTIC_AI_SYSTEM_PROMPT = """You are a data analyst examining a database schema. Your task is to infer the meaning of column names and sample values, detect standard coding systems where present, and classify each table's domain.

You will receive:
1. A list of tables with their columns and data types
2. For text/varchar columns: up to 50 distinct sample values (first 100 characters each)

For each column:
- Infer a human-readable meaning from the column name and sample values. Opaque names like "scr_ecog" or "t2_diab" should be explained.
- Check if the column values match a known coding system:
  * ICD-10: letter followed by 2-3 digits (e.g., "E11.9", "J45")
  * CPT: exactly 5 digits (e.g., "99213", "43239")
  * LOINC: NNNNN-N format (e.g., "26453-1", "4548-4")
  * SNOMED CT: 9+ digits (e.g., "22298006", "73211009")
  * NDC: 10-11 digits in 4-4-2 or 5-3-2 or 5-4-1 format
- Report detection confidence: "high" (>80% values match), "medium" (40-80%), "low" (<40%)

For each table, classify using ISIC Rev.4 codes. Format: a section letter A–U followed by 2–4 digits (e.g., G4763). Always include the letter prefix — bare numbers are invalid. Include a short description: e.g., "G4763 (Retail sale of sporting equipment)" or "Q (Health and social work)". A table may span multiple codes.

For each table, describe its purpose in one sentence: what does this table represent? Customer orders? Competition results? Lab measurements? Financial transactions?

Return ONLY valid JSON matching this schema. No markdown, no explanation outside the JSON:

{
  "columns": [
    {
      "name": "scr_ecog",
      "table": "patients",
      "meaning": "ECOG Performance Status (0-5 oncology functional assessment scale)",
      "confidence": "high"
    }
  ],
  "code_systems": [
    {
      "column": "diagnosis_code",
      "table": "diagnoses",
      "system": "ICD-10-CM",
      "confidence": "high",
      "evidence": "45 of 50 sample values match ICD-10 format"
    }
  ],
  "domains": [
    {
      "table": "patients",
      "domains": ["Q8610 (Hospital activities)", "Q (Human health and social work activities)"],
      "confidence": "high"
    }
  ],
  "table_purposes": [
    {
      "table": "patients",
      "purpose": "Core patient registry storing demographic and baseline clinical data for each patient"
    }
  ]
}

Rules:
- columns: one entry per column worth explaining. Skip obvious column names (id, name, date, etc.) unless they have unusual content.
- code_systems: only report columns with medium or high confidence detections. Include evidence (count/sample).
- domains: each table must have at least one domain. Multiple domains are common.
- table_purposes: one sentence per table. Specific to the data, not generic.
"""


def _build_user_context(
    schema: Dict[str, Any],
    sample_values: Optional[Dict[str, Any]] = None,
    max_chars: int = 12_000,
) -> str:
    """Build user context with schema info and text column sample values.

    Keeps under max_chars to fit within Flash LLM context windows.
    For schemas with many tables (>10), only shows table names +
    column counts to stay within limits. Sample values only if room permits.
    """
    tables = schema.get("tables", [])
    total_cols = sum(len(t.get("columns", [])) for t in tables)
    compact = len(tables) > 10 or total_cols > 150

    lines = ["## Schema\n"]
    lines.append(f"{len(tables)} tables, {total_cols} total columns\n")

    for t in tables:
        t_name = t.get("name", "unknown")
        cols = t.get("columns", [])
        if compact:
            # Just table name + column count for large schemas
            text_cols = [c.get("name","?") for c in cols if c.get("type","") in ("text","varchar","character varying","char","nvarchar","longtext","mediumtext")]
            lines.append(f"- {t_name} ({len(cols)} cols{', text: '+', '.join(text_cols[:5]) if text_cols else ''})")
        else:
            # Full column listing for small schemas
            lines.append(f"\n### Table: {t_name}")
            for c in cols:
                c_name = c.get("name", "?")
                c_type = c.get("type", c.get("data_type", "unknown"))
                lines.append(f"  - {c_name} ({c_type})")

    base = "\n".join(lines)
    remaining = max_chars - len(base) - 100

    # Phase 2: sample values only if room
    if sample_values and remaining > 500 and not compact:
        sample_lines = ["\n## Sample Values\n"]
        sample_chars = len("\n".join(sample_lines))
        for t in tables:
            t_name = t.get("name", "unknown")
            if t_name not in sample_values:
                continue
            sv = sample_values[t_name]
            if not sv:
                continue
            header = f"\n### {t_name}"
            sample_chars += len(header)
            if sample_chars > remaining:
                break
            sample_lines.append(header)
            for col_name, values in sv.items():
                if not values or not isinstance(values, list):
                    continue
                sample_str = ", ".join(str(v)[:100] for v in values[:5])
                line = f"  {col_name}: [{sample_str}{'...' if len(values) > 5 else ''}] ({len(values)} distinct)"
                sample_chars += len(line) + 1
                if sample_chars > remaining:
                    sample_lines.append("  ... (sample values truncated)")
                    break
                sample_lines.append(line)
            else:
                continue
            break
        base += "\n" + "\n".join(sample_lines)

    if len(base) > max_chars:
        base = base[:max_chars - 50] + "\n... (truncated)"

    return base


# ── Output Validation ─────────────────────────────────────────────────

_SEMANTIC_AI_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["columns", "code_systems", "domains", "table_purposes"],
    "properties": {
        "columns": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "table", "meaning", "confidence"],
            },
        },
        "code_systems": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["column", "table", "system", "confidence"],
            },
        },
        "domains": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["table", "domains", "confidence"],
            },
        },
        "table_purposes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["table", "purpose"],
            },
        },
    },
}


def _validate_output(data: dict) -> dict:
    """Validate AI output against the expected JSON schema."""
    try:
        import jsonschema
        jsonschema.validate(data, _SEMANTIC_AI_JSON_SCHEMA)
        return data
    except ImportError:
        if not isinstance(data, dict):
            return {"columns": [], "code_systems": [], "domains": [], "table_purposes": []}
        for key in ("columns", "code_systems", "domains", "table_purposes"):
            if key not in data or not isinstance(data.get(key), list):
                data[key] = []
        return data
    except Exception:
        return {"columns": [], "code_systems": [], "domains": [], "table_purposes": []}


# ── Main Entry Point ──────────────────────────────────────────────────

async def analyze(
    schema: Dict[str, Any],
    sample_values: Optional[Dict[str, Any]] = None,
    *,
    db_pool=None,
    user_id: str = "default",
    connection_id: Optional[int] = None,
    model: Optional[str] = None,
    language: str = "en",
) -> Dict[str, Any]:
    """Run Semantic AI analysis on a database schema.

    Args:
        schema: Full extracted schema (tables, columns, types).
        sample_values: Optional dict of {table_name: {col_name: [values]}}.
        db_pool: Database pool for AI connection lookup.
        user_id: User ID for AI connection lookup.
        connection_id: Optional specific AI connection to use.
        language: ISO 639-1 code for the response language.

    Returns:
        dict with 'columns', 'code_systems', 'domains', 'table_purposes',
        and 'status' ('ok' or 'error').
    """
    from .llm_client import call_llm, extract_json

    user_context = _build_user_context(schema, sample_values, max_chars=10_000)

    logger.info(
        "Semantic AI: analysing %d tables, context=%d chars (language=%s)",
        len(schema.get("tables", [])),
        len(user_context),
        language,
    )

    result = await call_llm(
        system_prompt=_SEMANTIC_AI_SYSTEM_PROMPT,
        user_context=user_context,
        db_pool=db_pool,
        user_id=user_id,
        connection_id=connection_id,
        model=model,
        language=language,
        caller="Semantic AI",
    )

    if "error" in result:
        logger.warning("Semantic AI failed: %s", result["error"])
        return {
            "status": "error",
            "error": result["error"],
            "columns": [],
            "code_systems": [],
            "domains": [],
            "table_purposes": [],
        }

    data = extract_json(result["content"])

    if data is None:
        logger.warning("Semantic AI returned invalid JSON. Raw (200 chars): %s",
                       result["content"][:200])
        return {
            "status": "error",
            "error": "LLM output could not be parsed as JSON",
            "columns": [],
            "code_systems": [],
            "domains": [],
            "table_purposes": [],
        }

    validated = _validate_output(data)
    validated["status"] = "ok"
    return validated
