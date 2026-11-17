// app/ai/translations.ts
// ============================================================
// AI MODULE TRANSLATIONS
// All translation keys used by AI assistant pages.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const AI = {
    database: {
        title: { key: "ai.database.title", fallback: "Database Design Assistant" },
        description: { key: "ai.database.description", fallback: "Analyze your database design for indexing, normalisation, relationship, data type, and naming issues." },
        placeholder: { key: "ai.database.placeholder", fallback: "Coming soon. This feature will help you design database schemas using AI." },
        select_connection: { key: "ai.database.select_connection", fallback: "Select Database Connection" },
        select_connection_placeholder: { key: "ai.database.select_connection_placeholder", fallback: "Choose a database connection..." },
        analyze: { key: "ai.database.analyze", fallback: "Analyze Schema" },
        analyzing: { key: "ai.database.analyzing", fallback: "Analyzing..." },
        schema_error: { key: "ai.database.schema_error", fallback: "Failed to analyze database schema" },
        timeout_error: { key: "ai.database.timeout_error", fallback: "Analysis timed out. The database may be too large or the AI service is unavailable." },
        timeout_log: { key: "ai.database.timeout_log", fallback: "Analysis timed out after 15 minutes." },
        empty_state: { key: "ai.database.empty_state", fallback: "Select a database connection and click Analyze to begin." },
        add_connection: { key: "ai.database.add_connection", fallback: "Add Database Connection" },
        analysis_report: { key: "ai.database.analysis_report", fallback: "Analysis Report" },
        analysis_summary: { key: "ai.database.analysis_summary", fallback: "{tables} tables, {columns} columns, {issues} issues found" },
        tables_label: { key: "ai.database.tables_label", fallback: "Tables" },
        columns_label: { key: "ai.database.columns_label", fallback: "Columns" },
        rows_label: { key: "ai.database.rows_label", fallback: "Rows" },
        issues_label: { key: "ai.database.issues_label", fallback: "Issues" },
        risk_breakdown: { key: "ai.database.risk_breakdown", fallback: "Risk Breakdown" },
        high_risk: { key: "ai.database.high_risk", fallback: "High" },
        medium_risk: { key: "ai.database.medium_risk", fallback: "Medium" },
        low_risk: { key: "ai.database.low_risk", fallback: "Low" },
        top_recommendations: { key: "ai.database.top_recommendations", fallback: "Top Recommendations" },
        all_issues: { key: "ai.database.all_issues", fallback: "All Issues" },
        no_issues: { key: "ai.database.no_issues", fallback: "No issues found. Your database design looks good!" },
        tables_explorer: { key: "ai.database.tables_explorer", fallback: "Tables Explorer" },
        foreign_keys: { key: "ai.database.foreign_keys", fallback: "Foreign Keys" },
        indexes_label: { key: "ai.database.indexes_label", fallback: "Indexes" },
        download_pdf: { key: "ai.database.download_pdf", fallback: "Download PDF" },
        email_pdf: { key: "ai.database.email_pdf", fallback: "Email PDF" },
        pdf_downloaded: { key: "ai.database.pdf_downloaded", fallback: "PDF downloaded successfully" },
        email_sent: { key: "ai.database.email_sent", fallback: "Report emailed successfully" },
        email_subject: { key: "ai.database.email_subject", fallback: "Database Design Analysis \u2014 {db_name} ({db_type}) [Connection {conn_id}]" },
        email_body_title: { key: "ai.database.email_body_title", fallback: "Database Design Analysis Report" },
        email_body_database: { key: "ai.database.email_body_database", fallback: "Database: {db_name}" },
        email_body_type: { key: "ai.database.email_body_type", fallback: "Database Type: {db_type}" },
        email_body_connection: { key: "ai.database.email_body_connection", fallback: "Connection: {conn_name}" },
        email_body_id: { key: "ai.database.email_body_id", fallback: "Connection ID: {conn_id}" },
        email_body_attachment: { key: "ai.database.email_body_attachment", fallback: "Please find the analysis report attached." },
        email_body_signature: { key: "ai.database.email_body_signature", fallback: "\u2014 Statisticians Workbench" },
        pdf_error: { key: "ai.database.pdf_error", fallback: "Failed to generate PDF" },
        email_error: { key: "ai.database.email_error", fallback: "Failed to email report" },
        semi_structured: { key: "ai.database.semi_structured", fallback: "Semi-Structured Data Analysis" },
        semi_structured_desc: { key: "ai.database.semi_structured_desc", fallback: "Text columns analysed for embedded codes, keywords, and patterns." },
        code_systems_detected: { key: "ai.database.code_systems_detected", fallback: "Code Systems Detected" },
        categories: { key: "ai.database.categories", fallback: "Categories" },
        no_semi_structured: { key: "ai.database.no_semi_structured", fallback: "No semi-structured data patterns detected in text columns." },
        normalisation_suggestions: { key: "ai.database.normalisation_suggestions", fallback: "Normalisation Suggestions" },
        normalisation_suggestions_desc: { key: "ai.database.normalisation_suggestions_desc", fallback: "Proposed reference tables based on keywords found in semi-structured text columns." },
        normalisation_warning: { key: "ai.database.normalisation_warning", fallback: "These are AI-generated suggestions. Database redesigns require careful review. Test changes on a replica first." },
        proposed_reference_table: { key: "ai.database.proposed_reference_table", fallback: "Proposed Reference Table" },
        confidence: { key: "ai.database.confidence", fallback: "Confidence" },
        business_value: { key: "ai.database.business_value", fallback: "Business Value" },
        rag_chat: { key: "ai.database.rag_chat", fallback: "RAG Chat — Ask Questions About Your Data" },
        rag_chat_desc: { key: "ai.database.rag_chat_desc", fallback: "Ask natural-language questions. The system searches text columns and returns AI-generated answers with citations." },
        rag_placeholder: { key: "ai.database.rag_placeholder", fallback: "e.g., What are the common diagnoses?" },
        rag_ask: { key: "ai.database.rag_ask", fallback: "Ask" },
        rag_sources: { key: "ai.database.rag_sources", fallback: "Sources" },
        rag_error: { key: "ai.database.rag_error", fallback: "RAG query failed" },
        select_connection_first: { key: "ai.database.select_connection_first", fallback: "Please select a database connection first." },
        enter_question: { key: "ai.database.enter_question", fallback: "Please enter a question." },
        pk_prefix: { key: "ai.database.pk_prefix", fallback: "PK – " },
        cols_rows_format: { key: "ai.database.cols_rows_format", fallback: "{cols} cols, {rows} rows" },
        // AI-augmented analysis sections
        ai_health_score: { key: "ai.database.ai_health_score", fallback: "AI Health Score" },
        health_score_desc: { key: "ai.database.health_score_desc", fallback: "Overall database health assessed by Schema AI. 0 = critical structural problems, 100 = production-ready." },
        priority_actions: { key: "ai.database.priority_actions", fallback: "Top Priority Actions" },
        semantic_analysis: { key: "ai.database.semantic_analysis", fallback: "Semantic Analysis" },
        semantic_analysis_desc: { key: "ai.database.semantic_analysis_desc", fallback: "AI-inferred column meanings, ISIC domain classifications, and code system detections." },
        column_meanings: { key: "ai.database.column_meanings", fallback: "Column Meanings" },
        isic_domains: { key: "ai.database.isic_domains", fallback: "ISIC Domain Classifications" },
        table_purposes: { key: "ai.database.table_purposes", fallback: "Table Purposes" },
        integration_analysis: { key: "ai.database.integration_analysis", fallback: "Integration Analysis" },
        integration_analysis_desc: { key: "ai.database.integration_analysis_desc", fallback: "Implicit relationships, research capabilities, and missing dimensions detected by Integration AI." },
        implicit_relationships: { key: "ai.database.implicit_relationships", fallback: "Implicit Relationships" },
        research_capabilities: { key: "ai.database.research_capabilities", fallback: "Research Capabilities" },
        missing_dimensions: { key: "ai.database.missing_dimensions", fallback: "Missing Dimensions" },
        is_missing: { key: "ai.database.is_missing", fallback: "is missing" },
        peer_tables: { key: "ai.database.peer_tables", fallback: "Peer tables:" },
        ai_unavailable: { key: "ai.database.ai_unavailable", fallback: "AI analysis unavailable. Connect an AI provider to enable enhanced analysis." },
        ai_augmented: { key: "ai.database.ai_augmented", fallback: "AI-Augmented Analysis" },
        ai_augmented_desc: { key: "ai.database.ai_augmented_desc", fallback: "Schema AI, Semantic AI, and Integration AI have analyzed this database." },
        ai_fallback: { key: "ai.database.ai_fallback", fallback: "Basic Analysis" },
        ai_fallback_desc: { key: "ai.database.ai_fallback_desc", fallback: "AI augmentation unavailable. Showing structural analysis only. Select an AI connection for deeper insights." },
    },
    dataclean: {
        title: { key: "ai.dataclean.title", fallback: "Dataset Cleaning Assistant" },
        description: { key: "ai.dataclean.description", fallback: "AI-powered dataset cleaning and preparation." },
        select_dataset: { key: "ai.dataclean.select_dataset", fallback: "Select Dataset" },
        select_dataset_placeholder: { key: "ai.dataclean.select_dataset_placeholder", fallback: "Choose a dataset..." },
        no_datasets: { key: "ai.dataclean.no_datasets", fallback: "No datasets available. Upload or define a dataset first." },
        loading_schema: { key: "ai.dataclean.loading_schema", fallback: "Loading schema..." },
        schema_summary: { key: "ai.dataclean.schema_summary", fallback: "{rows} rows, {cols} columns" },
        schema_error: { key: "ai.dataclean.schema_error", fallback: "Failed to load dataset schema" },
        chat_placeholder: { key: "ai.dataclean.chat_placeholder", fallback: "Ask about cleaning or preparing this dataset..." },
        send: { key: "ai.dataclean.send", fallback: "Send" },
        empty_chat: { key: "ai.dataclean.empty_chat", fallback: "Select a dataset and start asking questions about how to clean and prepare it." },
        chat_error: { key: "ai.dataclean.chat_error", fallback: "Failed to get response" },
        no_connection: { key: "ai.dataclean.no_connection", fallback: "Please configure a default AI connection in Settings > AI." },
        select_dataset_first: { key: "ai.dataclean.select_dataset_first", fallback: "Please select a dataset first." },
        enter_message: { key: "ai.dataclean.enter_message", fallback: "Please enter a message." },
        column_type_number: { key: "ai.dataclean.column_type.number", fallback: "Number" },
        column_type_datetime: { key: "ai.dataclean.column_type.datetime", fallback: "Date/Time" },
        column_type_category: { key: "ai.dataclean.column_type.category", fallback: "Category" },
        column_type_text: { key: "ai.dataclean.column_type.text", fallback: "Text" },
        shared_badge: { key: "ai.dataclean.shared_badge", fallback: "(shared)" },
        column_tooltip: { key: "ai.dataclean.column_tooltip", fallback: "{type} — {null_count} nulls, {unique_count} unique" },
        rules_title: { key: "ai.dataclean.rules_title", fallback: "Preparation rules" },
        no_rules: { key: "ai.dataclean.no_rules", fallback: "No rules yet" },
        operations_count: { key: "ai.dataclean.operations_count", fallback: "{count} operations" },
        preview_title: { key: "ai.dataclean.preview_title", fallback: "Data preview" },
        no_dataset_selected: { key: "ai.dataclean.no_dataset_selected", fallback: "No dataset selected" },
        clean_copy: { key: "ai.dataclean.clean_copy", fallback: "Clean copy" },
        clean_in_place: { key: "ai.dataclean.clean_in_place", fallback: "Clean in place" },
        clean_name_label: { key: "ai.dataclean.clean_name_label", fallback: "Name for the cleaned copy" },
        clean_no_rules: { key: "ai.dataclean.clean_no_rules", fallback: "No cleaning rules to apply yet." },
        clean_copy_success: { key: "ai.dataclean.clean_copy_success", fallback: "Created a new dataset '{name}' — the original is unchanged." },
        clean_in_place_success: { key: "ai.dataclean.clean_in_place_success", fallback: "Dataset '{name}' updated." },
    },
    recipe: {
        title: { key: "ai.recipe.title", fallback: "Analysis Rules Assistant" },
        description: { key: "ai.recipe.description", fallback: "AI-powered recipe and analysis rule generation." },
        select_dataset: { key: "ai.recipe.select_dataset", fallback: "Select Dataset" },
        select_dataset_placeholder: { key: "ai.recipe.select_dataset_placeholder", fallback: "Choose a dataset..." },
        no_datasets: { key: "ai.recipe.no_datasets", fallback: "No datasets available. Upload or define a dataset first." },
        loading_schema: { key: "ai.recipe.loading_schema", fallback: "Loading schema..." },
        schema_summary: { key: "ai.recipe.schema_summary", fallback: "{rows} rows, {cols} columns" },
        chat_placeholder: { key: "ai.recipe.chat_placeholder", fallback: "Ask about statistical analysis or recipe configuration..." },
        send: { key: "ai.recipe.send", fallback: "Send" },
        empty_chat: { key: "ai.recipe.empty_chat", fallback: "Select a dataset and ask about which statistical techniques to use." },
        chat_error: { key: "ai.recipe.chat_error", fallback: "Failed to get response" },
        select_dataset_first: { key: "ai.recipe.select_dataset_first", fallback: "Please select a dataset first." },
        enter_message: { key: "ai.recipe.enter_message", fallback: "Please enter a message." },
    },

    // Shared: AI connection/model selectors
    select_ai_connection: { key: "ai.select_ai_connection", fallback: "AI Connection" },
    select_ai_connection_placeholder: { key: "ai.select_ai_connection_placeholder", fallback: "Choose AI connection..." },
    select_model: { key: "ai.select_model", fallback: "Model" },
    select_model_placeholder: { key: "ai.select_model_placeholder", fallback: "Choose model..." },
    new_session: { key: "ai.new_session", fallback: "New Session" },
    no_ai_connections: { key: "ai.no_ai_connections", fallback: "No AI connections configured. Add one in Settings > AI." },

    // Shared: a turn is in flight (dataclean, recipe and virtual concierges)
    thinking: { key: "ai.thinking", fallback: "Thinking..." },

    // AI Recipe Concierge (Phase 3)
    ai_recipe_title: { key: "ai.recipe_concierge.title", fallback: "AI Recipe Concierge" },
    ai_recipe_welcome: { key: "ai.recipe_concierge.welcome", fallback: "Tell me what you want to discover in your data, and I'll help you build a complete analysis recipe." },
    ai_recipe_create_prompt: { key: "ai.recipe_concierge.create_prompt", fallback: "Create a new session to get started." },
    ai_recipe_new_session: { key: "ai.recipe_concierge.new_session", fallback: "New Session" },
    ai_recipe_no_sessions: { key: "ai.recipe_concierge.no_sessions", fallback: "No sessions yet" },
    ai_recipe_no_session: { key: "ai.recipe_concierge.no_session", fallback: "No session selected" },
    ai_recipe_schema_changes: { key: "ai.recipe_concierge.schema_changes", fallback: "Schema changes detected:" },
    ai_recipe_input_placeholder: { key: "ai.recipe_concierge.input_placeholder", fallback: "Ask about your data... or just say \"hi\"" },
    ai_recipe_draft_empty: { key: "ai.recipe_concierge.draft_empty", fallback: "Start a conversation to build your recipe. The draft will appear here as you make decisions." },
    ai_recipe_tab_sessions: { key: "ai.recipe_concierge.tab_sessions", fallback: "Sessions" },
    ai_recipe_tab_chat: { key: "ai.recipe_concierge.tab_chat", fallback: "Chat" },
    ai_recipe_tab_draft: { key: "ai.recipe_concierge.tab_draft", fallback: "Draft" },
    ai_recipe_stage_greeting: { key: "ai.recipe_concierge.stage_greeting", fallback: "Welcome" },
    ai_recipe_stage_goal: { key: "ai.recipe_concierge.stage_goal", fallback: "Research Question" },
    ai_recipe_stage_technique: { key: "ai.recipe_concierge.stage_technique", fallback: "Choose Technique" },
    ai_recipe_stage_columns: { key: "ai.recipe_concierge.stage_columns", fallback: "Select Columns" },
    ai_recipe_stage_transforms: { key: "ai.recipe_concierge.stage_transforms", fallback: "Data Preparation" },
    ai_recipe_stage_visualisation: { key: "ai.recipe_concierge.stage_visualisation", fallback: "Visualisation" },
    ai_recipe_stage_review: { key: "ai.recipe_concierge.stage_review", fallback: "Review Recipe" },
    ai_recipe_stage_complete: { key: "ai.recipe_concierge.stage_complete", fallback: "Recipe Ready" },
    ai_recipe_progress_decided: { key: "ai.recipe_concierge.progress_decided", fallback: "{count} of {total} decided" },
    ai_recipe_toggle_panel: { key: "ai.recipe_concierge.toggle_panel", fallback: "Toggle recipe panel" },
    ai_recipe_chat_error: { key: "ai.recipe_concierge.chat_error", fallback: "Failed to get response" },
    ai_recipe_delete_session: { key: "ai.recipe_concierge.delete_session", fallback: "Delete session" },
    ai_recipe_select_dataset: { key: "ai.recipe_concierge.select_dataset", fallback: "Select dataset..." },
    ai_recipe_done: { key: "ai.recipe_concierge.done", fallback: "Done" },
    ai_recipe_draft_title: { key: "ai.recipe_concierge.draft_title", fallback: "Recipe Draft" },
    ai_recipe_draft_dataset: { key: "ai.recipe_concierge.draft_dataset", fallback: "Dataset" },
    ai_recipe_draft_algorithm: { key: "ai.recipe_concierge.draft_algorithm", fallback: "Algorithm" },
    ai_recipe_draft_output: { key: "ai.recipe_concierge.draft_output", fallback: "Output" },
    ai_recipe_draft_no_visualisation: { key: "ai.recipe_concierge.draft_no_visualisation", fallback: "Numerical results" },
    ai_recipe_save: { key: "ai.recipe_concierge.save", fallback: "Save Recipe" },
    ai_recipe_saving: { key: "ai.recipe_concierge.saving", fallback: "Saving..." },
    ai_recipe_saved: { key: "ai.recipe_concierge.saved", fallback: "Recipe saved!" },
    ai_recipe_manual_label: { key: "ai.recipe_concierge.manual_label", fallback: "Manual Recipe" },
    ai_recipe_status_ready: { key: "ai.recipe_concierge.status_ready", fallback: "Ready" },
    ai_recipe_status_draft: { key: "ai.recipe_concierge.status_draft", fallback: "Draft" },
    ai_recipe_open: { key: "ai.recipe_concierge.open", fallback: "Open in editor" },
    ai_recipe_errors_heading: { key: "ai.recipe_concierge.errors_heading", fallback: "Cannot save yet" },
    ai_recipe_warnings_heading: { key: "ai.recipe_concierge.warnings_heading", fallback: "Warnings" },
} as const;

