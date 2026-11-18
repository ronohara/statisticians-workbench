"""
PDF generation for Database Design analysis reports.
Uses fpdf2 for pure-Python PDF generation.
"""

from fpdf import FPDF
from io import BytesIO
from typing import Dict, Any, List
from datetime import datetime


def _fmt_confidence(value) -> str:
    """Format a confidence value for display — handles both numeric (0.0-1.0)
    and string ('high'/'medium'/'low') formats from LLM output."""
    if isinstance(value, (int, float)):
        return f"{value:.0%}"
    if isinstance(value, str):
        return value.capitalize()
    return str(value)


def _sanitize(text) -> str:
    """Replace Unicode characters that Helvetica cannot render with ASCII equivalents."""
    # Handle non-string inputs from asyncpg (bytes, bytearray, memoryview, None)
    if text is None:
        return ""
    if isinstance(text, (bytes, bytearray, memoryview)):
        text = bytes(text).decode("utf-8", errors="replace")
    if not isinstance(text, str):
        text = str(text)

    # Replace common Unicode chars with ASCII
    replacements = {
        "\u2014": "--",   # em dash
        "\u2013": "-",    # en dash
        "\u2018": "'",    # left single quote
        "\u2019": "'",    # right single quote
        "\u201c": '"',    # left double quote
        "\u201d": '"',    # right double quote
        "\u2026": "...",  # ellipsis
        "\u00a0": " ",    # non-breaking space
        "\u2022": "-",    # bullet
        "\u2122": "(TM)", # trademark
        "\u00ae": "(R)",  # registered
        "\u2192": "->",   # right arrow
        "\u2264": "<=",   # less-than-or-equal
        "\u2265": ">=",   # greater-than-or-equal
    }
    for uchar, ascii_repl in replacements.items():
        text = text.replace(uchar, ascii_repl)

    # Strip any remaining non-Latin1 characters
    try:
        text.encode("latin-1")
    except UnicodeEncodeError:
        text = text.encode("latin-1", errors="replace").decode("latin-1")

    return text


class AnalysisPDF(FPDF):
    """Custom PDF with header/footer for analysis reports."""

    def __init__(self, tr: Dict[str, str]):
        super().__init__()
        self._tr = tr

    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, self._tr.get("header", "Database Design Analysis Report"), align="L")
        self.cell(0, 6, datetime.now().strftime("%Y-%m-%d %H:%M"), align="R", new_x="LMARGIN", new_y="NEXT")
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        page_text = self._tr.get("page", "Page {current}/{total}")
        page_text = page_text.replace("{current}", str(self.page_no())).replace("{total}", "{nb}")
        self.cell(0, 10, page_text, align="C")


