#!/usr/bin/env python3
"""Write 1-printing/PLATES.md: the sliced plate files of every release on the robot, with size and sha256.

The plate files (Bambu X1C .gcode.3mf and Elegoo Centauri Carbon .gcode, one per colour and release, about 200 MB in
all) are too large for the git tree. They are staged in a folder outside the repository and attached to a GitHub
Release; this manifest lets a reader check what they downloaded.

Run:  python3 scripts/plates_manifest.py --staging ../cmu-microduck-releases-staging
"""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

STATUS = {
    'V1.6': 'printed (head, speaker, trim, jaw support, neck pitch bracket, IMU holder, OpenRB tray; several parts since replaced, see PARTS.md)',
    'V1.8': 'printed (lower head shell, jaw frame, face, head cap, eye trim, rear pack, pack cover, neck ring and shims)',
    'V1.9': 'printed (Orange plate: rear pack with the IMU rib, head cap, speaker retainer, wire clips)',
    'V1.17': 'printed (rear converter box frame and cap, white shells and thighs, A7Z head cap and face, cap clip)',
    'V1.20': 'printed (box cap with 3 mm screw floors, battery backpack frame and cap)',
    'V1.21': 'printed in black although the plate file says Orange (sole molds for a hot-glue sole route that was dropped on 2026-10-19; not needed for the robot)',
    'V1.22': 'printed (ankle rework: bases and sides, sleeves, slip-fit feet)',
    'V1.24': 'printed (two-half ankles)',
    'V1.25': 'released 2026-10-20, round-bore inner halves; not recorded as printed',
    'V1.28': 'printed (right lower-leg link with the sleeve printed on)',
    'V1.31': 'released 2026-10-23, backpack frame with the wider DFR1202 slot; not printed',
}
SUPERSEDED_PLATES = {
    ('V1.6', 'Yellow'): 'lower head shell replaced by V1.8', ('V1.6', 'White'): 'face panel replaced by V1.8 and V1.17',
    ('V1.6', 'Orange'): 'head cap replaced by V1.8 and V1.9/V1.17, speaker cradle replaced by V1.9, IMU clamp replaced by the V1.8 pack',
    ('V1.6', 'Black'): 'OpenRB tray and IMU cover replaced by the V1.8 pack, neck pitch ring replaced by V1.8; jaw support, sliding ring and neck pitch bracket still used',
    ('V1.8', 'Orange'): 'head cap replaced by V1.9/V1.17, rear pack replaced by V1.9',
    ('V1.8', 'White'): 'face panel replaced by V1.17',
    ('V1.8', 'Black'): 'rear pack cover replaced by the V1.17 box frame; eye trim, neck ring and shims still used',
    ('V1.9', 'Orange'): 'head cap and cap clip replaced by V1.17; rear pack, speaker retainer and three clips still used',
    ('V1.17', 'Orange'): 'box cap replaced by V1.20; frame and cap clip still current',
    ('V1.20', 'Orange'): 'backpack frame replaced by V1.31; box cap and backpack cap still current',
    ('V1.22', 'Orange'): 'ankle bases and sides replaced by V1.24/V1.25',
    ('V1.22', 'Black'): 'right sleeve replaced by the V1.28 link; left sleeve still used',
    ('V1.24', 'Orange'): 'inner halves replaced by V1.25 (round bore)',
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--staging', type=Path, required=True)
    args = ap.parse_args()
    files = sorted(p for p in args.staging.iterdir() if p.suffix in ('.gcode', '.3mf'))
    pics = sorted(p for p in args.staging.iterdir() if p.suffix == '.png')
    L = ['# Sliced plate files', '',
         'One plate per colour and release, sliced on the project\'s pipeline for the two RoboClub printers: Bambu Lab X1C '
         '(`.gcode.3mf`, open in Bambu Studio or send to the printer; never re-open the sliced file in Orca, see PRINT-LESSONS.md) '
         'and Elegoo Centauri Carbon (`.gcode`). The files are not in the git tree (about 200 MB together); they are published '
         'as release assets of this repository. Check a download against the sha256 below. The STL of every part is in `stl/` '
         'if you prefer to slice yourself: PLA, 0.4 mm nozzle, 0.2 mm layers, four walls, tree supports where PARTS.md says so, '
         'brim per part as in PRINT-LESSONS.md.', '',
         'Plates of a release that a later release replaced in part are still listed: the note says which parts to skip. '
         'To print the robot from scratch, use PARTS.md as the shopping list and these plates only where every part on the plate is still current.', '']
    byver: dict[str, list] = {}
    for p in files:
        m = re.match(r'cmu-microduck_(V1\.\d+)_(\w+)_(Bambu-X1C|Elegoo-Centauri-Carbon)', p.name)
        if not m:
            continue
        byver.setdefault(m.group(1), []).append((m.group(2), m.group(3), p))

    def vkey(v):
        return tuple(int(x) for x in v[1:].split('.'))
    total = 0
    for v in sorted(byver, key=vkey):
        L.append(f'## {v}: {STATUS.get(v, "")}')
        L.append('')
        for colour, machine, p in sorted(byver[v]):
            size = p.stat().st_size
            total += size
            note = SUPERSEDED_PLATES.get((v, colour), 'all parts current')
            L.append(f'- `{p.name}` ({size / 1e6:.1f} MB) {colour} plate, {machine.replace("-", " ")}: {note}.  ')
            L.append(f'  sha256 `{sha256(p)}`')
        for pic in pics:
            if pic.name.startswith(v + '_'):
                L.append(f'- plate picture `{pic.name}`')
        L.append('')
    L.append(f'Total {total / 1e6:.0f} MB in {len(files)} files.')
    (ROOT / '1-printing' / 'PLATES.md').write_text('\n'.join(L) + '\n')
    print(f'{len(files)} files, {total / 1e6:.0f} MB')


if __name__ == '__main__':
    main()
