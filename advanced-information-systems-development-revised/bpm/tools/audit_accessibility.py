#!/usr/bin/env python3
"""
Accessibility and usability audit of the Camunda Forms.

    python3 tools/audit_accessibility.py [--out bpm/screenshots/v16/accessibility-report.json]

The task asks for forms that suit the intended users and consider accessibility,
and the unit's first learning outcome is a user-centred design that explicitly
recognises the user and is Disability Discrimination Act compliant. This script is
the check behind that claim: it reads every `.form`, and reports what a person
using a screen reader, a keyboard only, or a large-print letter would meet.

What it can and cannot see
--------------------------
It is a static audit of the form *definitions*. It cannot measure contrast, run a
screen reader, or time a keyboard-only pass, and it says so in the output rather
than implying a clean bill of health. What it can see is the structure: whether a
control has a human label, whether the field explains itself, whether a long form
is broken into groups, whether a choice offers words rather than a code, and
whether the field that decides a branch is required.
"""

import argparse
import glob
import json
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# field types whose options are shown to the user as words
CHOICE = ("radio", "select", "checklist")
# a value that is a code rather than a phrase a person reads
MACHINE = re.compile(r'^[A-Z][A-Z0-9_]{2,}$|^(true|false)$')
LONG_FORM = 7          # above this, grouping stops being optional


def walk(comps, path=""):
    for comp in comps:
        key = comp.get("key")
        if key:
            yield comp, path
        if comp.get("components"):
            yield from walk(comp["components"], path + "/" + (comp.get("label") or "group"))
        elif comp.get("type") == "group":
            yield from walk([], path)


def fields(comps):
    out = []
    for comp in comps:
        if comp.get("components"):
            out.extend(fields(comp["components"]))
        elif comp.get("key"):
            out.append(comp)
    return out


def groups(comps):
    return [c for c in comps if c.get("type") == "group"]


def audit(path):
    data = json.load(open(path, encoding="utf-8"))
    comps = data.get("components", [])
    fs = fields(comps)
    gs = groups(comps)
    findings = []

    for f in fs:
        key = f.get("key", "?")
        label = (f.get("label") or "").strip()
        kind = f.get("type")
        if not label:
            findings.append(("A1", "error", key, "control has no label"))
        elif label == key or re.match(r'^[a-z0-9_]+$', label):
            findings.append(("A1", "error", key, "label is the variable name, not words"))
        if len(fs) > 3 and not f.get("description"):
            findings.append(("A2", "warn", key, "no description: the field does not explain itself"))
        if kind in CHOICE and kind != "checklist":
            values = f.get("values") or []
            codes = [v.get("value") for v in values]
            bare = [v for v in values
                    if str(v.get("label")) == str(v.get("value")) and MACHINE.match(str(v.get("value")))]
            if not values:
                findings.append(("A3", "error", key, "a choice with no options"))
            elif bare:
                findings.append(("A3", "error", key,
                                 "%d of %d options show the code as the label (%s)"
                                 % (len(bare), len(codes), ", ".join(str(v.get("value")) for v in bare[:3]))))
        if kind in ("checkbox", "checklist") and not (f.get("validate") or {}).get("required"):
            # The concern is that an unticked box cannot be told apart from one the
            # person never considered. A description that says what unticked means
            # answers that without forcing a tick that may not apply.
            text = (f.get("description") or "").lower()
            if not any(w in text for w in ("leave it clear", "leave clear", "unticked",
                                           "tick everything that applies")):
                findings.append(("A4", "warn", key,
                                 "tick box is neither required nor explained: leaving it unticked "
                                 "is indistinguishable from ignoring it"))
    if len(fs) > LONG_FORM and not gs:
        findings.append(("A5", "warn", "(form)", "%d fields and no groups" % len(fs)))
    return {
        "form": os.path.basename(path),
        "fields": len(fs),
        "groups": len(gs),
        "required": sum(1 for f in fs if (f.get("validate") or {}).get("required")),
        "described": sum(1 for f in fs if f.get("description")),
        "findings": [{"rule": r, "severity": s, "field": k, "detail": d} for r, s, k, d in findings],
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "screenshots", "v16",
                                                 "accessibility-report.json"))
    args = ap.parse_args(argv[1:])

    reports = [audit(p) for p in sorted(glob.glob(os.path.join(ROOT, "model", "forms", "*.form")))]
    rules = Counter(f["rule"] for r in reports for f in r["findings"])
    errors = sum(1 for r in reports for f in r["findings"] if f["severity"] == "error")
    warns = sum(1 for r in reports for f in r["findings"] if f["severity"] == "warn")
    result = {
        "method": ("static audit of the .form definitions. It cannot measure colour "
                   "contrast, run a screen reader, or time a keyboard-only pass; those "
                   "were not done and are not claimed."),
        "forms": len(reports),
        "fields": sum(r["fields"] for r in reports),
        "groups": sum(r["groups"] for r in reports),
        "described": sum(r["described"] for r in reports),
        "required": sum(r["required"] for r in reports),
        "errors": errors,
        "warnings": warns,
        "findingsByRule": dict(rules),
        "rules": {
            "A1": "a control must carry a human label, not its variable name",
            "A2": "in a form of more than three fields every field should explain itself",
            "A3": "a choice should offer words; a code shown as its own label is not words",
            "A4": "a tick box that is not required cannot be told apart from one that was ignored",
            "A5": "a form of more than seven fields should be grouped",
        },
        "detail": reports,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(result, open(args.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    print("forms %d | fields %d | groups %d | described %d | required %d"
          % (result["forms"], result["fields"], result["groups"],
             result["described"], result["required"]))
    print("errors %d | warnings %d" % (errors, warns))
    for rule, n in sorted(rules.items()):
        print("  %s  %-4d %s" % (rule, n, result["rules"][rule]))
    print("wrote %s" % args.out)
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv))
