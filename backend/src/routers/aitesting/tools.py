"""
The AI-test concierge's tools — schema, one query, one report.

Three tools, deliberately tiny. The point of a fixed, minimal tool set is that
the instrument stops changing: a model that fails here failed at *driving a tool
loop*, not at reading a nine-tool prompt that was tuned last week.

THE DATA IS IN MEMORY, NOT IN A DATABASE
----------------------------------------
Each tool reads `agent.test_dataset`, a plain dict the caller supplies:

    {"table": "ai_test_dataset",
     "columns": [{"name": "region", "type": "text"}, …],
     "rows":    [{"region": "north", "amount": 12.5}, …]}

That keeps this package independent of where the dataset comes from. Item 9b
creates the real synthetic dataset in `workbench_data` and hands it over in this
shape; a fixture can hand over three rows instead. Neither the tools nor the
concierge need to know the difference, and the instrument can be exercised before
the database half exists.

WHAT THE TOOLS RETURN
---------------------
JSON-shaped data, not English sentences. The values are read by a model and
occasionally stored as evidence, so keeping them as data avoids the translation
question entirely — there is no user-facing prose here to translate.
"""

from src.chat.tool_agent import register_tool

from .translations import TOOL_NAMES

_SCHEMA_SCHEMA = {
    "type": "function",
    "function": {
        "name": "test_dataset_schema",
        "description": "Return the dataset's column names and types.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

_QUERY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "test_run_query",
        "description": (
            "Run one aggregate over the dataset. `operation` must be one of the "
            "declared values."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["count", "sum", "mean"],
                    "description": "The aggregate to compute",
                },
                "column": {
                    "type": "string",
                    "description": "Column to aggregate; required for sum and mean",
                },
            },
            "required": ["operation"],
        },
    },
}

_REPORT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "test_report_finding",
        "description": "Report the finding from the tools' results.",
        "parameters": {
            "type": "object",
            "properties": {
                "finding": {
                    "type": "string",
                    "description": "One or two sentences stating what the tools showed",
                }
            },
            "required": ["finding"],
        },
    },
}

# The operations `test_run_query` will actually perform. Kept beside the schema
# so the two cannot drift; the enum above is the model's view, this is the
# executor's.
OPERATIONS = ("count", "sum", "mean")


def _dataset(agent):
    """The dataset handed to this turn, or None when there is none."""
    return getattr(agent, "test_dataset", None)


def _error(kind: str, **extra) -> dict:
    return {"error": kind, **extra}


async def _exec_schema(agent, **args) -> dict:
    data = _dataset(agent)
    if not data:
        return _error("no_dataset")
    return {
        "table": data.get("table"),
        "columns": data.get("columns", []),
        "row_count": len(data.get("rows", [])),
    }


async def _exec_query(agent, operation=None, column=None, **args) -> dict:
    data = _dataset(agent)
    if not data:
        return _error("no_dataset")

    op = str(operation or "").strip().lower()
    if op not in OPERATIONS:
        # The executor validates even though the schema declares a closed set:
        # a model can emit a value outside it, and that observation is the whole
        # reason the `vocabulary` reason exists.
        return _error("unknown_operation", operation=operation, allowed=list(OPERATIONS))

    rows = data.get("rows", [])

    if op == "count":
        return {"operation": "count", "value": len(rows)}

    if not column:
        return _error("column_required", operation=op)

    values = []
    for row in rows:
        value = row.get(column)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))

    if not values:
        return _error("no_numeric_values", column=column)

    if op == "sum":
        return {"operation": "sum", "column": column, "value": sum(values)}
    return {"operation": "mean", "column": column, "value": sum(values) / len(values)}


async def _exec_report(agent, finding=None, **args) -> dict:
    # Recorded on the agent so the caller can see the turn produced a finding
    # rather than merely a tool call.
    setattr(agent, "test_finding", finding or "")
    return {"recorded": bool(finding), "finding": finding or ""}


_TOOLS = [
    (_SCHEMA_SCHEMA, _exec_schema),
    (_QUERY_SCHEMA, _exec_query),
    (_REPORT_SCHEMA, _exec_report),
]


# The aitesting concierge's own registry. Before this it registered into the
# shared `default` registry alongside the recipe and data-cleaning concierges, so
# a tool name two of them declared resolved to whichever module imported last.
AITESTING_REGISTRY = "aitesting"


def register_all_tools() -> None:
    """Register the test tools into the aitesting concierge's registry."""
    for schema, executor in _TOOLS:
        register_tool(AITESTING_REGISTRY, schema["function"]["name"], schema, executor)


# At module import, as Go's aitesting package does at init. The registry refuses
# a duplicate name, so registering per turn — which run_test_turn used to do — is
# not repeatable, and a second probe run would raise instead of measuring.
register_all_tools()


__all__ = ["AITESTING_REGISTRY", "register_all_tools", "TOOL_NAMES", "OPERATIONS"]
