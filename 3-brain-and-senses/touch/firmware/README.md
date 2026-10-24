# Touch readout firmware and bench test

- `touch_xiao/touch_main.cpp`: XIAO ESP32-S3 firmware. Five pads at 50 Hz (L1 D0, R1 D1, L2 D2, R2 D3, M D8), USB serial lines `T,<ms>,<L1>,<R1>,<L2>,<R2>,<M>`, and an I2C slave at 0x2A on D4/D5 (24-byte block: sequence, then the five counts, uint32 LE). The I2C side answers the A7Z on header pins 29 (SCL) and 31 (SDA) as of 2026-10-20; bit-banged reads see a 0x55 filler byte first; reads through the kernel bus come back aligned.
- `flash.sh`: compile and flash over USB-C (`arduino-cli`, core `esp32:esp32` 3.3.12, Homebrew `universal-ctags`).
- `touch_bench.py`: acceptance item 2 of `../PLAN.md` (fingertip delta at least 5x resting noise, no cross-trigger). Run with `~/.venvs/touch/bin/python touch_bench.py --pads L1`; it writes `touch_bench_<time>.json` here.
- `touch_live.py`: live bar per pad over USB serial on the Mac.
- `touch_live_a7z.py`: the same live view on the A7Z over I2C (`scp` it to the A7Z, `ssh -t a7z python3 touch_live_a7z.py`). It reads `/dev/i2c-0` (TWI0 on pins 29/31 from `guide/firmware/pi/duck-twi0-touch.dts`, installed 2026-10-21) and falls back to bit-banging gpiochip0 lines 34/35 when that bus is missing.
