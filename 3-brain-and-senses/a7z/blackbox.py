"""A7Z flight recorder: every kernel message and a 10 Hz system snapshot, written as they happen and fsynced to the SD
card within 0.1 s, so a hang, a watchdog reset or a power cut keeps the record up to the last fraction of a second.
Runs as root from duck-blackbox.service (/home/radxa/duck/blackbox.py), one pair of files per boot in
/home/radxa/duck-logs/blackbox/, named b<NNNN>-<boot8> (NNNN counts boots; the A7Z has no RTC, so its clock is no key):

  b<NNNN>-<boot8>-kmsg.log   one line per kernel record: <A7Z unix time seen> <kernel s since boot> <level> #<seq> <text>
                             (/dev/kmsg from the start of the boot, so early boot lines, the SoC boot-reason included)
  b<NNNN>-<boot8>-sys.jsonl  first row: header (A7Z clock, watchdog owner and timeout, lockup-detector settings);
                             then one row per period: uptime, CPU busy/iowait/irq/softirq %, load, MemAvailable, PSI,
                             the five busiest processes, every process in D state with its kernel stack, per-IRQ counts
                             since the last row, Wi-Fi link and RX/TX bytes, sysrq dumps requested

Writers only write and flush (to the page cache, which the live Mac mirror reads); a separate thread fsyncs both files
every 0.1 s, so an SD card stall cannot stop the record that reaches the Mac. When a process stays in D state for 2 s
or the recorder itself missed rows for 2 s, it asks the kernel for blocked-task and all-CPU backtraces (sysrq w, l),
at most every 30 s per kind; they land in kmsg.log. A restart within one boot appends to the same pair and skips kernel records
already copied. Only the newest --keep boots are kept. Temperatures and CPU clocks stay in thermal_log.py.

  python3 blackbox.py [--out DIR] [--period 0.2] [--keep 40] [--kmsg /dev/kmsg] [--proc /proc] [--sys /sys] [--rows N]
"""
import argparse, ctypes, errno, glob, json, os, re, select, subprocess, threading, time

LEVELS = ["emerg", "alert", "crit", "err", "warn", "notice", "info", "debug"]
SYSCTLS = ("kernel/watchdog_thresh", "kernel/watchdog", "kernel/softlockup_panic", "kernel/hung_task_timeout_secs",
           "kernel/hung_task_panic", "kernel/panic", "kernel/panic_on_oops", "vm/dirty_expire_centisecs",
           "vm/dirty_writeback_centisecs")
SYSRQ_GAP_S, SYSRQ_EVERY_S = 2.0, 30.0


def read(path, default=""):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return default


def kmsg_parse(record):
    """'<pri>,<seq>,<usec>,<flags>;<text>\n[ KEY=value continuation lines]' -> (seq, usec, level, text) or None."""
    head, sep, text = record.partition(";")
    if not sep:
        return None
    fields = head.split(",")
    try:
        pri, seq, usec = int(fields[0]), int(fields[1]), int(fields[2])
    except (IndexError, ValueError):
        return None
    return seq, usec, LEVELS[pri & 7], text.split("\n", 1)[0].rstrip()


def kmsg_line(record, seen):
    p = kmsg_parse(record)
    if p is None:
        return None
    seq, usec, level, msg = p
    return "%.3f %.6f %s #%d %s\n" % (seen, usec / 1e6, level, seq, msg)


def last_seq(path):
    """Highest '#<seq>' already in a kmsg.log (a restart in the same boot resumes after it), -1 if none."""
    best = -1
    for line in read(path).splitlines():
        p = line.split(" ", 4)
        if len(p) >= 4 and p[3].startswith("#") and p[3][1:].isdigit():
            best = max(best, int(p[3][1:]))
    return best


def note(out, text):
    out.write("%.3f - - - [blackbox: %s]\n" % (time.time(), text))
    out.flush()


