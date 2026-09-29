#!/usr/bin/env python3
"""Render one PNG per pool from the exported SVG, so each band of the
collaboration can be read at full size without zooming into a 5475 x 14480
overview. Run after render_diagram.sh."""

import os
import re
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL = os.path.join(ROOT, "model", "UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn")
SVG = os.path.join(ROOT, "diagram", "hospital-patient-pathway-v14.svg")
DEST = os.path.join(ROOT, "diagram", "sections")
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
if not os.path.exists(CHROME):
    for candidate in ("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                      "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                      "/Applications/Chromium.app/Contents/MacOS/Chromium"):
        if os.path.exists(candidate):
            CHROME = candidate
            break


def main():
    os.makedirs(DEST, exist_ok=True)
    os.makedirs("/tmp/render", exist_ok=True)
    # The pool order is optimised for message-flow travel and can change between
    # releases, which renumbers the files. Clear the folder first so a stale
    # section from an earlier ordering cannot be left behind beside the new ones.
    for stale in os.listdir(DEST):
        if stale.endswith(".png"):
            os.remove(os.path.join(DEST, stale))
    bpmn = open(MODEL, encoding="utf-8").read()
    svg = open(SVG, encoding="utf-8").read()
    body = svg[svg.index("<svg"):]

    pools = []
    for m in re.finditer(
            r'<bpmndi:BPMNShape id="(P_\w+)_di" bpmnElement="P_\w+" isHorizontal="true">\s*'
            r'<dc:Bounds x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', bpmn):
        nm = re.search(r'<bpmn:participant id="%s" name="([^"]+)"' % m.group(1), bpmn)
        pools.append((m.group(1), nm.group(1) if nm else m.group(1),
                      int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))))

    for idx, (pid, name, x, y, w, h) in enumerate(pools, 1):
        W, H = w + 50, h + 50
        b2 = re.sub(r'viewBox="[^"]+"', 'viewBox="%d %d %d %d"' % (x - 25, y - 25, W, H), body, count=1)
        b2 = re.sub(r'width="[\d.]+" height="[\d.]+"', 'width="%d" height="%d"' % (W, H), b2, count=1)
        html = ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>html,body{margin:0;'
                'padding:0;overflow:hidden}svg{display:block}</style></head><body>' + b2 + "</body></html>")
        open("/tmp/render/sec.html", "w", encoding="utf-8").write(html)
        safe = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
        out = os.path.join(DEST, "%02d_%s.png" % (idx, safe))
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                        "--force-device-scale-factor=1.4", "--window-size=%d,%d" % (W, H),
                        "--screenshot=%s" % out, "file:///tmp/render/sec.html"], capture_output=True)
        print("  %-46s %5dx%-6d %s" % (name[:45], W, H, os.path.basename(out)), flush=True)

    print("done: %d section images in %s" % (len(pools), DEST))


if __name__ == "__main__":
    main()
