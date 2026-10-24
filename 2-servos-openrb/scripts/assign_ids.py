"""Give every MicroDuck servo its joint ID when servos arrive from several kits with duplicate IDs.

Two servos with the same ID receive every write together, so a pair can only be split by
disconnecting one of them. One cut in the chain is enough when each duplicate pair straddles it:

  1. Power off, unplug one link near the middle of the chain, power on.
     assign_ids.py --port P park       # every cleanly answering kit ID moves to a free temporary ID 101+
  2. Power off, replug, power on.
     assign_ids.py --port P park       # the other twin of each pair is now alone; park it too
     (repeat with another cut while scan still reports SHARED IDs)
  3. assign_ids.py --port P identify   # torque off; move the joints by hand in role order 1..15
     (or: watch, turn joints in any order, then write id_map.json {joint: temporary ID} by hand)
  4. assign_ids.py --port P finalize   # temporary IDs -> joint IDs 1..15, then verify

park also sets Return Delay Time 0, as the build guide requires. Torque stays off throughout.
Needs: pip install dynamixel-sdk
"""
import argparse
import json
import sys
import time
from pathlib import Path

from dynamixel_sdk import COMM_RX_TIMEOUT, COMM_SUCCESS, PacketHandler, PortHandler

from scan_bus import ROLES

ADDR_ID = 7
ADDR_RETURN_DELAY = 9
ADDR_TORQUE_ENABLE = 64
ADDR_PRESENT_POSITION = 132
PARK = 100
TRIES = 8
TICKS_PER_DEG = 4096 / 360
MOVE_DEG = 20


def open_bus(port_name, baud):
    port = PortHandler(port_name)
    if not port.openPort() or not port.setBaudRate(baud):
        sys.exit(f"Cannot open {port_name} at {baud}")
    return port, PacketHandler(2.0)


def candidates(port, pk):
    """Kit IDs, temporary IDs, plus anything a few broadcast pings turn up."""
    ids = set(range(0, 21)) | set(range(PARK + 1, PARK + 31))
    for _ in range(3):
        data, r = pk.broadcastPing(port)
        if r == COMM_SUCCESS:
            ids |= set(data)
    return sorted(ids)


def survey(port, pk, ids=None):
    """Ping each ID TRIES times. clean = always answered; shared = answered garbled, i.e. duplicate IDs."""
    clean, shared = [], []
    for i in ids if ids is not None else candidates(port, pk):
        results = [pk.ping(port, i)[1] for _ in range(TRIES)]
        if all(r == COMM_SUCCESS for r in results):
            clean.append(i)
        elif any(r != COMM_RX_TIMEOUT for r in results):
            shared.append(i)
    return clean, shared


def write1(port, pk, dxl_id, addr, value):
    r, err = pk.write1ByteTxRx(port, dxl_id, addr, value)
    if r != COMM_SUCCESS or err:
        sys.exit(f"Write addr {addr}={value} to ID{dxl_id} failed: {pk.getTxRxResult(r)} {pk.getRxPacketError(err)}")


def report(clean, shared):
    print(f"temporary IDs: {[i for i in clean if i > PARK]}")
    print(f"kit IDs answering alone: {[i for i in clean if i <= PARK]}")
    print(f"SHARED IDs (two or more servos): {shared}")


def cmd_park(port, pk):
    clean, shared = survey(port, pk)
    used = {i for i in clean if i > PARK}
    free = (i for i in range(PARK + 1, PARK + 31) if i not in used)
    for old in [i for i in clean if i <= PARK]:
        new = next(free)
        write1(port, pk, old, ADDR_TORQUE_ENABLE, 0)
        write1(port, pk, old, ADDR_RETURN_DELAY, 0)
        write1(port, pk, old, ADDR_ID, new)
        if not survey(port, pk, [new])[0]:
            sys.exit(f"ID{new} does not answer after moving ID{old}")
        print(f"ID{old} -> temporary ID{new}")
    report(*survey(port, pk))


def read_positions(port, pk, ids):
    pos = {}
    for i in ids:
        v, r, err = pk.read4ByteTxRx(port, i, ADDR_PRESENT_POSITION)
        if r == COMM_SUCCESS and not err:
            pos[i] = v - (1 << 32) if v & 0x80000000 else v
    return pos


