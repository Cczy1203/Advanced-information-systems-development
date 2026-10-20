#!/usr/bin/env python3
"""
Clear the `path` on every group component in model/forms/*.form.

    python3 tools/fix_form_group_paths.py            # dry run, reports what it would do
    python3 tools/fix_form_group_paths.py --apply    # rewrite the form files

Why this exists
---------------
A group's path becomes a prefix on every child field's key. Camunda's data binding
documentation is explicit: "the group's path acts as a prefix to the key of each
child field within that group". The accessibility pass that added grouping to the
long forms also set `path` to `group0`, `group1`, ... on each group, which meant a
field keyed `supportingDocuments` was submitted as `group1.supportingDocuments`.

Every worker reads its variables at the top level, so none of them could see a
single field of the seven grouped forms. The visible symptom was the referral pack
validation reporting the pack as **unreadable** - it looks for a document list and
finds none - however carefully the form was filled. That in turn made the
missing-information loop impossible to leave from Tasklist: the reply was recorded,
the pack check ran again, the worker still saw nothing, and the case went round.

The path may be left empty, which is what this sets. The grouping stays exactly as
it is - same groups, same labels, same children, same order, so the accessibility
audit still counts them - and the field keys stay bare, so the workers read them.
"""

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.join(HERE, "..", "model", "forms")


def clear_paths(components):
    """Yield (group, old_path) for every group whose path is not already empty."""
    for comp in components:
        if comp.get("type") == "group":
            if comp.get("path"):
                yield comp, comp["path"]
            yield from clear_paths(comp.get("components") or [])
        elif comp.get("components"):
            yield from clear_paths(comp["components"])


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="rewrite the files; without it this is a dry run")
    args = ap.parse_args(argv[1:])

    changed = files = 0
    for path in sorted(glob.glob(os.path.join(FORMS, "*.form"))):
        data = json.load(open(path, encoding="utf-8"))
        hits = list(clear_paths(data.get("components") or []))
        if not hits:
            continue
        files += 1
        name = os.path.basename(path)
        for comp, old in hits:
            changed += 1
            print("  %-42s %-26s path %r -> \"\"" % (name, comp.get("id"), old))
            comp["path"] = ""
        if args.apply:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.write("\n")

    if not changed:
        print("no group carries a path; nothing to do")
        return 0
    print()
    print("%d group(s) in %d file(s) %s"
          % (changed, files, "cleared" if args.apply else
             "would be cleared - re-run with --apply"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
