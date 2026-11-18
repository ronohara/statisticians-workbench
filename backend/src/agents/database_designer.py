"""
Database Designer Agent — AI-powered database design analysis.
"""

from typing import Dict, Any, List, Optional

from src.chat.language import language_instruction
from .base import AIAgent, AgentFactory


class DatabaseDesignerAgent(AIAgent):
    """
    AI agent for database design analysis.
    Analyses database schemas, suggests indexing, normalisation,
    relationship improvements, and answers natural-language questions
    about the database structure.
    """

    async def build_system_prompt(
        self,
        schema: Optional[Dict[str, Any]] = None,
        db_type: str = "postgresql",
        search_results: Optional[list] = None,
        sample_data: Optional[str] = None,
        **context
    ) -> str:
        """
        Build a system prompt based on the context provided.
        Accepts schema (for analysis), search_results (for RAG), sample_data (for normalisation).
        """
        # RAG mode: search results from text columns
        if search_results is not None:
            return self._build_rag_system_prompt(search_results)

        # Normalisation mode: sample data from semi-structured columns
        if sample_data is not None:
            return self._build_normalisation_system_prompt(sample_data)

        # Schema analysis mode (default)
        return self._build_schema_system_prompt(schema, db_type)

    def _build_schema_system_prompt(self, schema: Optional[Dict[str, Any]], db_type: str) -> str:
        """Build system prompt for schema analysis."""
        if schema is None:
            return (
                "You are a database design assistant for Statisticians Workbench. "
                f"You are analysing a {db_type} database. "
                "Help the user understand their database structure, identify design issues, "
                "and suggest improvements for indexing, normalisation, relationships, data types, and naming."
            )

        tables = schema.get("tables", [])
        total_tables = schema.get("total_tables", len(tables))
        total_columns = schema.get("total_columns", 0)

        schema_text = f"Database type: {db_type}\n"
        schema_text += f"Total tables: {total_tables}, Total columns: {total_columns}\n\n"
        schema_text += "TABLES:\n"

        for t in tables[:50]:  # limit to avoid token overflow
            schema_text += f"\n  {t.get('schema', 'public')}.{t['name']}"
            comment = t.get("comment")
            if comment:
                schema_text += f" — {comment}"
            schema_text += f" ({t.get('row_count', '?')} rows)\n"
            schema_text += f"    Primary key: {', '.join(t.get('primary_key', []))}\n"

            for col in t.get("columns", [])[:30]:
                nullable = "NULL" if col.get("nullable") else "NOT NULL"
                default = f" DEFAULT {col['default']}" if col.get("default") else ""
                schema_text += f"    - {col['name']}: {col['type']} {nullable}{default}\n"

            fks = t.get("foreign_keys", [])
            if fks:
                schema_text += "    Foreign keys:\n"
                for fk in fks[:5]:
                    schema_text += f"      {fk['column']} → {fk['referenced_table']}.{fk['referenced_column']}\n"

            idxs = t.get("indexes", [])
            if idxs:
                schema_text += "    Indexes:\n"
                for idx in idxs[:5]:
                    schema_text += f"      {idx['name']}: {idx['definition']}\n"

        return (
            "You are a database design assistant for Statisticians Workbench. "
            "Analyse the following database schema and help the user with:\n"
            "  - Identifying missing indexes\n"
            "  - Normalisation issues\n"
            "  - Relationship and foreign key recommendations\n"
            "  - Data type improvements\n"
            "  - Naming convention suggestions\n"
            "  - Semi-structured data analysis (text columns with embedded codes/keywords)\n\n"
            + schema_text
            + "\n\nProvide concise, actionable recommendations. "
            "When suggesting changes, include the specific table and column names."
        )


    async def call_with_prompt(self, system_prompt: str, user_message: str) -> str:
        """Call the AI provider with explicit prompts (bypasses build_system_prompt).
        
        Use this when the caller needs to construct a specialised prompt that doesn't
        fit the standard build_system_prompt() pattern.
        """
        provider = await self._get_provider()
        system_prompt = language_instruction(self.language) + system_prompt
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        call_kwargs = {"messages": messages}
        if self.model:
            call_kwargs["model"] = self.model
        response = await provider.call(**call_kwargs)
        return response.get("content", "")

    def _build_rag_system_prompt(self, search_results: list) -> str:
        """Build system prompt for RAG-style Q&A over text column search results."""
        sources_text = "\n".join(
            f"[{r['source_table']}.{r['source_column']}] {r['text'][:300]}"
            for r in search_results[:15]
        )
        return (
            "You are a database assistant for Statisticians Workbench. "
            "Answer the user's question based ONLY on the data provided below. "
            "Include citations to source table.column for each fact. "
            "If the context doesn't contain enough information, say so.\n\n"
            "DATA:\n" + sources_text
        )

    def _build_normalisation_system_prompt(self, sample_data: str) -> str:
        """Build system prompt for semi-structured data normalisation suggestions."""
        return (
            "You are a database design expert. Analyse the following semi-structured text "
            "columns and propose reference tables to normalise them.\n\n"
            "For each proposed reference table, provide:\n"
            "1. table_name: A meaningful name for the reference table\n"
            "2. columns: List of columns with name and type\n"
            "3. source_column: Which original column this normalises\n"
            "4. rationale: Why this table is needed (1 sentence)\n"
            "5. business_value: Business benefit of this normalisation\n"
            "6. migration_sql: Complete migration script (reference table + FK + data migration)\n\n"
            "Return your response as a JSON array of objects with these fields.\n"
            "Only include columns that genuinely benefit from normalisation.\n\n"
            "SAMPLE DATA:\n" + sample_data[:8000]
            + "\n\nJSON RESPONSE:"
        )


# Auto-register
AgentFactory.register("database_designer", DatabaseDesignerAgent)
