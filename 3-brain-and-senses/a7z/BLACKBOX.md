# A7Z flight recorder

Purpose: when the A7Z hangs, resets itself or loses power while the brain runs, keep a record up to the last fraction
of a second before the stop, on the card and on the Mac, so the cause can be read afterwards.

## What records what

- `pi/blackbox.py` (service `duck-blackbox`, root): every kernel message from `/dev/kmsg` and a 10 Hz system snapshot
  (CPU busy/iowait/irq, load, free memory, pressure, the five busiest processes, processes stuck in D state with their
  kernel wait channel, IRQ counts, Wi-Fi link). Each line is fsynced to `~/duck-logs/blackbox/` as it is written,
  one `kmsg.log` + `sys.jsonl` pair per boot, newest 40 boots kept.
- `pi/thermal_log.py` (service `duck-thermal-log`, already installed): temperatures and CPU clocks at 10 Hz,
  fsynced, `~/duck-logs/thermal.log`.
- `walk_wired.py`: its jsonl log is fsynced every 50 ms (`~/duck-logs/duck_wired_log_*.jsonl`).
- journald: persistent and written every second (`journald-duck-blackbox.conf`); the default waited up to five
  minutes, which is why the crashed boots of 2026-10-21 had no last minutes in the journal.
- `mac/a7z_blackbox_mirror.sh`: streams the current boot's two blackbox files to `~/duck-blackbox/live/` on the Mac
  and logs every link loss with Mac time, so the record survives even a card that loses its last writes.

Blind spot: supply dips. The A7Z has no ADC on its 5 V input, and the servo-reported voltage in the brain log
(0.1 V steps, one servo per 20 ms cycle, about half the samples empty) misses a dip of a few milliseconds. On
2026-10-22 a 20 V 3 A charger behind the 5991 froze the A7Z four times while walking or standing up and none of these
records showed a voltage change; a 20 V 5 A charger ended the stops. A record that stops everywhere in the same 0.1 s
with no kernel warning (and a HOT-BOOT 16 s later, the sunxi watchdog timeout) is the signature of a supply event,
not evidence against one. Seeing the dip itself needs a hardware probe on the 5 V lead.

## Use

1. Install once (A7Z online): `bash a7z/install_blackbox.sh`. It must print `service: active`,
   `kmsg: marker on the card`, `sys: N rows in 2 s` with N at least 5, and where `~/duck-run.sh` sends the brain's
   printed messages.
2. Before a robot test: `bash mac/a7z_blackbox_mirror.sh` in a Terminal tab, left running.
3. After a hang, once the A7Z answers again: `bash mac/a7z_blackbox_collect.sh`. It copies everything to
   `~/duck-blackbox/collected/<time>/` and prints, per boot, whether it ended in a clean shutdown or stopped dead,
   the last system rows and the last kernel lines. `python3 mac/blackbox_report.py ~/duck-blackbox/live` reads the
   Mac copy the same way.

Tests: `python3 -m unittest test_blackbox` in `pi/`.

## What the record can and cannot tell apart

- Kernel or driver hang (cause a): a soft-lockup, hung-task or RCU-stall warning, or a D-state process with its
  kernel stack (sysrq w) before the rows stop. The warnings print within 5-6 s only with
  `90-duck-blackbox.conf` in force; the defaults (20-120 s) fire after the watchdog reset of about 15 s.
- Electrical noise (cause b) or a 5 V sag (cause c): the rows simply stop with no kernel line. A power cut, a
  brownout that wedges the SoC and a silent hard hang all look like this; the next boot's reason (HOT-BOOT = power
  stayed, COLD-BOOT = power came back) and the external measurements below separate them.
- A kernel panic's own text is lost (no pstore on this image: `/sys/fs/pstore` does not exist). Only a serial
  console keeps it.

## On the robot (2026-10-22)

1. A7Z online: `bash a7z/install_blackbox.sh`; all checks pass. Reboot once (`sudo reboot`) and run it again: it must
   report at least one earlier boot on the card.
2. `bash mac/a7z_blackbox_mirror.sh` in its own Terminal tab, left running.
3. 5 V: multimeter on header pins 2 (+) and 6 (-) at the A7Z itself, MIN/MAX mode, reset before each run. A meter
   misses dips shorter than about 100 ms unless it has a 1 ms peak mode; a scope triggered below 4.75 V catches them,
   and a second channel between A7Z ground and OpenRB ground under torque checks cause b.
4. Optional, catches panic text: a 3.3 V USB-UART adapter (club drawer row 2 has FTDI USB; check it is 3.3 V, a
   5 V one can damage the A7Z) on the debug UART, header pins 8 (A7Z TX) and 10 (A7Z RX) plus a ground pin, read with
   `screen /dev/cu.usbserial-* <baud>` after `sudo dmesg -n 8` on the A7Z (the baud is the `console=` entry in
   `/proc/cmdline`, which the installer prints; Allwinner boards usually use 115200). Its ground joins the Mac to the robot's
   grounds: run the MacBook on battery.
5. Runs, each at least 8 min (the longest survival seen was 7.4 min) and twice. The cause-checking runs, cheapest first:
   - A: brain on the A7Z, `monitor` only (torque off, servo bus read only). Survived 7 min on 2026-10-21.
   - B: brain on the A7Z, torque on, stand. The failing case: expect a stop within 1-8 min.
   - C: as B with `--touch-bus none`: removes the TWI0 touch reads.
   - D (not ready): brain on the Mac over USB with the A7Z idle would show whether the A7Z dies from electrical
     causes alone, but the Mac brain needs IMU frames over J12 and nothing on the A7Z sends them yet
     (`pi_imu_uart.py` served the Pi Zero). Without D, a stop in B and C with no kernel line and a clean 5 V reading
     points to noise (b) only by elimination.
6. After each stop: `bash mac/a7z_blackbox_collect.sh` once the A7Z answers (power-cycle it if it does not within
   1 min), then read the report.
