#!/usr/bin/env python3
"""تحويل مستندات المستودع من Markdown إلى PDF منسّق (عبر Chromium بلا واجهة).

    python docs/md2pdf.py docs/project-brief-EN.md docs/project-brief-EN.pdf

يتطلب: pip install markdown، ومتصفح Chromium/Chrome.
حدّد مسار المتصفح بمتغير البيئة CHROME_BIN إن اختلف على جهازك.
"""
import os, re, subprocess, sys, pathlib
import markdown

CHROME = os.environ.get("CHROME_BIN", "chromium")

src, out = pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve()
text = src.read_text(encoding="utf-8")

def preprocess(md: str) -> str:
    """Fixes for python-markdown strictness that GitHub tolerates."""
    out, prev, in_fence = [], "", False
    for line in md.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        # a list must be preceded by a blank line, else it is swallowed by the paragraph
        if not in_fence and re.match(r"^\s*([-*+]|\d+\.)\s", line) and prev.strip() \
                and not re.match(r"^\s*([-*+]|\d+\.)\s", prev) and not prev.startswith(("|", ">", "#")):
            out.append("")
        out.append(line)
        prev = line
    return "\n".join(out)


def cover(md: str) -> tuple[str, str]:
    """Pull the leading title + `**Key:** value` lines into a proper document header."""
    head, sep, rest = md.partition("\n---\n")
    if not sep:
        return "", md
    title = re.search(r"^#\s+(.+)$", head, re.M)
    subtitle = re.search(r"^##\s+(.+)$", head, re.M)
    meta = re.findall(r"^\*\*(.+?):\*\*\s*(.+)$", head, re.M)
    if not (title and meta):
        return "", md
    rows = "".join(
        f'<tr><th>{k}</th><td>{markdown.markdown(v).removeprefix("<p>").removesuffix("</p>")}</td></tr>'
        for k, v in meta)
    # any remaining prose in the header block (not title/subtitle/key-value) stays as a note
    leftover = [ln for ln in head.split("\n")
                if ln.strip() and not ln.startswith("#") and not re.match(r"^\*\*(.+?):\*\*", ln)]
    note = (f'<div class="cover-note">{markdown.markdown(" ".join(leftover))}</div>'
            if leftover else "")
    html = (f'<header class="cover"><h1>{title.group(1)}</h1>'
            + (f'<p class="subtitle">{subtitle.group(1)}</p>' if subtitle else "")
            + f'<table class="meta">{rows}</table>{note}</header>')
    return html, rest


cover_html, body_md = cover(text)
body_html = cover_html + markdown.markdown(
    preprocess(body_md), extensions=["tables", "fenced_code", "sane_lists", "attr_list"])

CSS = """
@page { size: A4; margin: 20mm 18mm 18mm 18mm;
        @bottom-center { content: counter(page); } }
* { box-sizing: border-box; }
body { font-family: "DejaVu Sans", "Helvetica Neue", Arial, sans-serif;
       font-size: 10.2pt; line-height: 1.55; color: #1b1f24; margin: 0; }
.cover { border-bottom: 2.5pt solid #0f766e; padding-bottom: 12pt; margin-bottom: 6pt; }
.cover .subtitle { font-size: 13pt; color: #475569; font-weight: 500; margin: 2pt 0 12pt; }
table.meta { width: 100%; border-collapse: collapse; font-size: 9pt; margin: 0; }
table.meta th { background: none; color: #0f766e; text-align: left; width: 78pt;
                padding: 2.5pt 8pt 2.5pt 0; font-size: 9pt; font-weight: 600;
                vertical-align: top; white-space: nowrap; }
table.meta td { border: 0; padding: 2.5pt 0; color: #334155; background: none !important; }
.cover-note { margin: 10pt 0 0; padding: 7pt 10pt; background: #f0fdfa;
              border-left: 3pt solid #0f766e; font-size: 9.5pt; }
.cover-note p { margin: 0; }
h1 { font-size: 21pt; line-height: 1.2; color: #0f172a; margin: 0 0 4pt;
     letter-spacing: -0.4pt; }
h1 + h2 { margin-top: 2pt; border: 0; padding: 0; color: #475569; font-size: 13pt;
          font-weight: 500; }
h2 { font-size: 13.5pt; color: #0f172a; margin: 22pt 0 7pt; padding-bottom: 4pt;
     border-bottom: 1.2pt solid #0f766e; page-break-after: avoid; letter-spacing: -0.2pt; }
h3 { font-size: 11pt; color: #0f766e; margin: 14pt 0 5pt; page-break-after: avoid; }
p { margin: 0 0 8pt; }
strong { color: #0f172a; }
ul, ol { margin: 0 0 9pt; padding-left: 16pt; }
li { margin-bottom: 3.5pt; }
li > strong:first-child { color: #0f766e; }
code { font-family: "DejaVu Sans Mono", Consolas, monospace; font-size: 8.6pt;
       background: #f1f5f9; padding: 1pt 3pt; border-radius: 2pt; color: #0f172a; }
pre { background: #0f172a; color: #e2e8f0; padding: 9pt 11pt; border-radius: 4pt;
      overflow-x: auto; page-break-inside: avoid; margin: 0 0 10pt; }
pre code { background: none; color: inherit; font-size: 8.2pt; line-height: 1.45; padding: 0; }
blockquote { margin: 10pt 0; padding: 8pt 12pt; background: #f0fdfa;
             border-left: 3pt solid #0f766e; page-break-inside: avoid; }
blockquote p { margin: 0; font-size: 10.4pt; }
blockquote p + p { margin-top: 6pt; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 12pt; font-size: 8.9pt;
        page-break-inside: auto; }
tr { page-break-inside: avoid; }
thead { display: table-header-group; }
th { background: #0f172a; color: #fff; text-align: left; padding: 5pt 7pt;
     font-weight: 600; font-size: 8.6pt; }
td { padding: 5pt 7pt; border-bottom: 0.5pt solid #e2e8f0; vertical-align: top; }
tr:nth-child(even) td { background: #f8fafc; }
hr { border: 0; border-top: 0.5pt solid #cbd5e1; margin: 16pt 0; }
a { color: #0f766e; text-decoration: none; }
h2, h3 { page-break-after: avoid; }
"""

html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>{src.stem}</title><style>{CSS}</style></head><body>{body_html}</body></html>"""

tmp_html = out.with_suffix(".render.html")
tmp_html.write_text(html, encoding="utf-8")
subprocess.run([
    CHROME, "--headless", "--disable-gpu",
    "--no-sandbox", "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
    f"--print-to-pdf={out}", tmp_html.as_uri(),
], check=True, capture_output=True)
tmp_html.unlink()
print(f"{out} — {out.stat().st_size/1024:.0f} KB")
