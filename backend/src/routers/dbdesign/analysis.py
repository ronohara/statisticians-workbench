"""
Structured analysis engine for the Database Design Assistant.
Analyzes extracted schema for indexing, normalisation, relationship,
data type, and naming issues.

All user-visible messages go through the translation system via t().
"""

from typing import Dict, Any, List, Optional
from src.utils.translation import t
from .translations import ANALYSIS_TK
import asyncio
import logging


async def analyze_schema(
    schema: Dict[str, Any],
    db_pool,
    language: str,
    *,
    use_ai: bool = False,
    user_id: str = "default",
    connection_id: Optional[int] = None,
    sample_values: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Run all structured analysis rules on the extracted schema.

    Args:
        schema: Extracted schema (tables, columns, types, FKs).
        db_pool: Database pool for AI connection and translation.
        language: ISO 639-1 code for translations and AI responses.
        use_ai: When True, runs three AI specialists in parallel to augment
                the mechanical analysis with semantic understanding,
                domain classification, and cross-table intelligence.
        user_id: User ID for AI connection lookup.
        connection_id: Optional specific AI connection to use.
        sample_values: Optional dict of {table: {col: [values]}} for Semantic AI.
    """
    tables = schema.get("tables", [])

    issues = []

    # Build lookup maps
    fk_columns = _build_fk_map(tables)
    all_columns_by_table = {t["name"]: [c["name"] for c in t["columns"]] for t in tables}

    for table in tables:
        # 1. Indexing analysis
        issues.extend(await _analyze_indexing(table, fk_columns, db_pool, language))

        # 2. Normalisation analysis
        issues.extend(await _analyze_normalisation(table, db_pool, language))

        # 3. Relationship analysis
        issues.extend(await _analyze_relationships(table, tables, db_pool, language))

        # 4. Data type analysis
        issues.extend(await _analyze_data_types(table, all_columns_by_table, db_pool, language))

        # 5. Naming analysis
        issues.extend(await _analyze_naming(table, db_pool, language))

    # Classify risk levels
    for issue in issues:
        if issue["severity"] in ("CRITICAL", "HIGH"):
            issue["risk"] = "HIGH"
        elif issue["severity"] in ("MEDIUM",):
            issue["risk"] = "MEDIUM"
        else:
            issue["risk"] = "LOW"

    mechanical_output = {
        "total_tables": len(tables),
        "total_columns": sum(len(t["columns"]) for t in tables),
        "total_issues": len(issues),
        "critical": len([i for i in issues if i["severity"] == "CRITICAL"]),
        "high": len([i for i in issues if i["severity"] == "HIGH"]),
        "medium": len([i for i in issues if i["severity"] == "MEDIUM"]),
        "low": len([i for i in issues if i["severity"] == "LOW"]),
        "issues": issues,
    }

    # AI augmentation — three specialists run in parallel
    if use_ai:
        return await _augment_with_ai(
            schema, mechanical_output, sample_values,
            db_pool, user_id, connection_id, language,
            model=model,
        )

    return mechanical_output


async def _augment_with_ai(
    schema: Dict[str, Any],
    mechanical: Dict[str, Any],
    sample_values: Optional[Dict[str, Any]],
    db_pool,
    user_id: str,
    connection_id: Optional[int],
    language: str,
    *,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Run all three AI specialists in parallel and merge results."""
    from .schema_ai import analyze as schema_ai_analyze
    from .semantic_ai import analyze as semantic_ai_analyze
    from .integration_ai import analyze as integration_ai_analyze
    from .coordinator import merge

    logger = logging.getLogger(__name__)

    async def run_schema_ai():
        try:
            return await schema_ai_analyze(
                schema, mechanical,
                db_pool=db_pool, user_id=user_id,
                connection_id=connection_id, language=language,
                model=model,
            )
        except Exception as e:
            logger.warning("Schema AI crashed: %s", e)
            return {"status": "error", "error": str(e)}

    async def run_semantic_ai():
        try:
            return await semantic_ai_analyze(
                schema, sample_values,
                db_pool=db_pool, user_id=user_id,
                connection_id=connection_id, language=language,
                model=model,
            )
        except Exception as e:
            logger.warning("Semantic AI crashed: %s", e)
            return {"status": "error", "error": str(e)}

    async def run_integration_ai():
        try:
            return await integration_ai_analyze(
                schema, None,  # semantic output not available at this level
                db_pool=db_pool, user_id=user_id,
                connection_id=connection_id, language=language,
                model=model,
            )
        except Exception as e:
            logger.warning("Integration AI crashed: %s", e)
            return {"status": "error", "error": str(e)}

    logger.info("Running three AI specialists in parallel...")
    s_ai, sem_ai, i_ai = await asyncio.gather(
        run_schema_ai(), run_semantic_ai(), run_integration_ai(),
    )

    return merge(mechanical, s_ai, sem_ai, i_ai)


def _build_fk_map(tables: List[Dict]) -> Dict[str, List[str]]:
    """Build map of foreign key columns across all tables."""
    fk_cols = {}
    for t in tables:
        for fk in t.get("foreign_keys", []):
            key = f"{t['name']}.{fk['column']}"
            if key not in fk_cols:
                fk_cols[key] = []
            fk_cols[key].append({
                "referenced_table": fk["referenced_table"],
                "referenced_column": fk["referenced_column"],
            })
    return fk_cols


# ============================================================
# 1. INDEXING ANALYSIS
# ============================================================

async def _analyze_indexing(
    table: Dict, fk_columns: Dict, db_pool, language: str
) -> List[Dict]:
    """Analyze indexing: missing indexes on FK columns."""
    issues = []
    table_name = table["name"]
    schema = table["schema"]

    indexed_columns = set()
    for idx in table.get("indexes", []):
        if idx.get("definition"):
            parts = idx["definition"].split("(")
            if len(parts) > 1:
                cols = parts[1].rstrip(")").split(",")
                for col in cols:
                    indexed_columns.add(col.strip())

    # Check FK columns for indexes
    for col in table.get("columns", []):
        col_name = col["name"]

        if _is_foreign_key(table, col_name, fk_columns):
            if col_name not in indexed_columns:
                issues.append({
                    "category": "indexing",
                    "severity": "HIGH",
                    "table": table_name,
                    "schema": schema,
                    "column": col_name,
                    "message": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.indexing.missing_fk_index"],
                        column=col_name,
                    ),
                    "recommendation": f"CREATE INDEX idx_{table_name}_{col_name} ON {schema}.{table_name}({col_name});",
                })

    return issues


