"""
Notebook parser and sanitisation module.
Handles .ipynb JSON validation, cell extraction, and security sanitisation.
"""

import json
import re
import html
from html.parser import HTMLParser
from typing import Dict, Any, List, Optional, Tuple

from .table import make_table
from .translations import NOTEBOOKS


# Size limits (R5)
MAX_NOTEBOOK_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_CELLS_PER_NOTEBOOK = 500
MAX_OUTPUT_SIZE_PER_CELL = 5 * 1024 * 1024  # 5 MB
MAX_TABLES_PER_NOTEBOOK = 20
MIN_ROWS_FOR_IMPORT = 1
MAX_BASE64_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB


class _FirstTableParser(HTMLParser):
    """Collect the first <table>'s rows as lists of cell text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._table_depth = 0
        self._done = False
        self._in_row = False
        self._in_cell = False
        self._row = []
        self._cell = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if self._done:
            return
        if tag == "table":
            self._table_depth += 1
        elif self._table_depth == 1 and tag == "tr":
            self._in_row = True
            self._row = []
        elif self._in_row and tag in ("td", "th"):
            self._in_cell = True
            self._cell = []

    def handle_endtag(self, tag):
        if self._done:
            return
        if tag == "table":
            self._table_depth -= 1
            if self._table_depth == 0:
                self._done = True
        elif self._in_cell and tag in ("td", "th"):
            self._in_cell = False
            self._row.append("".join(self._cell).strip())
        elif self._in_row and tag == "tr":
            self._in_row = False
            self.rows.append(self._row)

    def handle_data(self, data):
        if not self._done and self._in_cell:
            self._cell.append(data)


def extract_first_table(content):
    """Extract the first <table> from HTML into a de-pandased table.

    Mirrors the pd.read_html path: the first row is the header (columns) and the
    remaining rows are data. Returns None when no table is found, or the table
    has no header/data rows.
    """
    if content is None:
        return None
    if isinstance(content, list):
        content = "".join(str(c) for c in content)
    if not isinstance(content, str):
        return None
    if "<table" not in content.lower():
        return None

    parser = _FirstTableParser()
    try:
        parser.feed(content)
    except Exception:
        return None

    if len(parser.rows) < 2:
        return None

    columns = parser.rows[0]
    # Pandas-rendered tables have an empty leading header cell for the row
    # index; pd.read_html names these "Unnamed: N" by position. Match that so
    # the column is a valid SQL identifier in every storage engine.
    columns = [name if name != "" else f"Unnamed: {i}" for i, name in enumerate(columns)]
    rows = [dict(zip(columns, row)) for row in parser.rows[1:]]

    if not rows:
        return None

    return make_table(columns, rows)


class NotebookParser:
    """Parses and sanitises Jupyter Notebook (.ipynb) files."""

    def __init__(self):
        pass

    def parse(self, raw_bytes: bytes) -> Dict[str, Any]:
        """Parse raw notebook bytes into a structured dict.

        Returns:
            {
                "valid": bool,
                "metadata": {...},
                "cells": [...],
                "dataframes": [...],
                "markdown_content": str,
                "error": TranslationKey | None,
                "error_params": dict,
            }
        """
        result = {
            "valid": False,
            "metadata": {},
            "cells": [],
            "dataframes": [],
            "markdown_content": "",
            "error": None,
            "error_params": {},
        }

        # Size check
        if len(raw_bytes) > MAX_NOTEBOOK_FILE_SIZE:
            result["error"] = NOTEBOOKS["notebooks.file_too_large"]
            result["error_params"] = {"max_size": MAX_NOTEBOOK_FILE_SIZE // (1024 * 1024)}
            return result

        # Decode and parse JSON
        try:
            text = raw_bytes.decode("utf-8")
            notebook = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            result["error"] = NOTEBOOKS["notebooks.invalid_json"]
            result["error_params"] = {"error": str(e)}
            return result

        # Validate structure
        if not isinstance(notebook, dict) or "cells" not in notebook:
            result["error"] = NOTEBOOKS["notebooks.missing_cells"]
            return result

        cells = notebook.get("cells", [])
        if not isinstance(cells, list):
            result["error"] = NOTEBOOKS["notebooks.cells_not_list"]
            return result

        if len(cells) > MAX_CELLS_PER_NOTEBOOK:
            result["error"] = NOTEBOOKS["notebooks.too_many_cells"]
            result["error_params"] = {"count": len(cells), "max_cells": MAX_CELLS_PER_NOTEBOOK}
            return result

        # Extract metadata (R5: keep only kernelspec and language_info)
        nb_metadata = notebook.get("metadata", {})
        result["metadata"] = {
            "kernelspec": nb_metadata.get("kernelspec", {}),
            "language_info": nb_metadata.get("language_info", {}),
            "title": self._extract_title(cells),
        }

        # Sanitise cells and extract data
        markdown_parts = []
        df_count = 0
        for cell in cells:
            cell_type = cell.get("cell_type", "")

            if cell_type == "markdown":
                sanitised = self._sanitise_markdown_cell(cell)
                result["cells"].append(sanitised)
                source = cell.get("source", [])
                if isinstance(source, list):
                    markdown_parts.append("".join(source))
                else:
                    markdown_parts.append(str(source))

            elif cell_type == "code":
                sanitised = self._sanitise_code_cell(cell)
                result["cells"].append(sanitised)
                # Extract DataFrames from outputs
                dataframes = self._extract_dataframes_from_outputs(cell.get("outputs", []))
                for df in dataframes:
                    if df_count < MAX_TABLES_PER_NOTEBOOK and len(df) >= MIN_ROWS_FOR_IMPORT:
                        result["dataframes"].append(df)
                        df_count += 1

            elif cell_type == "raw":
                # R5: Raw cells stripped entirely
                pass

        result["markdown_content"] = "\n".join(markdown_parts)
        result["valid"] = True
        return result

    # ----------------------------------------------------------------
    # Sanitisation (R5)
    # ----------------------------------------------------------------

    def _sanitise_markdown_cell(self, cell: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitise a markdown cell — keep as-is, safe plain text."""
        return {
            "cell_type": "markdown",
            "source": cell.get("source", []),
            "metadata": {},
        }

    def _sanitise_code_cell(self, cell: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitise a code cell: replace source, strip dangerous outputs."""
        # Replace code source with placeholder
        sanitised = {
            "cell_type": "code",
            "source": ["[code cell omitted]"],
            "outputs": [],
            "metadata": {},
            "execution_count": None,
        }

        outputs = cell.get("outputs", [])
        if not isinstance(outputs, list):
            return sanitised

        for output in outputs:
            if not isinstance(output, dict):
                continue
            output_type = output.get("output_type", "")

            # Keep safe output types
            if output_type in ("stream", "execute_result", "display_data"):
                safe_output = self._sanitise_output(output)
                if safe_output is not None:
                    sanitised["outputs"].append(safe_output)

        return sanitised

    def _sanitise_output(self, output: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Sanitise a single output, stripping dangerous content."""
        output_type = output.get("output_type", "")
        safe = {"output_type": output_type}

        if output_type == "stream":
            safe["name"] = output.get("name", "stdout")
            text = output.get("text", [])
            if isinstance(text, list):
                # Check size
                total_len = sum(len(str(t)) for t in text)
                if total_len > MAX_OUTPUT_SIZE_PER_CELL:
                    safe["text"] = ["[output truncated]"]
                else:
                    safe["text"] = text
            else:
                safe["text"] = [str(text)]
            return safe

        if output_type in ("execute_result", "display_data"):
            data = output.get("data", {})
            if not isinstance(data, dict):
                return None
            safe_data = {}
            for mime_type, content in data.items():
                # Block JavaScript
                if mime_type in ("application/javascript", "text/javascript"):
                    continue
                # Sanitise HTML
                if mime_type == "text/html":
                    safe_data[mime_type] = self._sanitise_html(content)
                    continue
                # Cap base64 images
                if mime_type == "image/png" and isinstance(content, str):
                    if len(content) > MAX_BASE64_IMAGE_SIZE:
                        safe_data[mime_type] = "[image omitted — too large]"
                        continue
                # Keep plain text, JSON, SVGs, etc.
                if isinstance(content, (str, list)):
                    total = sum(len(str(c)) for c in (content if isinstance(content, list) else [content]))
                    if total < MAX_OUTPUT_SIZE_PER_CELL:
                        safe_data[mime_type] = content
            if safe_data:
                safe["data"] = safe_data
                safe["execution_count"] = output.get("execution_count")
                return safe
            return None

        return None

    def _sanitise_html(self, content) -> str:
        """Strip <script>, on* attributes, javascript: URLs from HTML content."""
        if isinstance(content, list):
            content = "".join(content)
        if not isinstance(content, str):
            content = str(content)

        # Remove <script> tags
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        # Remove on* attributes
        content = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', content, flags=re.IGNORECASE)
        # Remove javascript: URLs
        content = re.sub(r'href\s*=\s*["\']javascript:[^"\']*["\']', 'href="#"', content, flags=re.IGNORECASE)
        return content

    # ----------------------------------------------------------------
    # Data extraction
    # ----------------------------------------------------------------

    def _extract_dataframes_from_outputs(self, outputs: List[Any]) -> List[Dict[str, Any]]:
        """Extract tables from code cell outputs.

        Looks for text/plain outputs that contain DataFrame-like tabular data.
        """
        dataframes = []
        for output in outputs:
            if not isinstance(output, dict):
                continue
            output_type = output.get("output_type", "")
            if output_type not in ("execute_result", "display_data"):
                continue

            data = output.get("data", {})
            if not isinstance(data, dict):
                continue

            # Try text/plain first (DataFrame repr)
            text_content = data.get("text/plain", None)
            df = self._try_parse_dataframe(text_content)
            if df is not None:
                dataframes.append(df)
                continue

            # Try text/html (table in HTML)
            html_content = data.get("text/html", None)
            df = self._try_parse_html_table(html_content)
            if df is not None:
                dataframes.append(df)

        return dataframes

    def _try_parse_dataframe(self, content) -> Optional[Dict[str, Any]]:
        """Try to parse text/plain content as a table (best-effort fallback).

        Known limitation: the "split on 2+ spaces" heuristic does not strip the
        leading row index and merges single-space-separated columns, so values
        can be shifted/truncated. Accepted as approximate — the HTML path
        (extract_first_table) is the primary parser and handles `display(df)`
        correctly. (Conscious deferral; see code-quirks-history.)
        """
        if content is None:
            return None
        if isinstance(content, list):
            content = "".join(str(c) for c in content)
        if not isinstance(content, str):
            return None

        # Reject obvious non-tabular Python object reprs (numpy arrays, lists,
        # dicts, Index reprs) — the 2+ space heuristic otherwise false-positives
        # on them.
        if any(marker in content for marker in ("array(", "[", "]", "{", "}")):
            return None

        # Must have at least 2 lines (header + data)
        lines = [l.strip() for l in content.strip().split("\n") if l.strip()]
        if len(lines) < 2:
            return None

        # Skip if it looks like a simple value, not a table
        if len(lines) == 1 and not any(c in lines[0] for c in ("  ", "\t", "|", ",")):
            return None

        try:
            # Try to parse as CSV (space/tab separated first line as header)
            # DataFrame repr looks like: "   col1  col2\n0  val1  val2"
            header_line = lines[0]
            # Split on 2+ spaces
            headers = re.split(r'\s{2,}', header_line)
            headers = [h.strip() for h in headers if h.strip()]

            if len(headers) < 1:
                return None

            rows = []
            for line in lines[1:]:
                # Skip lines that don't have enough fields
                fields = re.split(r'\s{2,}', line)
                fields = [f.strip() for f in fields if f.strip()]
                if len(fields) >= len(headers):
                    rows.append(dict(zip(headers, fields)))

            if len(rows) < 1:
                return None

            return make_table(headers, rows)
        except Exception:
            pass

        return None

    def _try_parse_html_table(self, content) -> Optional[Dict[str, Any]]:
        """Try to parse HTML content as a table."""
        return extract_first_table(content)

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    def _extract_title(self, cells: List[Dict[str, Any]]) -> str:
        """Extract notebook title from the first H1 markdown cell."""
        for cell in cells:
            if cell.get("cell_type") == "markdown":
                source = cell.get("source", [])
                text = "".join(source) if isinstance(source, list) else str(source)
                m = re.match(r'^#\s+(.+)', text.strip())
                if m:
                    return m.group(1).strip()
        return "Untitled Notebook"

    def get_sanitised_notebook_json(self, raw_bytes: bytes) -> Optional[bytes]:
        """Return the sanitised notebook as JSON bytes for storage."""
        parsed = self.parse(raw_bytes)
        if not parsed["valid"]:
            return None
        sanitised = {
            "nbformat": 4,
            "nbformat_minor": 4,
            "metadata": parsed["metadata"],
            "cells": parsed["cells"],
        }
        return json.dumps(sanitised, indent=1).encode("utf-8")
