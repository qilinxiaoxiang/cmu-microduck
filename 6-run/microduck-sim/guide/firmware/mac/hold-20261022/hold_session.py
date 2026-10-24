"""Guided data collection for the head pads and the lifted-by-the-head hold (2026-10-22). Runs on the A7Z beside hold.py.

    python3 ~/duck/hold_session.py [--log PATH] [--labels PATH] [--hold-file ~/.duck_hold.json]

Tails the newest ~/duck-logs/duck_wired_log_*.jsonl that walk_wired.py writes (flushed every tick) and shows it as a
plain live view at 10 Hz: the five pad bars, leg and neck current, tilt, |acc|, mode, actions and the hold estimate
(computed every tick, applied only while the hold file says on). The builder labels each trial himself: Enter starts it,
Enter ends it, with t0/t1 in the log's own clock (row t). Labels go to ~/duck-logs/hold_labels_<suffix>.jsonl.

Keys: Enter start/end a trial, n/b next/previous step, x drop the running trial or mark the last one bad,
h hold on/off, c calibrate from the labelled trials and write the calibration into the hold file, q quit.
The only files written are the label file and the hold file. No command ever goes to the robot from here.
"""
import argparse
import bisect
import glob
import json
import os
import select
import statistics as st
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE)]  # ~/duck on the A7Z; the parent mac/ folder on the Mac
import hold  # noqa: E402

# Tick-log joint order (walk_brain.NAMES, servo IDs 1..14); the first ten are the legs.
NAMES = ["right_ankle", "right_knee", "right_hip_pitch", "right_hip_roll", "right_hip_yaw",
         "left_ankle", "left_knee", "left_hip_pitch", "left_hip_roll", "left_hip_yaw",
         "head_pitch", "neck_pitch", "head_yaw", "head_roll"]
HEAD_PITCH, NECK_PITCH = NAMES.index("head_pitch"), NAMES.index("neck_pitch")
PADS = list(hold.PADS)
LOG_GLOB = os.path.expanduser("~/duck-logs/duck_wired_log_*.jsonl")
BAR_FULL = 2000      # counts for a full bar, as on the live page
BAR_W = 30
REST_S = 2.0         # the live bars' rest baseline: the first 2 s of touch data
STALE_S = 1.0        # no new row for this long: the log has stopped
FRAME_S = 0.1
POLICY_MODES = ("walk",)  # where the hold acts (walk_brain: hold only in walk mode)

# (label, target count, instruction, hold required: False off, True on, None either)
STEPS = [
    ("rest", 1, "安静站立 30 秒，不碰头。机器人在 app 里 walk 零速度（stand61）。回车开始，约 30 秒后回车结束。", False),
    ("press_L1", 3, "一根手指按住 L1，3 秒，松开。回车开始，松开后回车结束。", False),
    ("press_R1", 3, "一根手指按住 R1，3 秒，松开。", False),
    ("press_L2", 3, "一根手指按住 L2，3 秒，松开。", False),
    ("press_R2", 3, "一根手指按住 R2，3 秒，松开。", False),
    ("press_M", 3, "一根手指按住 M，3 秒，松开。", False),
    ("hover", 3, "手悬在头顶上方 1-2 cm，不碰，停 3 秒。", False),
    ("grip", 5, "像要拎起来那样抓住头，不提，3 秒，松开。", False),
    ("lift_head_off", 5, "保持关（今天的行为）。回车，抓头慢慢提起 3-4 cm，停 3 秒，放下站稳，回车。"
                         "它挣扎或卡住的话，结束后口头记一下是哪一次。", False),
    ("lift_body", 3, "抓身体（不碰头）提起 3-4 cm，停 3 秒，放下站稳。", False),
    ("stroke", 10, "从前往后抚摸头顶一次。", False),
    ("pat", 10, "轻拍头顶 2-3 下。", False),
    ("pat_hard", 10, "用力、生气地快拍 2-3 下。", False),
    ("lift_head_on", 5, "先按 c 校准，再按 h 打开保持。然后同第 4 步：抓头提起 3-4 cm，停 3 秒，放下。"
                        "看：提起时变软吗，放下后重新站稳吗。", True),
    ("stroke_on", 3, "保持开着。从前往后抚摸一次：应仍站稳。", True),
    ("pat_on", 3, "保持开着。轻拍 2-3 下：应仍站稳。", True),
    ("pat_hard_on", 3, "保持开着。用力快拍 2-3 下：应仍站稳。", True),
]
PROTOCOL_NO = {"rest": "0", "hover": "2", "grip": "3", "lift_head_off": "4", "lift_body": "5", "stroke": "6",
               "pat": "6", "pat_hard": "6"}