def kmsg_loop(path, out, stop, after=-1, poll_s=0.5):
    try:
        _kmsg_copy(path, out, stop, after, poll_s)
    except Exception as e:  # leave the reason on the card; the sys rows then show kmsg_alive false
        note(out, "kernel copy stopped: %r" % (e,))


def _kmsg_copy(path, out, stop, after, poll_s):
    """Copy /dev/kmsg to out (records with seq > after). EPIPE: the ring overwrote records before we read them."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        while not stop.is_set():
            while True:
                try:
                    rec = os.read(fd, 8192)
                except BlockingIOError:
                    break
                except OSError as e:
                    if e.errno == errno.EPIPE:
                        note(out, "kernel ring overwrote unread records")
                        continue
                    raise
                if not rec:
                    break
                text = rec.decode("utf-8", "replace")
                p = kmsg_parse(text)
                if p and p[0] > after:
                    out.write(kmsg_line(text, time.time()))
            out.flush()
            select.select([fd], [], [], poll_s)
    finally:
        os.close(fd)


def sync_loop(files, stop, period=0.1):
    """fsync every file each period, off the writer threads: a stalled card blocks only this thread."""
    while not stop.is_set():
        for f in files:
            try:
                os.fsync(f.fileno())
            except (OSError, ValueError):
                pass
        stop.wait(period)


def cpu_times(proc):
    """Aggregate /proc/stat cpu line: (user, nice, system, idle, iowait, irq, softirq, steal)."""
    for line in read(proc + "/stat").splitlines():
        if line.startswith("cpu "):
            return [int(x) for x in line.split()[1:9]]
    return None


def cpu_pct(a, b):
    if not a or not b:
        return None
    d = [y - x for x, y in zip(a, b)]
    total = sum(d)
    if total <= 0:  # no tick between rows: unknown, not 100 % busy
        return None
    return {"busy": round(100 * (total - d[3] - d[4]) / total, 1), "iowait": round(100 * d[4] / total, 1),
            "irq": round(100 * d[5] / total, 1), "softirq": round(100 * d[6] / total, 1)}


def proc_ticks(proc):
    """{pid: (comm, state, utime+stime)} for every process."""
    out = {}
    for p in glob.glob(proc + "/[0-9]*/stat"):
        s = read(p)
        r = s.rfind(")")
        if r < 0:
            continue
        comm = s[s.find("(") + 1:r]
        rest = s[r + 2:].split()
        try:
            out[int(p.split("/")[-2])] = (comm, rest[0], int(rest[11]) + int(rest[12]))
        except (IndexError, ValueError):
            pass
    return out


def interrupts(proc):
    """{name: total count over CPUs}; name is the IRQ number plus its chip/device text."""
    out = {}
    lines = read(proc + "/interrupts").splitlines()
    if not lines:
        return out
    ncpu = len(lines[0].split())
    for line in lines[1:]:
        irq, _, rest = line.partition(":")
        parts = rest.split()
        counts = []
        for x in parts[:ncpu]:
            if not x.isdigit():
                break
            counts.append(int(x))
        name = (irq.strip() + " " + " ".join(parts[len(counts):])).strip()
        out[name] = sum(counts)
    return out


def meminfo(proc):
    m = re.search(r"MemAvailable:\s+(\d+)", read(proc + "/meminfo"))
    return int(m.group(1)) // 1024 if m else None


def psi(proc):
    out = {}
    for k in ("cpu", "memory", "io"):
        m = re.search(r"some avg10=([\d.]+)", read(proc + "/pressure/" + k))
        if m:
            out[k] = float(m.group(1))
    return out or None


def wifi(proc):
    """{iface: {link, level, rx, tx}} from /proc/net/wireless and /proc/net/dev."""
    out = {}
    for line in read(proc + "/net/wireless").splitlines()[2:]:
        f = line.split()
        if len(f) >= 4:
            out[f[0].rstrip(":")] = {"link": float(f[2].rstrip(".")), "level": float(f[3].rstrip("."))}
    for line in read(proc + "/net/dev").splitlines()[2:]:
        name, _, rest = line.partition(":")
        name, f = name.strip(), rest.split()
        if name in out and len(f) >= 9:
            out[name].update(rx=int(f[0]), tx=int(f[8]))
    return out or None


def watchdog_info(sysfs):
    """Who resets a hung board and after how long: hardware watchdog devices plus systemd's RuntimeWatchdog."""
    out = {}
    for w in sorted(glob.glob(sysfs + "/class/watchdog/watchdog*")):
        out[os.path.basename(w)] = {k: read(w + "/" + k, "?").strip() for k in ("identity", "timeout", "state")}
    try:
        out["systemd"] = subprocess.run(["systemctl", "show", "-p", "RuntimeWatchdogUSec", "-p", "RebootWatchdogUSec"],
                                        capture_output=True, text=True, timeout=3).stdout.split()
    except (OSError, subprocess.SubprocessError):
        out["systemd"] = None
    return out


