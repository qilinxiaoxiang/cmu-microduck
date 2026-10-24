"""MicroDuck probes and sim parameters for microduck-sim/CURRENT-STATE.json (standard: ~/code/claude-config/skills/current-state).

  robot_state_check.py                       run the shared checker (~/code/claude-config/scripts/state_check.py) on the file
  robot_state_check.py --probe FACT [--out STDOUT] [--log LOG.jsonl]   one JSON line for the shared checker
  robot_state_check.py --print-sim-args      brain_sim_check.py flags for the recorded real condition, for sim_suite.sh

The newest run is the newest /tmp/duck_wired_log*.jsonl; its stdout is the file with the same suffix
(/tmp/duck_wired_<sfx>.out, or /tmp/duck_wired_stdout<sfx>.txt for the default log name). If that run's stdout was not
captured, the imu probe reads the newest older stdout and reports the newer run as unmeasured evidence.
- imu_rate_hz: median of the runtime's own 'imu N/s' status lines in walk or groundpick mode with torque on (the
  fact is the rate while walking; stand-mode lines after the head board is shut down would read 0); ok is false when
  more than max_low_share of the lines sit two tolerances below the recorded rate (a mid-walk IMU dropout).
- servo_read_drop_fraction: ticks with fresh=False or missing servos while the legs move, from the JSONL log.
"""
import argparse
import bisect
import datetime
import glob
import json
import os
import re
import statistics
import subprocess
import sys

STATE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "CURRENT-STATE.json"))
CHECKER = os.path.expanduser("~/code/claude-config/scripts/state_check.py")


def imu_rates(out_path):
    return [int(m.group(1)) for line in open(out_path, errors="replace") if "torque True" in line
            and line.split(" ", 1)[0] in ("walk", "groundpick")
            for m in [re.search(r"imu\s+(\d+)/s", line)] if m]


def read_drops(log_path):
    """Walk-mode ticks within 0.3 s of a tick whose leg joints move faster than 0.5 rad/s. A tick with a dropped read
    runs no policy (action None), so the window is built from the moving ticks and every tick inside it counts."""
    rows = []
    for line in open(log_path, errors="replace"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("mode") == "walk" and "t" in r:
            rows.append(r)
    moving = [r["t"] for r in rows if r.get("dq") and max(abs(x) for x in r["dq"][:10]) > 0.5]
    def near(t):
        i = bisect.bisect_left(moving, t - 0.3)
        return i < len(moving) and moving[i] <= t + 0.3

    window = [r for r in rows if near(r["t"])]
    n = len(window)
    stale = sum(1 for r in window if (r.get("fresh") is False) or bool(r.get("missing")))
    return (stale / n, n) if n else (None, 0)


def paired_stdout(log_path):
    sfx = os.path.basename(log_path)[len("duck_wired_log"):-len(".jsonl")].lstrip("_")
    for c in (f"/tmp/duck_wired_{sfx}.out", f"/tmp/duck_wired_stdout{sfx}.txt", f"/tmp/duck_wired_stdout_{sfx}.txt"):
        if os.path.exists(c):
            return c
    return None


def day(path):
    return datetime.datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="seconds")


def probe(fact, facts, out, log):
    logs = sorted(glob.glob("/tmp/duck_wired_log*.jsonl"), key=os.path.getmtime)
    log = log or (logs[-1] if logs else None)
    if fact == "servo_read_drop_fraction":
        if not log:
            return {"value": None, "detail": "no walk_wired log in /tmp"}
        frac, n = read_drops(log)
        return {"value": None if frac is None else round(frac, 4), "measured_at": day(log),
                "detail": f"{os.path.basename(log)}, {n} legs-moving ticks"}
    if fact == "imu_rate_hz":
        latest = max([day(p) for p in (log, out) if p] or [None], key=lambda d: d or "")
        src = out or (paired_stdout(log) if log else None)
        note = ""
        if src is None:  # newest run without captured stdout: read the newest stdout that has status lines
            for c in sorted(glob.glob("/tmp/duck_wired*.out") + glob.glob("/tmp/duck_wired_stdout*.txt"), key=os.path.getmtime, reverse=True):
                if imu_rates(c):
                    src, note = c, "older run; the newest run's stdout was not captured"
                    break
        rates = imu_rates(src) if src else []
        if not rates:
            return {"value": None, "latest_evidence_at": latest, "detail": f"no torque-on status lines ({src or 'no stdout'})"}
        f = facts["imu_rate_hz"]
        floor = f["value"] - 2 * f["tolerance"]
        low = sum(r < floor for r in rates) / len(rates)
        return {"value": statistics.median(rates), "measured_at": day(src), "latest_evidence_at": latest,
                "ok": low <= f["max_low_share"],
                "detail": f"{os.path.basename(src)} median over {len(rates)} lines, {low:.1%} below {floor}/s"
                          f" (max {f['max_low_share']:.0%}){'; ' + note if note else ''}"}
    raise SystemExit(f"no probe for {fact}")


def sim_args(facts):
    args = ["--volt", str(facts["servo_rail_v"]["value"])]
    if facts["imu_rate_hz"]["value"] < 49:
        args += ["--imu-hz", str(facts["imu_rate_hz"]["value"])]
    if facts["servo_read_drop_fraction"]["value"] > 0:
        args += ["--drop", str(facts["servo_read_drop_fraction"]["value"])]
    if facts["imu_added_delay_ms"]["value"] > 0:  # brain_sim_check's default --sensor-delay 1 is the normal pipeline
        args += ["--sensor-delay", str(1 + round(facts["imu_added_delay_ms"]["value"] / 20))]
    return args


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=STATE)
    ap.add_argument("--probe")
    ap.add_argument("--out", default=None, help="walk_wired stdout (default: the newest run's paired stdout)")
    ap.add_argument("--log", default=None, help="walk_wired JSONL log (default: newest /tmp/duck_wired_log*.jsonl)")
    ap.add_argument("--print-sim-args", action="store_true")
    a, rest = ap.parse_known_args()
    facts = json.load(open(a.state))["facts"]
    if a.print_sim_args:
        print(" ".join(sim_args(facts)))
        return 0
    if a.probe:
        print(json.dumps(probe(a.probe, facts, a.out, a.log)))
        return 0
    return subprocess.call([sys.executable, CHECKER, a.state] + rest)


if __name__ == "__main__":
    sys.exit(main())
