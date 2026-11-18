"""
Translation keys for the Database Design Assistant router.
Imported by all submodules in the dbdesign package.
"""

from dataclasses import dataclass


@dataclass
class TranslationKey:
    """A translation key with an English fallback."""
    key: str
    fallback: str


# ============================================================
# TranslationKey entries for the extraction script
# ============================================================
# The extract-translations.py script scans for TranslationKey("key", "fallback")
# patterns. These entries expose the dbdesign keys to the extraction system.

DBDESIGN_TK = {
    "dbdesign.title": TranslationKey("dbdesign.title", "Database Design Assistant"),
    "dbdesign.description": TranslationKey("dbdesign.description", "Analyze and improve your database design using AI."),
    "dbdesign.not_implemented": TranslationKey("dbdesign.not_implemented", "This feature is coming soon."),
    "dbdesign.no_connection": TranslationKey("dbdesign.no_connection", "No database connection available. Please connect to a database first."),
    "dbdesign.schema_error": TranslationKey("dbdesign.schema_error", "Failed to extract schema: {error}"),
    "dbdesign.analyze_error": TranslationKey("dbdesign.analyze_error", "Failed to analyze database: {error}"),
    "dbdesign.connection_error": TranslationKey("dbdesign.connection_error", "Failed to connect to database: {error}"),
    "dbdesign.unsupported_type": TranslationKey("dbdesign.unsupported_type", "Only PostgreSQL, MySQL, MS SQL Server, and Microsoft Access databases are supported"),
    "dbdesign.report_data_required": TranslationKey("dbdesign.report_data_required", "Report data is required"),
    "dbdesign.question_required": TranslationKey("dbdesign.question_required", "Question is required"),
    # ---- Inline keys migrated from router call sites (P2) ----
    "rag.ai_provider_error": TranslationKey(
        "rag.ai_provider_error",
        "AI provider error: {error}"
    ),
    "dbdesign.invalid_token": TranslationKey(
        "dbdesign.invalid_token",
        "Invalid token"
    ),
    "rag.no_ai_provider": TranslationKey(
        "rag.no_ai_provider",
        "Found {count} matching records. (No AI provider configured for natural-language answers.)"
    ),
    "rag.no_matches": TranslationKey(
        "rag.no_matches",
        "No matching text found in the database for your question. Try rephrasing or selecting a different data source."
    ),
    "rag.no_tables": TranslationKey(
        "rag.no_tables",
        "No tables found in the schema to search."
    ),
    "dbdesign.pdf_error": TranslationKey(
        "dbdesign.pdf_error",
        "Failed to generate PDF: {error}"
    ),
    "error.database.pool_not_initialized": TranslationKey(
        "error.database.pool_not_initialized",
        "Database pool not initialized"
    ),
    "dbdesign.rag_error": TranslationKey(
        "dbdesign.rag_error",
        "RAG query failed: {error}"
    ),
    "dbdesign.rag_not_available": TranslationKey(
        "dbdesign.rag_not_available",
        "RAG search is only available for PostgreSQL databases. MySQL text search is planned for a future release."
    ),
    "dbdesign.schema_error_2": TranslationKey(
        "dbdesign.schema_error_2",
        "Failed to decrypt database password: {error}"
    ),
    "dbdesign.unsupported_type_2": TranslationKey(
        "dbdesign.unsupported_type_2",
        "Only PostgreSQL, MySQL, and MS SQL Server databases are supported"
    ),
    # ---- SSE streaming progress + analysis-status keys ----
    # Converted from the plain DBDESIGN dict. They were previously built at
    # runtime as f"dbdesign.{key}" with an inline fallback, so the extractor
    # never saw them and they never reached the translation pipeline.
    "dbdesign.stream_connecting": TranslationKey("dbdesign.stream_connecting", "Connecting to database..."),
    "dbdesign.stream_connected": TranslationKey("dbdesign.stream_connected", "Connected to {db_type}: {db_name}"),
    "dbdesign.stream_extracting_schema": TranslationKey("dbdesign.stream_extracting_schema", "Extracting schema from {db_type}..."),
    "dbdesign.stream_unsupported_type": TranslationKey("dbdesign.stream_unsupported_type", "Unsupported database type: {db_type}"),
    "dbdesign.stream_schema_done": TranslationKey("dbdesign.stream_schema_done", "Schema extracted: {tables} tables, {columns} columns"),
    "dbdesign.stream_mechanical_start": TranslationKey("dbdesign.stream_mechanical_start", "Running mechanical analysis..."),
    "dbdesign.stream_mechanical_done": TranslationKey("dbdesign.stream_mechanical_done", "Mechanical analysis: {count} issues found"),
    "dbdesign.stream_ai_start": TranslationKey("dbdesign.stream_ai_start", "Starting AI analysis \u2014 3 specialists in parallel..."),
    "dbdesign.stream_ai_schema_start": TranslationKey("dbdesign.stream_ai_schema_start", "Schema AI: analysing {tables} tables..."),
    "dbdesign.stream_ai_schema_done": TranslationKey("dbdesign.stream_ai_schema_done", "Schema AI: health score {score}/100"),
    "dbdesign.stream_ai_semantic_start": TranslationKey("dbdesign.stream_ai_semantic_start", "Semantic AI: analysing {tables} tables..."),
    "dbdesign.stream_ai_semantic_done": TranslationKey("dbdesign.stream_ai_semantic_done", "Semantic AI: {columns} column meanings, {domains} ISIC domains"),
    "dbdesign.stream_ai_integration_start": TranslationKey("dbdesign.stream_ai_integration_start", "Integration AI: detecting relationships..."),
    "dbdesign.stream_ai_integration_done": TranslationKey("dbdesign.stream_ai_integration_done", "Integration AI: {relationships} relationships, {capabilities} capabilities"),
    "dbdesign.stream_ai_done": TranslationKey("dbdesign.stream_ai_done", "AI analysis complete \u2014 status: {status}"),
    "dbdesign.stream_semistructured_start": TranslationKey("dbdesign.stream_semistructured_start", "Analysing semi-structured columns..."),
    "dbdesign.stream_normalisation_start": TranslationKey("dbdesign.stream_normalisation_start", "Generating normalisation suggestions..."),
    "dbdesign.stream_normalisation_done": TranslationKey("dbdesign.stream_normalisation_done", "Normalisation: {count} suggestions"),
    "dbdesign.stream_normalisation_timeout": TranslationKey("dbdesign.stream_normalisation_timeout", "Normalisation: timed out after 90s"),
    "dbdesign.stream_normalisation_skipped": TranslationKey("dbdesign.stream_normalisation_skipped", "Normalisation: skipped ({error})"),
    "dbdesign.stream_analysis_failed": TranslationKey("dbdesign.stream_analysis_failed", "Analysis failed: {error}"),
    "dbdesign.ai_skipped_message": TranslationKey(
        "dbdesign.ai_skipped_message",
        "AI analysis skipped \u2014 {count} issues found (limit: {limit}). Review mechanical findings below, clean up the database, then re-run with AI."
    ),
    "dbdesign.ai_skipped_reason": TranslationKey(
        "dbdesign.ai_skipped_reason",
        "This report contains mechanical analysis only. AI-augmented analysis was skipped because the database generated {count} issues (limit: {limit}). Review the mechanical findings below, clean up the database, then re-run with AI for context-aware explanations, semantic insights, and normalisation suggestions."
    ),
    "dbdesign.analysis_complete": TranslationKey("dbdesign.analysis_complete", "Analysis complete"),
    "dbdesign.analysis_cancelled": TranslationKey("dbdesign.analysis_cancelled", "Analysis stream cancelled (client disconnected)"),
}

