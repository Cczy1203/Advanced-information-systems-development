"""
Camunda Form validation inventory.

Scans `bpm/model/forms/*.form` and counts the fields, types and validation rules
of every form, marking the **date-like fields** separately, because the feedback
singled out date selections. It produces:

  * `forms-inventory.json` — the full machine-readable inventory, which the
    hardening script and the tests both rely on
  * a console summary — per form: fields, date fields, required fields and the
    number of fields carrying a pattern

Usage
-----
    python forms_inventory.py <forms-dir> [--json out.json] [--quiet]

Rules
-----
A `dateLike` field is a component that meets either of these conditions:
  1. `type == "datetime"` (in Camunda Forms a date is datetime + subtype)
  2. the component key or label contains words such as date / dob / birth / time,
     including the Chinese words for date, time and birth
Rule 2 catches fields that should be a date but use a textfield — exactly the
gap the feedback asks to fix under "particularly for date selections".
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Component types -> whether the component counts as an input
INPUT_TYPES = {
    "textfield", "textarea", "number", "datetime", "select", "radio",
    "checkbox", "checklist", "taglist", "group", "table", "image",
}

# Vocabulary for deciding whether a field is date-like.
#
# Only words that genuinely denote a date are listed, and **key and label are
# treated with different strictness**:
#   * a key is a name the developer chose, so a camel-case split that hits
#     date/dob/birth is enough to classify it;
#   * a label is natural language written for the user and is easy to over-match
#     ("Slot reference", "Clinic location", "Any valid reason" and "Priced by"
#     were all misjudged by the previous, looser rule), so a label only counts
#     when it states the date or time explicitly, and on a word boundary.
DATE_IN_KEY = re.compile(r"(^|[^a-z])(date|dates|dob|birth|birthdate|datetime|timestamp)([^a-z]|$)",
                         re.IGNORECASE)
# The trailing alternatives are the Chinese words for "date", "time" and "birth",
# written as escapes to keep this file ASCII. They are kept because a label may
# legitimately be authored in Chinese even though the delivered forms are English.
DATE_IN_LABEL = re.compile(r"(\bdate\b|\bdates\b|\btime\b|\bdob\b|date of birth|"
                           r"\u65e5\u671f|\u65f6\u95f4|\u51fa\u751f)", re.IGNORECASE)

# Camel-case split: chosenSlotRef -> chosen Slot Ref, so words can be matched
CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def split_words(text: str) -> str:
    """Split an identifier at camel case so DATE_IN_KEY's word boundaries match chosenSlotRef."""
    return CAMEL.sub(" ", text or "")


def walk(components, path="", prefix=""):
    """Walk the Camunda Form component tree, yielding one flat record per bindable field.

    `prefix` accumulates the group path: under Camunda's binding rules a group's
    path becomes the prefix of every child field key. Once it is non-empty, the
    submitted key carries that prefix while every worker reads variables at the
    top level, so no field of that form can be read. That is what happened on
    2026-10-16: seven grouped forms had a group `path` of `group0/group1/...`,
    `supportingDocuments` became `group1.supportingDocuments`, referral validation
    could only report that the document pack was unreadable, and the
    missing-information loop never exited. This function turns that into an
    inventory finding, so one inventory run shows it again.
    """
    for comp in components:
        ctype = comp.get("type", "?")
        cid = comp.get("id", "?")
        label = comp.get("label", "")
        key = comp.get("key")
        here = f"{path}/{cid}"
        if ctype == "group":
            inherited = prefix + (comp.get("path") or "")
            if comp.get("components"):
                yield from walk(comp["components"], here, inherited)
            continue
        if key:
            validate = comp.get("validate") or {}
            yield {
                "form_path": here,
                "id": cid,
                "key": key,
                "label": label,
                "type": ctype,
                "subtype": comp.get("subtype"),
                "required": bool(validate.get("required")),
                "pattern": validate.get("pattern"),
                # A datetime's date bound is not under validate but at the top level (form-js)
                "disallowPassedDates": comp.get("disallowPassedDates"),
                "min": validate.get("min"),
                "max": validate.get("max"),
                "minLength": validate.get("minLength"),
                "maxLength": validate.get("maxLength"),
                "has_values": bool(comp.get("values")),
                "value_count": len(comp.get("values") or []),
                # Non-empty means the group path prefixes this key on submit, so workers miss it
                "nested_under": prefix or None,
            }
        # Container components are walked further down
        if comp.get("components"):
            yield from walk(comp["components"], here, prefix)