// ── Flat declarations (AGENTS.md: a NEW declaration is a module-level name) ──
//
// Everything above is the old table form, which the flat-declarations refactor will
// convert. It is not extended: adding an entry to `AI` would be a new declaration in
// a shape the rule has retired, and it costs three linter findings (one TABLE-SHAPE
// for the entry, two TABLE-SHAPE-USE at the call site) that a flat name does not.

/** Joins the decided count to the next pending piece's sentence: "5 of 6 decided · Name the recipe".
 *  Its own declaration rather than a format string, because the separator is punctuation a
 *  translator may legitimately re-punctuate — a middle dot is not universal. */
export const ai_recipe_progress_next: TranslationKey = {
    key: "ai.recipe_concierge.progress_next",
    fallback: "{progress} · {next}",
};

/** Says how many chip choices a capped row is not showing. The count travels from
 *  the backend (`withheld`) and this is the only place it becomes words, so a
 *  six-of-eleven row can say so instead of reading as complete. Parameterised
 *  rather than three fixed strings: the number is data, not a declaration. */
export const ai_recipe_chip_withheld: TranslationKey = {
    key: "ai.recipe_concierge.chip_withheld",
    fallback: "+{count} more",
};

/** Opens a chip row that has more choices than it can show at once. The cap still
 *  bounds what is on screen by default; this is what makes the remainder
 *  reachable, so a choice the row hid can never dead-end a conversation.
 *  Parameterised rather than fixed: the number is data, not a declaration. */
export const ai_recipe_chip_expand: TranslationKey = {
    key: "ai.recipe_concierge.chip_expand",
    fallback: "Show {count} more",
};

/** Closes an expanded chip row. */
export const ai_recipe_chip_collapse: TranslationKey = {
    key: "ai.recipe_concierge.chip_collapse",
    fallback: "Show fewer",
};

/** Shown under a chip row that a newer offer has replaced. The row stays visible
 *  — it is part of the conversation — but it is inert, and this is why. An inert
 *  control with no explanation reads as broken. */
export const ai_recipe_chip_superseded: TranslationKey = {
    key: "ai.recipe_concierge.chip_superseded",
    fallback: "Replaced by a newer offer.",
};

/** Shown when the dataset's sources could not be read while building the schema.
 *  Without it the turn looks as though it forgot to offer columns, when in fact
 *  it could not see any — the unread list itself is the detail beneath. */
export const ai_recipe_unread_sources: TranslationKey = {
    key: "ai.recipe_concierge.unread_sources",
    fallback: "Some sources could not be read, so the column list may be incomplete.",
};