PDF_REPORT_TK = {
    "dbdesign.pdf.header": TranslationKey("dbdesign.pdf.header", "Database Design Analysis Report"),
    "dbdesign.pdf.title": TranslationKey("dbdesign.pdf.title", "Database Design Analysis"),
    "dbdesign.pdf.subtitle": TranslationKey("dbdesign.pdf.subtitle", "Database: {db_name} ({db_type}) | Connection: {conn_name} (ID: {conn_id})"),
    "dbdesign.pdf.summary": TranslationKey("dbdesign.pdf.summary", "Summary"),
    "dbdesign.pdf.tables": TranslationKey("dbdesign.pdf.tables", "Tables"),
    "dbdesign.pdf.columns": TranslationKey("dbdesign.pdf.columns", "Columns"),
    "dbdesign.pdf.rows": TranslationKey("dbdesign.pdf.rows", "Rows"),
    "dbdesign.pdf.issues_found": TranslationKey("dbdesign.pdf.issues_found", "Issues Found"),
    "dbdesign.pdf.risk_breakdown": TranslationKey("dbdesign.pdf.risk_breakdown", "Risk Breakdown"),
    "dbdesign.pdf.high": TranslationKey("dbdesign.pdf.high", "High"),
    "dbdesign.pdf.medium": TranslationKey("dbdesign.pdf.medium", "Medium"),
    "dbdesign.pdf.low": TranslationKey("dbdesign.pdf.low", "Low"),
    "dbdesign.pdf.top_recommendations": TranslationKey("dbdesign.pdf.top_recommendations", "Top Recommendations"),
    "dbdesign.pdf.issues_count": TranslationKey("dbdesign.pdf.issues_count", "Issues ({count})"),
    "dbdesign.pdf.semi_structured_title": TranslationKey("dbdesign.pdf.semi_structured_title", "Semi-Structured Data Analysis ({count} columns)"),
    "dbdesign.pdf.none": TranslationKey("dbdesign.pdf.none", "None"),
    "dbdesign.pdf.code_systems": TranslationKey("dbdesign.pdf.code_systems", "Code Systems"),
    "dbdesign.pdf.top_keywords": TranslationKey("dbdesign.pdf.top_keywords", "Top keywords"),
    "dbdesign.pdf.categories": TranslationKey("dbdesign.pdf.categories", "Categories"),
    "dbdesign.pdf.normalisation_title": TranslationKey("dbdesign.pdf.normalisation_title", "Normalisation Suggestions ({count})"),
    "dbdesign.pdf.confidence": TranslationKey("dbdesign.pdf.confidence", "Confidence"),
    "dbdesign.pdf.value": TranslationKey("dbdesign.pdf.value", "Value"),
    "dbdesign.pdf.proposed_table": TranslationKey("dbdesign.pdf.proposed_table", "Proposed table"),
    "dbdesign.pdf.schema_title": TranslationKey("dbdesign.pdf.schema_title", "Schema ({count} tables)"),
    "dbdesign.pdf.col_name": TranslationKey("dbdesign.pdf.col_name", "Column"),
    "dbdesign.pdf.col_type": TranslationKey("dbdesign.pdf.col_type", "Type"),
    "dbdesign.pdf.col_nullable": TranslationKey("dbdesign.pdf.col_nullable", "Nullable"),
    "dbdesign.pdf.col_pk": TranslationKey("dbdesign.pdf.col_pk", "PK"),
    "dbdesign.pdf.col_default": TranslationKey("dbdesign.pdf.col_default", "Default"),
    "dbdesign.pdf.yes": TranslationKey("dbdesign.pdf.yes", "YES"),
    "dbdesign.pdf.no": TranslationKey("dbdesign.pdf.no", "NO"),
    "dbdesign.pdf.pk": TranslationKey("dbdesign.pdf.pk", "PK"),
    "dbdesign.pdf.page": TranslationKey("dbdesign.pdf.page", "Page {current}/{total}"),
    # AI-augmented sections
    "dbdesign.pdf.health_score_title": TranslationKey("dbdesign.pdf.health_score_title", "Health Score"),
    "dbdesign.pdf.health_score_subtitle": TranslationKey("dbdesign.pdf.health_score_subtitle", "Overall database health assessed by Schema AI. 0 = critical structural problems, 100 = production-ready."),
    "dbdesign.pdf.health_score_label": TranslationKey("dbdesign.pdf.health_score_label", "Database Health Score: {score}/100"),
    "dbdesign.pdf.top_actions_label": TranslationKey("dbdesign.pdf.top_actions_label", "Top Priority Actions"),
    "dbdesign.pdf.ai_disclaimer": TranslationKey("dbdesign.pdf.ai_disclaimer", "AI-generated analysis — review before applying to production."),
    "dbdesign.pdf.semantic_title": TranslationKey("dbdesign.pdf.semantic_title", "AI Semantic Analysis"),
    "dbdesign.pdf.semantic_subtitle": TranslationKey("dbdesign.pdf.semantic_subtitle", "AI-inferred column meanings, ISIC domain classifications, and code system detections."),
    "dbdesign.pdf.domain_label": TranslationKey("dbdesign.pdf.domain_label", "ISIC Domain Classifications"),
    "dbdesign.pdf.table_purposes_label": TranslationKey("dbdesign.pdf.table_purposes_label", "Table Purposes"),
    "dbdesign.pdf.column_meanings_label": TranslationKey("dbdesign.pdf.column_meanings_label", "Column Meanings"),
    "dbdesign.pdf.code_systems_label": TranslationKey("dbdesign.pdf.code_systems_label", "Detected Code Systems"),
    "dbdesign.pdf.integration_title": TranslationKey("dbdesign.pdf.integration_title", "AI Integration Findings"),
    "dbdesign.pdf.integration_subtitle": TranslationKey("dbdesign.pdf.integration_subtitle", "Implicit relationships, research capabilities, and missing dimensions detected by Integration AI."),
    "dbdesign.pdf.implicit_relationships_label": TranslationKey("dbdesign.pdf.implicit_relationships_label", "Implicit Relationships"),
    "dbdesign.pdf.research_capabilities_label": TranslationKey("dbdesign.pdf.research_capabilities_label", "Research Capabilities"),
    "dbdesign.pdf.missing_dimensions_label": TranslationKey("dbdesign.pdf.missing_dimensions_label", "Missing Dimensions"),
    "dbdesign.pdf.supported_label": TranslationKey("dbdesign.pdf.supported_label", "Supported"),
    "dbdesign.pdf.unsupported_label": TranslationKey("dbdesign.pdf.unsupported_label", "Not Supported"),
    "dbdesign.pdf.partial_label": TranslationKey("dbdesign.pdf.partial_label", "Partial"),
    "dbdesign.pdf.rationale_label": TranslationKey("dbdesign.pdf.rationale_label", "Rationale"),
    "dbdesign.pdf.relationship_label": TranslationKey("dbdesign.pdf.relationship_label", "Relationship"),
    "dbdesign.pdf.evidence_label": TranslationKey("dbdesign.pdf.evidence_label", "Evidence"),
    "dbdesign.pdf.proposed_ddl_label": TranslationKey("dbdesign.pdf.proposed_ddl_label", "Proposed DDL"),
    "dbdesign.pdf.confidence_label": TranslationKey("dbdesign.pdf.confidence_label", "Confidence"),
    "dbdesign.pdf.ai_skipped_warning": TranslationKey("dbdesign.pdf.ai_skipped_warning", "AI Analysis Skipped"),
}

