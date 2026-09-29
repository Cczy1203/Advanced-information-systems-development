#!/usr/bin/env bash
# Render the BPMN to SVG and PNG.
#
# Uses bpmn-js (the rendering engine inside Camunda Modeler) in headless Chrome,
# so the export matches what the Modeler canvas shows. Chrome is used twice:
# once to run bpmn-js and hand back the SVG, once to rasterise it.
#
# Usage:  ./render_diagram.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
BPMN="$ROOT/model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn"
OUT="$ROOT/diagram"
WORK="${TMPDIR:-/tmp}/ufcep603-render"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
if [ ! -x "$CHROME" ]; then
  for candidate in "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
                   "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
                   "/Applications/Chromium.app/Contents/MacOS/Chromium"; do
    [ -x "$candidate" ] && CHROME="$candidate" && break
  done
fi
BPMN_JS="https://unpkg.com/bpmn-js@17.11.1/dist/bpmn-navigated-viewer.production.min.js"

mkdir -p "$WORK" "$OUT"

echo "1/3  importing the model with bpmn-js ..."
python3 - "$BPMN" "$WORK" "$BPMN_JS" <<'PY'
import json, sys
bpmn, work, cdn = sys.argv[1], sys.argv[2], sys.argv[3]
xml = open(bpmn, encoding="utf-8").read()
html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<script src="%s"></script></head><body>
<div id="canvas" style="width:1200px;height:800px"></div><div id="out"></div><div id="err"></div>
<script>
var BPMN_XML = %s;
var Ctor = window.BpmnJS || window.BpmnNavigatedViewer || window.BpmnViewer;
var viewer = new Ctor({ container: '#canvas' });
viewer.importXML(BPMN_XML).then(function () { return viewer.saveSVG(); })
  .then(function (r) {
    document.getElementById('out').textContent = 'BEGIN' + btoa(unescape(encodeURIComponent(r.svg))) + 'END';
  })
  .catch(function (e) { document.getElementById('err').textContent = 'FAILED ' + e.message; });
</script></body></html>
""" % (cdn, json.dumps(xml))
open(work + "/index.html", "w", encoding="utf-8").write(html)
PY

"$CHROME" --headless=new --disable-gpu --no-sandbox --allow-file-access-from-files \
  --virtual-time-budget=60000 --dump-dom "file://$WORK/index.html" > "$WORK/dom.html" 2>/dev/null

python3 - "$WORK" "$OUT" <<'PY'
import base64, re, sys
work, out = sys.argv[1], sys.argv[2]
dom = open(work + "/dom.html", encoding="utf-8", errors="replace").read()
m = re.search(r"BEGIN([A-Za-z0-9+/=]+)END", dom)
if not m:
    err = re.search(r"FAILED[^<]*", dom)
    raise SystemExit("bpmn-js could not import the model: " + (err.group(0) if err else "unknown"))
svg = base64.b64decode(m.group(1)).decode("utf-8")
open(out + "/hospital-patient-pathway-v14.svg", "w", encoding="utf-8").write(svg)
body = svg[svg.index("<svg"):]
open(work + "/full.html", "w", encoding="utf-8").write(
    '<!DOCTYPE html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;'
    "overflow:hidden}svg{display:block}</style></head><body>" + body + "</body></html>")
w = int(float(re.search(r'width="([\d.]+)"', svg).group(1)))
h = int(float(re.search(r'height="([\d.]+)"', svg).group(1)))
open(work + "/size.txt", "w").write("%d %d\n" % (w, h))
print("     SVG %d x %d" % (w, h))
PY

read -r W H < "$WORK/size.txt"
echo "2/3  rasterising to PNG ..."
"$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars --force-device-scale-factor=1 \
  --window-size="$W,$H" --screenshot="$OUT/hospital-patient-pathway-v14.png" \
  "file://$WORK/full.html" 2>/dev/null

echo "3/3  writing a scaled overview ..."
sips -Z 2400 "$OUT/hospital-patient-pathway-v14.png" --out "$OUT/hospital-patient-pathway-v14-overview.png" >/dev/null

echo "done:"
ls -la "$OUT"/hospital-patient-pathway-v14.* | awk '{print "     " $5 " bytes  " $9}'
