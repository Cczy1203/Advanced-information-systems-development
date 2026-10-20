#!/usr/bin/env python3
"""
Write the v16.0 operational model.

    python3 tools/build_v3.py [output.bpmn]

Everything the model contains is declared in tools/spec_v3.py; this script only
writes it out and reports what it wrote.
"""

import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import spec_v3                                              # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, "model",
                           "UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn")


def main(argv):
    out = argv[1] if len(argv) > 1 else DEFAULT_OUT
    b = spec_v3.build()
    problems = b.validate()
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        return 2
    xml = b.to_xml()
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(xml)

    pool = b.pools[0]
    kinds = Counter(n.kind for n in pool.nodes.values())
    print("wrote %s" % out)
    print("  %d bytes" % len(xml))
    print("  pools        : %d (%d executable)"
          % (len(b.pools), sum(1 for p in b.pools if p.process_id)))
    print("  lanes        : %d leaf in %d responsibility lanes"
          % (len(pool.lanes), len(pool.lane_groups or [])))
    print("  flow nodes   : %d" % len([n for n in pool.nodes.values()
                                       if not n.is_boundary]))
    print("  boundary     : %d" % len([n for n in pool.nodes.values()
                                       if n.is_boundary]))
    print("  sequence     : %d" % len(pool.flows))
    print("  messages     : %d" % len(b.message_flows))
    print("  user tasks   : %d" % kinds["utask"])
    print("  service tasks: %d" % kinds["stask"])
    r = b.router
    print("  pool size    : %.0f x %.0f" % (pool.w, pool.h))
    right = max(p.x + p.w for p in b.pools)
    bottom = max(p.y + p.h for p in b.pools)
    print("  diagram      : %.0f x %.0f" % (right, bottom))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
