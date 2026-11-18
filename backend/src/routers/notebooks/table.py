"""
De-pandased table representation (DP-1).

The notebooks module previously used pandas.DataFrame as the interchange type
between the parser, the preview endpoint, and the storage engine. That is
replaced by a plain structure available natively in both Python and Go:

    table = {
        "columns": ["col1", "col2", ...],   # ordered — SQL CREATE TABLE needs it
        "rows":    [{"col1": v, "col2": v}, ...],
    }

The columns list carries the order explicitly (a dict alone does not), and each
row is a column-name -> value mapping.
"""


def make_table(columns, rows):
    """Build a table from an ordered column list and a list of row-dicts."""
    return {"columns": list(columns), "rows": rows}


def table_from_rows(rows):
    """Build a table from a list of row-dicts, inferring the ordered columns.

    Mirrors pandas.DataFrame(rows): columns are the ordered union of the dict
    keys in first-appearance order; the rows are returned unchanged.
    """
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return {"columns": columns, "rows": rows}
