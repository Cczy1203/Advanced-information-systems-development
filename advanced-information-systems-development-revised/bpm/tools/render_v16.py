#!/usr/bin/env python3
"""
Render a BPMN file with bpmn-js, the renderer inside Camunda Modeler.

    python3 tools/render_v16.py <file.bpmn> <output-stem> [--scale 1.0]

Writes <stem>.svg, <stem>.png, <stem>-overview.png and <stem>.pdf. The SVG comes
out of bpmn-js itself, so what the Modeler canvas shows is what is exported.

Chrome is used twice: once to run bpmn-js and hand back the SVG, once to
rasterise that SVG. The PDF is the same page printed with a paper size equal to
the drawing, which keeps the text as text.
"""

import base64
import json
import os
import re
import subprocess
import sys
import tempfile

BPMN_JS = "https://unpkg.com/bpmn-js@17.11.1/dist/bpmn-navigated-viewer.production.min.js"
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
]


def chrome():
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    raise SystemExit("no headless-capable browser found")


def run(argv, **kw):
    return subprocess.run(argv, capture_output=True, text=True, **kw)


def import_svg(bpmn_path, work):
    xml = open(bpmn_path, encoding="utf-8").read()
    html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<script src="%s"></script></head><body>
<div id="canvas" style="width:1200px;height:800px"></div><div id="out"></div><div id="err"></div>
<script>
var BPMN_XML = %s;
var Ctor = window.BpmnJS || window.BpmnNavigatedViewer || window.BpmnViewer;
var viewer = new Ctor({ container: '#canvas' });
viewer.importXML(BPMN_XML).then(function () { return viewer.saveSVG(); })
  .then(function (r) {
    document.getElementById('out').textContent =
      'BEGIN' + btoa(unescape(encodeURIComponent(r.svg))) + 'END';
  })
  .catch(function (e) {
    document.getElementById('err').textContent = 'FAILED ' + e.message;
  });
</script></body></html>
""" % (BPMN_JS, json.dumps(xml))
    path = os.path.join(work, "index.html")
    open(path, "w", encoding="utf-8").write(html)
    proc = run([chrome(), "--headless=new", "--disable-gpu", "--no-sandbox",
                "--allow-file-access-from-files", "--virtual-time-budget=120000",
                "--dump-dom", "file://" + path])
    dom = proc.stdout
    m = re.search(r"BEGIN([A-Za-z0-9+/=]+)END", dom)
    if not m:
        err = re.search(r"FAILED[^<]*", dom)
        raise SystemExit("bpmn-js could not import the model: "
                         + (err.group(0) if err else "unknown"))
    return base64.b64decode(m.group(1)).decode("utf-8")


def page_html(svg, w, h, scale=1.0):
    body = svg[svg.index("<svg"):]
    return ("<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
            "<style>@page{size:%dpx %dpx;margin:0}"
            "html,body{margin:0;padding:0;background:#fff;overflow:hidden}"
            "svg{display:block;width:%dpx;height:%dpx}</style></head><body>%s</body></html>"
            % (w, h, w, h, body))


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    bpmn_path, stem = argv[1], argv[2]
    scale = 1.0
    if "--scale" in argv:
        scale = float(argv[argv.index("--scale") + 1])

    work = tempfile.mkdtemp(prefix="render-v16-")
    svg = import_svg(bpmn_path, work)
    w = int(float(re.search(r'width="([\d.]+)"', svg).group(1)))
    h = int(float(re.search(r'height="([\d.]+)"', svg).group(1)))
    print("  SVG %d x %d" % (w, h))

    open(stem + ".svg", "w", encoding="utf-8").write(svg)

    full = os.path.join(work, "full.html")
    open(full, "w", encoding="utf-8").write(page_html(svg, w, h))

    if scale >= 1.0:
        run([chrome(), "--headless=new", "--disable-gpu", "--no-sandbox",
             "--hide-scrollbars", "--force-device-scale-factor=1",
             "--window-size=%d,%d" % (w, h), "--screenshot=" + stem + ".png",
             "file://" + full])
        shot = stem + ".png"
    else:
        sw, sh = int(w * scale), int(h * scale)
        open(full, "w", encoding="utf-8").write(page_html(svg, sw, sh))
        run([chrome(), "--headless=new", "--disable-gpu", "--no-sandbox",
             "--hide-scrollbars", "--force-device-scale-factor=1",
             "--window-size=%d,%d" % (sw, sh), "--screenshot=" + stem + ".png",
             "file://" + full])
        shot = stem + ".png"

    if os.path.exists(shot):
        print("  PNG %s (%.1f MB)" % (shot, os.path.getsize(shot) / 1e6))
        run(["sips", "-Z", "2400", shot, "--out", stem + "-overview.png"])

    run([chrome(), "--headless=new", "--disable-gpu", "--no-sandbox",
         "--no-pdf-header-footer", "--print-to-pdf=" + stem + ".pdf",
         "file://" + full])
    if os.path.exists(stem + ".pdf"):
        print("  PDF %s.pdf (%.1f MB)" % (stem, os.path.getsize(stem + ".pdf") / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