def cmd_identify(port, pk, state):
    clean, shared = survey(port, pk)
    temp = [i for i in clean if i > PARK]
    if shared or len(temp) != len(ROLES) or any(i <= PARK for i in clean):
        sys.exit(f"Need {len(ROLES)} temporary IDs and nothing else first; got temporary {temp}, "
                 f"kit {[i for i in clean if i <= PARK]}, shared {shared}")
    for i in temp:
        write1(port, pk, i, ADDR_TORQUE_ENABLE, 0)
    base = read_positions(port, pk, temp)
    mapping = {}
    for role_id, role in ROLES.items():
        print(f"\n>>> Move joint {role_id}: {role}  (slowly, more than {MOVE_DEG} degrees)", flush=True)
        while True:
            pos = read_positions(port, pk, [i for i in temp if i not in mapping.values()])
            moved = {i: abs(pos[i] - base[i]) / TICKS_PER_DEG for i in pos}
            best = max(moved, key=moved.get, default=None)
            if best is not None and moved[best] >= MOVE_DEG:
                mapping[role_id] = best
                print(f"    {role} = temporary ID{best}", flush=True)
                time.sleep(1.5)
                break
            time.sleep(0.05)
    Path(state).write_text(json.dumps({str(k): v for k, v in mapping.items()}, indent=1))
    print(f"\nAll {len(mapping)} joints identified; mapping saved to {state}. Run finalize next.")


def cmd_watch(port, pk, minutes, move_deg=MOVE_DEG):
    """Free-order identification: log which temporary ID moved most each time a joint is turned by hand."""
    temp = [i for i in survey(port, pk)[0] if i > PARK]
    for i in temp:
        write1(port, pk, i, ADDR_TORQUE_ENABLE, 0)
    base = read_positions(port, pk, temp)
    print(f"watching {temp}; turn one joint at a time by more than {move_deg} deg, then let go", flush=True)
    seen, n, end = [], 0, time.time() + 60 * minutes
    while time.time() < end and len(set(seen)) < len(temp):
        pos = read_positions(port, pk, temp)
        moved = {i: abs(pos[i] - base[i]) / TICKS_PER_DEG for i in pos if i in base}
        best = max(moved, key=moved.get, default=None)
        if best is not None and moved[best] >= move_deg:
            n += 1
            others = sorted(((round(v), i) for i, v in moved.items() if i != best and v >= 3), reverse=True)[:3]
            print(f"move {n}: temporary ID{best} turned {moved[best]:.0f} deg"
                  f"{'  (also ' + ', '.join(f'ID{i} {v} deg' for v, i in others) + ')' if others else ''}", flush=True)
            seen.append(best)
            last = pos[best]
            while True:  # wait until the hand lets go, then take a new baseline
                time.sleep(0.6)
                now = read_positions(port, pk, temp)
                if best in now and abs(now[best] - last) / TICKS_PER_DEG < 1:
                    break
                last = now.get(best, last)
            base = read_positions(port, pk, temp)
        time.sleep(0.05)
    print(f"done; distinct IDs moved: {len(set(seen))}/{len(temp)}", flush=True)


def cmd_finalize(port, pk, state):
    mapping = {int(k): v for k, v in json.loads(Path(state).read_text()).items()}
    if sorted(mapping) != sorted(ROLES) or len(set(mapping.values())) != len(ROLES):
        sys.exit(f"{state} does not map every joint 1-15 to a distinct temporary ID")
    clean, shared = survey(port, pk)
    if shared or sorted(clean) != sorted(mapping.values()):
        sys.exit(f"Bus does not match {state}: clean {clean}, shared {shared}")
    for role_id, temp in sorted(mapping.items()):
        write1(port, pk, temp, ADDR_ID, role_id)
    clean, shared = survey(port, pk)
    ok = clean == sorted(ROLES) and not shared
    print("IDs 1-15 all answer cleanly" if ok else f"Check failed: clean {clean}, shared {shared}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/serial0")
    ap.add_argument("--baud", type=int, default=1_000_000)
    ap.add_argument("--state", default="id_map.json")
    ap.add_argument("--minutes", type=float, default=15)
    ap.add_argument("--move-deg", type=float, default=MOVE_DEG)
    ap.add_argument("cmd", choices=["scan", "park", "identify", "watch", "finalize"])
    args = ap.parse_args()
    port, pk = open_bus(args.port, args.baud)
    try:
        if args.cmd == "scan":
            report(*survey(port, pk))
        elif args.cmd == "park":
            cmd_park(port, pk)
        elif args.cmd == "watch":
            cmd_watch(port, pk, args.minutes, args.move_deg)
        elif args.cmd == "identify":
            cmd_identify(port, pk, args.state)
        else:
            return cmd_finalize(port, pk, args.state)
    finally:
        port.closePort()
    return 0


if __name__ == "__main__":
    sys.exit(main())
