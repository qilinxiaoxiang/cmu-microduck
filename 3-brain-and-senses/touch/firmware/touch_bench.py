"""Bench test for one or more copper pads read through a PLA wall by the XIAO ESP32-S3 (touch_xiao.ino).

Acceptance item 2 of ../PLAN.md: a fingertip through the wall gives a delta at least five times the resting noise,
and the other pads do not cross-trigger. Run on the Mac with the XIAO on USB:

    python3 touch_bench.py --pads L1            # one pad on the bench
    python3 touch_bench.py --pads L1 R1 L2 R2 M # all five, in the cap

Per pad it records 10 s at rest, then 5 s with a fingertip held on the outside of the wall over that pad.
noise = standard deviation at rest; delta = median while touched minus median at rest; ratio = delta / noise.
Cross-trigger: every other connected pad's delta stays below 20 % of the touched pad's delta.
Writes the raw samples and the verdict to touch_bench_<time>.json next to this script.
"""
from __future__ import annotations

import argparse
import glob
import json
import statistics
import sys
import time
from pathlib import Path

import serial

PADS = ['L1', 'R1', 'L2', 'R2', 'M']
RATIO_MIN = 5.0
CROSS_MAX = 0.20


def port() -> str:
    found = sorted(glob.glob('/dev/cu.usbmodem*'))
    if not found:
        sys.exit('No /dev/cu.usbmodem* port: plug the XIAO into the Mac with a data USB-C cable.')
    return found[0]


def record(ser: serial.Serial, seconds: float) -> list[list[int]]:
    ser.reset_input_buffer()
    rows, end = [], time.time() + seconds
    while time.time() < end:
        line = ser.readline().decode(errors='replace').strip()
        parts = line.split(',')
        if len(parts) == 7 and parts[0] == 'T':
            try:
                rows.append([int(p) for p in parts[2:]])
            except ValueError:
                pass
    if len(rows) < seconds * 40:
        sys.exit(f'Only {len(rows)} samples in {seconds:.0f} s (expected about {seconds * 50:.0f}): is touch_xiao.ino flashed?')
    return rows


def column(rows: list[list[int]], i: int) -> list[int]:
    return [r[i] for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--pads', nargs='+', default=['L1'], choices=PADS)
    ap.add_argument('--wall', default='1.7 mm PLA', help='what the finger touches through, for the record')
    args = ap.parse_args()

    p = port()
    ser = serial.Serial()   # open with DTR and RTS low: on the S3 USB serial they reset the chip
    ser.port, ser.baudrate, ser.timeout, ser.dtr, ser.rts = p, 115200, 0.2, False, False
    ser.open()
    time.sleep(1.0)
    used = [PADS.index(n) for n in args.pads]
    result = {'port': p, 'wall': args.wall, 'pads': {}, 'time': time.strftime('%Y-%m-%dT%H:%M:%S%z')}

    for name in args.pads:
        i = PADS.index(name)
        input(f'\n[{name}] Hands off every pad and wire, then press Enter (10 s at rest) ')
        rest = record(ser, 10)
        input(f'[{name}] Hold one fingertip on the wall over pad {name}, keep still, press Enter (5 s) ')
        touch = record(ser, 5)
        print(f'[{name}] Done, take the finger off.')

        noise = statistics.pstdev(column(rest, i)) or 1.0
        base = statistics.median(column(rest, i))
        delta = statistics.median(column(touch, i)) - base
        cross = {PADS[j]: statistics.median(column(touch, j)) - statistics.median(column(rest, j)) for j in used if j != i}
        cross_ok = all(abs(d) < CROSS_MAX * abs(delta) for d in cross.values()) if delta else False
        ok = delta / noise >= RATIO_MIN and cross_ok
        result['pads'][name] = {'rest_median': base, 'rest_noise_std': round(noise, 1), 'touch_delta': delta,
                                'ratio': round(delta / noise, 1), 'cross_delta': cross, 'pass': ok,
                                'rest': rest, 'touch': touch}
        print(f'[{name}] rest {base:.0f}, noise {noise:.1f}, touch delta {delta:+.0f}, ratio {delta / noise:.1f} '
              f'(need >= {RATIO_MIN:.0f}), cross {cross} -> {"PASS" if ok else "FAIL"}')

    out = Path(__file__).with_name(f'touch_bench_{time.strftime("%Y%m%d_%H%M%S")}.json')
    out.write_text(json.dumps(result, indent=1))
    verdict = all(v['pass'] for v in result['pads'].values())
    print(f'\n{"PASS" if verdict else "FAIL"}  ({out})')


if __name__ == '__main__':
    main()
