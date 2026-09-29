#!/usr/bin/env python3
"""Generate the v2.0 BPMN and every Camunda Form."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

# forms_spec must be imported before spec_v2: spec_v2 puts the v1.0 tools
# directory on sys.path to port the model, and that directory also holds a
# forms_spec.py. Importing this one first keeps the v2.0 forms.
from forms_spec import FORMS, FORM_VERSION
import spec_v2

BPMN = "UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn"

def user_tasks(b):
    used = {}
    for pool in b.pools:
        for n in pool.nodes.values():
            if n.kind == "utask":
                used.setdefault(n.opts.get("form"), []).append(pool.name)
            if n.kind == "subprocess":
                for (_id, _k, _n, kopts) in n.opts.get("inner", []):
                    if _k == "utask":
                        used.setdefault(kopts.get("form"), []).append(pool.name + " (in subprocess)")
    return used

def check_cells(b):
    """Two elements on one grid cell draw on top of each other."""
    problems = []
    for pool in b.pools:
        seen = {}
        for n in pool.nodes.values():
            if n.is_boundary:
                continue
            key = (n.lane, n.row, n.col)
            if key in seen:
                problems.append("%s: %s and %s share cell %s"
                                % (pool.name, seen[key].id, n.id, key))
            seen[key] = n
    return problems


# Timers the demonstration cannot wait for. The shipped model keeps the real
# durations (a seven day letter target, a three day capacity retry); this variant
# shortens only the clock so those branches can be shown in a live run. It is a
# separate file and is never the deliverable.
DEMO_TIMERS = [("R/PT168H", "R/PT15S"), ("P3D", "PT15S"), ("P7D", "PT15S")]
DEMO_VARIANT = "UFCEP6-0-3_Hospital_Patient_Pathway_v14_demo-timers.bpmn"


def write_demo_timer_variant(xml):
    """Write the short-timer variant beside the model, for demonstrating only."""
    out = xml
    for real, demo in DEMO_TIMERS:
        out = out.replace(">%s<" % real, ">%s<" % demo)
    out = out.replace('id="Collaboration_HospitalPatientPathway"',
                      'id="Collaboration_HospitalPatientPathway_DemoTimers"', 1)
    dest = os.path.join(ROOT, "model", "demo")
    os.makedirs(dest, exist_ok=True)
    path = os.path.join(dest, DEMO_VARIANT)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(out)
    note = ("# Short-timer demonstration variant\n\n"
            "`%s` is the shipped model with three timers shortened so the\n"
            "branches that are gated on the clock can be shown in a live run:\n\n"
            "| timer | shipped | this variant |\n|---|---|---|\n"
            "| weekly correspondence review | `R/PT168H` | `R/PT15S` |\n"
            "| capacity retry wait | `P3D` | `PT15S` |\n"
            "| clinic letter overdue boundary | `P7D` | `PT15S` |\n\n"
            "Everything else is identical, including every process id, so the same\n"
            "forms, workers and demo script drive it. **This file is not the\n"
            "deliverable** - the shipped model keeps the real durations. It exists so\n"
            "the escalation ladder and the compensation handlers can be demonstrated\n"
            "rather than only asserted. See `docs/08-test-plan.md` DEF-20.\n") % DEMO_VARIANT
    with open(os.path.join(dest, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(note)


def main():
    b = spec_v2.build()
    used = user_tasks(b)
    problems = b.validate() + check_cells(b)
    for fid in used:
        if fid and fid not in FORMS:
            problems.append("form %s bound but not defined" % fid)
    for fid in FORMS:
        if fid not in used:
            problems.append("form %s defined but not bound" % fid)
    if problems:
        print("check failed:")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)
    xml = b.to_xml()
    os.makedirs(os.path.join(ROOT, "model", "forms"), exist_ok=True)

    # The shipped model is now maintained in Camunda Modeler and this generator
    # no longer reproduces it (it emits a 15-participant build). Refuse to write
    # over a file that has been edited by hand unless the caller insists.
    target = os.path.join(ROOT, "model", BPMN)
    if os.path.exists(target) and os.environ.get("FORCE_REBUILD") != "1":
        print("refusing to overwrite %s" % os.path.relpath(target, ROOT))
        print("  this generator produces the 15-participant spec build, which no")
        print("  longer matches the shipped model (edited in Camunda Modeler).")
        print("  set FORCE_REBUILD=1 to overwrite anyway.")
        raise SystemExit(2)

    with open(target, "w", encoding="utf-8") as fh:
        fh.write(xml)
    for fid, spec in FORMS.items():
        doc = {"components": spec["components"], "type": "default", "id": fid,
               "executionPlatform": "Camunda Cloud", "executionPlatformVersion": FORM_VERSION,
               "exporter": {"name": "Camunda Modeler", "version": "5.51.0"}, "schemaVersion": 19}
        if spec.get("description"):
            doc["description"] = spec["description"]
        with open(os.path.join(ROOT, "model", "forms", fid + ".form"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    write_demo_timer_variant(xml)

    r = b.router
    print("pools %d | nodes %d | flows %d | message flows %d | forms %d"
          % (len(b.pools), sum(len(p.nodes) for p in b.pools),
             sum(len(p.flows) for p in b.pools), len(b.message_flows), len(FORMS)))
    print("channel width %.0f px | canvas %.0f x %.0f"
          % (r.chan_w, max(p.x + p.w for p in b.pools), max(p.y + p.h for p in b.pools)))
    for w in r.problems:
        print("  layout note:", w)

if __name__ == "__main__":
    main()