def generate_analysis_pdf(report: Dict[str, Any], tr: Dict[str, str]) -> bytes:
    """Generate a PDF from an analysis report and return as bytes.

    Args:
        report: The analysis report dict.
        tr: Translations dict with keys like 'title', 'summary', 'tables', etc.
    """
    pdf = AnalysisPDF(tr)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    summary = report.get("summary", {})
    analysis = report.get("analysis", {})
    schema = report.get("schema", {})
    raw_issues = analysis.get("issues", [])
    # Handle both wrapped {total, items: [...]} (from coordinator) and flat list (from frontend normalisation)
    if isinstance(raw_issues, dict):
        issues = raw_issues.get("items", [])
    else:
        issues = raw_issues if isinstance(raw_issues, list) else []

    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 12, tr.get("title", "Database Design Analysis"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    db_name = report.get("database_name", report.get("connection_name", "Unknown"))
    db_type = report.get("database_type", "Unknown")
    conn_name = report.get("connection_name", "")
    conn_id = report.get("connection_id", "N/A")
    subtitle_tmpl = tr.get("subtitle", "Database: {db_name} ({db_type}) | Connection: {conn_name} (ID: {conn_id})")
    subtitle = subtitle_tmpl.replace("{db_name}", str(db_name)).replace("{db_type}", str(db_type)).replace("{conn_name}", str(conn_name)).replace("{conn_id}", str(conn_id))
    subtitle = _sanitize(subtitle)
    pdf.cell(0, 6, subtitle, align="C", new_x="LMARGIN", new_y="NEXT")

    # AI provider / model line
    ai_provider = report.get("ai_provider")
    ai_model = report.get("ai_model")
    if ai_provider and ai_model:
        ai_line = f"AI: {ai_provider} ({ai_model})"
    elif ai_model:
        ai_line = f"AI Model: {ai_model}"
    else:
        ai_line = ""
    if ai_line:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 5, _sanitize(f"  {ai_line}"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # AI-skipped warning banner
    if report.get("ai_skipped"):
        reason = report.get("ai_skipped_reason", "")
        pdf.set_fill_color(255, 243, 205)   # light amber background
        pdf.set_draw_color(212, 175, 55)     # amber border
        pdf.set_text_color(146, 98, 0)       # dark amber text
        pdf.set_font("Helvetica", "B", 10)
        warning_label = _sanitize(tr.get("ai_skipped_warning", "AI Analysis Skipped"))
        pdf.cell(0, 7, f"  {warning_label}", fill=True, new_x="LMARGIN", new_y="NEXT")
        if reason:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(120, 90, 20)
            # MultiCell for wrapped text within the warning box
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.set_xy(x + 4, y)
            pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - 8, 5, _sanitize(reason), fill=True)
            pdf.set_xy(x, pdf.get_y())
        pdf.set_draw_color(200, 200, 200)  # reset border
        pdf.ln(6)

    # Summary section
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(30, 30, 30)
    pdf.set_fill_color(240, 240, 245)
    pdf.cell(0, 8, f"  {tr.get('summary', 'Summary')}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)

    stats = [
        (tr.get("tables", "Tables"), str(summary.get("total_tables", 0))),
        (tr.get("columns", "Columns"), str(summary.get("total_columns", 0))),
        (tr.get("rows", "Rows"), str(summary.get("total_rows", 0))),
        (tr.get("issues_found", "Issues Found"), str(summary.get("issue_count", 0))),
    ]
    for label, value in stats:
        pdf.cell(50, 6, f"  {label}:", new_x="RIGHT")
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
    pdf.ln(4)

    # Risk breakdown
    risk = summary.get("risk_summary", {})
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, f"  {tr.get('risk_breakdown', 'Risk Breakdown')}:", new_x="LMARGIN", new_y="NEXT")
    risks = [
        (tr.get("high", "High"), str(risk.get("high", 0)), (220, 50, 50)),
        (tr.get("medium", "Medium"), str(risk.get("medium", 0)), (200, 150, 0)),
        (tr.get("low", "Low"), str(risk.get("low", 0)), (50, 100, 180)),
    ]
    for label, value, color in risks:
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(50, 6, f"    {label}: {value}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(50, 50, 50)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(6)

    # Top recommendations
    recommendations = summary.get("top_recommendations", [])
    if recommendations:
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(30, 30, 30)
        pdf.set_fill_color(240, 240, 245)
        pdf.cell(0, 8, f"  {tr.get('top_recommendations', 'Top Recommendations')}", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(50, 50, 50)
        for i, rec in enumerate(recommendations, 1):
            pdf.cell(8, 5, f"{i}.", new_x="RIGHT")
            pdf.multi_cell(0, 5, _sanitize(rec), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        pdf.ln(4)

    # Issues section
    if issues:
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(30, 30, 30)
        pdf.set_fill_color(240, 240, 245)
        issues_title = tr.get("issues_count", "Issues ({count})").replace("{count}", str(len(issues)))
        pdf.cell(0, 8, f"  {issues_title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        severity_colors = {
            "CRITICAL": (180, 30, 30),
            "HIGH": (200, 100, 0),
            "MEDIUM": (180, 150, 0),
            "LOW": (50, 100, 180),
        }

        for issue in issues:
            sev = issue.get("severity", "LOW")
            color = severity_colors.get(sev, (100, 100, 100))

            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*color)
            header = _sanitize(f"[{sev}] {issue.get('category', '').upper()} - {issue.get('table', '')}")
            pdf.cell(0, 5, header, new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(0, 4, _sanitize(f"  {issue.get('message', '')}"), new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Courier", "", 7)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(0, 4, _sanitize(f"  -> {issue.get('recommendation', '')}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

    # ── AI-Augmented: Health Score ──────────────────────────────────
    health = analysis.get("health", {})
    if health:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(30, 30, 30)
        pdf.set_fill_color(240, 240, 245)
        pdf.cell(0, 8, f"  {tr.get('health_score_title', 'Health Score')}", fill=True,
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # Section subtitle
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 5, _sanitize(f"  {tr.get('health_score_subtitle', 'Overall database health assessed by Schema AI.')}"),
                       new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        score = health.get("score", 50)
        pdf.set_font("Helvetica", "B", 18)
        if score >= 80:
            pdf.set_text_color(22, 163, 74)
        elif score >= 60:
            pdf.set_text_color(200, 150, 0)
        else:
            pdf.set_text_color(220, 50, 50)
        score_text = tr.get("health_score_label", "Database Health Score: {score}/100")
        score_text = score_text.replace("{score}", str(score))
        pdf.cell(0, 12, _sanitize(f"  {score_text}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(50, 50, 50)
        pdf.ln(6)

        top_actions = health.get("top_actions", [])
        if top_actions:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, f"  {tr.get('top_actions_label', 'Top Priority Actions')}:",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            for i, action in enumerate(top_actions, 1):
                pdf.cell(8, 5, f"{i}.", new_x="RIGHT")
                pdf.multi_cell(0, 5, _sanitize(action), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(1)
        pdf.ln(2)

    # ── AI-Augmented: Semantic Analysis ─────────────────────────────
    semantic = analysis.get("semantic")
    if semantic:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(30, 30, 30)
        pdf.set_fill_color(240, 240, 245)
        pdf.cell(0, 8, f"  {tr.get('semantic_title', 'AI Semantic Analysis')}", fill=True,
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # Section subtitle
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 5, _sanitize(f"  {tr.get('semantic_subtitle', 'AI-inferred column meanings, ISIC domain classifications, and code system detections.')}"),
                       new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # AI disclaimer
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 4, _sanitize(f"  {tr.get('ai_disclaimer', 'AI-generated analysis')}"),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(50, 50, 50)
        pdf.ln(4)

        # Code systems
        code_systems = semantic.get("code_systems", [])
        if code_systems:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(0, 7, f"  {tr.get('code_systems_label', 'Detected Code Systems')}:",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            for cs in code_systems:
                name = cs.get("name", "")
                conf = cs.get("confidence", 0)
                columns = cs.get("columns", [])
                col_str = ", ".join(columns[:5])
                conf_text = tr.get("confidence_label", "Confidence")
                pdf.cell(0, 5, _sanitize(f"    {name} ({conf_text}: {_fmt_confidence(conf)})"),
                         new_x="LMARGIN", new_y="NEXT")
                if col_str:
                    pdf.cell(0, 5, _sanitize(f"      Columns: {col_str}"),
                             new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

        # ISIC Domain Classifications
        domains = semantic.get("domains", [])
        if domains:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(0, 7, f"  {tr.get('domain_label', 'ISIC Domain Classifications')}:",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            for d in domains:
                table = d.get("table", "")
                codes = d.get("domains", [])
                codes_str = ", ".join(codes) if isinstance(codes, list) else str(codes)
                pdf.cell(0, 5, _sanitize(f"    {table} \u2192 {codes_str}"),
                         new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

        # Table purposes
        table_purposes = semantic.get("table_purposes", [])
        if table_purposes:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(0, 7, f"  {tr.get('table_purposes_label', 'Table Purposes')}:",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            for tp in table_purposes:
                table = tp.get("table", "")
                purpose = tp.get("purpose", "")
                pdf.cell(0, 5, _sanitize(f"    {table}"), new_x="LMARGIN", new_y="NEXT")
                pdf.multi_cell(0, 4, _sanitize(f"      {purpose}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        # Column meanings
        columns = semantic.get("columns", [])
        if columns:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(0, 7, f"  {tr.get('column_meanings_label', 'Column Meanings')}:",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)
            for col in columns:
                col_name = col.get("column", "")
                meaning = col.get("meaning", "")
                conf = col.get("confidence", 0)
                conf_text = tr.get("confidence_label", "Confidence")
                pdf.cell(0, 4, _sanitize(f"    {col_name} ({conf_text}: {_fmt_confidence(conf)}): {meaning}"),
                         new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

    # ── AI-Augmented: Integration Findings ──────────────────────────
    integration = analysis.get("integration")
    if integration:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(30, 30, 30)
        pdf.set_fill_color(240, 240, 245)
        pdf.cell(0, 8, f"  {tr.get('integration_title', 'AI Integration Findings')}", fill=True,
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # Section subtitle
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 5, _sanitize(f"  {tr.get('integration_subtitle', 'Implicit relationships, research capabilities, and missing dimensions detected by Integration AI.')}"),
                       new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # Implicit relationships
        rels = integration.get("implicit_relationships", [])
        if rels:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(60, 60, 60)
            pdf.set_fill_color(230, 240, 235)
            pdf.cell(0, 7, f"  {tr.get('implicit_relationships_label', 'Implicit Relationships')}",
                     fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)
            for rel in rels:
                t1 = rel.get("from_table", "")
                t2 = rel.get("to_table", "")
                c1 = rel.get("from_column", "")
                c2 = rel.get("to_column", "")
                conf = rel.get("confidence", "")
                # Relationship header line
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(40, 40, 40)
                pdf.cell(0, 5, _sanitize(f"    {t1}.{c1}  \u2192  {t2}.{c2}"),
                         new_x="LMARGIN", new_y="NEXT")
                # Confidence badge
                if conf:
                    conf_color = (22, 163, 74) if conf.lower() == "high" else (180, 150, 0)
                    pdf.set_font("Helvetica", "", 7)
                    pdf.set_text_color(*conf_color)
                    pdf.cell(0, 4, _sanitize(f"      {_fmt_confidence(conf)} confidence"),
                             new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(60, 60, 60)
                # Evidence
                evidence = rel.get("evidence", "")
                if evidence:
                    pdf.set_font("Helvetica", "", 8)
                    ev_label = tr.get("evidence_label", "Evidence")
                    pdf.multi_cell(0, 4, _sanitize(f"      {ev_label}: {evidence}"),
                                  new_x="LMARGIN", new_y="NEXT")
                # Proposed DDL
                ddl = rel.get("proposed_ddl", "")
                if ddl:
                    pdf.set_font("Courier", "", 6)
                    pdf.set_text_color(80, 80, 80)
                    ddl_label = tr.get("proposed_ddl_label", "Proposed DDL")
                    pdf.cell(0, 4, _sanitize(f"      {ddl_label}:"),
                             new_x="LMARGIN", new_y="NEXT")
                    for line in ddl.split("\n")[:8]:
                        pdf.cell(0, 4, _sanitize(f"        {line[:110]}"),
                                 new_x="LMARGIN", new_y="NEXT")
                pdf.ln(4)
            pdf.ln(2)

        # Research capabilities
        capabilities = integration.get("research_capabilities", [])
        if capabilities:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(60, 60, 60)
            pdf.set_fill_color(230, 240, 235)
            pdf.cell(0, 7, f"  {tr.get('research_capabilities_label', 'Research Capabilities')}",
                     fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)
            for cap in capabilities:
                study = cap.get("study_type", "")
                supported = cap.get("supported")
                conf = cap.get("confidence", "")
                rationale = cap.get("rationale", "")
                # Icon + study type + confidence on one line
                if supported is True:
                    label = tr.get("supported_label", "Supported")
                    label_color = (22, 163, 74)
                elif supported is False:
                    label = tr.get("unsupported_label", "Not Supported")
                    label_color = (180, 30, 30)
                else:
                    label = tr.get("partial_label", "Partial")
                    label_color = (200, 150, 0)
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(*label_color)
                pdf.cell(0, 5, _sanitize(f"    [{label}]  {study}"), new_x="LMARGIN", new_y="NEXT")
                # Confidence
                if conf:
                    conf_color = (22, 163, 74) if conf.lower() == "high" else (180, 150, 0)
                    pdf.set_font("Helvetica", "", 7)
                    pdf.set_text_color(*conf_color)
                    pdf.cell(0, 4, _sanitize(f"      {_fmt_confidence(conf)} confidence"),
                             new_x="LMARGIN", new_y="NEXT")
                # Rationale
                if rationale:
                    pdf.set_font("Helvetica", "", 8)
                    pdf.set_text_color(80, 80, 80)
                    pdf.multi_cell(0, 4, _sanitize(f"      {rationale}"),
                                  new_x="LMARGIN", new_y="NEXT")
                pdf.ln(3)
            pdf.ln(2)

        # Missing dimensions
        missing = integration.get("missing_dimensions", [])
        if missing:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(60, 60, 60)
            pdf.set_fill_color(250, 240, 230)
            pdf.cell(0, 7, f"  {tr.get('missing_dimensions_label', 'Missing Dimensions')}",
                     fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)
            for md in missing:
                table = md.get("table", "")
                feature = md.get("missing_feature", "")
                explanation = md.get("likely_explanation", "")
                peers = md.get("peer_tables", [])
                # Table is missing feature
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(40, 40, 40)
                pdf.cell(0, 5, _sanitize(f"    {table}"),
                         new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(180, 100, 40)
                pdf.cell(0, 5, _sanitize(f"      missing: {feature}"),
                         new_x="LMARGIN", new_y="NEXT")
                # Peer tables
                if peers:
                    peer_str = ", ".join(peers)
                    pdf.set_font("Helvetica", "", 7)
                    pdf.set_text_color(100, 100, 100)
                    pdf.cell(0, 4, _sanitize(f"      Peer tables: {peer_str}"),
                             new_x="LMARGIN", new_y="NEXT")
                # Explanation
                if explanation:
                    pdf.set_font("Helvetica", "", 8)
                    pdf.set_text_color(80, 80, 80)
                    pdf.multi_cell(0, 4, _sanitize(f"      {explanation}"),
                                  new_x="LMARGIN", new_y="NEXT")
                pdf.ln(4)

    # Semi-structured analysis section
    semi_structured = report.get("semi_structured", {})
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(30, 30, 30)
    pdf.set_fill_color(240, 240, 245)
    findings = semi_structured.get("findings", [])
    sst_title = tr.get("semi_structured_title", "Semi-Structured Data Analysis ({count} columns)").replace("{count}", str(len(findings)))
    pdf.cell(0, 8, f"  {sst_title}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if not findings:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 10, f"  {tr.get('none', 'None')}", new_x="LMARGIN", new_y="NEXT")
    else:
        for f in findings:
            key = f"{f.get('schema', '')}.{f.get('table', '')}.{f.get('column', '')}"
            code_systems = f.get("code_systems", [])
            keywords = f.get("keywords", {})
            top_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:10]

            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(80, 80, 160)
            pdf.cell(0, 6, _sanitize(f"  {key}"), new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(60, 60, 60)

            if code_systems:
                systems = ", ".join(cs.get("name", "") for cs in code_systems)
                cs_label = tr.get("code_systems", "Code Systems")
                pdf.cell(0, 5, f"    {cs_label}: {systems}", new_x="LMARGIN", new_y="NEXT")

            if top_keywords:
                kw_list = ", ".join(f"{k}({v})" for k, v in top_keywords[:5])
                kw_label = tr.get("top_keywords", "Top keywords")
                pdf.multi_cell(0, 5, _sanitize(f"    {kw_label}: {kw_list}"), new_x="LMARGIN", new_y="NEXT")

            categories = f.get("categories", {})
            if categories:
                cat_list = ", ".join(f"{cat}({cnt})" for cat, cnt in list(categories.items())[:5])
                cat_label = tr.get("categories", "Categories")
                pdf.multi_cell(0, 5, _sanitize(f"    {cat_label}: {cat_list}"), new_x="LMARGIN", new_y="NEXT")

            pdf.ln(3)

    # Normalisation suggestions section
    normalisation = report.get("normalisation_suggestions", [])
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(30, 30, 30)
    pdf.set_fill_color(240, 240, 245)
    norm_title = tr.get("normalisation_title", "Normalisation Suggestions ({count})").replace("{count}", str(len(normalisation)))
    pdf.cell(0, 8, f"  {norm_title}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if not normalisation:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 10, f"  {tr.get('none', 'None')}", new_x="LMARGIN", new_y="NEXT")
    else:
        for i, s in enumerate(normalisation, 1):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(80, 80, 160)
            pdf.cell(0, 6, _sanitize(f"  {i}. {s.get('description', '')[:120]}"), new_x="LMARGIN", new_y="NEXT")

            confidence = s.get("confidence", 0)
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(120, 120, 120)
            conf_label = tr.get("confidence", "Confidence")
            pdf.cell(0, 5, f"    {conf_label}: {_fmt_confidence(confidence)}", new_x="LMARGIN", new_y="NEXT")

            business = s.get("business_value", "")
            if business:
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(60, 60, 60)
                val_label = tr.get("value", "Value")
                pdf.multi_cell(0, 5, _sanitize(f"    {val_label}: {business}"), new_x="LMARGIN", new_y="NEXT")

            proposed = s.get("proposed_table", {})
            if proposed:
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(60, 60, 60)
                pt_label = tr.get("proposed_table", "Proposed table")
                pdf.cell(0, 5, f"    {pt_label}: {proposed.get('name', '')}", new_x="LMARGIN", new_y="NEXT")

                columns = proposed.get("columns", [])
                for col in columns:
                    pdf.set_font("Courier", "", 7)
                    pdf.set_text_color(80, 80, 80)
                    pdf.cell(0, 4, _sanitize(f"      {col.get('name','')} {col.get('type','')}"), new_x="LMARGIN", new_y="NEXT")

            migration = s.get("proposed_migration", "")
            if migration:
                pdf.set_font("Courier", "", 6)
                pdf.set_text_color(100, 100, 100)
                for line in migration.split("\n")[:20]:
                    pdf.cell(0, 4, _sanitize(f"    {line[:100]}"), new_x="LMARGIN", new_y="NEXT")

            pdf.ln(4)

    # Tables section
    tables = schema.get("tables", [])
    if tables:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(30, 30, 30)
        pdf.set_fill_color(240, 240, 245)
        schema_title = tr.get("schema_title", "Schema ({count} tables)").replace("{count}", str(len(tables)))
        pdf.cell(0, 8, f"  {schema_title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        for table in tables:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(30, 30, 30)
            pdf.set_fill_color(230, 235, 245)
            cols = str(len(table.get("columns", [])))
            rows = str(table.get("row_count", 0))
            title = _sanitize(f"  {table.get('schema', '')}.{table['name']}  ({cols} {tr.get('columns', 'columns')}, {rows} {tr.get('rows', 'rows')})")
            pdf.cell(0, 7, title, fill=True, new_x="LMARGIN", new_y="NEXT")

            columns = table.get("columns", [])
            if columns:
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_fill_color(245, 245, 250)
                col_widths = [55, 35, 20, 20, 60]
                headers = [
                    tr.get("col_name", "Column"),
                    tr.get("col_type", "Type"),
                    tr.get("col_nullable", "Nullable"),
                    tr.get("col_pk", "PK"),
                    tr.get("col_default", "Default"),
                ]
                for i, (header, w) in enumerate(zip(headers, col_widths)):
                    pdf.cell(w, 5, header, border=1, fill=True, align="C")
                pdf.ln()

                pdf.set_font("Helvetica", "", 7)
                pk_cols = set(_sanitize(k) for k in table.get("primary_key", []))
                for col in columns:
                    col_name = _sanitize(col.get("name", ""))
                    is_pk = tr.get("pk", "PK") if col_name in pk_cols else ""
                    nullable = tr.get("yes", "YES") if col.get("nullable") else tr.get("no", "NO")
                    default = _sanitize(col.get("default") or "")

                    name = col_name[:25]
                    dtype = _sanitize(col.get("type", ""))[:15]
                    default = default[:28]

                    row_data = [name, dtype, nullable, is_pk, default]
                    for i, (val, w) in enumerate(zip(row_data, col_widths)):
                        pdf.cell(w, 5, val, border=1, align="C" if i > 0 else "L")
                    pdf.ln()
            pdf.ln(3)

    return pdf.output()
