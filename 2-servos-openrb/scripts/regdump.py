"""Read the control-table registers that shape position tracking from every servo over the OpenRB USB link.
Run only while walk_wired.py is stopped (it owns the port); torque stays as it is, nothing is written.

  ~/.venvs/microduck-walk/bin/python regdump.py
"""
import glob
import time

from walk_wired import IDS, NAMES, Link

REGS = [("mode", 11, 1), ("pwm_lim", 36, 2), ("cur_lim", 38, 2), ("vel_lim", 44, 4), ("D", 80, 2), ("I", 82, 2),
        ("P", 84, 2), ("prof_acc", 108, 4), ("prof_vel", 112, 4), ("torque", 64, 1), ("volt_dv", 144, 2),
        ("temp_C", 146, 1), ("hw_err", 70, 1)]

link = Link(glob.glob("/dev/cu.usbmodem*")[0])
time.sleep(0.3)
vals = {}
for name, addr, size in REGS:
    got = {}
    for _ in range(3):
        got.update(link.sync_read(addr, size, [i for i in IDS if i not in got], timeout=0.05, allow_alert=True))
        if len(got) == len(IDS):
            break
    vals[name] = {i: int.from_bytes(b, "little", signed=size == 4) for i, b in got.items()}
print(f"{'id':>2} {'joint':16}" + "".join(f"{n:>9}" for n, _, _ in REGS))
for i, nm in zip(IDS, NAMES):
    print(f"{i:>2} {nm:16}" + "".join(f"{vals[n].get(i, '-'):>9}" for n, _, _ in REGS))
