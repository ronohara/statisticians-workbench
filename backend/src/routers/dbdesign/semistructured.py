"""
Semi-Structured Data Analysis for Database Design Assistant.
Analyses text/varchar columns for embedded codes, keywords, and patterns.
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple


# ============================================================
# CODE SYSTEM KNOWLEDGE BASE
# ============================================================

CODE_SYSTEMS = [
    # Healthcare — specific patterns, lower confidence threshold
    {
        "name": "ICD-10",
        "domain": "Healthcare",
        "patterns": [r"\b[A-Z]\d{2}(?:\.\d{1,3})?\b"],
        "min_confidence": 0.15,
        "context_words": ["diagnosis", "patient", "medical", "icd", "health", "clinical", "condition"],
    },
    # Financial — needs letter prefix to distinguish from medical numbers
    {
        "name": "ISIN",
        "domain": "Financial",
        "patterns": [r"\b[A-Z]{2}[A-Z0-9]{10}\b"],
        "min_confidence": 0.15,
        "context_words": ["isin", "security", "bond", "stock", "investment"],
    },
    {
        "name": "SIC/NAICS",
        "domain": "Financial",
        "patterns": [r"\b(SIC|NAICS)[:\s]*\d{4,6}\b", r"\b\d{4,6}\b.*\b(SIC|NAICS)\b"],
        "min_confidence": 0.20,
        "context_words": ["industry", "sic", "naics", "sector", "classification"],
    },
    # Logistics — specific prefix match
    {
        "name": "HS Code",
        "domain": "Logistics",
        "patterns": [r"\b(HS|HTS)[:\s]*\d{4,10}(?:\.\d{2,4})?\b"],
        "min_confidence": 0.20,
        "context_words": ["hs", "tariff", "customs", "import", "export", "commodity"],
    },
    # Retail — specific length for barcodes
    {
        "name": "UPC/EAN",
        "domain": "Retail",
        "patterns": [r"\b\d{12,13}\b"],
        "min_confidence": 0.25,
        "context_words": ["upc", "ean", "barcode", "gtin", "product", "sku"],
    },
    # General — always useful
    {
        "name": "Email",
        "domain": "General",
        "patterns": [r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"],
        "min_confidence": 0.10,
        "context_words": [],
    },
    {
        "name": "Date (ISO)",
        "domain": "General",
        "patterns": [r"\b\d{4}-\d{2}-\d{2}\b"],
        "min_confidence": 0.15,
        "context_words": ["date", "timestamp", "created", "updated"],
    },
]


# ============================================================
# PATTERN DETECTION
# ============================================================

def _is_text_column(col: Dict) -> bool:
    """Check if a column type is text/varchar."""
    dtype = col.get("type", "").lower()
    return any(t in dtype for t in ("text", "varchar", "char", "character"))


def _detect_key_value_patterns(samples: List[str]) -> bool:
    """Detect if samples contain key:value or key=value patterns."""
    kv_count = 0
    for sample in samples:
        if not sample:
            continue
        # Patterns: "key: value", "key = value", "key=value"
        if re.search(r"\w+\s*[:=]\s*\S", sample):
            kv_count += 1
    return kv_count >= len(samples) * 0.3  # at least 30% have key-value


def _detect_separators(samples: List[str]) -> Optional[str]:
    """Detect common separators in samples (pipe, comma, semicolon)."""
    separator_counts = {"|": 0, ";": 0, "\t": 0}
    for sample in samples:
        if not sample:
            continue
        for sep in separator_counts:
            if sep in sample:
                separator_counts[sep] += 1
    best = max(separator_counts, key=separator_counts.get)
    if separator_counts[best] >= len(samples) * 0.3:
        return best
    return None


# ============================================================
# CODE SYSTEM DETECTION
# ============================================================

def _detect_code_systems(samples: List[str], table_name: str = "", col_name: str = "") -> List[Dict]:
    """Identify code systems present in the samples using context-aware thresholds."""
    results = []
    context = (table_name + " " + col_name).lower()
    
    for cs in CODE_SYSTEMS:
        matches = 0
        total_potential = 0
        for sample in samples:
            if not sample:
                continue
            for pattern in cs["patterns"]:
                found = re.findall(pattern, sample)
                if found:
                    matches += 1
                total_potential += 1
        confidence = matches / max(total_potential, 1)
        
        # Boost confidence if context words match the domain
        context_boost = 0.0
        for word in cs.get("context_words", []):
            if word in context:
                context_boost = 0.15
                break
        
        threshold = cs.get("min_confidence", 0.20)
        if (confidence + context_boost) >= threshold:
            results.append({
                "name": cs["name"],
                "domain": cs["domain"],
                "confidence": round(confidence, 2),
                "sample_matches": min(matches, 5),
            })
    return sorted(results, key=lambda x: x["confidence"], reverse=True)


# ============================================================
# KEYWORD EXTRACTION
# ============================================================

def _extract_keywords(samples: List[str]) -> Dict[str, int]:
    """Extract distinct keyword tokens from text samples."""
    keywords = {}
    for sample in samples:
        if not sample:
            continue
        # Extract quoted strings
        for quoted in re.findall(r'"([^"]+)"', sample):
            keywords[quoted] = keywords.get(quoted, 0) + 1
        for quoted in re.findall(r"'([^']+)'", sample):
            keywords[quoted] = keywords.get(quoted, 0) + 1
        # Extract colon-prefixed values: "Label: value"
        for match in re.findall(r"\b[A-Za-z][\w\s]*:\s*([^,;|\n]+)", sample):
            val = match.strip()
            if len(val) > 1 and len(val) < 80:
                keywords[val] = keywords.get(val, 0) + 1
    # Filter: keep only keywords appearing multiple times
    return {k: v for k, v in keywords.items() if v >= 2}


# ============================================================
# CATEGORY CLASSIFIER
# ============================================================

def _classify_keywords(keywords: Dict[str, int]) -> Dict[str, List[str]]:
    """Classify keywords into high-level categories."""
    categories = {}
    
    category_keywords = {
        "Diagnosis Codes": ["diagnosis", "icd", "condition", "disease", "syndrome"],
        "Medication Codes": ["medication", "rx", "drug", "prescription", "dose"],
        "Industry Codes": ["industry", "naics", "sic", "sector", "vertical"],
        "Risk Ratings": ["risk", "rating", "level", "tier", "grade", "score"],
        "Location Codes": ["location", "city", "state", "country", "region", "zip"],
        "Product Codes": ["product", "sku", "item", "part", "upc", "ean"],
        "Status Values": ["status", "state", "phase", "stage", "active", "pending"],
        "Customer Segments": ["segment", "customer", "client", "enterprise", "smb"],
    }
    
    for kw in keywords:
        kw_lower = kw.lower()
        for cat, terms in category_keywords.items():
            if any(t in kw_lower for t in terms):
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(kw)
    
    return categories


# ============================================================
# MAIN ANALYSIS FUNCTION
# ============================================================

async def analyze_semi_structured(
    schema: Dict[str, Any],
    samples: Dict[str, List[str]],  # { "schema.table.column": [sample1, sample2, ...] }
    db_pool=None,
    language: str = "en",
) -> Dict[str, Any]:
    """Analyze text columns for semi-structured data."""
    tables = schema.get("tables", [])
    findings = []
    
    for table in tables:
        table_name = table["name"]
        table_schema = table.get("schema", "public")
        # Samples are keyed by table_name → {col_name: [values]}
        table_samples = samples.get(table_name, {})
        
        for col in table.get("columns", []):
            if not _is_text_column(col):
                continue
            
            col_name = col["name"]
            col_samples = table_samples.get(col_name, [])
            
            if not col_samples:
                continue
            
            # Filter out None/empty samples
            col_samples = [s for s in col_samples if s]
            if len(col_samples) < 3:
                continue
            
            result = {
                "table": table_name,
                "schema": table_schema,
                "column": col_name,
                "sample_count": len(col_samples),
            }
            
            # 1. Pattern detection
            result["has_key_value_pairs"] = _detect_key_value_patterns(col_samples)
            result["separator"] = _detect_separators(col_samples)
            
            # 2. Code system detection (context-aware with table/column names)
            code_systems = _detect_code_systems(col_samples, table_name, col_name)
            if code_systems:
                result["code_systems"] = code_systems
            
            # 3. Keyword extraction
            keywords = _extract_keywords(col_samples)
            if keywords:
                result["keywords"] = {k: v for k, v in sorted(keywords.items(), key=lambda x: -x[1])[:20]}
                result["unique_keywords"] = len(keywords)
            
            # 4. Category classification
            if keywords:
                categories = _classify_keywords(keywords)
                if categories:
                    result["categories"] = categories
            
            # 5. Reference table potential
            if keywords and len(keywords) > 5 and len(keywords) < 500:
                from src.utils.translation import t as tr_func
                result["reference_table_potential"] = {
                    "type": "controlled_vocabulary",
                    "confidence": 0.85,
                    "description": await tr_func(
                        db_pool, language,
                        "dbdesign.analysis.semistructured.controlled_vocab",
                        "Column {column} contains a controlled vocabulary of {count} distinct values",
                        column=col_name, count=len(keywords),
                    ) if db_pool else f"Column {col_name} contains a controlled vocabulary of {len(keywords)} distinct values",
                    "recommendation": await tr_func(
                        db_pool, language,
                        "dbdesign.analysis.semistructured.create_ref_table",
                        "Create a reference table for {column} values to normalize the {table} table",
                        column=col_name, table=table_name,
                    ) if db_pool else f"Create a reference table for {col_name} values to normalize the {table_name} table",
                }
            
            # Only include if actual semi-structured content was detected
            # (key_value_pairs and separators are supplementary; they don't count alone)
            has_findings = (
                result.get("code_systems") or
                result.get("keywords") or
                result.get("reference_table_potential")
            )
            if has_findings:
                findings.append(result)
    
    # Summary
    return {
        "total_text_columns": sum(
            1 for t in tables for c in t.get("columns", []) if _is_text_column(c)
        ),
        "columns_with_findings": len(findings),
        "findings": findings,
    }


async def generate_normalisation_suggestions(
    semi_structured: Dict[str, Any],
    db_pool,
    samples: Dict[str, List[str]],
    language: str = "en",
    ai_connection_id: Optional[int] = None,
    ai_model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Generate actionable normalisation suggestions using AI.
    
    Sends sample data from semi-structured columns to the configured AI provider
    and parses the response into structured reference table proposals.
    """
    if not semi_structured:
        return []
    
    findings = semi_structured.get("findings", [])
    
    if not findings:
        return []
    
    return await _ai_normalisation_suggestions(db_pool, semi_structured, samples, language,
                                                ai_connection_id=ai_connection_id, ai_model=ai_model)


