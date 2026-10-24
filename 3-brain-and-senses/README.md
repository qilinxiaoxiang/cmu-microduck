# 3. Brain and senses

The head holds the computer and every sensor: a Radxa Cubie A7Z (Allwinner A733, 40-pin header) screwed to the rails of the V1.17 head cap, the Radxa Camera 13M 214 behind the eye on the face panel, a BNO085 IMU in the rear pack (wired up to the head), a MAX98357A I2S amplifier with the speaker in the head, and a Seeed XIAO ESP32-S3 reading five copper touch pads glued inside the cap. Seventeen Dupont wires meet the A7Z header; `../docs/A7Z-PINS.html` shows every one of them on photos, `../docs/A7Z-WIRES.html` is the one-picture summary, `../docs/A7Z-ANTENNA.html` places the Wi-Fi antenna, `../docs/A7Z-TOUCH.html` builds the touch pads.

## Pin map (A7Z 40-pin header)

Inner row, odd pins: 1 IMU 3.3 V (red), 3 IMU SDA (blue, TWI7), 5 IMU SCL (yellow, TWI7), 7 UART2 TX (green, to the OpenRB J12 Rx), 9 IMU GND (black), 11 UART2 RX (white, from the OpenRB J12 Tx), 17 touch board 3.3 V, 25 touch GND, 29 touch SCL (XIAO D5), 31 touch SDA (XIAO D4), 35 amplifier LRC, 39 amplifier GND. Edge row, even pins: 2 5 V in (red), 4 amplifier Vin, 6 GND (black), 12 amplifier BCLK, 40 amplifier DIN. Pins 8 and 10 stay empty (debug console). The camera board covers the edge-row plugs of pins 10 to 34, so those wires bend down at the plug.

## Operating system and first boot

Image: Radxa's unified Debian 11 CLI image for the A733, release rsdk-r6 (`radxa-a733_bullseye_cli_r6.output_512.img.xz` from the Cubie A7Z download page on docs.radxa.com; check the sha512 they publish). Write it to a 16 GB or larger microSD. Before the first boot, on the card's FAT partition: enable the ssh service unconditionally in `config/before.txt` (the stock image enables it only when no display is found), add a NetworkManager profile for your Wi-Fi network, and put your public key where sshd will read it (we added `/etc/ssh/authorized_keys.d/%u` to `AuthorizedKeysFile` and placed the key for user `radxa`). Change the default password at first login. The board comes up on ssh about 35 s after power. Give the `radxa` user passwordless sudo (`/etc/sudoers.d/90-radxa-nopasswd`) if you want to run the install scripts without typing. Wi-Fi: the AC019 FPC antenna is stuck under the front of the cap crown; at a new location, a phone hotspot is the easiest network, turned on before the robot is powered.

## Device-tree overlays

Two of our overlays go into `/boot/dtbo/` (or wherever `rsetup` keeps enabled overlays on your image) and are compiled from `overlays/`:

- `duck-twi7-engine.dts` -> `zz-duck-twi7-engine.dtbo`: puts TWI7 (header pins 3/5, `/dev/i2c-7`) in engine mode. Radxa's own "Enable TWI7" overlay leaves the sunxi-twi driver in drv mode, which wedges after boot, after zero-length writes and during an IMU reset; this overlay must sort after Radxa's (hence the `zz-` prefix).
- `duck-twi0-touch.dts` -> `zz-duck-twi0-touch.dtbo`: TWI0 on PB2/PB3 (header pins 29/31, `/dev/i2c-0`) for the touch board. No stock overlay serves these pins on the A7Z.

Also enable Radxa's "Enable UART2" (pins 7/11, `/dev/ttyAS2`) and "Enable I2S0" overlays in `rsetup`. Compile with `dtc -@ -I dts -O dtb -o zz-duck-twi7-engine.dtbo duck-twi7-engine.dts`, copy, reboot, and check `ls /dev/i2c-7 /dev/i2c-0 /dev/ttyAS2`.

## IMU

