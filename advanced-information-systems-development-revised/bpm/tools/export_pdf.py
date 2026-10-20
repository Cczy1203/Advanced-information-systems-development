#!/usr/bin/env python3
"""Export the diagram and the markdown documents to PDF.

Headless Chrome does both jobs. It renders the SVG as vector rather than
rasterising it, and it is the same renderer the PNG and the section crops are
produced with, so the PDF, the PNG and the SVG show the same drawing.

    python3 tools/export_pdf.py             # everything
    python3 tools/export_pdf.py --diagram   # both diagram PDFs
    python3 tools/export_pdf.py --full      # the whole drawing on one page
    python3 tools/export_pdf.py --sections  # the overview and one pool per page
    python3 tools/export_pdf.py --docs      # the documents

The diagram is rendered by its own two scripts, because the drawing has to come
out of bpmn-js and the sections are cut from the render; this file only calls
them so that one command still produces everything.

    python3 tools/render_v16.py <model.bpmn> diagram/hospital-patient-pathway-v16
    python3 tools/render_sections_v16.py <full.png> <sections.pdf>

Outputs
    diagram/hospital-patient-pathway-v16.pdf           full drawing, one page
    diagram/hospital-patient-pathway-v16-sections.pdf  one stage of the pathway per page
    docs/pdf/*.pdf                                     the documents, A4 landscape
"""

from __future__ import annotations

import html
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE = Path(tempfile.gettempdir()) / "chrome-pdf-profile"

# Documents worth a PDF: the ones a reader is handed rather than the working notes.
DOCS = [
    "04-modelling-decisions.md",
    "17-single-pool-operational-model.md",
    "18-cited-files-no-longer-present.md",
    "19-standups.md",
    "20-accessibility-and-the-forms.md",
    "21-date-rules-and-the-form-layer.md",
    "07-product-backlog.md",
    "08-test-plan.md",
    "09-risk-contingency-and-config-management.md",
    "10-sprint-reviews-and-feedback.md",
    "11-white-box-external-participants.md",
]

PAGE = """
@page {{ size: {size}; margin: {margin}; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 0; font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; }}
"""


def chrome_print(body: str, css: str, out: Path, *, timeout: float = 300.0) -> None:
    """Render `body` under `css` through headless Chrome and write a PDF.

    Chrome writes the file but does not reliably exit afterwards on these
    pages, so the output file is polled and the process is stopped once the
    file has stopped growing, instead of waiting on the process.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{css}</style></head>
<body>{body}</body></html>"""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "page.html"
        src.write_text(page, encoding="utf-8")
        proc = subprocess.Popen(
            [
                CHROME,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                f"--user-data-dir={PROFILE}",
                "--no-pdf-header-footer",
                "--virtual-time-budget=15000",
                f"--print-to-pdf={out}",
                src.as_uri(),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + timeout
        last_size, stable, written = -1, 0, False
        while time.time() < deadline:
            if out.exists():
                size = out.stat().st_size
                if size > 0 and size == last_size:
                    stable += 1
                    if stable >= 4:  # unchanged across four polls: done
                        written = True
                        break
                else:
                    stable = 0
                last_size = size
            if proc.poll() is not None:
                written = out.exists() and out.stat().st_size > 0
                break
            time.sleep(0.4)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
    if not written:
        raise SystemExit(f"Chrome produced no output for {out.name}")
    print(f"  {out.relative_to(ROOT)}  ({out.stat().st_size / 1024:.0f} KB)")


# --------------------------------------------------------------------------- diagram


def strip_svg_declaration(svg: str) -> str:
    """Drop the XML prolog and the doctype so the SVG can be inlined in HTML."""
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    svg = re.sub(r"<!DOCTYPE[^>]*>", "", svg)
    return svg.strip()


def svg_size(svg: str) -> tuple[float, float]:
    m = re.search(r'<svg[^>]*?width="([\d.]+)"[^>]*?height="([\d.]+)"', svg)
    if not m:
        raise SystemExit("cannot read the width and height off the SVG")
    return float(m.group(1)), float(m.group(2))


def _delegate(script: str, *args: str) -> None:
    """Run one of the diagram scripts, so there is still a single entry point."""
    cmd = [sys.executable, str(Path(__file__).resolve().parent / script), *args]
    print("   ", " ".join(cmd))
    subprocess.run(cmd, check=True)


def build_full_diagram() -> None:
    """The whole drawing on one page, at its own aspect ratio.

    Vector, so the page can be zoomed to any level without softening. The drawing
    itself comes out of bpmn-js in render_v16.py, which also writes the SVG and
    the PNG beside it, so all three show the same picture.
    """
    _delegate("render_v16.py",
              str(ROOT / "model" / "UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn"),
              str(ROOT / "diagram" / "hospital-patient-pathway-v16"))


def build_sections() -> None:
    """The readable version: one stage of the pathway per page, captioned.

    A single pool 17,500 px wide cannot be read at any zoom that also fits a
    screen, so the sections carry the same drawing at a size where the text is
    legible.
    """
    _delegate("render_sections_v16.py",
              str(ROOT / "diagram" / "hospital-patient-pathway-v16.png"),
              str(ROOT / "diagram" / "hospital-patient-pathway-v16-sections.pdf"))


# ----------------------------------------------------------------------- markdown


def inline(text: str) -> str:
    """Bold, italic, code and links, with the HTML escaped first."""
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        r'<a href="\2">\1</a>',
        text,
    )
    return text


def table_block(lines: list[str]) -> str:
    """A pipe table. The first row is the header, the second the alignment row."""
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    if len(rows) < 2:
        return ""
    head, body = rows[0], rows[2:]
    out = ["<table><thead><tr>"]
    out += [f"<th>{inline(c)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>")
        out += [f"<td>{inline(c)}</td>" for c in row]
        out.append("</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def markdown_to_html(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # fenced code
        if line.lstrip().startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].lstrip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            out.append(f"<pre>{html.escape(chr(10).join(block))}</pre>")
            continue

        # tables
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(
            r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]
        ):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            out.append(table_block(block))
            continue

        # headings
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # horizontal rule
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
            out.append("<hr>")
            i += 1
            continue

        # blockquote
        if line.lstrip().startswith(">"):
            block = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                block.append(lines[i].lstrip()[1:].strip())
                i += 1
            out.append(
                "<blockquote>" + markdown_to_html("\n".join(block)) + "</blockquote>"
            )
            continue

        # lists
        if re.match(r"^\s*([-*+]|\d+\.)\s+", line):
            ordered = bool(re.match(r"^\s*\d+\.\s+", line))
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines) and re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i]):
                item = re.sub(r"^\s*([-*+]|\d+\.)\s+", "", lines[i])
                # a wrapped continuation line belongs to the item
                i += 1
                while (
                    i < len(lines)
                    and lines[i].strip()
                    and not re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i])
                    and not re.match(r"^\s*(#{1,6}\s|\||```|>)", lines[i])
                ):
                    item += " " + lines[i].strip()
                    i += 1
                items.append(f"<li>{inline(item)}</li>")
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue

        # blank
        if not line.strip():
            i += 1
            continue

        # paragraph
        para = [line]
        i += 1
        while (
            i < len(lines)
            and lines[i].strip()
            and not re.match(r"^\s*(#{1,6}\s|\||```|>|[-*+]\s|\d+\.\s)", lines[i])
            and not re.match(r"^\s*(-{3,}|\*{3,})\s*$", lines[i])
        ):
            para.append(lines[i])
            i += 1
        out.append(f"<p>{inline(' '.join(x.strip() for x in para))}</p>")

    return "".join(out)