async def _ai_normalisation_suggestions(
    db_pool,
    semi_structured: Dict[str, Any],
    samples: Dict[str, List[str]],
    language: str = "en",
    ai_connection_id: Optional[int] = None,
    ai_model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Ask the AI provider to analyse semi-structured samples and propose reference tables."""
    import json as json_mod
    
    if ai_connection_id is None:
        return _rule_based_suggestions(semi_structured)  # fallback
    
    # Build the prompt with sample data
    findings = semi_structured.get("findings", [])
    sample_texts = []
    for f in findings:
        key = f"{f['schema']}.{f['table']}.{f['column']}"
        # Samples are keyed by table_name → {col_name: [values]}
        table_samples = samples.get(f['table'], {})
        col_samples = table_samples.get(f['column'], [])
        if col_samples:
            sample_texts.append(f"Column: {key}")
            sample_texts.append(f"Samples ({len(col_samples)} rows):")
            for s in col_samples[:500]:
                sample_texts.append(f"  {s[:300]}")
            sample_texts.append("")
    
    if not sample_texts:
        return []
    
    sample_data = chr(10).join(sample_texts[:8000])
    
    # Delegate to DatabaseDesignerAgent via Agent Framework
    try:
        from src.agents.database_designer import DatabaseDesignerAgent
        agent = DatabaseDesignerAgent(
            db_pool=db_pool,
            connection_id=ai_connection_id,
            user_id="semistructured",
            model=ai_model,
            language=language,
        )
        content = await agent.ask("", sample_data=sample_data)
    except Exception:
        return _rule_based_suggestions(semi_structured)
    
    # Parse JSON from AI response (may be wrapped in markdown code blocks)
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    
    try:
        suggestions = json_mod.loads(content)
    except (json.JSONDecodeError, ValueError):
        return _rule_based_suggestions(semi_structured)
    
    # Guard: AI may return a single object instead of an array
    if isinstance(suggestions, dict):
        suggestions = [suggestions]
    elif not isinstance(suggestions, list):
        return []
    
    # Normalise into the format the frontend expects
    result = []
    for s in suggestions:
        result.append({
            "description": s.get("rationale", s.get("description", "")),
            "confidence": 0.85,
            "business_value": s.get("business_value", ""),
            "source_column": s.get("source_column", ""),
            "proposed_table": {
                "name": s.get("table_name", ""),
                "columns": s.get("columns", []),
            },
            "proposed_migration": s.get("migration_sql", ""),
        })
    
    return result if result else _rule_based_suggestions(semi_structured)

def _rule_based_suggestions(semi_structured: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fallback: rule-based suggestions when no AI provider is available."""
    suggestions = []
    findings = semi_structured.get("findings", [])
    for f in findings:
        keywords = f.get("keywords", {})
        unique_count = f.get("unique_keywords", len(keywords))
        if unique_count < 4 or unique_count > 500:
            continue
        suggestions.append({
            "description": f"Column {f.get('schema','')}.{f.get('table','')}.{f.get('column','')} contains {unique_count} distinct values worth normalising.",
            "confidence": 0.70,
            "business_value": f"Standardise {unique_count} distinct values",
            "proposed_table": {
                "name": f"{f.get('table','')}_{f.get('column','')}_ref",
                "columns": [
                    {"name": "id", "type": "SERIAL", "nullable": False},
                    {"name": "value", "type": "VARCHAR(255)", "nullable": False},
                ],
            },
        })
    return suggestions