A BNO085 at I2C address 0x4A on `/dev/i2c-7`. `imu/microduck_rt/imu_reader.py` (from AI-FanGe's runtime) and `imu/imu_read.py` read it; the runtime in `6-run/` reads it directly in the same process as the control loop (`--imu-bus 7`) at the full 50 samples per second with no added delay. `imu/pi_imu_uart.py` and the `systemd/duck-imu.service` unit are the earlier arrangement in which the head board only streamed the IMU over the J12 UART while a Mac drove the servos over USB; they still work for bench runs with the Mac in the loop (the unit files say `User=pi` and `/home/pi` from that era and need the user and paths changed for the A7Z).

## UART to the OpenRB

UART2 on pins 7/11 goes to the OpenRB-150's J12 at 500 kbaud (the A7Z UART clock cannot make 1 Mbaud). The OpenRB firmware in `2-servos-openrb/` serves this port as a second host, so the head computer drives all 15 servos alone: 15 of 15 answer at 500 kbaud.

## Speaker

Wire the MAX98357A as in the pin map and leave its GAIN and SD pads open (9 dB). Install `audio/asound.conf` as `/etc/asound.conf`: it routes the default ALSA device through a software volume with a hard ceiling of -3 dB, which keeps a full-scale signal at about 0.8 W into the 1 W speaker. Mask PulseAudio for the user so programs reach ALSA directly. `aplay -L` must list the default device; `audio/duck_sound.py` plays one call through it, and `audio/build_duck_calls.py` makes the call files (Pollen's simulator voices, high-passed at 500 Hz, -1 dBFS) that the runtime's `quack` command picks from.

## Touch board

Five pads of 5 mm copper tape inside the head cap (L1 and R1 18 mm long, L2, R2 and M 12 mm) each with a lead soldered across, to XIAO ESP32-S3 inputs D0, D1, D2, D3 and D8. The XIAO runs `touch/firmware/touch_xiao/touch_main.cpp` (`touch/firmware/flash.sh` compiles and flashes it with `arduino-cli` over USB-C): it samples the pads at 50 Hz, prints them on USB serial, and serves them as an I2C slave at address 0x2A (a 24-byte block) on D4/D5, which go to A7Z pins 31/29. `touch/firmware/touch_live.py` (Mac, USB) and `touch_live_a7z.py` (A7Z, I2C) show a live bar per pad; `touch_bench.py` is the acceptance test (fingertip at least 5x the resting noise, no cross-trigger). The runtime reads the block every tick (`--touch-bus auto`) for the graded hold. `touch/touch_layout.png` and `touch/touch_routes.json` give the pad positions and wire routes; `../docs/A7Z-TOUCH.html` is the picture-first build page.

## Camera

The Radxa Camera 13M 214 plugs into the A7Z CSI connector and screws to the four bosses of the V1.17 face panel with M2 x 4. It captures 1080p on `/dev/video0` once the Radxa ISP is enabled (`en-awisp=1`). The streaming scripts under `camera/` (`duck_cam.py`, `duck_cam.sh`, `CAMERA.md`, `systemd/duck-cam.service`) are from the Raspberry Pi camera era (`rpicam-vid`) and are kept as the description of what the stream looked like; they do not run on the A7Z as they stand. On this foundation the robot's app pulls the duck's-eye view with a V4L2 capture over ssh; the orange-target detector was calibrated on the earlier Pi camera and still needs recalibration on this one.

## Starting the brain and keeping records

`a7z/install_teleop.sh` copies the runtime closure from `6-run/` to `~/rt/microduck-sim/...` on the board, builds the quack calls, and checks the venv, the policies and the ALSA default device; `a7z/duck-run.sh <suffix>` starts the brain in monitor mode (torque untouched) with its log under `~/duck-logs/`. The brain does not start at boot. `a7z/install_blackbox.sh` installs the 10 Hz flight recorder (`blackbox.py`, `systemd/duck-blackbox.service`, `BLACKBOX.md`); `a7z/thermal_log.py` logs SoC temperature and CPU clocks; `a7z/pwrlog.py` logs the supply.

## Thermal limit (read before you run it for long)

In the closed V1.17 head the A7Z has no airflow. Measured on the robot: the SoC reaches 85 C after 5 minutes and 93 C after 9 minutes; the thermal governor (which trips at 60 C) pins both CPU clusters at 416 MHz, the 50 Hz brain loop slows to a p50 of 23.6 ms and p90 of 24.6 ms (about 42 ticks per second), and the board reset at about 90 C in stand61 and twice within 10 s of a walk start (3 resets in 25 minutes). In the run of 2026-10-23 21:01 the loop ran at 35.7 Hz at 85 to 86 C and walk61 diverged within 0.4 s of the walk start. The builder's working figure is about 30 minutes of running per session before the head must cool. The acceptance for keeping the board in the head would be a p90 under 18 ms and at least 49 ticks per second after a one-hour soak; the foundation does not meet it. The project's answer (a roof saddle with a heatsink and a fan) is an extension and is not in this repository.