# Analysis engine translation keys — used in analysis.py for issue messages and recommendations
ANALYSIS_TK = {
    "dbdesign.analysis.indexing.missing_fk_index": TranslationKey("dbdesign.analysis.indexing.missing_fk_index", "Foreign key column '{column}' has no index"),
    "dbdesign.analysis.normalisation.repeating_group": TranslationKey("dbdesign.analysis.normalisation.repeating_group", "Repeating group detected: {columns}"),
    "dbdesign.analysis.normalisation.create_separate_table": TranslationKey("dbdesign.analysis.normalisation.create_separate_table", "Create a separate table for '{base}' values with a FK to {table}"),
    "dbdesign.analysis.normalisation.multiple_address": TranslationKey("dbdesign.analysis.normalisation.multiple_address", "Multiple address-related columns ({count}) detected"),
    "dbdesign.analysis.normalisation.separate_address_table": TranslationKey("dbdesign.analysis.normalisation.separate_address_table", "Consider creating a separate address table with FK to {table}"),
    "dbdesign.analysis.relationships.missing_fk": TranslationKey("dbdesign.analysis.relationships.missing_fk", "Column '{column}' looks like a foreign key but has no FK constraint"),
    "dbdesign.analysis.relationships.add_fk": TranslationKey("dbdesign.analysis.relationships.add_fk", "Consider adding a FK constraint if '{column}' references another table"),
    "dbdesign.analysis.data_types.short_text_enum": TranslationKey("dbdesign.analysis.data_types.short_text_enum", "Text column '{column}' has max length of {max_len} \u2014 consider using ENUM or CHECK constraint"),
    "dbdesign.analysis.data_types.add_check_constraint": TranslationKey("dbdesign.analysis.data_types.add_check_constraint", "Add a CHECK constraint or use an ENUM type for '{column}' with limited valid values"),
    "dbdesign.analysis.data_types.unbounded_varchar": TranslationKey("dbdesign.analysis.data_types.unbounded_varchar", "Unbounded VARCHAR column '{column}'"),
    "dbdesign.analysis.data_types.set_max_length": TranslationKey("dbdesign.analysis.data_types.set_max_length", "Consider setting a max length for '{column}' to prevent oversized data"),
    "dbdesign.analysis.data_types.allows_null": TranslationKey("dbdesign.analysis.data_types.allows_null", "Column '{column}' allows NULL \u2014 consider NOT NULL constraint"),
    "dbdesign.analysis.data_types.add_not_null": TranslationKey("dbdesign.analysis.data_types.add_not_null", "Add NOT NULL constraint to '{column}'"),
    "dbdesign.analysis.naming.reserved_keyword_column": TranslationKey("dbdesign.analysis.naming.reserved_keyword_column", "Column '{column}' is a reserved SQL keyword"),
    "dbdesign.analysis.naming.rename_column_reserved": TranslationKey("dbdesign.analysis.naming.rename_column_reserved", "Rename column '{column}' to avoid SQL reserved word conflicts"),
    "dbdesign.analysis.naming.reserved_keyword_table": TranslationKey("dbdesign.analysis.naming.reserved_keyword_table", "Table name '{table}' is a reserved SQL keyword"),
    "dbdesign.analysis.naming.rename_table_reserved": TranslationKey("dbdesign.analysis.naming.rename_table_reserved", "Rename table '{table}' to avoid SQL reserved word conflicts"),
    "dbdesign.analysis.naming.mixed_case_table": TranslationKey("dbdesign.analysis.naming.mixed_case_table", "Table name '{table}' uses mixed case \u2014 snake_case recommended"),
    "dbdesign.analysis.naming.rename_table_snake_case": TranslationKey("dbdesign.analysis.naming.rename_table_snake_case", "Rename table to lowercase snake_case for consistency"),
    "dbdesign.analysis.naming.mixed_case_column": TranslationKey("dbdesign.analysis.naming.mixed_case_column", "Column '{column}' uses mixed case \u2014 snake_case recommended"),
    "dbdesign.analysis.naming.rename_column_snake_case": TranslationKey("dbdesign.analysis.naming.rename_column_snake_case", "Rename column to lowercase snake_case for consistency"),
    "dbdesign.analysis.semistructured.controlled_vocab": TranslationKey("dbdesign.analysis.semistructured.controlled_vocab", "Column {column} contains a controlled vocabulary of {count} distinct values"),
    "dbdesign.analysis.semistructured.create_ref_table": TranslationKey("dbdesign.analysis.semistructured.create_ref_table", "Create a reference table for {column} values to normalize the {table} table"),
}