DOC_CSS = PAGE.format(size="A4 landscape", margin="14mm") + """
body { font-size: 9.5pt; line-height: 1.45; color: #111; }
h1 { font-size: 17pt; border-bottom: 2px solid #1f3b73; padding-bottom: 2mm; margin: 0 0 5mm; }
h2 { font-size: 13pt; margin: 7mm 0 3mm; color: #1f3b73; page-break-after: avoid; }
h3 { font-size: 11pt; margin: 6mm 0 2mm; page-break-after: avoid; }
h4 { font-size: 10pt; margin: 5mm 0 2mm; page-break-after: avoid; }
p, li { margin: 0 0 2.2mm; }
ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
hr { border: 0; border-top: 1px solid #ccc; margin: 6mm 0; }
code { font-family: "SF Mono", Menlo, monospace; font-size: 8.5pt;
       background: #f2f3f5; padding: 0.3mm 1mm; border-radius: 2px; }
pre { font-family: "SF Mono", Menlo, monospace; font-size: 8pt; background: #f6f7f9;
      border: 1px solid #e2e4e8; border-radius: 3px; padding: 2.5mm;
      white-space: pre-wrap; page-break-inside: avoid; }
blockquote { margin: 3mm 0; padding: 2mm 4mm; border-left: 3px solid #b9c2d6;
             background: #f7f9fc; color: #333; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; font-size: 7.8pt;
        page-break-inside: auto; }
th, td { border: 1px solid #ccd1da; padding: 1.3mm 1.8mm; text-align: left;
         vertical-align: top; }
th { background: #e9edf5; font-weight: 600; }
tr { page-break-inside: avoid; }
a { color: #1f3b73; text-decoration: none; word-break: break-all; }
"""


def build_docs() -> None:
    out_dir = ROOT / "docs" / "pdf"
    for name in DOCS:
        src = ROOT / "docs" / name
        if not src.exists():
            print(f"  skip {name} (not present)")
            continue
        body = markdown_to_html(src.read_text(encoding="utf-8"))
        chrome_print(body, DOC_CSS, out_dir / name.replace(".md", ".pdf"))


def main() -> None:
    args = sys.argv[1:]
    everything = not args
    do_full = everything or "--full" in args or "--diagram" in args
    do_sections = everything or "--sections" in args or "--diagram" in args
    do_docs = everything or "--docs" in args
    if not Path(CHROME).exists():
        raise SystemExit(f"headless Chrome not found at {CHROME}")
    if do_full:
        print("full drawing:")
        build_full_diagram()
    if do_sections:
        print("one pool per page:")
        build_sections()
    if do_docs:
        print("documents:")
        build_docs()


if __name__ == "__main__":
    main()
