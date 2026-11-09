#!/usr/bin/env python3
"""Render a PRD Check report JSON into HTML and PDF.

Usage: render_report.py <report.json> <output.pdf>

Writes <output>.html next to the PDF. The PDF is printed with headless
Chrome/Chromium/Edge; if none is found, only the HTML is written.
"""
import html
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

STATUSES = {
    "match": ("✅", "Match", "#1a7f37", "#dafbe1"),
    "partial": ("🟡", "Partial", "#9a6700", "#fff8c5"),
    "mismatch": ("❌", "Mismatch", "#cf222e", "#ffebe9"),
    "missing": ("⛔", "Missing", "#a40e26", "#ffebe9"),
    "undocumented": ("➕", "Undocumented", "#0550ae", "#ddf4ff"),
    "unclear": ("❓", "PRD unclear", "#8250df", "#fbefff"),
    "accepted": ("☑️", "Accepted", "#57606a", "#f6f8fa"),
    "elsewhere": ("🔍", "Not verifiable here", "#57606a", "#f6f8fa"),
}
ORDER = list(STATUSES)
NEEDS_DECISION = {"mismatch", "missing", "partial", "unclear", "undocumented"}

CSS = """
@page { size: A4 landscape; margin: 12mm; }
* { box-sizing: border-box; }
body { font: 10px/1.4 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #1f2328; margin: 0; }
h1 { font-size: 20px; margin: 0 0 4px; }
h2 { font-size: 15px; margin: 22px 0 6px; padding-bottom: 4px; border-bottom: 2px solid #d0d7de; page-break-after: avoid; }
h3 { font-size: 12px; margin: 14px 0 4px; page-break-after: avoid; }
.meta { color: #57606a; margin: 0 0 2px; }
table { width: 100%; border-collapse: collapse; margin: 6px 0 10px; table-layout: fixed; }
th, td { border: 1px solid #d0d7de; padding: 3px 5px; vertical-align: top; text-align: left; word-wrap: break-word; overflow-wrap: anywhere; }
th { background: #f6f8fa; font-weight: 600; }
tr { page-break-inside: avoid; }
code { font: 9px ui-monospace, Menlo, monospace; background: #f6f8fa; padding: 0 2px; border-radius: 3px; }
.pill { display: inline-block; padding: 1px 6px; border-radius: 10px; font-weight: 600; white-space: nowrap; }
.counts td, .counts th { text-align: center; }
.counts td:first-child, .counts th:first-child { text-align: left; }
ul { margin: 4px 0 8px 18px; padding: 0; }
li { margin: 1px 0; }
.note { background: #ddf4ff; border: 1px solid #54aeff; padding: 6px 8px; border-radius: 6px; margin: 8px 0; }
.page-break { page-break-before: always; }
"""


def esc(value):
    text = html.escape(str(value or ""))
    # `backticks` → <code>
    parts = text.split("`")
    return "".join(f"<code>{p}</code>" if i % 2 else p for i, p in enumerate(parts))


def pill(status):
    emoji, label, fg, bg = STATUSES.get(status, ("", status, "#000", "#fff"))
    return f'<span class="pill" style="color:{fg};background:{bg}">{emoji} {label}</span>'


def count_rows(rows):
    counts = {s: 0 for s in ORDER}
    for row in rows:
        counts[row.get("status", "")] = counts.get(row.get("status", ""), 0) + 1
    return counts


def counts_table(report):
    head = "".join(f"<th>{STATUSES[s][0]} {STATUSES[s][1]}</th>" for s in ORDER)
    body, total = "", {s: 0 for s in ORDER}
    for prd in report["prds"]:
        c = count_rows(prd["rows"])
        c["undocumented"] += len(prd.get("undocumented", []))
        for s in ORDER:
            total[s] += c.get(s, 0)
        body += f"<tr><td>{esc(prd['title'])}</td>" + "".join(f"<td>{c.get(s, 0) or ''}</td>" for s in ORDER) + "</tr>"
    body += "<tr><th>Total</th>" + "".join(f"<th>{total[s]}</th>" for s in ORDER) + "</tr>"
    return f'<table class="counts"><tr><th style="width:22%">PRD</th>{head}</tr>{body}</table>', total


def rows_table(rows):
    out = ['<table><tr><th style="width:5%">#</th><th style="width:6%">PRD §</th><th style="width:24%">Requirement</th>'
           '<th style="width:22%">Code location</th><th style="width:11%">Status</th><th>Finding</th></tr>']
    for r in rows:
        out.append(
            f"<tr><td>{esc(r.get('id'))}</td><td>{esc(r.get('section'))}</td><td>{esc(r.get('requirement'))}</td>"
            f"<td>{esc(r.get('location') or '—')}</td><td>{pill(r.get('status'))}</td><td>{esc(r.get('finding'))}</td></tr>"
        )
    out.append("</table>")
    return "".join(out)


