"""Live view of the XIAO touch pads: one bar per pad, the reading and its change since start. Ctrl-C to quit.

    ~/.venvs/touch/bin/python touch_live.py
"""
import glob
import sys

import serial

PADS = ['L1', 'R1', 'L2', 'R2', 'M']
FULL = 2000          # counts for a full bar

ports = sorted(glob.glob('/dev/cu.usbmodem*'))
if not ports:
    sys.exit('找不到 XIAO：插上 USB-C')
ser = serial.Serial()
ser.port, ser.baudrate, ser.timeout, ser.dtr, ser.rts = ports[0], 115200, 0.2, False, False
ser.open()

start = None
print('\033[2J')
try:
    while True:
        p = ser.readline().decode(errors='replace').strip().split(',')
        if len(p) != 7 or p[0] != 'T':
            continue
        try:
            v = [int(x) for x in p[2:]]
        except ValueError:
            continue
        if max(v) > 100000:          # a line cut in half when the port opened
            continue
        start = start or v
        out = ['\033[H按铜箔看条的变化（Ctrl-C 退出）\n']
        for name, now, s in zip(PADS, v, start):
            d = now - s
            n = max(0, min(40, round(40 * d / FULL)))
            out.append(f'{name:>2}  {now:6d}  {d:+6d}  {"█" * n:<40}')
        print('\n'.join(out), flush=True)
except KeyboardInterrupt:
    print()
