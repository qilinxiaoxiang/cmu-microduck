"""One-off: move ID5 (right hip yaw) off the encoder seam mechanically, keeping its calibration exact.

The ID5 horn sits half a turn round, so leg-forward lands near the encoder's 0/4095 seam and pi/seam_fix.py has to
pick a +-2048 Homing Offset in Extended Position mode after every power-up. The mechanical fix: take the horn off,
let ID5 turn its bare shaft exactly 2048 ticks (half a turn, no load), put the horn back on in the leg's old
orientation. The raw encoder then reads what the seam-fixed position read before, so Position mode (3) with Homing
Offset 0 gives the same numbers as the software fix and every calibration downstream stays valid.

  python id5_horn_turn.py ref      leg held straight forward: record the seam-fixed reading (before) or compare (after)
  python id5_horn_turn.py turn     horn OFF, nothing on the shaft: torque on ID5 alone, +2048 ticks slowly, torque off
  python id5_horn_turn.py finalize horn back ON: ID5 to Position mode 3, Homing Offset 0, reboot, read
  python id5_horn_turn.py watch    print ID5 every 0.2 s

Runs over the OpenRB USB link (openrb_dual_host); nothing else may be driving the bus. Only ID5 is ever written.
"""
import glob
import json
import os
import struct
import sys
import time

import serial

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pi"))
from dxl_fast import _packet  # noqa: E402

ID = 5
ADDR_MODE, ADDR_HOMING, ADDR_TORQUE, ADDR_PROF_ACC, ADDR_PROF_VEL, ADDR_GOAL, ADDR_POS = 11, 20, 64, 108, 112, 116, 132
REF = "/tmp/id5_horn_ref.json"


class Bus:
    def __init__(self, port):
        self.ser = serial.Serial(port, 1_000_000, timeout=0.05)

    def _status(self):
        buf, end = b"", time.time() + 0.1
        while time.time() < end:
            buf += self.ser.read(64)
            k = buf.find(b"\xff\xff\xfd\x00")
            if k >= 0 and len(buf) >= k + 7:
                n = struct.unpack_from("<H", buf, k + 5)[0]
                if len(buf) >= k + 7 + n:
                    pkt = buf[k:k + 7 + n]
                    if pkt[4] == ID and pkt[7] == 0x55:
                        return pkt[8], pkt[9:7 + n - 2]
                    buf = buf[k + 1:]
        raise RuntimeError(f"ID{ID}: no status packet")

    def read(self, addr, size):
        return self._retry(self._read, addr, size)

    def write(self, addr, size, value):
        return self._retry(self._write, addr, size, value)  # every write here is idempotent

    @staticmethod
    def _retry(fn, *a):
        for k in range(4):
            try:
                return fn(*a)
            except RuntimeError:
                if k == 3:
                    raise
                time.sleep(0.02)

    def _read(self, addr, size):
        self.ser.reset_input_buffer()
        self.ser.write(_packet(ID, 0x02, struct.pack("<HH", addr, size)))
        err, data = self._status()
        if err & 0x7F:
            raise RuntimeError(f"ID{ID} read {addr}: error {err:#x}")
        return int.from_bytes(data[:size], "little", signed=size == 4)

    def _write(self, addr, size, value):
        self.ser.reset_input_buffer()
        self.ser.write(_packet(ID, 0x03, struct.pack("<H", addr) + int(value).to_bytes(size, "little", signed=size == 4)))
        err, _ = self._status()
        if err & 0x7F:
            raise RuntimeError(f"ID{ID} write {addr}={value}: error {err:#x}")

    def reboot(self):
        self.ser.write(_packet(ID, 0x08, b""))
        time.sleep(0.6)
        self.ser.reset_input_buffer()


def state(bus):
    return dict(mode=bus.read(ADDR_MODE, 1), homing=bus.read(ADDR_HOMING, 4), torque=bus.read(ADDR_TORQUE, 1),
                pos=bus.read(ADDR_POS, 4))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "watch"
    port = (glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/ttyACM*"))[0]
    bus = Bus(port)
    s = state(bus)
    print("ID5 now:", s, flush=True)

    if cmd == "watch":
        while True:
            p = bus.read(ADDR_POS, 4)
            print(f"ID5 pos {p}  ({(p - 2048) * 360 / 4096:+.1f} deg from 2048)", flush=True)
            time.sleep(0.2)

    if cmd == "ref":
        ref = json.load(open(REF)) if os.path.exists(REF) else None
        if ref is None:
            json.dump(dict(s, t=time.time()), open(REF, "w"))
            print(f"recorded leg-forward reference {s['pos']} (mode {s['mode']}, homing {s['homing']})")
        else:
            d = s["pos"] - ref["pos"]
            print(f"leg-forward now {s['pos']}, before {ref['pos']}: {d:+d} ticks ({d * 360 / 4096:+.1f} deg)")

    if cmd == "turn":
        if s["torque"]:
            sys.exit("ID5 torque is already on; stop whatever drives it first")
        if s["mode"] != 4:
            sys.exit(f"ID5 mode {s['mode']}, expected 4 (Extended Position) for the half turn")
        start = s["pos"]
        bus.write(ADDR_PROF_ACC, 4, 10)
        bus.write(ADDR_PROF_VEL, 4, 40)  # about 9 rev/min: the half turn takes about 3.5 s
        bus.write(ADDR_GOAL, 4, start)  # hold where it is first, so torque-on cannot jump to an old goal
        bus.write(ADDR_TORQUE, 1, 1)
        try:
            goal = start + 2048
            bus.write(ADDR_GOAL, 4, goal)
            end = time.time() + 15
            while time.time() < end:
                p = bus.read(ADDR_POS, 4)
                print(f"  pos {p}  ({p - start:+d} of +2048)", flush=True)
                if abs(p - goal) <= 4:
                    break
                time.sleep(0.25)
            time.sleep(0.5)
            p = bus.read(ADDR_POS, 4)
        finally:
            bus.write(ADDR_TORQUE, 1, 0)
        print(f"turned {p - start:+d} ticks ({(p - start) * 360 / 4096:+.1f} deg); torque off")

    if cmd == "finalize":
        if s["torque"]:
            sys.exit("ID5 torque is on; finalize needs it off")
        bus.write(ADDR_MODE, 1, 3)
        bus.write(ADDR_HOMING, 4, 0)
        bus.reboot()
        s = state(bus)
        print("ID5 after:", s)
        if s["mode"] != 3 or s["homing"] != 0:
            sys.exit("mode/homing did not stick")


if __name__ == "__main__":
    main()