# Email-pdf route response keys — canonical-keyed (one name per key, no alias).
# The email CONTENT itself uses the frontend-owned ai.database.email_* keys
# (referenced by string in email.py, like email.verification.*), not these.
# ai.database.email_sent is the exception: it is a route RESPONSE key (the
# success message), and the backend references it through t(), so it must be
# declared here — same canonical key as the frontend's ai/translations.ts.
EMAIL_PDF_TK = {
    "dbdesign.email_pdf.no_email": TranslationKey(
        "dbdesign.email_pdf.no_email",
        "No email address found for your account"
    ),
    "dbdesign.email_pdf.invalid_body": TranslationKey(
        "dbdesign.email_pdf.invalid_body",
        "Invalid request body"
    ),
    "dbdesign.email_pdf.send_failed": TranslationKey(
        "dbdesign.email_pdf.send_failed",
        "Failed to email the report. Please try again."
    ),
    "ai.database.email_sent": TranslationKey(
        "ai.database.email_sent",
        "Report emailed successfully"
    ),
}

# LLM client error keys — used by llm_client.call_llm (routed through t()).
LLM_CLIENT_TK = {
    "dbdesign.llm.no_ai_provider": TranslationKey(
        "dbdesign.llm.no_ai_provider",
        "No AI provider configured. Connect an AI provider in Settings → AI Connections."
    ),
    "dbdesign.llm.no_model": TranslationKey(
        "dbdesign.llm.no_model",
        "No AI model configured. Set a default model on the AI connection or pass an explicit model."
    ),
    "dbdesign.llm.http_error": TranslationKey(
        "dbdesign.llm.http_error",
        "LLM returned HTTP {status_code}"
    ),
    "dbdesign.llm.timeout": TranslationKey(
        "dbdesign.llm.timeout",
        "LLM request timed out after {timeout_seconds}s"
    ),
    "dbdesign.llm.empty_content": TranslationKey(
        "dbdesign.llm.empty_content",
        "LLM returned empty content"
    ),
    "dbdesign.llm.unknown_error": TranslationKey(
        "dbdesign.llm.unknown_error",
        "Unknown LLM error"
    ),
}