def conditional_problems(components, field_types):
    """Type errors in conditional expressions.

    A form-js radio/select submits a **string**. `=field = false` compares a
    string with a boolean, which does not hold in FEEL, so the field stays hidden
    for good — and a **hidden required field is not validated**, so the form still
    submits with that variable empty. That is what happened on 2026-10-16:
    `treatmentPlan` stayed hidden and the process failed at
    `TRT_Auto_ValidateRequest` after `treatment.record-funding-approval`
    ("Required process variable 'treatmentPlan' is missing or blank"). The two
    other conditionals in the same file wrote "false"/"true"; only this one was
    missing the quotes — the same class of defect as DEF-02, so it becomes an
    inventory finding.
    """
    out = []
    for comp in components:
        for kind, expr in (comp.get("conditional") or {}).items():
            for var, lit in re.findall(
                    r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(true|false)", str(expr)):
                if field_types.get(var) in ("radio", "select", "textfield", "textarea"):
                    out.append((var, kind, expr))
        if comp.get("components"):
            out.extend(conditional_problems(comp["components"], field_types))
    return out


def classify(form_id, field):
    """Decide whether a field is date-related and whether its type and constraints fit.

    The rule table in `harden_forms.py` is reused deliberately, so that the
    inventory and the hardening script judge the same facts; otherwise the
    inventory would keep reporting fields that **cannot be constrained at all**
    (a datetime supports neither min nor max).
    """
    import harden_forms as H

    is_datetime_type = field["type"] == "datetime"
    key = field["key"] or ""
    key_words = split_words(key)
    key_hits = bool(DATE_IN_KEY.search(key_words))
    label_hits = bool(DATE_IN_LABEL.search(field["label"] or ""))
    looks_like_date = key_hits or label_hits
    date_like = is_datetime_type or looks_like_date
    problems = []
    if field.get("nested_under"):
        problems.append("KEY_NESTED_BY_GROUP_PATH")

    # Only a field whose name clearly means a date but is not a datetime counts
    # as a type error. A label hit with no date word in the key does not, which
    # avoids over-matching labels such as "Clinic location".
    if key_hits and not is_datetime_type and field["type"] in ("textfield", "textarea"):
        problems.append("DATE_FIELD_NOT_DATETIME_TYPE")
    # A datetime must declare a subtype, or rendering and value handling are undefined
    if is_datetime_type and not field.get("subtype"):
        problems.append("DATETIME_WITHOUT_SUBTYPE")

    if date_like:
        # Whether a date field should be required: the rule table records the
        # reason for the fields deliberately left optional, so they are not problems
        if not field["required"] and (form_id, key) not in H.KEEP_OPTIONAL:
            problems.append("DATE_FIELD_NOT_REQUIRED")

        if is_datetime_type:
            # Future dates: form-js uses the top-level disallowPassedDates (calendar minDate: today)
            if (form_id, key) in H.FUTURE_DATES:
                if field.get("disallowPassedDates") is not True:
                    problems.append("FUTURE_DATE_WITHOUT_DISALLOW_PASSED")
            # Record-type dates (referral received, decision date, ...): form-js
            # cannot express "not later than today", so DateRuleValidator covers
            # them on the worker side and they are not form defects
            elif (form_id, key) in H.PAST_ONLY_DATES:
                pass
            # Deliberately unconstrained: the demonstration compresses time, so an
            # attendance date gets filled in with a future appointment date. The
            # reason is in the shared rule table, as for the other two classes.
            elif (form_id, key) in H.FREE_DATES:
                pass
            else:
                # In neither the future nor the past set: a date field nobody has classified
                problems.append("DATE_FIELD_UNCLASSIFIED")

    # A numeric field should use the number type rather than a text box.
    # Word boundaries stop "price" matching "pricedBy" (split into "priced By").
    if field["type"] == "textfield" and re.search(
            r"(^|\s)(amount|charge|cost|price|total|fee|balance|cycles|count|quantity)(\s|$)",
            split_words(key), re.IGNORECASE):
        problems.append("NUMERIC_FIELD_NOT_NUMBER_TYPE")
    return date_like, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forms_dir")
    ap.add_argument("--json", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    forms_dir = Path(args.forms_dir)
    files = sorted(forms_dir.glob("*.form"))
    if not files:
        print(f"no .form files under {forms_dir}", file=sys.stderr)
        return 1

    report = {"forms_dir": str(forms_dir), "form_count": len(files), "forms": []}
    totals = {"fields": 0, "required": 0, "dated": 0, "patterns": 0, "problems": 0, "selects": 0, "values": 0}

    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        form_id = doc.get("id") or path.stem
        fields = list(walk(doc.get("components", [])))
        rows = []
        for f in fields:
            date_like, problems = classify(form_id, f)
            f["date_like"] = date_like
            f["problems"] = problems
            rows.append(f)
        # A conditional type error is attached to the field it references, so the existing
        # per-code count picks it up
        field_types = {f["key"]: f["type"] for f in rows}
        for var, _kind, _expr in conditional_problems(doc.get("components", []),
                                                      field_types):
            for f in rows:
                if f["key"] == var:
                    f["problems"].append("CONDITIONAL_TYPE_MISMATCH")
        n_date = sum(1 for f in rows if f["date_like"])
        n_req = sum(1 for f in rows if f["required"])
        n_pat = sum(1 for f in rows if f["pattern"])
        n_prob = sum(len(f["problems"]) for f in rows)
        entry = {
            "file": path.name,
            "form_id": doc.get("id"),
            "description": doc.get("description"),
            "schema_version": doc.get("schemaVersion"),
            "field_count": len(rows),
            "required_count": n_req,
            "date_like_count": n_date,
            "pattern_count": n_pat,
            "select_like_count": sum(1 for f in rows if f["type"] in ("select", "radio", "checklist")),
            "problem_count": n_prob,
            "fields": rows,
        }
        report["forms"].append(entry)
        totals["fields"] += len(rows)
        totals["required"] += n_req
        totals["dated"] += n_date
        totals["patterns"] += n_pat
        totals["problems"] += n_prob
        totals["selects"] += entry["select_like_count"]
        totals["values"] += sum(f["value_count"] for f in rows)
        if not args.quiet:
            print(f"{path.name:34s} fields={len(rows):3d} req={n_req:3d} "
                  f"date={n_date:2d} pattern={n_pat:2d} select={entry['select_like_count']:2d} "
                  f"problems={n_prob:3d}")

    report["totals"] = totals
    print("\n" + "=" * 78)
    print(f"FORMS      {report['form_count']}")
    print(f"FIELDS     {totals['fields']}")
    print(f"REQUIRED   {totals['required']}")
    print(f"DATE-LIKE  {totals['dated']}")
    print(f"PATTERNS   {totals['patterns']}")
    print(f"SELECTLIKE {totals['selects']}  (total options {totals['values']})")
    print(f"PROBLEMS   {totals['problems']}")
    print("=" * 78)
    if not args.quiet:
        from collections import Counter
        c = Counter(p for f in report["forms"] for fld in f["fields"] for p in fld["problems"])
        for k, v in c.most_common():
            print(f"  {v:4d}  {k}")
        c2 = Counter(fld["type"] for f in report["forms"] for fld in f["fields"])
        print("  field types:", dict(c2.most_common()))

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
