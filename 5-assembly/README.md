# 5. Assembly and bring-up pages

The build guide and the bring-up pages are self-contained HTML files under `../docs/` (images embedded; open them from disk or from GitHub Pages). `../docs/index.html` lists them.

- `../docs/MICRODUCK-BUILD.html`: the assembly guide for this robot, built from the project's guide data at the foundation state: 11 chapters, 82 steps, 176 parts, with a 3D view of every step, the fastener for every hole, and the cable routes. Follow it in order after printing block 1 and setting up the servos of block 2. Its subtitle still gives the voltages of an earlier power version (15 V in, 7.40 V servo rail, Raspberry Pi); `../4-power/README.md` has the current numbers (20 V in, 7.0 V rail, A7Z).
- `../docs/A7Z-PINS.html`: every Dupont wire on the A7Z header, on photos, with the pin numbers of `../3-brain-and-senses/README.md`. In Chinese; the pin numbers, colours and photos carry the content.
- `../docs/A7Z-WIRES.html`: the one-picture wire summary (click a pin or wire to isolate it).
- `../docs/A7Z-ANTENNA.html`: sticking the Wi-Fi antenna into the head cap and routing its pigtail.
- `../docs/A7Z-TOUCH.html`: building the five touch pads and the XIAO board in the cap, with the bench test.
- `../docs/BATTERY-WIRING.html`: the battery backpack wiring (power route B; designed, not yet run).
- `../docs/BRINGUP.html`: the step-by-step bring-up written for the Raspberry Pi Zero W head, in Chinese. The Pi was replaced by the A7Z on 2026-10-17, so its OS and camera steps are history; its OpenRB, servo-chain, amplifier and head-fit steps still describe this robot and the A7Z pages link into it.
- `../docs/parts-sheets/`: one page per print release with a picture and the size of every part (V1.6, V1.9, V1.17, V1.20, V1.21, V1.22, V1.24, V1.25, V1.31).

Every page was rendered in headless Chrome at 1280 px and 390 px width before publication: no horizontal overflow, no missing image, no console error, and controls at least 16 px on the phone width (`../scripts/probe_docs.mjs`, results in `../scripts/probe/results.json`).