def _is_foreign_key(table: Dict, col_name: str, fk_columns: Dict) -> bool:
    """Check if a column is a foreign key."""
    key = f"{table['name']}.{col_name}"
    return key in fk_columns or any(
        fk["column"] == col_name for fk in table.get("foreign_keys", [])
    )


# ============================================================
# 2. NORMALISATION ANALYSIS
# ============================================================

async def _analyze_normalisation(
    table: Dict, db_pool, language: str
) -> List[Dict]:
    """Analyze normalisation: repeating groups, denormalised data."""
    issues = []
    table_name = table["name"]
    schema = table["schema"]

    columns = table.get("columns", [])
    col_names = [c["name"] for c in columns]

    # Detect repeating groups (columns like phone1, phone2, phone3)
    base_names = {}
    for col in columns:
        name = col["name"]
        import re
        match = re.match(r"^(.+?)(\d+)$", name)
        if match:
            base = match.group(1)
            if base not in base_names:
                base_names[base] = []
            base_names[base].append(name)

    for base, names in base_names.items():
        if len(names) > 1:
            issues.append({
                "category": "normalisation",
                "severity": "HIGH",
                "table": table_name,
                "schema": schema,
                "message": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.normalisation.repeating_group"],
                    columns=", ".join(names),
                ),
                "recommendation": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.normalisation.create_separate_table"],
                    base=base, table=table_name,
                ),
            })

    # Detect multiple address/contact fields
    address_patterns = ["address", "city", "state", "zip", "postcode", "country"]
    address_count = sum(1 for c in col_names if any(p in c.lower() for p in address_patterns))
    if address_count >= 3:
        issues.append({
            "category": "normalisation",
            "severity": "MEDIUM",
            "table": table_name,
            "schema": schema,
            "message": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.normalisation.multiple_address"],
                count=address_count,
            ),
            "recommendation": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.normalisation.separate_address_table"],
                table=table_name,
            ),
        })

    return issues


# ============================================================
# 3. RELATIONSHIP ANALYSIS
# ============================================================

async def _analyze_relationships(
    table: Dict, all_tables: List[Dict], db_pool, language: str
) -> List[Dict]:
    """Analyze relationships: missing FK constraints."""
    issues = []
    table_name = table["name"]
    schema = table["schema"]

    columns = table.get("columns", [])

    for col in columns:
        name = col["name"].lower()
        if name.endswith("_id") or name.endswith("_fk"):
            # Check if a FK constraint exists for this column
            has_fk = any(
                fk["column"].lower() == col["name"].lower()
                for fk in table.get("foreign_keys", [])
            )

            if not has_fk and name != "id":
                issues.append({
                    "category": "relationships",
                    "severity": "MEDIUM",
                    "table": table_name,
                    "schema": schema,
                    "column": col["name"],
                    "message": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.relationships.missing_fk"],
                        column=col["name"],
                    ),
                    "recommendation": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.relationships.add_fk"],
                        column=col["name"],
                    ),
                })

    return issues


