"""
reports.py — Module 8: Reporting & Export
==========================================
Routes:
  GET /reports              — reports landing page
  GET /reports/export/csv   — download transactions as CSV
  GET /reports/export/pdf   — download monthly summary PDF
"""

import csv, io
from datetime import datetime
from flask import Blueprint, render_template, session, send_file, jsonify, request
from auth import login_required, api_login_required, log_event
from analysis import _fetch, get_savings_summary, get_category_summary, get_monthly_spending

reports_bp = Blueprint("reports", __name__)
_mysql = None

def init_reports(mysql_instance):
    global _mysql
    _mysql = mysql_instance


@reports_bp.route("/reports")
@login_required
def reports_page():
    return render_template("reports.html", user_name=session.get("user_name", ""))


@reports_bp.route("/reports/export/csv")
@login_required
def export_csv():
    """Download all transactions as a CSV file."""
    rows = _fetch()
    buf  = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Type", "Category", "Amount (ZMW)", "Description"])
    for r in rows:
        writer.writerow([r["date"], r["type"].capitalize(), r["category"],
                         f"{float(r['amount']):.2f}", r["description"] or ""])

    buf.seek(0)
    filename = f"IFMS_transactions_{datetime.now().strftime('%Y%m%d')}.csv"
    log_event(_mysql, "EXPORT", session.get("user_id"), "CSV export")
    return send_file(
        io.BytesIO(buf.read().encode("utf-8-sig")),   # utf-8-sig for Excel compat
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename
    )


@reports_bp.route("/reports/export/pdf")
@login_required
def export_pdf():
    """Generate and download a monthly summary PDF report."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError:
        return "reportlab not installed. Run: pip install reportlab", 500

    summary    = get_savings_summary()
    cat_sum    = get_category_summary()
    monthly    = get_monthly_spending()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story  = []

    # Title
    title_style = ParagraphStyle("title", parent=styles["Heading1"],
                                  textColor=colors.HexColor("#7c5cfc"), fontSize=18)
    story.append(Paragraph("NewGen — Financial Summary Report", title_style))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M')} &nbsp;|&nbsp; {session.get('user_name','')}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.5*cm))

    # Overview table
    story.append(Paragraph("Financial Overview", styles["Heading2"]))
    overview_data = [
        ["Metric", "Amount (ZMW)"],
        ["Total Income",   f"K {summary['total_income']:,.2f}"],
        ["Total Expenses", f"K {summary['total_expenses']:,.2f}"],
        ["Net Savings",    f"K {summary['net_savings']:,.2f}"],
        ["Savings Rate",   f"{summary['savings_rate']}%"],
    ]
    t = Table(overview_data, colWidths=[9*cm, 7*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), colors.HexColor("#7c5cfc")),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 11),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#f7f9ff"), colors.white]),
        ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#c8d0e8")),
        ("PADDING",      (0,0), (-1,-1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5*cm))

    # Category breakdown
    if cat_sum["labels"]:
        story.append(Paragraph("Spending by Category", styles["Heading2"]))
        cat_data = [["Category", "Amount (ZMW)", "% of Expenses"]]
        total_exp = sum(cat_sum["amounts"])
        for cat, amt in zip(cat_sum["labels"], cat_sum["amounts"]):
            pct = round(amt / total_exp * 100, 1) if total_exp > 0 else 0
            cat_data.append([cat, f"K {amt:,.2f}", f"{pct}%"])
        ct = Table(cat_data, colWidths=[8*cm, 5*cm, 4*cm])
        ct.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,0), colors.HexColor("#0f1420")),
            ("TEXTCOLOR",    (0,0), (-1,0), colors.HexColor("#7c5cfc")),
            ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",     (0,0), (-1,-1), 10),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#f7f9ff"), colors.white]),
            ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#c8d0e8")),
            ("PADDING",      (0,0), (-1,-1), 7),
        ]))
        story.append(ct)
        story.append(Spacer(1, 0.5*cm))

    # Monthly summary
    if monthly["labels"]:
        story.append(Paragraph("Monthly Summary", styles["Heading2"]))
        mon_data = [["Month", "Income (ZMW)", "Expenses (ZMW)", "Net"]]
        for i, label in enumerate(monthly["labels"]):
            inc = monthly["income"][i]
            exp = monthly["expenses"][i]
            net = round(inc - exp, 2)
            mon_data.append([label, f"K {inc:,.2f}", f"K {exp:,.2f}", f"K {net:,.2f}"])
        mt = Table(mon_data, colWidths=[4*cm, 4.5*cm, 4.5*cm, 4*cm])
        mt.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), colors.HexColor("#4f8ef7")),
            ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 10),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.HexColor("#f0f4ff"), colors.white]),
            ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#c8d0e8")),
            ("PADDING",       (0,0), (-1,-1), 7),
        ]))
        story.append(mt)

    doc.build(story)
    buf.seek(0)
    filename = f"IFMS_report_{datetime.now().strftime('%Y%m%d')}.pdf"
    log_event(_mysql, "EXPORT", session.get("user_id"), "PDF report")
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=True, download_name=filename)


@reports_bp.route("/api/audit-log")
@login_required
def api_audit_log():
    """Return recent audit log entries for the current user (admin view)."""
    uid = session["user_id"]
    cur = _mysql.connection.cursor()
    cur.execute("""
        SELECT event_type, ip_address, detail,
               DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i') AS ts
        FROM audit_log
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 20
    """, (uid,))
    rows = cur.fetchall()
    cur.close()
    return jsonify(list(rows))