def step_no(label):
    """The protocol's step number (PLAN.md and the builder's sheet): presses are step 1, the hold-on repeats step 7."""
    return "1" if label.startswith("press_") else "7" if label.endswith("_on") else PROTOCOL_NO[label]


REQUIRED_FOR_CAL = ["rest"] + ["press_" + p for p in PADS] + ["grip", "lift_head_off"]


# ---------- log access ----------

def newest_log(pattern=LOG_GLOB):
    logs = glob.glob(pattern)
    return max(logs, key=os.path.getmtime) if logs else None


def suffix_of(log_path):
    name = os.path.basename(log_path)
    for ext in (".gz", ".jsonl"):
        name = name[:-len(ext)] if name.endswith(ext) else name
    return name[len("duck_wired_log_"):] if name.startswith("duck_wired_log_") else name


class Tail:
    """New complete JSON rows of a growing file; a half-written last line waits for its newline."""

    def __init__(self, path, from_start=False):
        self.f = open(path, "rb")
        if not from_start:
            self.f.seek(0, os.SEEK_END)
        self.buf = b""

    def close(self):
        self.f.close()

    def read(self):
        while True:
            chunk = self.f.read(1 << 20)
            if not chunk:
                return
            self.buf += chunk
            *lines, self.buf = self.buf.split(b"\n")
            for ln in lines:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict) and "t" in r:
                    yield r


# ---------- labels ----------

def load_trials(path):
    """Good trials in order: trial rows minus those a later {"kind": "bad"} row names."""
    rows = []
    try:
        with open(path) as f:
            rows = [json.loads(ln) for ln in f if ln.strip()]
    except OSError:
        pass
    bad = {r["n"] for r in rows if r.get("kind") == "bad"}
    return [r for r in rows if r.get("kind") == "trial" and r["n"] not in bad], rows


def append_jsonl(path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj) + "\n")


# ---------- per-row signals ----------

def legs_of(r):
    """Summed |current| of the ten leg servos (mA): the logged legs_ma, else from cur_ma."""
    if r.get("legs_ma") is not None:
        return float(r["legs_ma"])
    cur = r.get("cur_ma")
    return hold.legs_current_ma(cur, NAMES) if cur and len(cur) == len(NAMES) else None


def touch_of(r):
    """Raw pad counts if this row's block is fresh, else None."""
    c, age = r.get("touch"), r.get("touch_age")
    if not c or len(c) != len(PADS) or (age is not None and age > hold.TOUCH_STALE_S):
        return None
    return c


def slim(r):
    """What calibration needs from a row, so a long session fits in memory."""
    return {"t": r["t"], "touch": touch_of(r), "legs_ma": legs_of(r)}


def window(rows, t0, t1):
    """Rows (a Rows list) with t0 <= t <= t1."""
    return rows[bisect.bisect_left(rows.ts, t0):bisect.bisect_right(rows.ts, t1)]


class Rows(list):
    """Time-ordered rows with a parallel list of t for bisect."""

    def __init__(self, rows=()):
        super().__init__(rows)
        self.ts = [r["t"] for r in self]

    def append(self, r):
        super().append(r)
        self.ts.append(r["t"])