def bullet_list(items):
    return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>" if items else ""


def render(report):
    counts_html, total = counts_table(report)
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(report['title'])}</title><style>{CSS}</style></head><body>"]
    parts.append(f"<h1>{esc(report['title'])}</h1>")
    for line in report.get("meta", []):
        parts.append(f'<p class="meta">{esc(line)}</p>')
    parts.append('<div class="note">Read through this report before the review session. For every item under '
                 '<b>Decisions needed</b>, decide whether the <b>code</b> or the <b>PRD</b> is wrong, whether it is '
                 '<b>intentional</b>, or whether to <b>skip</b> it for now.</div>')

    parts.append("<h2>Summary</h2>" + counts_html)
    if report.get("legend"):
        parts.append("<h3>Path shorthand</h3>" + bullet_list(report["legend"]))

    changes = report.get("prd_changes", [])
    if changes:
        parts.append(f"<h2>PRD changes since this platform last checked ({len(changes)})</h2>")
        parts.append("<p>Changes logged by other platforms, or found by comparing against the last checked version. Review these first.</p>")
        parts.append('<table><tr><th style="width:14%">PRD</th><th style="width:6%">§</th><th style="width:26%">Change</th>'
                     '<th style="width:16%">Source</th><th style="width:11%">Status</th><th>Finding</th></tr>')
        for c in changes:
            parts.append(f"<tr><td>{esc(c.get('prd'))}</td><td>{esc(c.get('section'))}</td><td>{esc(c.get('change'))}</td>"
                         f"<td>{esc(c.get('source'))}</td><td>{pill(c.get('status'))}</td><td>{esc(c.get('finding'))}</td></tr>")
        parts.append("</table>")

    decisions = report.get("decisions", [])
    if decisions:
        parts.append(f"<h2>Decisions needed ({len(decisions)})</h2>")
        parts.append('<table><tr><th style="width:5%">#</th><th style="width:10%">PRD rows</th><th style="width:9%">Status</th>'
                     '<th>Issue</th><th style="width:24%">Where</th></tr>')
        for d in decisions:
            parts.append(f"<tr><td>{esc(d['id'])}</td><td>{esc(d.get('rows'))}</td><td>{pill(d.get('status', 'mismatch'))}</td>"
                         f"<td>{esc(d['issue'])}</td><td>{esc(d.get('where') or '—')}</td></tr>")
        parts.append("</table>")

    for prd in report["prds"]:
        parts.append(f'<h2 class="page-break">{esc(prd["title"])}</h2>')
        for line in prd.get("meta", []):
            parts.append(f'<p class="meta">{esc(line)}</p>')
        parts.append(rows_table(prd["rows"]))
        if prd.get("undocumented"):
            parts.append("<h3>➕ In code, not in the PRD</h3>" + bullet_list(prd["undocumented"]))
        if prd.get("open_questions"):
            parts.append("<h3>Open questions and contradictions</h3>" + bullet_list(prd["open_questions"]))
        if prd.get("docs_disagree"):
            parts.append("<h3>Where the package docs disagree</h3>" + bullet_list(prd["docs_disagree"]))

    elsewhere = [(p["title"], r) for p in report["prds"] for r in p["rows"] if r.get("status") == "elsewhere"]
    if elsewhere:
        parts.append(f'<h2 class="page-break">Check elsewhere ({len(elsewhere)})</h2>')
        parts.append("<p>These can't be verified from this repo. Check them in the repo or platform named.</p>")
        parts.append('<table><tr><th style="width:18%">PRD</th><th style="width:5%">#</th><th style="width:30%">Requirement</th><th>Why / where to check</th></tr>')
        for title, r in elsewhere:
            parts.append(f"<tr><td>{esc(title)}</td><td>{esc(r.get('id'))}</td><td>{esc(r.get('requirement'))}</td><td>{esc(r.get('finding'))}</td></tr>")
        parts.append("</table>")

    if report.get("learned"):
        parts.append("<h2>What was learned for next time</h2>" + bullet_list(report["learned"]))
    parts.append("</body></html>")
    return "".join(parts)


def find_browser():
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge"):
        if path := shutil.which(name):
            candidates.insert(0, path)
    return next((c for c in candidates if os.path.exists(c)), None)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    report = json.loads(Path(sys.argv[1]).read_text())
    pdf_path = Path(sys.argv[2]).expanduser().resolve()
    html_path = pdf_path.with_suffix(".html")
    html_path.write_text(render(report))
    print(f"HTML: {html_path}")

    browser = find_browser()
    if not browser:
        print("No Chrome/Chromium/Edge found; open the HTML and print it to PDF.")
        return
    subprocess.run(
        [browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={pdf_path}", html_path.as_uri()],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"PDF: {pdf_path}")


if __name__ == "__main__":
    main()
