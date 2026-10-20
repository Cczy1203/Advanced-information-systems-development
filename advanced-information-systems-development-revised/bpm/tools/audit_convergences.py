#!/usr/bin/env python3
"""Can any node in the model receive two tokens at once?

An uncontrolled merge - two sequence flows into one activity, with no merging
gateway between them - is legal BPMN and is what this model does 24 times. Whether
it is *safe* depends on something the count alone cannot tell you: can the two
incoming flows ever carry a token at the same time?

* If both come from different branches of the **same inclusive or parallel fork**,
  they can, and the activity fires once per token. For a service task that sends a
  letter, that is a duplicate letter.
* If one of them is a **loop-back** edge, they cannot: the token that comes round
  again can only do so after the activity has completed. Arrival is sequential.
* If both come from the **same exclusive fork**, or from a linear stretch, only one
  token exists by construction.

This tool tells the three cases apart and **fails** if any merge is in the first
category, so adding a merge gateway is driven by a reason rather than by the count.

Note on the loop-back test: a node is treated as having a loop-back when it can
reach one of its own sources again, which is exactly the condition for the token to
come round a second time rather than arrive alongside the first.

    python3 tools/audit_convergences.py [model.bpmn]
"""
import collections
import os
import sys
import xml.etree.ElementTree as ET

B = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "..", "model",
                       "UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn")

SPLIT = {"inclusiveGateway": "OR", "parallelGateway": "AND", "exclusiveGateway": "XOR"}
# Elements that *do* something and therefore fire once per token. Gateways are not
# in this list on purpose: a converging inclusive or parallel gateway is the merge,
# so receiving two tokens is exactly what it is for, not a defect.
ACTIVITIES = ("task", "userTask", "serviceTask", "sendTask", "receiveTask", "manualTask",
              "scriptTask", "businessRuleTask", "callActivity", "subProcess",
              "intermediateThrowEvent", "intermediateCatchEvent", "endEvent")


def load(path):
    root = ET.parse(path).getroot()
    kind, name = {}, {}
    for element in root.iter():
        if "id" in element.attrib:
            kind[element.get("id")] = element.tag.replace(B, "")
            name[element.get("id")] = element.get("name") or ""
    flows = {}
    for flow in root.iter(B + "sequenceFlow"):
        flows[flow.get("id")] = (flow.get("sourceRef"), flow.get("targetRef"))
    return kind, name, flows


def analyse(kind, name, flows):
    outgoing = collections.defaultdict(list)
    incoming = collections.defaultdict(list)
    for fid, (source, target) in flows.items():
        outgoing[source].append(fid)
        incoming[target].append(fid)

    successors = collections.defaultdict(set)
    for source, target in flows.values():
        successors[source].add(target)

    def reaches(start, goal, seen=None):
        if start == goal:
            return True
        seen = seen if seen is not None else set()
        if start in seen:
            return False
        seen.add(start)
        return any(reaches(nxt, goal, seen) for nxt in successors[start])

    def converging_gateway(node):
        """A gateway that merges: more than one incoming flow, OR or AND."""
        return (kind.get(node) in ("inclusiveGateway", "parallelGateway")
                and len(incoming[node]) > 1)

    def reaches_within_branch(start, goal):
        """Can this branch deliver a token to `goal` *before* the branch rejoins?

        Plain reachability is the wrong question: once the two branches of a fork have
        merged at their join, one token flows on from the join, and everything
        downstream is reachable from both branches without ever being double-fed.
        A branch therefore ends at the first converging inclusive or parallel gateway,
        which is its matching join.
        """
        queue, seen = [start], set()
        while queue:
            node = queue.pop(0)
            if node == goal:
                return True
            if node in seen:
                continue
            seen.add(node)
            if node != start and converging_gateway(node):
                continue  # the branch has rejoined; past here it is one token again
            queue.extend(flows[e][1] for e in outgoing.get(node, []))
        return False

    unsafe, sequential, exclusive = [], [], []
    for node, edges in incoming.items():
        if len(edges) < 2 or kind.get(node) not in ACTIVITIES:
            continue
        sources = [flows[e][0] for e in edges]

        # How many outgoing edges of one OR/AND fork can deliver a token here? Two or
        # more means the fork can put two tokens into this activity.
        fork_hits = collections.defaultdict(int)
        for gateway, gate_edges in list(outgoing.items()):
            if len(gate_edges) < 2 or kind.get(gateway) not in ("inclusiveGateway",
                                                                "parallelGateway"):
                continue
            hits = sum(1 for e in gate_edges if reaches_within_branch(flows[e][1], node))
            if hits >= 2:
                fork_hits[gateway] = hits

        loop_back = [s for s in sources if reaches(node, s)]

        # A genuine double-feed is unsafe even where there is also a loop-back: the
        # two conditions are independent, and a loop-back must not mask the first.
        if fork_hits:
            unsafe.append((node, list(fork_hits.items())))
        elif loop_back:
            sequential.append((node, loop_back))
        else:
            exclusive.append(node)
    return unsafe, sequential, exclusive


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    path = os.path.abspath(path)
    kind, name, flows = load(path)
    unsafe, sequential, exclusive = analyse(kind, name, flows)
    total = len(unsafe) + len(sequential) + len(exclusive)

    print("convergence audit: %s" % os.path.basename(path))
    print("  nodes with more than one incoming sequence flow: %d" % total)
    print()
    print("  %-62s %d" % ("safe: an incoming edge is a loop-back, so arrivals are"
                          " sequential", len(sequential)))
    for node, loop_back in sequential:
        print("      %-38s via %s" % (node, ", ".join(loop_back)))
    print()
    print("  %-62s %d" % ("safe: the sources share one exclusive fork, so one token"
                          " exists", len(exclusive)))
    for node in exclusive:
        print("      %s" % node)
    print()
    if unsafe:
        print("  UNSAFE: two branches of one inclusive/parallel fork rejoin with no"
              " merging gateway: %d" % len(unsafe))
        for node, hits in unsafe:
            for gateway, count in hits:
                print("      %s <- %d outgoing edge(s) of %s can reach it"
                      % (node, count, gateway))
        print()
        print("FAIL: an activity here would fire once per token")
        return 1

    print("  0 merges can double-fire: every convergence is either a return round a"
          " loop or a single exclusive branch")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