def middle(t0, t1, keep=None, edge=0.5):
    """The settled part of a trial: `keep` s around the centre, or the trial minus `edge` s at each end."""
    if keep is not None:
        c = (t0 + t1) / 2
        return c - keep / 2, c + keep / 2
    return (t0 + edge, t1 - edge) if t1 - t0 > 3 * edge else (t0, t1)


def pad_rest(rows, trials):
    """Per-pad median and std of the counts over the rest trials."""
    vals = [r["touch"] for tr in trials for r in window(rows, tr["t0"], tr["t1"]) if r["touch"]]
    if len(vals) < 10:
        return None, None
    cols = list(zip(*vals))
    return [st.median(c) for c in cols], [st.pstdev(c) for c in cols]


def pre_base(rows, t0, fallback):
    """Pad baseline just before a trial (1.2..0.2 s before t0), so slow drift over the session cancels."""
    vals = [r["touch"] for r in window(rows, t0 - 1.2, t0 - 0.2) if r["touch"]]
    return [st.median(c) for c in zip(*vals)] if len(vals) >= 5 else fallback


def trial_rise(rows, tr, rest_med):
    """Per-pad median rise over the settled middle of a trial, or None without touch data."""
    base = pre_base(rows, tr["t0"], rest_med)
    a, b = middle(tr["t0"], tr["t1"])
    vals = [r["touch"] for r in window(rows, a, b) if r["touch"]]
    if not vals or base is None:
        return None
    return [st.median(c) - b0 for c, b0 in zip(zip(*vals), base)]


def levels(delta, lo, hi):
    return [hold.clip01((d - l) / max(1.0, h - l)) for d, l, h in zip(delta, lo, hi)]


def area_mm2(lv):
    return sum(hold.PAD_AREA_MM2[p] * v for p, v in zip(PADS, lv))


def compute_cal(trials, rows):
    """(cal, problems): the hold calibration from the labelled trials; cal is None when any problem stands."""
    rows = rows if isinstance(rows, Rows) else Rows(rows)
    by = {lb: [tr for tr in trials if tr["label"] == lb] for lb in REQUIRED_FOR_CAL}
    problems = [f"{lb} 还没有试次" for lb in REQUIRED_FOR_CAL if not by[lb]]
    if problems:
        return None, problems
    rest_med, rest_std = pad_rest(rows, by["rest"])
    if rest_med is None:
        return None, ["rest 试次里没有铜箔数据"]
    rise, lo, hi = [], [], []
    for k, p in enumerate(PADS):
        rs = [x[k] for x in (trial_rise(rows, tr, rest_med) for tr in by["press_" + p]) if x]
        r = st.median(rs) if rs else 0.0
        rise.append(r)
        lo.append(max(5 * rest_std[k], 0.25 * r))
        hi.append(0.8 * r)
        if hi[k] <= lo[k]:
            problems.append(f"{p}: 按压只升高 {r:.0f}，静止噪声 {rest_std[k]:.1f}，分不开")
    grip = []
    if not problems:
        for tr in by["grip"]:
            base = pre_base(rows, tr["t0"], rest_med)
            a, b = middle(tr["t0"], tr["t1"])
            areas = [area_mm2(levels([c - b0 for c, b0 in zip(r["touch"], base)], lo, hi))
                     for r in window(rows, a, b) if r["touch"]]
            if areas:
                grip.append(st.median(areas))
        if not grip or st.median(grip) < 100:
            problems.append(f"抓头时盖住的面积太小（{st.median(grip) if grip else 0:.0f} mm2）")
    stand = [r["legs_ma"] for tr in by["rest"] for r in window(rows, tr["t0"], tr["t1"]) if r["legs_ma"] is not None]
    air = [r["legs_ma"] for tr in by["lift_head_off"] for r in window(rows, *middle(tr["t0"], tr["t1"], keep=1.0))
           if r["legs_ma"] is not None]
    if not stand or not air:
        problems.append("没有腿电流数据（legs_ma / cur_ma）")
    else:
        s_ma, a_ma = st.median(stand), st.median(air)
        if s_ma - a_ma < 0.2 * s_ma:
            problems.append(f"腿电流站立 {s_ma:.0f} mA，提起 {a_ma:.0f} mA，差不到 20%，分不出离地")
    if problems:
        return None, problems
    r1 = lambda x: round(float(x), 1)  # noqa: E731
    return {"pad_lo": [r1(x) for x in lo], "pad_hi": [r1(x) for x in hi], "grip_full_mm2": r1(st.median(grip)),
            "legs_stand_ma": r1(st.median(stand)), "legs_air_ma": r1(st.median(air)),
            "pad_rest_std": [r1(x) for x in rest_std], "pad_rise": [r1(x) for x in rise],
            "made": time.strftime("%Y-%m-%dT%H:%M:%S"), "trials": len(trials)}, []