class Snapshot:
    """Holds the previous counters so every row reports what happened since the last one."""

    def __init__(self, proc, hz, sysrq=None):
        self.proc, self.hz, self.sysrq = proc, hz, sysrq
        self.cpu, self.ticks, self.irq, self.t = cpu_times(proc), proc_ticks(proc), interrupts(proc), time.time()
        self.d_since, self.last_sysrq = {}, {}

    def trigger(self, keys, now):
        """Ask the kernel for backtraces (sysrq), rate-limited per kind ('w' D-state, 'lw' recorder gap)."""
        if not self.sysrq or now - self.last_sysrq.get(keys, 0.0) < SYSRQ_EVERY_S:
            return None
        self.last_sysrq[keys] = now
        for k in keys:
            try:
                with open(self.sysrq, "w") as f:
                    f.write(k)
            except OSError:
                return None
        return keys

    def row(self):
        proc = self.proc
        t, cpu, ticks, irq = time.time(), cpu_times(proc), proc_ticks(proc), interrupts(proc)
        dt = max(t - self.t, 1e-6)
        busiest = []
        for pid, (comm, state, tk) in ticks.items():
            prev = self.ticks.get(pid)
            if prev and tk > prev[2]:
                busiest.append((round(100 * (tk - prev[2]) / self.hz / dt, 1), pid, comm))
        busiest.sort(reverse=True)
        dstate = []
        for pid, (comm, state, _) in ticks.items():
            if state == "D":
                since = self.d_since.setdefault(pid, t)
                dstate.append({"pid": pid, "comm": comm, "s": round(t - since, 1),
                               "wchan": read("%s/%d/wchan" % (proc, pid), "?").strip(),
                               "stack": [l.split("] ", 1)[-1] for l in read("%s/%d/stack" % (proc, pid)).splitlines()][:12]})
        self.d_since = {d["pid"]: self.d_since[d["pid"]] for d in dstate}
        irq_d = {k: v - self.irq.get(k, 0) for k, v in irq.items() if v - self.irq.get(k, 0) > 0}
        up = read(proc + "/uptime", "0").split()
        r = {"t": round(t, 3), "up": float(up[0]) if up else None, "dt": round(dt, 3), "cpu": cpu_pct(self.cpu, cpu),
             "load": float(read(proc + "/loadavg", "0").split()[0]), "mem_avail_mb": meminfo(proc), "psi": psi(proc),
             "top": [{"pid": pid, "comm": comm, "cpu": pct} for pct, pid, comm in busiest[:5]],
             "dstate": dstate, "irq": irq_d, "wifi": wifi(proc)}
        if dt > SYSRQ_GAP_S:  # this recorder itself could not run: dump what everyone is blocked on
            r["sysrq"] = self.trigger("lw", t)
        elif any(d["s"] >= SYSRQ_GAP_S for d in dstate):
            r["sysrq"] = self.trigger("w", t)
        self.cpu, self.ticks, self.irq, self.t = cpu, ticks, irq, t
        return r


