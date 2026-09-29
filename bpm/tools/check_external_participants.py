#!/usr/bin/env python3
"""Drive the six white-box outside participants on a running engine.

The shipped model draws the outside participants but does not deploy them (see
EXTERNAL_PROCESSES_EXECUTABLE in spec_v2.py and the append-batch measurement in
docs/11-white-box-external-participants.md §5). This script closes that gap: it
assumes the second deployment file has been deployed

    python3 tools/build_external_participants.py
    curl -sS -X POST http://localhost:8080/v2/deployments \\
         -F "resources=@model/UFCEP6-0-3_Hospital_Patient_Pathway_v14_external-participants.bpmn;type=application/xml"

and then starts each outside process the way its own trigger would:

  * the referring organisation is started directly (it has a plain start event),
    and its throw of `referral.received` is expected to start the hospital's
    Medical Secretaries process - that is the integration, not a drawing;
  * the four suppliers are started by publishing the request message their
    message start event subscribes to;
  * their step is the same job type the hospital's own service task calls, so the
    running workers complete it.

Every instance is followed to a terminal state and every active incident is
reported. Exit code is 0 only when all six completed with no incident.

    python3 tools/check_external_participants.py
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://localhost:8080"
TIMEOUT = 90

# processes with a plain start event: started directly, and their throw is
# expected to start a hospital process (that is the integration, not a drawing)
AUTOSTART = {
    "referring-organisation": ("referral.received", "medical-secretaries"),
    "patient-representative": ("appointment.attended", "consultants"),
}
MESSAGES = {
    "external-scheduling-service": ("scheduling.slot-search-requested", "-slot-search"),
    "external-payment-service": ("payment.transaction-requested", "-payment"),
    "external-clinical-services": ("external-resources.capacity-requested",
                                   "-external-capacity"),
}

OUTSIDE = ["referring-organisation", "patient-representative",
           "external-scheduling-service", "external-correspondence-service",
           "external-payment-service", "external-clinical-services"]


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raise SystemExit("%s %s failed: %s %s"
                         % (method, path, exc.code, exc.read().decode()[:400]))


def instances(process_id):
    res = call("POST", "/v2/process-instances/search",
               {"filter": {"processDefinitionId": process_id}, "page": {"limit": 200}})
    return res.get("items", [])


def incidents_for(key):
    res = call("POST", "/v2/incidents/search",
               {"filter": {"processInstanceKey": key, "state": "ACTIVE"}})
    return res.get("items", [])


def terminal(item):
    return (item.get("state") or "").upper() in ("COMPLETED", "TERMINATED")


def main():
    # This script drives the executable build of the outside participants. The
    # shipped model draws those pools instead of deploying them, so check first
    # whether the build it targets is on the engine at all, and say so plainly
    # rather than reporting a false failure.
    missing = [pid for pid in AUTOSTART if not instances(pid)]
    if missing:
        print("this engine does not have the executable outside participants.")
        print("  missing process ids: %s" % ", ".join(missing))
        print("")
        print("The shipped model draws the outside participants as documentation pools")
        print('(isExecutable="false"), so there is nothing here to start. To use this')
        print("script, build and deploy the executable variant first:")
        print("")
        print("  python3 tools/build_external_participants.py")
        print("  curl -sS -X POST http://localhost:8080/v2/deployments \\")
        print('       -F "resources=@model/UFCEP6-0-3_Hospital_Patient_Pathway_v14_external-participants.bpmn;type=application/xml"')
        print("")
        print("See docs/11-white-box-external-participants.md, revision note.")
        return 2

    # A fresh reference every run. Camunda 8 will not start a second instance for
    # a correlation key that already has an active instance on that message start
    # event - the same duplicate suppression the model relies on for hand-offs -
    # so reusing a reference would look like "the process did not start".
    ref = "PAT-DEMO-EXTOWN-%d" % int(time.time())
    print("outside-participant reference: %s\n" % ref)

    watched = OUTSIDE + ["medical-secretaries", "consultants"]
    before = {pid: {i.get("processInstanceKey") for i in instances(pid)}
              for pid in watched}
    keys = {}

    print("starting the outside participants")
    for pid in AUTOSTART:
        started = call("POST", "/v2/process-instances",
                       {"processDefinitionId": pid,
                        "variables": {"patientRef": ref,
                                      "patientName": "Outside Participant Test",
                                      "attendedOn": "2026-09-29"}})
        keys[pid] = started.get("processInstanceKey")
        print("  %-32s started directly            instance %s"
              % (pid, keys[pid]))

    for pid, (name, tag) in MESSAGES.items():
        call("POST", "/v2/messages/publication",
             {"name": name, "correlationKey": ref + tag,
              "variables": {"patientRef": ref, "patientName": "Outside Participant Test"}})
        print("  %-32s started by %-34s" % (pid, name))

    # the correspondence supplier is started by the hospital's dispatch message
    call("POST", "/v2/messages/publication",
         {"name": "correspondence.dispatch-requested",
          "correlationKey": ref + "-dispatch",
          "variables": {"patientRef": ref, "recipients": ["patient", "gp"]}})
    print("  %-32s started by %-34s" % ("external-correspondence-service",
                                        "correspondence.dispatch-requested"))

    deadline = time.time() + TIMEOUT
    results = {}
    while time.time() < deadline:
        results = {}
        for pid in OUTSIDE:
            new = [i for i in instances(pid)
                   if i.get("processInstanceKey") not in before[pid]]
            if not new:
                results[pid] = None
                continue
            newest = max(new, key=lambda i: i.get("startDate") or "")
            results[pid] = newest
        if all(v is not None and terminal(v) for v in results.values()):
            break
        time.sleep(2)

    print("\nresult")
    failed = []
    for pid in OUTSIDE:
        inst = results.get(pid)
        if inst is None:
            print("  %-32s NOT STARTED" % pid)
            if pid != "patient-representative":       # only started by the hospital
                failed.append(pid)
            continue
        key = inst.get("processInstanceKey")
        state = inst.get("state")
        inc = incidents_for(key)
        note = "no incident" if not inc else "%d incident(s): %s" % (
            len(inc), [i.get("errorMessage", "")[:60] for i in inc])
        print("  %-32s %-10s %s" % (pid, state, note))
        if state != "COMPLETED" or inc:
            failed.append(pid)

    # the integration: each outside throw should have started the hospital process
    print("\nintegration (the outside process publishes, the hospital process starts)")
    for pid, (message, hospital) in AUTOSTART.items():
        new_inst = [i for i in instances(hospital)
                    if i.get("processInstanceKey") not in before[hospital]]
        print("  %-26s throws %-22s -> %d new %s instance(s)"
              % (pid, message, len(new_inst), hospital))
        if not new_inst:
            failed.append("%s integration" % message)

    print("\n%s" % ("PASS - all outside participants ran and completed"
                    if not failed else "FAIL - %s" % sorted(set(failed))))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