# ============================================================
# 4. DATA TYPE ANALYSIS
# ============================================================

async def _analyze_data_types(
    table: Dict, all_columns: Dict[str, List[str]], db_pool, language: str
) -> List[Dict]:
    """Analyze data types: inappropriate types, missing constraints."""
    issues = []
    table_name = table["name"]
    schema = table["schema"]

    for col in table.get("columns", []):
        col_type = col["type"].lower()
        col_name = col["name"].lower()

        # Check for text columns that could be enum/boolean
        if col_type in ("text", "varchar", "character varying"):
            max_len = col.get("max_length")
            if max_len and max_len <= 3:
                issues.append({
                    "category": "data_types",
                    "severity": "LOW",
                    "table": table_name,
                    "schema": schema,
                    "column": col["name"],
                    "message": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.data_types.short_text_enum"],
                        column=col["name"], max_len=max_len,
                    ),
                    "recommendation": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.data_types.add_check_constraint"],
                        column=col["name"],
                    ),
                })

        # Check for varchar without limit
        if col_type == "character varying" and col.get("max_length") is None:
            issues.append({
                "category": "data_types",
                "severity": "LOW",
                "table": table_name,
                "schema": schema,
                "column": col["name"],
                "message": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.data_types.unbounded_varchar"],
                    column=col["name"],
                ),
                "recommendation": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.data_types.set_max_length"],
                    column=col["name"],
                ),
            })

        # Check for nullable columns that probably shouldn't be
        if col_type in ("text", "varchar", "character varying") and col["nullable"]:
            if any(keyword in col_name for keyword in ["name", "title", "email", "code", "status"]):
                issues.append({
                    "category": "data_types",
                    "severity": "LOW",
                    "table": table_name,
                    "schema": schema,
                    "column": col["name"],
                    "message": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.data_types.allows_null"],
                        column=col["name"],
                    ),
                    "recommendation": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.data_types.add_not_null"],
                        column=col["name"],
                    ),
                })

    return issues


# ============================================================
# 5. NAMING ANALYSIS
# ============================================================

async def _analyze_naming(
    table: Dict, db_pool, language: str
) -> List[Dict]:
    """Analyze naming: inconsistent naming, reserved keywords, ambiguous names."""
    issues = []
    table_name = table["name"]
    schema = table["schema"]

    POSTGRESQL_RESERVED = {
        "user", "group", "order", "table", "select", "from", "where",
        "grant", "role", "schema", "type", "cast", "check", "create",
        "default", "delete", "drop", "insert", "update", "values",
    }

    for col in table.get("columns", []):
        col_name = col["name"].lower()

        if col_name in POSTGRESQL_RESERVED:
            issues.append({
                "category": "naming",
                "severity": "MEDIUM",
                "table": table_name,
                "schema": schema,
                "column": col["name"],
                "message": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.naming.reserved_keyword_column"],
                    column=col["name"],
                ),
                "recommendation": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.naming.rename_column_reserved"],
                    column=col["name"],
                ),
            })

    # Check table name
    if table_name.lower() in POSTGRESQL_RESERVED:
        issues.append({
            "category": "naming",
            "severity": "MEDIUM",
            "table": table_name,
            "schema": schema,
            "message": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.naming.reserved_keyword_table"],
                table=table_name,
            ),
            "recommendation": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.naming.rename_table_reserved"],
                table=table_name,
            ),
        })

    # Check for inconsistent naming (camelCase vs snake_case)
    if any(c.isupper() for c in table_name):
        issues.append({
            "category": "naming",
            "severity": "LOW",
            "table": table_name,
            "schema": schema,
            "message": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.naming.mixed_case_table"],
                table=table_name,
            ),
            "recommendation": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.naming.rename_table_snake_case"],
            ),
        })

    for col in table.get("columns", []):
        if any(c.isupper() for c in col["name"]):
            issues.append({
                "category": "naming",
                "severity": "LOW",
                "table": table_name,
                "schema": schema,
                "column": col["name"],
                "message": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.naming.mixed_case_column"],
                    column=col["name"],
                ),
                "recommendation": await t(db_pool, language, ANALYSIS_TK["dbdesign.analysis.naming.rename_column_snake_case"],
                ),
            })

    return issues
