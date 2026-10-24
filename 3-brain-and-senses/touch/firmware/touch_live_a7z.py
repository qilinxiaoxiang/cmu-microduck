"""Live view of the touch pads on the A7Z: one bar per pad, read from the XIAO (I2C 0x2A) on header pins 29/31.

    python3 touch_live_a7z.py        (on the A7Z, no root; Ctrl-C to quit)

With the TWI0 overlay for pins 29 (PB2, SCL) and 31 (PB3, SDA) loaded (guide/firmware/pi/duck-twi0-touch.dts) it reads
/dev/i2c-N; without it, it bit-bangs the two lines through the GPIO character device (gpiochip0 lines 34 and 35,
open-drain), the same method as ~/bb_i2c.py used for the IMU on 2026-10-18.
Block from touch_main.cpp: 24 bytes, uint32 LE sequence number then the counts of L1, R1, L2, R2, M.
"""
import ctypes
import fcntl
import glob
import os
import struct
import time

CHIP, SDA_LINE, SCL_LINE, ADDR = 0, 35, 34, 0x2A
PADS = ['L1', 'R1', 'L2', 'R2', 'M']
FULL = 2000          # counts for a full bar
T = 5e-6


class HandleReq(ctypes.Structure):
    _fields_ = [("lineoffsets", ctypes.c_uint32 * 64), ("flags", ctypes.c_uint32),
                ("default_values", ctypes.c_uint8 * 64), ("consumer_label", ctypes.c_char * 32),
                ("lines", ctypes.c_uint32), ("fd", ctypes.c_int)]


class HandleData(ctypes.Structure):
    _fields_ = [("values", ctypes.c_uint8 * 64)]


def _iowr(nr, size):
    return (3 << 30) | (size << 16) | (0xB4 << 8) | nr


GET_LINEHANDLE = _iowr(0x03, ctypes.sizeof(HandleReq))
GET_VALUES = _iowr(0x08, ctypes.sizeof(HandleData))
SET_VALUES = _iowr(0x09, ctypes.sizeof(HandleData))
OUTPUT, OPEN_DRAIN = 1 << 1, 1 << 3


class Line:
    def __init__(self, chipfd, off):
        r = HandleReq(); r.lineoffsets[0] = off; r.lines = 1
        r.flags = OUTPUT | OPEN_DRAIN; r.default_values[0] = 1; r.consumer_label = b"touch"
        fcntl.ioctl(chipfd, GET_LINEHANDLE, r)
        self.fd, self.d = r.fd, HandleData()

    def set(self, v):
        self.d.values[0] = v; fcntl.ioctl(self.fd, SET_VALUES, self.d)

    def get(self):
        d = HandleData(); fcntl.ioctl(self.fd, GET_VALUES, d); return d.values[0]


KERNEL = next(("/dev/" + n.split("/")[-2] for n in glob.glob("/sys/bus/i2c/devices/i2c-*/of_node")
               if os.path.realpath(n).endswith("/twi@2510000")), None)
if KERNEL:
    bus = os.open(KERNEL, os.O_RDWR)
    fcntl.ioctl(bus, 0x0703, ADDR)  # I2C_SLAVE
else:
    chip = os.open(f"/dev/gpiochip{CHIP}", os.O_RDWR)
    sda, scl = Line(chip, SDA_LINE), Line(chip, SCL_LINE)


def scl_high():
    scl.set(1); t0 = time.time()
    while not scl.get():                 # the XIAO may stretch the clock while it fills the block
        if time.time() - t0 > 0.05:
            raise RuntimeError("SCL held low")
    time.sleep(T)


def start():
    sda.set(1); scl_high(); sda.set(0); time.sleep(T); scl.set(0); time.sleep(T)


def stop():
    sda.set(0); time.sleep(T); scl_high(); sda.set(1); time.sleep(T)


def write_byte(b):
    for i in range(8):
        sda.set((b >> (7 - i)) & 1); time.sleep(T); scl_high(); scl.set(0)
    sda.set(1); time.sleep(T); scl_high(); ack = sda.get() == 0; scl.set(0); time.sleep(T)
    return ack


def read_byte(ack):
    v = 0; sda.set(1)
    for _ in range(8):
        scl_high(); v = (v << 1) | sda.get(); scl.set(0); time.sleep(T)
    sda.set(0 if ack else 1); time.sleep(T); scl_high(); scl.set(0); sda.set(1); time.sleep(T)
    return v


SATURATED = 0x3FFFFF   # touchRead's ceiling: the pad cannot charge (lead shorted to ground or touching metal)


def decode(raw):
    """Bit-banged reads get a filler byte (0x55) first and lose the block's last byte, the top byte of M (always 0);
    a read without the filler is the block as sent. The wrong alignment shifts every count above 0x3FFFFF."""
    for block in (raw[1:] + b'\0', raw):
        b = struct.unpack('<6I', block)
        if max(b[1:]) <= SATURATED:
            return b
    return None


def read_block():
    """One read of exactly 24 bytes: reading more than the XIAO queued leaves filler bytes for later blocks."""
    if KERNEL:
        return decode(os.read(bus, 24))
    start()
    if not write_byte((ADDR << 1) | 1):
        stop(); return None
    raw = bytes(read_byte(i < 23) for i in range(24))
    stop()
    return decode(raw)


start_v, last_seq, ok, bad = None, None, 0, 0
prev_v, same_since = None, time.time()
print('\033[2J')
try:
    while True:
        try:
            b = read_block()
        except (RuntimeError, OSError):
            b = None
        if b is None or (last_seq is not None and not 0 < b[0] - last_seq < 500):
            bad += 1
            last_seq = None if b is None else last_seq
            continue
        last_seq, v = b[0], b[1:]
        ok += 1
        start_v = start_v or v
        if v != prev_v:
            prev_v, same_since = v, time.time()
        out = ['\033[H按铜箔看条的变化（Ctrl-C 退出）\033[K', '\033[K']
        for name, now, s in zip(PADS, v, start_v):
            d = now - s
            n = max(0, min(40, round(40 * d / FULL)))
            if now == SATURATED:
                out.append(f'{name:>2}  {now:7d}  读数顶满：铜箔或引线碰到了金属或地线\033[K')
            else:
                out.append(f'{name:>2}  {now:7d}  {d:+6d}  {"█" * n}\033[K')
        out.append('\033[K')
        if SATURATED in v and time.time() - same_since > 2:
            # touch_main.cpp leaves max_meas_time_us at 0, so a pad that never charges holds the scan on that pad forever
            # and the other pads keep their last count (2026-10-20: M shorted, the four others frozen)
            out.append('扫描卡住了：顶满的那块不放开，其他铜箔都不更新\033[K')
        out.append(f'读到 {ok} 次，丢 {bad} 次（{KERNEL or "程序拨针脚读"}）\033[J')
        print('\n'.join(out), flush=True)
        time.sleep(0.02)
except KeyboardInterrupt:
    print()