def stem_for(out_dir, boot):
    """Existing stem of this boot (recorder restart), else b<next counter>-<boot>."""
    names = [os.path.basename(p) for p in glob.glob(out_dir + "/b[0-9][0-9][0-9][0-9]-*-kmsg.log")
             + glob.glob(out_dir + "/b[0-9][0-9][0-9][0-9]-*-sys.jsonl")]
    for n in names:
        if n.split("-")[1] == boot:
            return os.path.join(out_dir, n.rsplit("-", 1)[0])
    n = max([int(x[1:5]) for x in names] or [0]) + 1
    return os.path.join(out_dir, "b%04d-%s" % (n, boot))


def prune(out_dir, keep):
    """Keep the files of the newest `keep` boots (by boot counter)."""
    stems = sorted({os.path.basename(p).rsplit("-", 1)[0] for p in glob.glob(out_dir + "/b[0-9][0-9][0-9][0-9]-*")})
    for stem in stems[:-keep] if keep > 0 else []:
        for p in glob.glob(os.path.join(out_dir, stem + "-*")):
            os.remove(p)


def lock_memory():
    """Keep the recorder's own pages in RAM, so a stalled card cannot make it wait on paging in its code."""
    try:
        return ctypes.CDLL(None, use_errno=True).mlockall(3) == 0  # MCL_CURRENT | MCL_FUTURE
    except (OSError, AttributeError):
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="/home/radxa/duck-logs/blackbox")
    ap.add_argument("--period", type=float, default=0.1)
    ap.add_argument("--keep", type=int, default=40)
    ap.add_argument("--kmsg", default="/dev/kmsg")
    ap.add_argument("--proc", default="/proc")
    ap.add_argument("--sys", default="/sys")
    ap.add_argument("--rows", type=int, default=None, help="stop after N sys rows (tests); default: run forever")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    boot = read(a.proc + "/sys/kernel/random/boot_id", "unknown").strip().replace("-", "")[:8] or "unknown"
    stem = stem_for(a.out, boot)
    restart = os.path.exists(stem + "-kmsg.log")
    after = last_seq(stem + "-kmsg.log") if restart else -1
    kout, sout = open(stem + "-kmsg.log", "a"), open(stem + "-sys.jsonl", "a")
    prune(a.out, a.keep)
    stop = threading.Event()
    if restart:
        note(kout, "recorder restarted in the same boot, resuming after kernel record #%d" % after)
    kt = threading.Thread(target=kmsg_loop, args=(a.kmsg, kout, stop, after), daemon=True)
    kt.start()
    threading.Thread(target=sync_loop, args=([kout, sout], stop), daemon=True).start()
    snap = Snapshot(a.proc, os.sysconf("SC_CLK_TCK"),
                    a.proc + "/sysrq-trigger" if os.path.exists(a.proc + "/sysrq-trigger") else None)
    sout.write(json.dumps({"start": round(time.time(), 3), "boot": boot, "period": a.period, "restart": restart,
                           "mlocked": lock_memory(), "watchdog": watchdog_info(a.sys),
                           "sysctl": {k: read(a.proc + "/sys/" + k, "?").strip() for k in SYSCTLS},
                           "rcu_stall_s": read(a.sys + "/module/rcupdate/parameters/rcu_cpu_stall_timeout", "?").strip()})
               + "\n")
    sout.flush()
    snap.t = time.time()  # the header (systemctl at early boot) must not count as a recorder gap
    k = 0
    while a.rows is None or k < a.rows:
        time.sleep(a.period)
        r = snap.row()
        r["kmsg_alive"] = kt.is_alive()  # false = the kernel copy died; its last line says why
        sout.write(json.dumps(r, separators=(",", ":")) + "\n")
        sout.flush()
        k += 1
    stop.set()
    kt.join(2)
    for f in (kout, sout):
        f.flush(); os.fsync(f.fileno()); f.close()


if __name__ == "__main__":
    main()
