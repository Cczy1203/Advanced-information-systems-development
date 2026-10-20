"""
Compact report of a bpmn-analysis-*.json file.

The JSON written by `analyse_bpmn.py` is large, so this script prints the parts
that need action as tables a person can read:
  * activities with several incoming sequence flows and no merging gateway
    (Use merging gateways)
  * exclusive/inclusive gateways whose outgoing flows have no conditionExpression
    (Add conditions to outgoing flows)
  * the candidateGroups / formId bindings of every user task (Role-based assignment)
  * the distribution of task types (Appropriate BPMN task types)

Usage
-----
    python report_bpmn.py tools/bpmn-analysis-v14.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    print("=" * 78)
    print(f"FILE            {data['file']}  ({data['bytes']:,} bytes)")
    print(f"PROCESSES       {data['processCount']}")
    print(f"PARTICIPANTS    {data['participantCount']}")
    print(f"FLOW NODES      {data['totalFlowNodes']}")
    print(f"SEQUENCE FLOWS  {data['totalSequenceFlows']}")
    print(f"MESSAGE FLOWS   {data['totalMessageFlows']}")
    print(f"LANES           {data['laneCount']}")
    print("ELEMENT COUNTS  " + json.dumps(data["elementCounts"]))
    print("=" * 78)

    print("\n### 1. converging flows without a merging gateway")
    rows = data["unmergedConvergingTasks"]
    print(f"count = {len(rows)}")
    for r in rows:
        srcs = ", ".join(f"{s['id']}({s['kind']})" for s in r["incomingFrom"])
        print(f"  - {r['elementId']:34s} {r['kind']:14s} in={r['incomingCount']}  <- {srcs}")
        print(f"      name={r['elementName']}  lane={r['lane']}")

    print("\n### 2. gateways with unconditioned outgoing flows")
    rows = [g for g in data["gatewayConditionFindings"]
            if g["outgoing"] > 1 and g["conditioned"] < g["outgoing"]
            and g["unconditionedFlows"] and not g["defaultFlow"]]
    print(f"count = {len(rows)}")
    for r in rows:
        print(f"  - {r['elementId']:34s} {r['kind']:18s} in={r['incoming']} out={r['outgoing']} "
              f"conditioned={r['conditioned']} default={r['defaultFlow']}")
        print(f"      missing on: {r['unconditionedFlows']}")
        print(f"      name={r['elementName']}  lane={r['lane']}")

    print("\n### 3. merging-only gateways")
    rows = [g for g in data["gatewayConditionFindings"] if g["isMergingOnly"]]
    print(f"count = {len(rows)}")
    for r in rows:
        print(f"  - {r['elementId']:34s} {r['kind']:18s} in={r['incoming']} out={r['outgoing']}")

    print("\n### 4. user task candidate groups and forms")
    uts = data["userTasks"]
    print(f"user tasks = {len(uts)}")
    print(f"  without formId          = {len(data['userTasksWithoutForm'])}")
    print(f"  without candidateGroups = {len(data['userTasksWithoutRole'])}")
    groups = Counter(g for t in uts for g in t["candidateGroups"])
    print("  candidateGroups in use:")
    for g, n in groups.most_common():
        print(f"      {n:3d}  {g}")

    print("\n### 5. task type counts per process")
    for pid, counts in data["taskTypeCounts"].items():
        print(f"  {pid:34s} {json.dumps(counts)}")

    print("\n### 6. empty lanes / elements with no diagram shape")
    print(f"  empty lanes                 = {len(data['emptyLanes'])}")
    print(f"  missing diagram shape       = {len(data['elementsMissingDiagramShape'])}")
    if data["elementsMissingDiagramShape"]:
        print("      " + ", ".join(data["elementsMissingDiagramShape"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
