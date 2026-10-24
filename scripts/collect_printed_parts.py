#!/usr/bin/env python3
"""Derive the as-built printed part set of the CMU MicroDuck foundation (2026-10-23) from the release records.

Inputs (read only), all inside the robotics working tree given with --robotics:
  build-pack-20260913/redesign-20260913/print-manifest.json        the 89-instance community batch printed 2026-10-01
  build-pack-20260913/redesign-20260913/printing/copy-manifest.json  object id -> instance index of that batch
  guide/print/release-V1.6-final/final-V1.6.json and
  guide/print/release-V1.*/manifest-V1.*.json                      our incremental releases (parts, replaced stock,
                                                                   retired parts, print poses, sha256)

The releases are applied in order (CHAIN below). A later release's `retiredParts` removes earlier parts; its
`replacesStockIds` marks community instances as replaced. Releases after the foundation (V1.29 saddle, V1.30 U20
camera face and neck exit, V1.32) are not applied.

Outputs under --out (default 1-printing next to this script's parent):
  stl/our-parts/<Colour>/<key>.stl   our parts in print pose (bed = z 0) when the release recorded one, else in the
                                     robot frame (flagged in PARTS.md)
  stl/community/<file>.stl           the retained community parts in the 10/1 print orientation
  parts.json                         the machine-readable list with sha256 of every copied file
  PARTS.md                           the human list

Run:  python3 scripts/collect_printed_parts.py --robotics ~/code/robotics/microduck-sim
      (with trimesh installed, parts without a recorded print STL are rotated into their print pose)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

try:
    import numpy as np
    import trimesh
except ImportError:  # pragma: no cover
    trimesh = None

HERE = Path(__file__).resolve().parent

# (version, manifest path relative to microduck-sim, print status on 2026-10-23, source of that status)
CHAIN = [
    ('V1.6', 'guide/print/release-V1.6-final/final-V1.6.json', 'printed',
     'the V1.7 and V1.8 release records build on "the printed V1.6/V1.7 set"'),
    ('V1.7', 'guide/print/release-V1.7/manifest-V1.7.json', 'printed',
     'manifest-V1.8.json: "on top of the printed V1.6/V1.7 set"'),
    ('V1.8', 'guide/print/release-V1.8/manifest-V1.8.json', 'printed',
     'manifest-V1.9.json: "on top of the printed V1.8 set"'),
    ('V1.9', 'guide/print/release-V1.9/manifest-V1.9.json', 'printed',
     'manifest-V1.17.json baseline: "printed V1.8 set with the V1.9 Orange plate"'),
    ('V1.17', 'guide/print/release-V1.17/manifest-V1.17.json', 'printed',
     'manifest-V1.18.json: "V1.17 is the printed baseline (the builder started printing it on 2026-10-15)"'),
    ('V1.20', 'guide/print/release-V1.20/manifest-V1.20.json', 'printed',
     'manifest-V1.21.json: "V1.20 is printed (the builder 2026-10-19)"'),
    ('V1.21', 'guide/print/release-V1.21/manifest-V1.21.json', 'printed (in black, not the orange of the plate file)',
     'manifest-V1.23.json retired list: "V1.21 mold (printed black 2026-10-19)"'),
    ('V1.22', 'guide/print/release-V1.22/manifest-V1.22.json', 'printed',
     'manifest-V1.24.json: "V1.22 is printed (the builder 2026-10-20)"'),
    ('V1.24', 'guide/print/release-V1.24/manifest-V1.24.json', 'printed',
     'manifest-V1.25.json: "V1.22 and V1.24 are printed"'),
    ('V1.25', 'guide/print/release-V1.25/manifest-V1.25.json', 'released 2026-10-20; the robot carries the V1.24 halves',
     'FOUNDATION-20261023.md lists V1.22/V1.24/V1.25 for the ankle; no release record says V1.25 was printed'),
    ('V1.28', 'guide/print/release-V1.28/manifest-V1.28.json', 'printed',
     'FOUNDATION-20261023.md: "the one-piece right lower-leg link (V1.28)" is on the robot'),
    ('V1.31', 'guide/print/release-V1.31/manifest-V1.31.json', 'released 2026-10-23, not printed',
     'FOUNDATION-20261023.md: "the battery backpack frame (V1.20, being replaced by V1.31)"'),
]

# Community (10/1 batch) instances that V1.6 to V1.8 retired. Index = position in print-manifest.json instances.
# Reasons from guide/print/make_parts_sheet.py (RETIRED) and manifest-V1.8.json prototypeScope.
RETIRED_STOCK = {
    0: ('Integrated power support', 'replaced by the V1.8 rear electronics pack'),
    1: ('Small-regulator cover', 'no small regulator in this build'),
    2: ('Jaw-clearance head cap with USB service window', 'replaced by the head cap releases'),
    3: ('Torso IMU clamp', 'the BNO085 sits on the V1.9 rear pack rib'),
    4: ('IMU rear cover', 'same'),
    5: ('Eleven-fuse carrier', 'no fuses in the harness'),
    6: ('Coaxial jaw motor support', 'the open jaw support (V1.6 jaw_support_original) is used instead'),
    7: ('Lower head shell', 'replaced by the V1.8 lower head shell'),
    8: ('Moving jaw frame', 'replaced by the V1.8 jaw frame with the lower lip'),
    9: ('Left shell', 'replaced by the white V1.17 left torso shell'),
    10: ('Right shell', 'replaced by the white V1.17 right torso shell'),
    17: ('Original PCB retaining strip', 'battery-bay part of the upstream design, not used'),
    18: ('Neck U bracket', 'replaced by the V1.6 neck pitch bracket with integral screw seats'),
    24: ('Fixed upper lip pad', 'printed as part of the V1.8 lower head shell'),
    25: ('Moving lower lip pad', 'printed as part of the V1.8 jaw frame'),
    28: ('Eye outer ring', 'replaced by the eye trim'),
    84: ('Face panel and Pi mount', 'replaced by the face panel releases'),
    85: ('Open regulator insert', 'replaced by the V1.8 rear electronics pack'),
    86: ('Camera tilt foot', 'the camera sits in the eye'),
    87: ('Camera cradle', 'same'),
    88: ('Audio carrier', 'the speaker sits in the V1.9 retainer in the head cap'),
}

# Parts of an earlier release that a later release made obsolete without a `retiredParts` entry.
# version -> {key: reason}; applied before that version's parts are added.
EXTRA_RETIRED = {
    'V1.8': {
        'openrb_tray': 'manifest-V1.8.json: the rear electronics pack replaces the OpenRB tray',
        'imu_cover': 'manifest-V1.8.json: the rear electronics pack replaces the IMU clamp and cover',
        'imu_clamp': 'manifest-V1.8.json: the rear electronics pack replaces the IMU clamp and cover',
        'camera_retainer': 'manifest-V1.8.json: the V1.8 face plate carries direct camera screws',
    },
    'V1.9': {
        'speaker_cradle': 'the V1.9 speaker retainer in the head cap replaces the V1.6 speaker cage (guide/content/build_guide_data.py)',
        'speaker_keeper': 'same',
    },
    'V1.17': {
        'rear_pack_cover': 'manifest-V1.17.json retired list: replaced by the rear converter box frame, which carries the same cover plate',
    },
    'V1.28': {
        'ankle_sleeve_right': 'manifest-V1.28.json: the right link carries its sleeve printed on',
    },
}

# Plain names for the release keys (from the release records and the build guide).
NAMES = {
    'head_bottom': 'Lower head shell (upper lip printed on, no beak-roof window)',
    'jaw_frame': 'Jaw frame with the lower lip',
    'face_panel_a7z': 'Face panel for the Radxa Camera 13M 214 (A7Z head)',
    'head_cap_a7z': 'Head cap for the Radxa Cubie A7Z',
    'eye_trim': 'Eye trim',
    'jaw_support_original': 'Jaw support (open, original style)',
    'mouth_sliding_ring': 'Jaw sliding ring',
    'neck_pitch_integrated_1mm_seats': 'Neck pitch bracket with integral 1 mm screw seats',
    'neck_pitch_ring': 'Head-pitch sliding ring',
    'neck_ring_shim_1mm': 'Head-pitch ring shim, 1 mm (optional)',
    'neck_ring_shim_2mm': 'Head-pitch ring shim, 2 mm (optional)',
    'rear_pack': 'Rear electronics pack (OpenRB-150 upright, BNO085 rib, shell seat bars)',
    'rear_frame': 'Rear converter box frame (layout F)',
    'rear_lid': 'Rear converter box cap, 3 mm screw floors',
    'shell_left_v20': 'Left torso shell, screwed to the pack',
    'shell_right_v20': 'Right torso shell, screwed to the pack',
    'thigh_left': 'Left thigh body (community part reprinted in white)',
    'thigh_right': 'Right thigh body (community part reprinted in white)',
    'speaker_retainer_v19': 'Speaker retainer frame in the head cap',
    'clip_torso_v19': 'Neck wire clip, torso end (printed, not fitted)',
    'clip_bracket_v19': 'Neck wire clip, bracket (printed, not fitted)',
    'clip_head_v19': 'Neck wire clip, head end (printed, not fitted)',
    'clip_cap_a7z': 'Cap wire clip with the micro HDMI notch (printed, not fitted)',
    'battery_backpack_frame': 'Battery backpack frame (DFR1202 slot widened in V1.31)',
    'battery_backpack_cap': 'Battery backpack cap, 3 mm screw floors',
    'hotglue_mold_left': 'Left foot sole mold (tool)',
    'hotglue_mold_right': 'Right foot sole mold (tool)',
    'ankle_sleeve_left': 'Left ankle sleeve, 10.4 mm bore',
    'foot_left_slipfit': 'Left foot, slip fit on the ankle',
    'foot_right_slipfit': 'Right foot, slip fit on the ankle',
    'ankle_outer_left': 'Left ankle outer half, on the servo horn',
    'ankle_inner_left': 'Left ankle inner half, on the sleeve (round bore)',
    'ankle_outer_right': 'Right ankle outer half, on the servo horn',
    'ankle_inner_right': 'Right ankle inner half, on the sleeve (round bore)',
    'lower_right': 'Right lower-leg link with the ankle sleeve printed on',
}

NOT_FITTED = {'clip_torso_v19', 'clip_bracket_v19', 'clip_head_v19', 'clip_cap_a7z'}
TOOLS = {'hotglue_mold_left', 'hotglue_mold_right'}
OPTIONAL = {'neck_ring_shim_1mm', 'neck_ring_shim_2mm'}
BATTERY_ROUTE = {'battery_backpack_frame', 'battery_backpack_cap'}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def scrub(text: str) -> str:
    """The release records name the builder in their notes; the public tree keeps the name only in LICENSE and README."""
    return text.replace("Shawn's", "the builder's").replace('Shawn', 'the builder')


def rel(path: str, root: Path) -> str:
    """A manifest path made relative to the microduck-sim tree (no user paths in the output)."""
    p = Path(path)
    try:
        return str(p.relative_to(root))
    except ValueError:
        return p.name


def base_key(text: str) -> str:
    """'face_panel (V1.8)' -> 'face_panel'; 'ankle_inner_left_V1.24' -> 'ankle_inner_left'."""
    k = re.split(r'[ (,]', text.strip())[0]
    return re.sub(r'_V\d+\.\d+$', '', k)


def first_sentence(text: str, limit: int = 240) -> str:
    text = (text or '').replace('\n', ' ').strip()
    m = re.match(r'(.+?\.)(\s|$)', text)
    s = m.group(1) if m else text
    return s if len(s) <= limit else s[:limit].rsplit(' ', 1)[0] + ' ...'


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--robotics', type=Path, required=True, help='path of the microduck-sim tree')
    ap.add_argument('--out', type=Path, default=HERE.parent / '1-printing')
    args = ap.parse_args()
    root = args.robotics.resolve()
    out = args.out.resolve()

    instances = json.loads((root / 'build-pack-20260913/redesign-20260913/print-manifest.json').read_text())['instances']
    copy_records = json.loads((root / 'build-pack-20260913/redesign-20260913/printing/copy-manifest.json').read_text())['copy_records']
    object_to_index = {str(r['object_id']): r['manifest_instance_index'] for r in copy_records if r.get('object_id') is not None}

    parts: dict[str, dict] = {}
    removed: list[dict] = []
    replaced_stock: dict[int, str] = {}  # instance index -> replaced by key

    def retire(key: str, version: str, reason: str) -> None:
        if key in parts:
            rec = parts.pop(key)
            removed.append({'key': key, 'version': rec['version'], 'retiredBy': version, 'reason': reason})

    for version, mpath, status, status_source in CHAIN:
        m = json.loads((root / mpath).read_text())
        for r in m.get('retiredParts', []):
            text = r.get('key') or r.get('part') or ''
            if r.get('stockId') is not None and str(r['stockId']) in object_to_index:
                replaced_stock[object_to_index[str(r['stockId'])]] = f"{version}: {r.get('reason', '')}"
            retire(base_key(text), version, r.get('reason', ''))
        for key, reason in EXTRA_RETIRED.get(version, {}).items():
            retire(key, version, reason)
        for p in m['parts']:
            key = p['key']
            if key in parts:  # same key re-released: the newer geometry wins
                removed.append({'key': key, 'version': parts[key]['version'], 'retiredBy': version,
                                'reason': 'same part re-released'})
            for sid in p.get('replacesStockIds', []):
                idx = object_to_index.get(str(sid))
                if idx is None:
                    print(f'warning: {version} {key} replaces unknown stock id {sid}')
                else:
                    replaced_stock[idx] = f'{version} {key}'
            print_stl = ((p.get('poseCheck') or {}).get('printStl') or {}).get('path')
            parts[key] = {
                'key': key,
                'name': NAMES.get(key, key.replace('_', ' ')),
                'version': version,
                'status': status,
                'statusSource': status_source,
                'color': p['color'],
                'quantity': int(p.get('quantity', 1)),
                'sourceStl': rel(p['path'], root),
                'sourceSha256': p.get('sha256'),
                'printStl': rel(print_stl, root) if print_stl else None,
                'sourceToPrint': p.get('sourceToPrint'),
                'sourceFrame': p.get('sourceFrame'),
                'pose': first_sentence(p.get('poseOrigin', '')),
                'reason': first_sentence(p.get('changeReason', ''), 400),
                '_abs_source': p['path'],
                '_abs_print': print_stl,
            }

    # ---- copy our parts
    our_dir = out / 'stl' / 'our-parts'
    if our_dir.exists():
        shutil.rmtree(our_dir)
    for rec in parts.values():
        dest_dir = our_dir / rec['color']
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{rec['key']}.stl"
        src_print = rec.pop('_abs_print')
        src_world = rec.pop('_abs_source')
        frame = 'print pose (bed at z 0)'
        if src_print and Path(src_print).exists():
            shutil.copyfile(src_print, dest)
        elif trimesh is not None and rec.get('sourceToPrint') and Path(src_world).exists():
            mesh = trimesh.load(src_world, force='mesh')
            mesh.apply_transform(np.array(rec['sourceToPrint'], dtype=float))
            mesh.apply_translation([0, 0, -mesh.bounds[0][2]])
            mesh.export(dest)
            frame = 'print pose (bed at z 0), rotated here with the release sourceToPrint matrix'
        elif Path(src_world).exists():
            shutil.copyfile(src_world, dest)
            frame = f"as released ({rec.get('sourceFrame') or 'robot frame, x forward, y left, z up'}); not rotated into the print pose"
        else:
            print(f"warning: missing file for {rec['key']}: {src_world}")
            continue
        rec['file'] = str(dest.relative_to(out))
        rec['fileSha256'] = sha256(dest)
        rec['frame'] = frame
        if trimesh is not None:
            b = trimesh.load(dest, force='mesh').bounds
            rec['sizeMm'] = [round(float(x), 1) for x in (b[1] - b[0])]
        rec.pop('sourceToPrint', None)

    # ---- retained community parts
    com_dir = out / 'stl' / 'community'
    if com_dir.exists():
        shutil.rmtree(com_dir)
    com_dir.mkdir(parents=True)
    retained: dict[str, dict] = {}
    retired_rows = []
    for idx, inst in enumerate(instances):
        if idx in RETIRED_STOCK:
            name, why = RETIRED_STOCK[idx]
            retired_rows.append({'index': idx, 'name': inst['name'], 'reason': why})
            continue
        if idx in replaced_stock:
            retired_rows.append({'index': idx, 'name': inst['name'], 'reason': f'replaced by {replaced_stock[idx]}'})
            continue
        fname = Path(inst['file']).name
        if fname not in retained:
            src = Path(inst['file'])
            if not src.exists():
                print(f'warning: missing community file {src}')
                continue
            dest = com_dir / fname
            shutil.copyfile(src, dest)
            retained[fname] = {'file': str(dest.relative_to(out)), 'name': inst['name'], 'quantity': 0,
                               'fileSha256': sha256(dest), 'sourceName': inst.get('source_name'),
                               'instances': []}
        retained[fname]['quantity'] += int(inst.get('quantity', 1))
        retained[fname]['instances'].append(idx)

    # tools (the dropped hot-glue sole molds, 10 MB each) are recorded but their STLs are not shipped
    tools_dropped = []
    for key in list(parts):
        if key in TOOLS:
            tools_dropped.append({'key': key, 'name': parts[key]['name'], 'version': parts[key]['version'],
                                  'note': 'sole mold for the hot-glue route dropped on 2026-10-19; STL not included, the soles are cut from a bicycle inner tube'})
            f = out / parts[key]['file']
            if f.exists():
                f.unlink()
            del parts[key]

    result = {
        'foundation': '2026-10-23',
        'toolsNotIncluded': tools_dropped,
        'releasesApplied': [c[0] for c in CHAIN],
        'ourParts': sorted(parts.values(), key=lambda r: (r['color'], r['key'])),
        'retiredOurParts': removed,
        'communityRetained': sorted(retained.values(), key=lambda r: r['name']),
        'communityRetired': retired_rows,
        'communitySource': {
            'file': 'community/microduck-community-print-set.3mf',
            'repository': 'https://github.com/AI-FanGe/Microduck-build-tutorial',
            'commit': '49678215d0b40529522772a40c06c216390449dd',
            'license': 'MIT (community/LICENSE-AI-FanGe)',
        },
    }
    (out / 'parts.json').write_text(scrub(json.dumps(result, indent=1, ensure_ascii=False) + '\n'))
    write_parts_md(out / 'PARTS.md', result)
    print(json.dumps({'ourParts': len(parts), 'communityFiles': len(retained),
                      'communityInstancesRetained': sum(r['quantity'] for r in retained.values()),
                      'communityInstancesRetired': len(retired_rows), 'out': str(out)}))


def write_parts_md(path: Path, r: dict) -> None:
    L = []
    L.append('# Printed parts of the foundation robot (2026-10-23)\n')
    L.append('Generated by `scripts/collect_printed_parts.py` from the release records; do not edit by hand. '
             'Two sources make the body: the community print set from AI-FanGe\'s Microduck build tutorial '
             '(`community/microduck-community-print-set.3mf`, MIT, commit 4967821), printed on 2026-10-01 as 89 instances, '
             'and our incremental releases V1.6 to V1.31 that replaced or added parts. '
             f"Releases applied, in order: {', '.join(r['releasesApplied'])}. Later releases (V1.29 saddle, V1.30 USB camera face) are extensions and are not here.\n")
    L.append('Colour scheme C: white shells, thighs and head cap; yellow lower head shell, jaw and feet; orange rear pack, '
             'converter box, backpack and ankles; black links, rings, trim and small parts. Material PLA, 0.4 mm nozzle, '
             '0.2 mm layers; print on a Bambu X1C or an Elegoo Centauri Carbon (the per-colour plate files are listed in PLATES.md). '
             'Supports: tree supports from the slicer profile where the pose notes say so; brims per part as in PRINT-LESSONS.md.\n')

    L.append('## Our parts, by colour\n')
    L.append('Each entry: name, STL in this folder, quantity, release that introduced the geometry, print status on 2026-10-23, '
             'then the print pose and the reason for the part. STLs under `stl/our-parts/` are in print pose unless the entry says otherwise.\n')
    by_color: dict[str, list] = {}
    for p in r['ourParts']:
        by_color.setdefault(p['color'], []).append(p)
    for color in ('White', 'Yellow', 'Orange', 'Black'):
        rows = by_color.get(color, [])
        if not rows:
            continue
        L.append(f'### {color} ({len(rows)} parts)\n')
        for p in rows:
            flags = []
            if p['key'] in NOT_FITTED:
                flags.append('printed but not fitted: the head wires run free down the left side of the neck')
            if p['key'] in TOOLS:
                flags.append('tool for casting the bike-inner-tube soles, not a robot part')
            if p['key'] in OPTIONAL:
                flags.append('optional shim, fit only if the head-pitch ring has play')
            if p['key'] in BATTERY_ROUTE:
                flags.append('battery route (4-power), designed and printed, backpack not yet on the robot')
            size = f" Size {p['sizeMm'][0]} x {p['sizeMm'][1]} x {p['sizeMm'][2]} mm." if p.get('sizeMm') else ''
            L.append(f"- **{p['name']}** (`{p['file']}`), x{p['quantity']}, {p['version']}, {p['status']}.{size}")
            if flags:
                L.append(f"  {'; '.join(flags)}.")
            L.append(f"  Pose: {p['pose'] or 'as released'} File frame: {p['frame']}.")
            if p.get('reason'):
                L.append(f"  Why: {p['reason']}")
            L.append(f"  sha256 {p['fileSha256']}")
        L.append('')

    if r.get('toolsNotIncluded'):
        L.append('### Tools, not included\n')
        for t in r['toolsNotIncluded']:
            L.append(f"- **{t['name']}** ({t['version']}): {t['note']}.")
        L.append('')

    L.append('## Community parts kept from the 10/1 batch\n')
    total = sum(c['quantity'] for c in r['communityRetained'])
    L.append(f"{total} instances in {len(r['communityRetained'])} files, copied to `stl/community/` in the orientation of the 2026-10-01 batch "
             '(the same geometry as in the community 3MF). Quantities are the batch counts; the rings, idlers and caps include spares.\n')
    for c in r['communityRetained']:
        L.append(f"- **{c['name']}** (`{c['file']}`), x{c['quantity']}; sha256 {c['fileSha256']}")
    L.append('')
    L.append('## Community parts not used any more\n')
    L.append('Printed on 2026-10-01 and later taken off the robot or never fitted. Do not print these from the community 3MF.\n')
    for c in r['communityRetired']:
        L.append(f"- {c['name']} (batch instance {c['index']}): {c['reason']}")
    L.append('')
    L.append('## Our parts that a later release replaced\n')
    L.append('Listed so an old plate file is not printed by mistake.\n')
    for c in r['retiredOurParts']:
        L.append(f"- {c['key']} ({c['version']}), retired by {c['retiredBy']}: {c['reason']}")
    L.append('')
    path.write_text(scrub('\n'.join(L) + '\n'))


if __name__ == '__main__':
    main()
