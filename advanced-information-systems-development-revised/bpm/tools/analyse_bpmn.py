"""
BPMN structural analyser.

Purpose
-------
Static structural analysis of `bpm/model/*.bpmn`, giving reproducible evidence
for three review comments: merging gateways, task types and gateway conditions.

1. Count participants, lanes and elements by type;
2. Find the places where several sequence flows lead into the same activity
   without a merging gateway
   (review comment: Use merging gateways where multiple paths lead into a task);
3. Find the distribution of task types such as serviceTask / sendTask /
   userTask / manualTask
   (review comment: Use appropriate BPMN task types);
4. Find exclusive/inclusive gateway branches whose outgoing flow has no
   conditionExpression
   (review comment: Add conditions to outgoing gateway flows);
5. List the candidateGroups / formDefinition bindings of every user task
   (review comment: Configure role-based task assignments).

Usage
-----
    python analyse_bpmn.py <model.bpmn> [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "zeebe": "http://camunda.org/schema/zeebe/1.0",
    "modeler": "http://camunda.org/schema/modeler/1.0",
}
B = "{%s}" % NS["bpmn"]
Z = "{%s}" % NS["zeebe"]

FLOW_NODE_TAGS = (
    "task", "userTask", "serviceTask", "sendTask", "receiveTask", "manualTask",
    "scriptTask", "businessRuleTask", "callActivity", "subProcess",
    "exclusiveGateway", "parallelGateway", "inclusiveGateway",
    "eventBasedGateway", "complexGateway",
    "startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent",
    "boundaryEvent",
)
GATEWAY_TAGS = ("exclusiveGateway", "parallelGateway", "inclusiveGateway",
                "eventBasedGateway", "complexGateway")


def local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def attr(el, name, default=None):
    return el.get(name, default)


def analyse(path: Path) -> dict:
    tree = ET.parse(path)
    root = tree.getroot()

    processes = {}
    for proc in root.iter(B + "process"):
        processes[attr(proc, "id")] = proc

    collaborations = list(root.iter(B + "collaboration"))

    # ---------------------------------------------------------------- participants
    participants = []
    for collab in collaborations:
        for part in collab.findall(B + "participant"):
            participants.append({
                "id": attr(part, "id"),
                "name": attr(part, "name"),
                "processRef": attr(part, "processRef"),
            })

    # ---------------------------------------------------------------- node census
    node_kind = {}          # elementId -> local tag
    node_name = {}          # elementId -> name
    node_process = {}       # elementId -> process id
    node_lane = {}          # elementId -> lane name
    lane_of_process = defaultdict(list)

    for pid, proc in processes.items():
        for child in proc.iter():
            tag = local(child.tag)
            if tag in FLOW_NODE_TAGS:
                eid = attr(child, "id")
                if eid:
                    node_kind[eid] = tag
                    node_name[eid] = attr(child, "name", "")
                    node_process[eid] = pid
        for lane_set in proc.findall(B + "laneSet"):
            for lane in lane_set.findall(B + "lane"):
                lane_name = attr(lane, "name", "")
                lane_of_process[pid].append(lane_name)
                for ref in lane.findall(B + "flowNodeRef"):
                    if ref.text:
                        node_lane[ref.text.strip()] = lane_name

    kinds = Counter(node_kind.values())

    # ---------------------------------------------------------------- sequence flows
    incoming = defaultdict(list)   # targetId -> [flow]
    outgoing = defaultdict(list)   # sourceId -> [flow]
    flows = {}
    for pid, proc in processes.items():
        for sf in proc.findall(B + "sequenceFlow"):
            fid = attr(sf, "id")
            src = attr(sf, "sourceRef")
            tgt = attr(sf, "targetRef")
            cond_el = sf.find(B + "conditionExpression")
            cond = None
            if cond_el is not None:
                cond = "".join(cond_el.itertext()).strip()
            flows[fid] = {
                "id": fid, "source": src, "target": tgt, "name": attr(sf, "name"),
                "condition": cond, "process": pid,
            }
            outgoing[src].append(flows[fid])
            incoming[tgt].append(flows[fid])

    # ------------------------------------------- 1. unmerged converging paths
    # A "task" that receives >1 sequence flow and is not preceded by a merging gateway.
    merging_findings = []
    for eid, kind in node_kind.items():
        if kind not in ("task", "userTask", "serviceTask", "sendTask", "receiveTask",
                        "manualTask", "scriptTask", "businessRuleTask", "callActivity",
                        "subProcess"):
            continue
        ins = incoming.get(eid, [])
        if len(ins) < 2:
            continue
        sources = sorted({f["source"] for f in ins})
        source_kinds = {node_kind.get(s, "?") for s in sources}
        # If every distinct source is the SAME gateway, the gateway is already the merge point.
        if len(sources) == 1 and next(iter(source_kinds)) in GATEWAY_TAGS:
            continue
        merging_findings.append({
            "elementId": eid,
            "elementName": node_name.get(eid),
            "kind": kind,
            "lane": node_lane.get(eid),
            "incomingCount": len(ins),
            "incomingFrom": [{"id": s, "kind": node_kind.get(s), "name": node_name.get(s),
                              "lane": node_lane.get(s)} for s in sources],
        })

    # ------------------------------------------- 2. tasks with >1 outgoing flow, no split gateway
    split_findings = []
    for eid, kind in node_kind.items():
        if kind not in ("task", "userTask", "serviceTask", "sendTask", "receiveTask",
                        "manualTask", "scriptTask", "businessRuleTask", "callActivity"):
            continue
        outs = outgoing.get(eid, [])
        if len(outs) > 1:
            split_findings.append({
                "elementId": eid, "elementName": node_name.get(eid), "kind": kind,
                "outgoingCount": len(outs),
                "withCondition": sum(1 for f in outs if f["condition"]),
            })

    # ------------------------------------------- 3. gateway outgoing conditions
    gateway_default = {}
    for pid, proc in processes.items():
        for tag in GATEWAY_TAGS:
            for g in proc.iter(B + tag):
                gateway_default[attr(g, "id")] = attr(g, "default")

    gateway_conditions = []
    for eid, kind in node_kind.items():
        if kind not in GATEWAY_TAGS:
            continue
        outs = outgoing.get(eid, [])
        conds = [bool(f["condition"]) for f in outs]
        if kind in ("exclusiveGateway", "inclusiveGateway") and len(outs) > 1:
            gateway_conditions.append({
                "elementId": eid, "elementName": node_name.get(eid), "kind": kind,
                "lane": node_lane.get(eid),
                "incoming": len(incoming.get(eid, [])),
                "outgoing": len(outs),
                "conditioned": sum(conds),
                "unconditionedFlows": [f["id"] for f, c in zip(outs, conds) if not c],
                "defaultFlow": gateway_default.get(eid),
                "isMergingOnly": len(incoming.get(eid, [])) > 1 and len(outs) <= 1,
            })

    # ------------------------------------------- 4. user task role / form bindings
    # NOTE: <zeebe:assignmentDefinition> and <zeebe:formDefinition> are nested inside
    # <bpmn:extensionElements>, so they must be searched with .// (descendants), not find().
    user_tasks = []
    for pid, proc in processes.items():
        for ut in proc.iter(B + "userTask"):
            eid = attr(ut, "id")
            groups = []
            users = []
            for ad in ut.iter(Z + "assignmentDefinition"):
                if attr(ad, "candidateGroups"):
                    groups.append(attr(ad, "candidateGroups").strip())
                if attr(ad, "candidateUsers"):
                    users.append(attr(ad, "candidateUsers").strip())
                if attr(ad, "assignee"):
                    groups.append("assignee:" + attr(ad, "assignee").strip())
            form = None
            for fd in ut.iter(Z + "formDefinition"):
                form = attr(fd, "formId")
            task_def = None
            for td in ut.iter(Z + "taskDefinition"):
                task_def = attr(td, "type")
            user_tasks.append({
                "elementId": eid,
                "name": node_name.get(eid),
                "lane": node_lane.get(eid),
                "candidateGroups": groups,
                "candidateUsers": users,
                "formId": form,
                "taskDefinitionType": task_def,
                "process": pid,
            })

    # ------------------------------------------- 5. service/send task types
    task_types = defaultdict(Counter)
    for pid, proc in processes.items():
        for tag in ("serviceTask", "sendTask", "receiveTask", "manualTask",
                    "businessRuleTask", "scriptTask"):
            for el in proc.iter(B + tag):
                task_types[pid][tag] += 1

    # ------------------------------------------- 6. message flows
    message_flows = []
    for collab in collaborations:
        for mf in collab.findall(B + "messageFlow"):
            message_flows.append({
                "id": attr(mf, "id"), "name": attr(mf, "name"),
                "source": attr(mf, "sourceRef"), "target": attr(mf, "targetRef"),
            })

    # ------------------------------------------- 7. lanes without any flow node
    empty_lanes = []
    lane_nodes = Counter()
    for eid, lane in node_lane.items():
        lane_nodes[lane] += 1
    for pid, names in lane_of_process.items():
        for name in names:
            if lane_nodes.get(name, 0) == 0:
                empty_lanes.append({"process": pid, "lane": name})

    # ------------------------------------------- 8. elements with no DI shape
    di_shapes = set()
    for shape in root.iter("{%s}BPMNShape" % NS["bpmndi"]):
        ref = attr(shape, "bpmnElement")
        if ref:
            di_shapes.add(ref)
    missing_di = sorted(eid for eid in node_kind if eid not in di_shapes)

    return {
        "file": str(path),
        "bytes": path.stat().st_size,
        "processCount": len(processes),
        "participantCount": len(participants),
        "participants": participants,
        "elementCounts": dict(sorted(kinds.items())),
        "totalFlowNodes": len(node_kind),
        "totalSequenceFlows": len(flows),
        "totalMessageFlows": len(message_flows),
        "laneCount": len({v for v in node_lane.values()}),
        "unmergedConvergingTasks": merging_findings,
        "tasksWithMultipleOutgoing": split_findings,
        "gatewayConditionFindings": gateway_conditions,
        "userTasks": user_tasks,
        "userTasksWithoutForm": [t for t in user_tasks if not t["formId"]],
        "userTasksWithoutRole": [t for t in user_tasks if not t["candidateGroups"]],
        "taskTypeCounts": {pid: dict(c) for pid, c in task_types.items()},
        "emptyLanes": empty_lanes,
        "elementsMissingDiagramShape": missing_di,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="BPMN structural analyser")
    ap.add_argument("model")
    ap.add_argument("--json")
    args = ap.parse_args()
    path = Path(args.model)
    if not path.is_file():
        print(f"not a file: {path}", file=sys.stderr)
        return 2
    result = analyse(path)
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("participants", "userTasks", "gatewayConditionFindings",
                                   "unmergedConvergingTasks", "taskTypeCounts")},
                     indent=2, ensure_ascii=False))
    print(f"\nunmerged converging tasks: {len(result['unmergedConvergingTasks'])}")
    print(f"user tasks: {len(result['userTasks'])}, without form: {len(result['userTasksWithoutForm'])},"
          f" without role: {len(result['userTasksWithoutRole'])}")
    print(f"gateway condition findings: {len(result['gatewayConditionFindings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
