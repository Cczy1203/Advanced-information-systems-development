#!/usr/bin/env python3
"""Write a deployable file containing only the six outside participants.

Why this exists. The collaboration is one file and one diagram, but a Camunda 8
deployment stores the whole BPMN resource inside every process definition record,
so the deployment of the full model is bounded by the append batch. Measured
against c8run 8.10.0-alpha5 with all fifteen processes executable:

    Can't append entry: ... valueType=PROCESS ... with size: 405002 this would
    exceed the maximum batch size. [ currentBatchEntryCount: 24,
    currentBatchSize: 4095764 ]

Nine process records fit; the tenth is rejected. The shipped model therefore sets
EXTERNAL_PROCESSES_EXECUTABLE = False in spec_v2.py, which draws all six outside
participants but deploys only the nine hospital processes.

This script is the second way out of the same ceiling: it emits the six outside
participants on their own, so they can be deployed as a second batch while the
collaboration stays one file and one diagram. It is generated from the same spec
as the shipped model, so the two cannot drift.

    python3 tools/build_external_participants.py
    curl -sS -X POST http://localhost:8080/v2/deployments \
         -F "resources=@model/UFCEP6-0-3_Hospital_Patient_Pathway_v14_external-participants.bpmn;type=application/xml"
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from bpmn_builder_v2 import V2Builder      # noqa: E402
import spec_v2                             # noqa: E402

OUT = "UFCEP6-0-3_Hospital_Patient_Pathway_v14_external-participants.bpmn"


def main():
    full = spec_v2.build()

    ext = V2Builder()
    ext.collaboration_id = "Collaboration_ExternalParticipants"
    ext.definitions_id = "Definitions_external_participants"

    for pool in full.pools:
        if not getattr(pool, "external", False):
            continue
        # this file exists precisely to deploy them
        pool.executable = True
        pool.documentation = (
            (pool.documentation + " " if pool.documentation else "")
            + "Deployed on its own so that the fifteen-process collaboration stays "
              "inside the Camunda 8 append batch; the hospital processes are "
              "deployed from the main model file.")
        ext.pools.append(pool)

    # only the messages these processes actually use, or the file would carry
    # every message in the collaboration and deploy subscriptions it never uses
    for pool in ext.pools:
        for node in pool.nodes.values():
            name = node.opts.get("msg")
            if name:
                ext.messages[name] = full.messages.get(name)

    problems = ext.validate()
    if problems:
        print("check failed:")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)

    xml = ext.to_xml()
    dest = os.path.join(ROOT, "model", OUT)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(xml)

    size = os.path.getsize(dest)
    print("%s" % OUT)
    print("  pools %d | nodes %d | flows %d | messages %d | %d bytes"
          % (len(ext.pools), sum(len(p.nodes) for p in ext.pools),
             sum(len(p.flows) for p in ext.pools), len(ext.messages), size))
    for pool in ext.pools:
        print("  %-28s %s" % (pool.process_id, pool.name))


if __name__ == "__main__":
    main()
