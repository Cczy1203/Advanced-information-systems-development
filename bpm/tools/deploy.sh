#!/usr/bin/env bash
# Deploy the model and every Camunda Form to a Camunda 8 cluster.
#
# Camunda 8 keeps a copy of the whole BPMN resource inside each process
# definition record, so the model and its forms have to go up in the same
# deployment. The default 4 MB append batch is what limits how large a single
# collaboration can get - see the README.
#
# Usage:  ./deploy.sh [base-url]        (default http://localhost:8080)
set -euo pipefail

BASE="${1:-http://localhost:8080}"
HERE="$(cd "$(dirname "$0")" && pwd)"
MODEL_DIR="$HERE/../model"
# Second argument (or $BPMN) overrides the file, which is how the short-timer
# demonstration variant in model/demo/ is deployed.
BPMN="${BPMN:-$MODEL_DIR/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn}"

args=()
for f in "$MODEL_DIR"/forms/*.form; do
  args+=(-F "resources=@$f;type=application/json")
done
args+=(-F "resources=@$BPMN;type=application/xml")

echo "Deploying $(ls "$MODEL_DIR"/forms/*.form | wc -l | tr -d ' ') forms and one BPMN to $BASE ..."
curl -sS -X POST "$BASE/v2/deployments" "${args[@]}" \
  | python3 -c '
import json, sys
d = json.load(sys.stdin)
if "detail" in d:
    print("DEPLOY FAILED")
    print(d["detail"])
    sys.exit(1)
print("deployment key:", d["deploymentKey"])
for item in d["deployments"]:
    p = item.get("processDefinition")
    f = item.get("form")
    if p:
        print("  process  %-32s v%s" % (p["processDefinitionId"], p["processDefinitionVersion"]))
    elif f:
        print("  form     %-32s v%s" % (f["formId"], f["version"]))
'