# ---------- the session ----------

def fmt(x, spec="+.0f", none="  -"):
    return none if x is None else format(x, spec)


def width(s):
    return sum(2 if ord(c) > 0x2E7F else 1 for c in s)  # CJK and full-width punctuation take two columns


def wrap(s, cols=98):
    """Lines of at most `cols` terminal columns (Chinese text has no spaces to break at)."""
    out, cur = [], ""
    for c in s:
        if width(cur + c) > cols:
            out.append(cur)
            cur = ""
        cur += c
    return out + [cur]


def bar(d):
    n = max(0, min(BAR_W, round(BAR_W * d / BAR_FULL)))
    return "█" * n + "·" * (BAR_W - n)


class Session:
    def __init__(self, labels_path, hold_path=hold.HOLD_FILE, log_name=""):
        self.labels_path, self.hold_path, self.log_name = labels_path, hold_path, log_name
        self.trials, raw = load_trials(labels_path)
        self.n = max([r["n"] for r in raw if r.get("kind") == "trial"], default=0)
        self.step = 0
        if self.trials:  # resume at the step of the last trial
            self.step = [s[0] for s in STEPS].index(self.trials[-1]["label"])
        self.rows = Rows()
        self.last, self.last_mono, self.active = None, None, None
        self.base, self._base_rows = None, []
        self.mode, self.faults = None, []
        self.events, self.msg = [], ""

    # rows
    def feed(self, r, mono, replay=False):
        self.rows.append(slim(r))
        if replay:
            self.mode = r.get("mode")
            return
        self.last, self.last_mono = r, mono
        c = touch_of(r)
        if self.base is None and c:
            self._base_rows.append((r["t"], c))
            if self._base_rows[-1][0] - self._base_rows[0][0] >= REST_S:
                self.base = [st.median(v) for v in zip(*(x[1] for x in self._base_rows))]
        mode = r.get("mode")
        if self.mode is not None and mode != self.mode:
            why = "（可能是护栏触发）" if self.mode in POLICY_MODES and mode in ("stand", "monitor") else ""
            self.event(r["t"], f"模式 {self.mode} → {mode}{why}")
        self.mode = mode
        faults = r.get("hw_faults") or []
        if faults and faults != self.faults:
            self.event(r["t"], f"硬件错误 {faults}")
        self.faults = faults

    def event(self, t, text):
        self.events = (self.events + [time.strftime("%H:%M:%S", time.localtime(t)) + " " + text])[-4:]

    def count(self, label):
        return sum(tr["label"] == label for tr in self.trials)

    def hold_state(self):
        return hold.read_hold_file(self.hold_path)

    # keys
    def key(self, k, mono):
        """Handle one key; False to quit."""
        label, target, _, need = STEPS[self.step]
        if k in ("\n", "\r"):
            if self.active is None:
                if self.last is None or mono - self.last_mono > STALE_S:
                    self.msg = "日志没有更新，不能开始"
                    return True
                on = self.hold_state()["on"]
                if need is not None and on != need:
                    self.msg = f"这一步要保持{'开' if need else '关'}：先按 h"
                    return True
                self.active = {"t0": self.last["t"], "hold_file_on": on, "hold_on": self.last.get("hold_on")}
                self.msg = f"{label} 第 {self.count(label) + 1} 次：开始"
            else:
                self.n += 1
                tr = dict(kind="trial", n=self.n, step=self.step, label=label, trial=self.count(label) + 1,
                          t0=self.active["t0"], t1=self.last["t"], log=self.log_name, **{
                              k2: self.active[k2] for k2 in ("hold_file_on", "hold_on")})
                append_jsonl(self.labels_path, tr)
                self.trials.append(tr)
                self.active = None
                self.msg = f"{label} 第 {tr['trial']} 次：{tr['t1'] - tr['t0']:.1f} s 已记"
                if tr["trial"] >= target:
                    self.msg += "，这一步够了，按 n 下一步"
        elif k in ("n", "b"):
            if self.active is not None:
                self.msg = "试次进行中：先回车结束，或按 x 丢弃"
            else:
                self.step = max(0, min(len(STEPS) - 1, self.step + (1 if k == "n" else -1)))
                self.msg = ""
        elif k == "x":
            if self.active is not None:
                self.active, self.msg = None, "进行中的试次已丢弃"
            elif self.trials:
                tr = self.trials.pop()
                append_jsonl(self.labels_path, {"kind": "bad", "n": tr["n"], "t": self.last["t"] if self.last else None})
                self.msg = f"{tr['label']} 第 {tr['trial']} 次标为作废"
        elif k == "h":
            if self.active is not None:
                self.msg = "试次进行中不能切换保持"
            else:
                s = self.hold_state()
                hold.write_hold_file(not s["on"], s["cal"], self.hold_path)
                self.msg = f"保持已{'打开' if not s['on'] else '关闭'}" + ("" if s["cal"] else "（还没有校准，用默认值）")
        elif k == "c":
            cal, problems = compute_cal(self.trials, self.rows)
            if problems:
                self.msg = "校准拒绝：" + "；".join(problems)
            else:
                s = self.hold_state()
                hold.write_hold_file(s["on"], cal, self.hold_path)
                self.msg = (f"校准已写入：pad_lo {cal['pad_lo']} pad_hi {cal['pad_hi']} 抓满 {cal['grip_full_mm2']} mm2 "
                            f"腿 站 {cal['legs_stand_ma']} / 空 {cal['legs_air_ma']} mA")
        elif k == "q":
            return False  # the hold stays as it is: on survives quitting, a brain restart and a reboot
        return True

    # view
    def render(self, mono):
        r, out = self.last, []
        stale = r is None or mono - self.last_mono > STALE_S
        out.append(f"MicroDuck 抱头测试   {self.log_name}   " + ("日志没有更新" if stale else f"t {r['t']:.1f}"))
        if r is None:
            return out + ["等日志……"]
        kp = r.get("kp")
        kp_s = f"leg {kp.get('left_knee')} neck {kp.get('neck_pitch')}" if isinstance(kp, dict) else str(kp)
        gb, acc = r.get("gb"), r.get("acc")
        tilt = hold.tilt_deg(gb) if gb else None
        dacc = (sum(a * a for a in acc) ** 0.5 - 9.81) if acc else None
        out.append(f"模式 {r.get('mode')}  策略 {r.get('policy')}  扭矩 {'开' if r.get('torque') else '关'}  kp {kp_s}"
                   f"   倾斜 {fmt(tilt, '4.1f')}°  |acc|-g {fmt(dacc, '+.2f')}")
        h = r.get("hold") or {}
        lv = h.get("lv") or [None] * len(PADS)
        c = touch_of(r)
        if c is None:
            out.append("铜箔：没有数据（touch 为空或过期）")
        for k, p in enumerate(PADS):
            if c is None:
                break
            d = c[k] - self.base[k] if self.base else None
            out.append(f" {p:>2} {c[k]:7d} {fmt(d, '+6.0f', '  基线中')} {bar(d or 0)} lv {fmt(lv[k], '.2f')}")
        cur = r.get("cur_ma") or [None] * len(NAMES)
        out.append(f"腿电流和 {fmt(legs_of(r), '6.0f')} mA   neck_pitch {fmt(cur[NECK_PITCH], '+5.0f')} mA"
                   f"   head_pitch {fmt(cur[HEAD_PITCH], '+5.0f')} mA")
        amax = lambda a: max(abs(x) for x in a) if a else None  # noqa: E731
        out.append(f"动作 max|a| {fmt(amax(r.get('action')), '.3f')}   max|a_raw| {fmt(amax(r.get('action_raw')), '.3f')}")
        fs = self.hold_state()
        out.append(f"保持 文件{'开' if fs['on'] else '关'}{'' if fs['cal'] else '(未校准)'} "
                   f"{'应用中' if r.get('hold_on') else '影子'}  e {fmt(h.get('e'), '.2f')} cov {fmt(h.get('cov'), '.2f')}"
                   f" load {fmt(h.get('load'), '.2f')} h_load {fmt(h.get('h_load'), '.2f')} s {fmt(h.get('s'), '.2f')}"
                   f" kp_leg {h.get('kp_leg')} kp_neck {h.get('kp_neck')}")
        faults = r.get("hw_faults") or []
        out.append("硬件错误：" + (", ".join(map(str, faults)) if faults else "无")
                   + (f"   缺读 {r.get('missing')}" if r.get("missing") else ""))
        out.append("─" * 60)
        label, target, text, _ = STEPS[self.step]
        run = f"   [进行中 {r['t'] - self.active['t0']:.1f} s]" if self.active else ""
        out.append(f"步骤 {step_no(label)}：{label}（第 {self.step + 1}/{len(STEPS)} 屏）  目标 {target} 次  "
                   f"已记 {self.count(label)} 次{run}")
        out += wrap(text)
        out.append("回车 开始/结束  n 下一步  b 上一步  x 作废  h 保持开关  c 校准  q 退出")
        out += wrap(self.msg)
        for e in self.events:
            out += wrap(e)
        return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", help="tick log (default: the newest ~/duck-logs/duck_wired_log_*.jsonl)")
    ap.add_argument("--labels", help="label file (default: hold_labels_<suffix>.jsonl beside the log)")
    ap.add_argument("--hold-file", default=hold.HOLD_FILE)
    a = ap.parse_args()
    log = a.log or newest_log()
    if not log:
        sys.exit("没有 ~/duck-logs/duck_wired_log_*.jsonl：先启动 walk_wired.py（~/duck-run.sh <suffix>）")
    labels = a.labels or os.path.join(os.path.dirname(log), f"hold_labels_{suffix_of(log)}.jsonl")
    sess = Session(labels, a.hold_file, os.path.basename(log))
    tail = Tail(log, from_start=bool(sess.trials))
    if sess.trials:  # restarted mid-session: reload the rows the earlier trials need for calibration
        print(f"接着 {labels} 的 {len(sess.trials)} 个试次，读取已有日志……", flush=True)
        for r in tail.read():
            sess.feed(r, time.monotonic(), replay=True)
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    sys.stdout.write("\033[2J\033[?25l")
    next_check = 0.0
    try:
        while True:
            mono = time.monotonic()
            for r in tail.read():
                sess.feed(r, mono)
            if mono > next_check:  # the brain restarted with a new suffix: these labels would point at the old log
                next_check = mono + 2.0
                nl = newest_log() if not a.log else log
                if nl and os.path.abspath(nl) != os.path.abspath(log) and not any("新日志" in e for e in sess.events):
                    sess.event(time.time(), f"有新日志 {os.path.basename(nl)}：brain 重启过，按 q 退出再开")
            sys.stdout.write("\033[H" + "\n".join(ln + "\033[K" for ln in sess.render(mono)) + "\033[J")
            sys.stdout.flush()
            if select.select([fd], [], [], FRAME_S)[0]:
                if not sess.key(sys.stdin.read(1), time.monotonic()):
                    break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\033[?25h\n")
        print(f"标签：{labels}（{len(sess.trials)} 个试次）")


if __name__ == "__main__":
    main()
