"""
Form validation hardening.

Addresses **row 7, item 2** of the Group Feedback sheet:

    "Improve form validation, particularly for date selections, to prevent
     invalid or inappropriate dates."

The script applies one **declarative rule table** to 36 `.form` files. It can be
run repeatedly (it is idempotent) and it writes a per-field before/after report
as evidence for the feedback response.

============================================================================
Design constraints (verified against the form-js sources on this machine)
============================================================================
Modeler 5.51.0 with form-js-editor 1.25.0; the c8run Tasklist renders with
form-js-viewer 1.24.1. The validation code of the two is byte-identical by
SHA256. `validate` supports only these eight properties:

    required / pattern / patternErrorMessage / min / max / minLength / maxLength
    / validationType (email|phone|"")

Three hard rules follow, and the script keeps to them:

1) **Never** add `validate.min`, `validate.max` or `validate.pattern` to a
   `datetime` field. A datetime reads only `validate.required`; min/max are not
   merely ignored, `Big("2024-01-01")` throws, and the end user is shown
   "Min validation value is not a valid number.". A date bound can only be
   expressed by the **top-level** `disallowPassedDates`, or enforced by custom
   validation on the worker side.
2) `pattern` is an **unanchored** regular expression (`new RegExp(p).test(v)`),
   so every pattern written here carries its own `^...$` and is accompanied by a
   `patternErrorMessage` that gives the user a neutral, readable message.
3) `validationType` is **never used**. When it is set, the Modeler
   ValidateBehavior `delete`s minLength / maxLength / pattern: a hand-written
   combination works in Tasklist, but is silently removed as soon as a team
   member touches the field in the Modeler. Patterns express email and telephone
   more reliably.

============================================================================
Usage
============================================================================
    python harden_forms.py <forms-dir> [--apply] [--json report.json]

Without `--apply` the script is a dry run: it only reports the changes it would
make and writes no files.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Regular expressions: only syntax that JS RegExp also supports
# ---------------------------------------------------------------------------
# Structured reference: starts with a letter or digit; letters, digits and the
# separators . / - _ only, no spaces
RE_REFERENCE = r"^[A-Za-z0-9][A-Za-z0-9._/\-]*$"
MSG_REFERENCE = ("Use letters, digits and the separators . / - _ only, "
                 "with no spaces.")

# Person / handler name: must not be "digits only" (the feedback sheet named this
# counter-example for another group)
RE_NOT_ONLY_DIGITS = r"^(?!\s*\d+\s*$).+$"
MSG_NOT_ONLY_DIGITS = "This must be a name, not only digits."

# Email: good enough, not aiming for full RFC conformance
RE_EMAIL = r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$"
MSG_EMAIL = "Enter a valid email address, for example name@example.org."

# Telephone (international and UK local both allowed): leading +, brackets, spaces, hyphens
RE_PHONE = r"^\+?[0-9][0-9 ()\-]{6,19}$"
MSG_PHONE = "Enter a valid telephone number, digits with optional + ( ) - and spaces."

# Money ceiling: stops a mistyped 10000000; leaves ample business headroom
MONEY_MAX = 1000000

# ---------------------------------------------------------------------------
# The two date field classes — read from the **shared rule table**, not hard-coded here
# ---------------------------------------------------------------------------
# There is one rule table: bpm/workers/src/main/resources/date-rules.json.
# The Java DateRuleValidator reads it from the classpath at run time for its
# server-side backstop; this script reads the same file from disk to decide which
# form fields take disallowPassedDates and which are left to the worker. Both
# sides read one file so that the form rules and the server rules cannot drift.
RULES_PATH = (Path(__file__).resolve().parent.parent
              / "workers" / "src" / "main" / "resources" / "date-rules.json")


def _load_shared_rules() -> dict:
    if not RULES_PATH.exists():
        raise SystemExit(
            f"shared date rule table not found: {RULES_PATH}\n"
            "The Java DateRuleValidator reads it too; without it the two rule sets cannot agree.")
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


_RULES = _load_shared_rules()

# (A) Future dates — planned and booked ones, which must not fall in the past.
#     form-js can express this: the top-level `disallowPassedDates: true`, which
#     gives the calendar a minDate of today.
FUTURE_DATES = {(e["form"], e["field"]) for e in _RULES["futureDates"]}

# (B) Today or earlier — record-type dates (referral received, decision,
#     consultation, contact, ...). form-js **cannot** express "not later than
#     today": a datetime does not support validate.max. These fields are therefore
#     covered by the Java DateRuleValidator on the server side.
PAST_ONLY_DATES = {(e["form"], e["field"]) for e in _RULES["pastOnlyDates"]}

# (C) Deliberately unconstrained — record-type dates, but the demonstration
#     compresses time: appointments sit in the future, so whoever fills the form
#     naturally writes the appointment day as the attendance or consultation date.
#     Any "not later than today" check would then fail falsely in normal operation
#     (on 2026-10-16 it did raise an incident, first on attendanceDate and later on
#     consultationDate), so no date rule is set here. The reason is in the shared
#     rule table, as for the other two classes.
FREE_DATES = {(e["form"], e["field"]) for e in _RULES.get("freeDates", [])}

# ---------------------------------------------------------------------------
# Required: only date fields whose absence stops a later step from deciding
# ---------------------------------------------------------------------------
MAKE_REQUIRED = {
    ("contact-consultant-overdue-letter", "contactedOn"):
        "Records that the consultant was contacted; without the date the escalation deadline cannot be judged",
    ("contact-consultant-overdue-letter", "expectedCompletionDate"):
        "An escalation must agree a completion date with the consultant, otherwise the loop cannot be tracked",
    ("record-cycle-delay", "newProposedStartDate"):
        "A recorded delay must give a new proposed start date, otherwise the case cannot be rescheduled",
    ("review-appointment-availability", "preferredFromDate"):
        "A review of appointment availability must give the start of the acceptable window",
    ("review-appointment-availability", "preferredToDate"):
        "A review of appointment availability must give the end of the acceptable window",
}

# Date fields deliberately **left optional**, with reasons (reported in the log so
# they are not mistaken for omissions). Also taken from the shared rule table, so
# that the Java documentation and the Python decisions see the same fields.
KEEP_OPTIONAL = {(e["form"], e["field"]): e["reason"] for e in _RULES["knownOptionalDates"]}

# ---------------------------------------------------------------------------
# Pattern rules for text fields (matched on the shape of the key, not 69 hard-coded entries)
# ---------------------------------------------------------------------------
PERSON_KEY = re.compile(r"(By|Name|Clinician)$")
REFERENCE_KEY = re.compile(r"(Ref|Reference|Code)$")
EMAIL_KEY = re.compile(r"Email$", re.IGNORECASE)
PHONE_KEY = re.compile(r"(Phone|Telephone|Mobile|ContactNumber)$", re.IGNORECASE)
MONEY_KEY = re.compile(r"(Amount|Charge|Paid|Fee|Cost)$", re.IGNORECASE)


def text_rule(form_id: str, field: dict):
    """Decide pattern / max for a text field. Returns (patch_dict, reason) or (None, reason)."""
    key = field.get("key") or ""
    if field.get("type") not in ("textfield", "textarea"):
        return None, None

    if EMAIL_KEY.search(key):
        return ({"pattern": RE_EMAIL, "patternErrorMessage": MSG_EMAIL},
                "Email field: format validation required")
    if PHONE_KEY.search(key):
        return ({"pattern": RE_PHONE, "patternErrorMessage": MSG_PHONE},
                "Telephone field: format validation required")
    if REFERENCE_KEY.search(key):
        return ({"pattern": RE_REFERENCE, "patternErrorMessage": MSG_REFERENCE},
                "Reference field: no spaces and no illegal characters")
    if PERSON_KEY.search(key):
        return ({"pattern": RE_NOT_ONLY_DIGITS, "patternErrorMessage": MSG_NOT_ONLY_DIGITS},
                "Person / handler field: digits only is not allowed")
    return None, None


def number_rule(form_id: str, field: dict):
    """Give a numeric field a generous ceiling against mistyped digits or decimal points."""
    key = field.get("key") or ""
    if field.get("type") != "number":
        return None, None
    if MONEY_KEY.search(key):
        validate = field.get("validate") or {}
        if validate.get("max") is None:
            return ({"max": MONEY_MAX}, "Money field: generous ceiling to catch mistyped input")
    return None, None


def patch_validate(field: dict, patch: dict):
    """Write the patch into the validate dictionary, keeping key order stable."""
    validate = field.setdefault("validate", {})
    for k, v in patch.items():
        validate[k] = v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forms_dir")
    ap.add_argument("--apply", action="store_true", help="write the files back; defaults to a dry run")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    forms_dir = Path(args.forms_dir)
    files = sorted(forms_dir.glob("*.form"))
    if not files:
        print(f"no .form under {forms_dir}", file=sys.stderr)
        return 1

    changes = []
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        form_id = doc.get("id") or path.stem
        touched = False

        def visit(components):
            nonlocal touched
            for comp in components:
                key = comp.get("key")
                if key:
                    # ---- date fields: top-level disallowPassedDates ----
                    if comp.get("type") == "datetime":
                        if (form_id, key) in FUTURE_DATES and comp.get("disallowPassedDates") is not True:
                            # The old value must be read **before** the assignment.
                            # A comp.get(...) written inside the appended dict is
                            # evaluated later, once comp has changed, and "from"
                            # would then wrongly show the new value.
                            old_flag = comp.get("disallowPassedDates")
                            comp["disallowPassedDates"] = True
                            touched = True
                            changes.append({
                                "form": path.name, "key": key, "kind": "disallowPassedDates",
                                "from": old_flag, "to": True,
                                "reason": "future dates (planned or booked) must not fall in the past",
                            })
                        if (form_id, key) in PAST_ONLY_DATES:
                            changes.append({
                                "form": path.name, "key": key, "kind": "worker-side-required",
                                "from": None, "to": "DateRuleValidator: not in the future",
                                "reason": "record-type dates must not be later than today; a form-js"
                                          " datetime does not support max, so the worker covers it",
                            })
                        if (form_id, key) in FREE_DATES:
                            changes.append({
                                "form": path.name, "key": key, "kind": "deliberately-unconstrained",
                                "from": None, "to": "no date rule",
                                "reason": "the demonstration compresses time, so an attendance"
                                          " date becomes a future appointment date; a constraint"
                                          " would only fail falsely in normal operation"
                                          " (docs/17 section 4)",
                            })

                    # ---- date fields: add required ----
                    if (form_id, key) in MAKE_REQUIRED:
                        validate = comp.setdefault("validate", {})
                        if not validate.get("required"):
                            validate["required"] = True
                            touched = True
                            changes.append({
                                "form": path.name, "key": key, "kind": "required",
                                "from": False, "to": True,
                                "reason": MAKE_REQUIRED[(form_id, key)],
                            })

                    # ---- text fields: pattern ----
                    patch, why = text_rule(form_id, comp)
                    if patch:
                        validate = comp.get("validate") or {}
                        old_pattern = validate.get("pattern")   # old value first (avoids aliasing)
                        if old_pattern != patch["pattern"]:
                            patch_validate(comp, patch)
                            touched = True
                            changes.append({
                                "form": path.name, "key": key, "kind": "pattern",
                                "from": old_pattern, "to": patch["pattern"],
                                "reason": why,
                            })

                    # ---- numeric fields: ceiling ----
                    npatch, nwhy = number_rule(form_id, comp)
                    if npatch:
                        old_max = (comp.get("validate") or {}).get("max")
                        patch_validate(comp, npatch)
                        touched = True
                        changes.append({
                            "form": path.name, "key": key, "kind": "max",
                            "from": old_max, "to": MONEY_MAX, "reason": nwhy,
                        })

                if comp.get("components"):
                    visit(comp["components"])

        visit(doc.get("components", []))

        if touched and args.apply:
            path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")

    by_kind = {}
    for c in changes:
        by_kind.setdefault(c["kind"], []).append(c)

    print("=" * 78)
    print(f"forms scanned       {len(files)}")
    print(f"changes             {len(changes)}")
    for k, v in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
        print(f"  {k:24s} {len(v)}")
    print("=" * 78)
    for kind in ("disallowPassedDates", "required", "pattern", "max",
                 "worker-side-required", "deliberately-unconstrained"):
        rows = by_kind.get(kind, [])
        if not rows:
            continue
        print(f"\n--- {kind} ({len(rows)}) ---")
        for c in rows:
            print(f"  {c['form'][:-5]:40s} {c['key']:30s} {str(c['from'])[:22]:24s} -> {str(c['to'])[:40]}")

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"apply": args.apply, "form_count": len(files), "changes": changes},
            indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {args.json}")
    if not args.apply:
        print("\n(dry run — pass --apply to write files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
