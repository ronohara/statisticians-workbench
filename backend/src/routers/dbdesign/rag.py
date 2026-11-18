"""
RAG (Retrieval-Augmented Generation) for Database Design Assistant.
Full-text search across text columns + AI-powered answer generation.
"""

import asyncio
from typing import Dict, Any, List, Optional

from src.chat.providers.base import ProviderFactory
from src.chat.connection import get_connection_details as get_ai_connection
from src.utils.translation import t
from .translations import DBDESIGN_TK


async def search_text_columns(
    conn,
    tables: List[Dict],
    query: str,
    limit: int = 15,
) -> List[Dict]:
    """Full-text search across text/varchar columns using ILIKE."""
    results = []
    text_types = ("text", "varchar", "char", "character")
    
    for table in tables:
        schema = table["schema"]
        table_name = table["name"]
        
        for col in table.get("columns", []):
            dtype = col["type"].lower()
            if not any(t in dtype for t in text_types):
                continue
            
            col_name = col["name"]
            
            # Search for query terms in this column
            terms = query.split()
            conditions = " AND ".join(
                [f'"{col_name}" ILIKE \'%{t}%\'' for t in terms if len(t) > 1]
            )
            if not conditions:
                continue
            
            try:
                sql = (
                    f'SELECT "{col_name}" AS text, '
                    f"'{schema}.{table_name}' AS source_table, "
                    f"'{col_name}' AS source_column "
                    f'FROM "{schema}"."{table_name}" '
                    f"WHERE {conditions} "
                    f"LIMIT {limit}"
                )
                rows = await conn.fetch(sql)
                for row in rows:
                    if row["text"]:
                        results.append({
                            "text": str(row["text"])[:1000],
                            "source_table": row["source_table"],
                            "source_column": row["source_column"],
                        })
                        if len(results) >= limit:
                            break
            except Exception:
                pass
            
            if len(results) >= limit:
                break
    
    return results[:limit]


def build_rag_prompt(question: str, search_results: List[Dict]) -> str:
    """Build a RAG prompt with search results as context."""
    if not search_results:
        return None
    
    context_parts = []
    for i, result in enumerate(search_results, 1):
        context_parts.append(
            f"[{i}] Source: {result['source_table']}.{result['source_column']}\n"
            f"    Text: {result['text']}"
        )
    context = "\n\n".join(context_parts)
    
    prompt = f"""You are a database analysis assistant. Answer the user's question based on the following data retrieved from their database.

CONTEXT (from database text columns):
{context}

USER QUESTION: {question}

INSTRUCTIONS:
- Answer based only on the context provided above.
- Include citations to the source table.column for each fact.
- If the context doesn't contain enough information, say so.
- Suggest 2-3 follow-up questions the user might want to ask.
- Keep the answer concise and well-structured."""
    
    return prompt


async def rag_query(
    db_pool,
    conn_details: Dict,
    schema: Dict,
    question: str,
    connection_id: int,
    language: str,
    ai_connection_id: Optional[int] = None,
    ai_model: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a RAG query: search text columns + generate AI answer."""
    import asyncpg
    from src.utils.encryption import decrypt_field
    
    # Step 1: Connect to the external database
    try:
        decrypted_password = decrypt_field(conn_details["password"])
    except Exception:
        decrypted_password = conn_details["password"]
    
    pg_conn = await asyncpg.connect(
        host=conn_details["host"],
        port=conn_details["port"],
        database=conn_details["database"],
        user=conn_details["username"],
        password=decrypted_password,
    )
    
    try:
        # Step 2: Full-text search across text columns
        tables = schema.get("tables", [])
        if not tables:
            return {"answer": await t(db_pool, language, DBDESIGN_TK["rag.no_tables"]), "sources": []}
        
        search_results = await search_text_columns(pg_conn, tables, question, limit=15)
    finally:
        await pg_conn.close()
    
    if not search_results:
        return {
            "answer": await t(db_pool, language, DBDESIGN_TK["rag.no_matches"]),
            "sources": [],
        }
    
    # Step 3: Delegate to DatabaseDesignerAgent via Agent Framework
    if ai_connection_id is None:
        # No AI connection — return search results only
        sources = [
            {"text": r["text"][:200], "source": f"{r['source_table']}.{r['source_column']}"}
            for r in search_results[:10]
        ]
        return {
            "answer": await t(db_pool, language, DBDESIGN_TK["rag.no_ai_provider"], count=len(search_results)),
            "sources": sources,
            "search_results": [r["text"][:200] for r in search_results[:5]],
        }
    
    try:
        from src.agents.database_designer import DatabaseDesignerAgent
        agent = DatabaseDesignerAgent(
            db_pool=db_pool,
            connection_id=ai_connection_id,
            user_id="rag",
            model=ai_model,
            language=language,
        )
        answer = await agent.ask(question, search_results=search_results)
    except Exception as e:
        answer = await t(db_pool, language, DBDESIGN_TK["rag.ai_provider_error"], error=str(e)) + f"\n\nFound {len(search_results)} matching records."
    
    sources = [
        {"text": r["text"][:200], "source": f"{r['source_table']}.{r['source_column']}"}
        for r in search_results[:10]
    ]
    
    return {
        "answer": answer,
        "sources": sources,
        "total_matches": len(search_results),
    }
