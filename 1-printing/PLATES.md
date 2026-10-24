# Sliced plate files

One plate per colour and release, sliced on the project's pipeline for the two RoboClub printers: Bambu Lab X1C (`.gcode.3mf`, open in Bambu Studio or send to the printer; never re-open the sliced file in Orca, see PRINT-LESSONS.md) and Elegoo Centauri Carbon (`.gcode`). The files are not in the git tree (about 200 MB together); they are published as release assets of this repository. Check a download against the sha256 below. The STL of every part is in `stl/` if you prefer to slice yourself: PLA, 0.4 mm nozzle, 0.2 mm layers, four walls, tree supports where PARTS.md says so, brim per part as in PRINT-LESSONS.md.

Plates of a release that a later release replaced in part are still listed: the note says which parts to skip. To print the robot from scratch, use PARTS.md as the shopping list and these plates only where every part on the plate is still current.

## V1.6: printed (head, speaker, trim, jaw support, neck pitch bracket, IMU holder, OpenRB tray; several parts since replaced, see PARTS.md)

- `cmu-microduck_V1.6_Black_Bambu-X1C_2h32m.gcode.3mf` (3.2 MB) Black plate, Bambu X1C: OpenRB tray and IMU cover replaced by the V1.8 pack, neck pitch ring replaced by V1.8; jaw support, sliding ring and neck pitch bracket still used.  
  sha256 `31c795ade47a267c604461e7a8137226904d44ed99f51f1ac97bb4922b1ef871`
- `cmu-microduck_V1.6_Black_Elegoo-Centauri-Carbon_2h34m.gcode` (8.6 MB) Black plate, Elegoo Centauri Carbon: OpenRB tray and IMU cover replaced by the V1.8 pack, neck pitch ring replaced by V1.8; jaw support, sliding ring and neck pitch bracket still used.  
  sha256 `167fc6b4dbea43a94215cfe983b2db888e5aa143771bb36cb092a9217ad14938`
- `cmu-microduck_V1.6_Orange_Bambu-X1C_2h40m.gcode.3mf` (4.1 MB) Orange plate, Bambu X1C: head cap replaced by V1.8 and V1.9/V1.17, speaker cradle replaced by V1.9, IMU clamp replaced by the V1.8 pack.  
  sha256 `81f0f255140a549b65f8f0b5682cb6c63b956184016bbfa6e603aa8b7cf5b1c0`
- `cmu-microduck_V1.6_Orange_Elegoo-Centauri-Carbon_2h57m.gcode` (11.1 MB) Orange plate, Elegoo Centauri Carbon: head cap replaced by V1.8 and V1.9/V1.17, speaker cradle replaced by V1.9, IMU clamp replaced by the V1.8 pack.  
  sha256 `d4153881df295bb1c3ea3a0fcc1648bf4f122828aa186c09293667cfe5072b1c`
- `cmu-microduck_V1.6_White_Bambu-X1C_19m.gcode.3mf` (0.3 MB) White plate, Bambu X1C: face panel replaced by V1.8 and V1.17.  
  sha256 `d28598c5528d2f07d9dd75f5ea40c53bf56778b139cd2fe5396b6e65f3044426`
- `cmu-microduck_V1.6_White_Elegoo-Centauri-Carbon_15m.gcode` (0.8 MB) White plate, Elegoo Centauri Carbon: face panel replaced by V1.8 and V1.17.  
  sha256 `a1e5648052399751e60ea229714a5e75e1b0fd304e987f041767f86000b64dd0`
- `cmu-microduck_V1.6_Yellow_Bambu-X1C_1h56m.gcode.3mf` (2.8 MB) Yellow plate, Bambu X1C: lower head shell replaced by V1.8.  
  sha256 `82959fd2dff0036fa5e09068422875536d2bef1993ed9df19e710e8810a53150`
- `cmu-microduck_V1.6_Yellow_Elegoo-Centauri-Carbon_1h42m.gcode` (4.8 MB) Yellow plate, Elegoo Centauri Carbon: lower head shell replaced by V1.8.  
  sha256 `1fb06085e74891446dbadc86f190595b2a30d5457b72deb35b8657b4855d0682`

## V1.8: printed (lower head shell, jaw frame, face, head cap, eye trim, rear pack, pack cover, neck ring and shims)

- `cmu-microduck_V1.8_Black_Bambu-X1C_45m.gcode.3mf` (0.8 MB) Black plate, Bambu X1C: rear pack cover replaced by the V1.17 box frame; eye trim, neck ring and shims still used.  
  sha256 `68023e34161175787bd1b87824ae979e963fc007ee413d6950b5bb4a640a6f9e`
- `cmu-microduck_V1.8_Black_Elegoo-Centauri-Carbon_44m.gcode` (2.4 MB) Black plate, Elegoo Centauri Carbon: rear pack cover replaced by the V1.17 box frame; eye trim, neck ring and shims still used.  
  sha256 `022f82101a509fd773a491bbcc9cb00f59b1516b67445f5fe073f0ccd74f241a`
- `cmu-microduck_V1.8_Orange_Bambu-X1C_3h9m.gcode.3mf` (3.9 MB) Orange plate, Bambu X1C: head cap replaced by V1.9/V1.17, rear pack replaced by V1.9.  
  sha256 `9cef8214d019384b2fea64a12354024949adca5b95e6786d1b86292fb1d719d0`
- `cmu-microduck_V1.8_Orange_Elegoo-Centauri-Carbon_3h28m.gcode` (12.0 MB) Orange plate, Elegoo Centauri Carbon: head cap replaced by V1.9/V1.17, rear pack replaced by V1.9.  
  sha256 `a94b0f0257ebe1bec9f72c0e2e2372357435373d62d89d5de3f4f52f732ec20d`
- `cmu-microduck_V1.8_White_Bambu-X1C_16m.gcode.3mf` (0.2 MB) White plate, Bambu X1C: face panel replaced by V1.17.  
  sha256 `0d46f667680e665f357ef5f35283758c9696342de92b3014afa4bef284d7f530`
- `cmu-microduck_V1.8_White_Elegoo-Centauri-Carbon_10m.gcode` (0.3 MB) White plate, Elegoo Centauri Carbon: face panel replaced by V1.17.  
  sha256 `df1f3fef02068b70f1e1e040f94365d1757fb0daa142717586318e2213554f6a`
- `cmu-microduck_V1.8_Yellow_Bambu-X1C_3h2m.gcode.3mf` (4.5 MB) Yellow plate, Bambu X1C: all parts current.  
  sha256 `3e63039d590cf91e6a3367fc19f45ce579a3432b6721d4e55b440e6ba1ee891d`
- `cmu-microduck_V1.8_Yellow_Elegoo-Centauri-Carbon_2h56m.gcode` (9.1 MB) Yellow plate, Elegoo Centauri Carbon: all parts current.  
  sha256 `22e48d393688ff306dda22c540df0179cc7014ef21662815e86fdc1cf6bf8616`

## V1.9: printed (Orange plate: rear pack with the IMU rib, head cap, speaker retainer, wire clips)

- `cmu-microduck_V1.9_Orange_Bambu-X1C_3h39m.gcode.3mf` (5.1 MB) Orange plate, Bambu X1C: head cap and cap clip replaced by V1.17; rear pack, speaker retainer and three clips still used.  
  sha256 `a7f6c15ed0f84433da35162fc19360a2185412fc7902cc284a51e4d42f1f90fe`
- `cmu-microduck_V1.9_Orange_Elegoo-Centauri-Carbon_3h56m.gcode` (15.0 MB) Orange plate, Elegoo Centauri Carbon: head cap and cap clip replaced by V1.17; rear pack, speaker retainer and three clips still used.  
  sha256 `99a7d6ba0102bde3870d08f1bf735776e40453ff866f59befd25b5d0cad09791`

## V1.17: printed (rear converter box frame and cap, white shells and thighs, A7Z head cap and face, cap clip)

- `cmu-microduck_V1.17_Orange_Bambu-X1C_1h51m.gcode.3mf` (2.2 MB) Orange plate, Bambu X1C: box cap replaced by V1.20; frame and cap clip still current.  
  sha256 `20a55b4f3a65e4e9dbf650544edcc0c65a186ede6060dcfd7d767188cf0082e8`
- `cmu-microduck_V1.17_Orange_Elegoo-Centauri-Carbon_1h49m.gcode` (6.0 MB) Orange plate, Elegoo Centauri Carbon: box cap replaced by V1.20; frame and cap clip still current.  
  sha256 `b42e6d4c7d481f85bd0e98e390f177a904273c5de51c99b03a3acfd871dd5e0c`
- `cmu-microduck_V1.17_White_Bambu-X1C_4h12m.gcode.3mf` (6.1 MB) White plate, Bambu X1C: all parts current.  
  sha256 `cdb1c1c5e854ceec2b7b11a9290b85045826168b42936c3f0866848971250af7`
- `cmu-microduck_V1.17_White_Elegoo-Centauri-Carbon_4h26m.gcode` (18.8 MB) White plate, Elegoo Centauri Carbon: all parts current.  
  sha256 `85a56c7250eceda0cd560b9a29a3f94c69ec0b3bfcb4a9c7d837f987b2f17e2a`
- plate picture `V1.17_Orange-plate.png`
- plate picture `V1.17_White-plate.png`

## V1.20: printed (box cap with 3 mm screw floors, battery backpack frame and cap)

- `cmu-microduck_V1.20_Orange_Bambu-X1C_2h20m.gcode.3mf` (2.7 MB) Orange plate, Bambu X1C: backpack frame replaced by V1.31; box cap and backpack cap still current.  
  sha256 `9733640f35ec04a9ebd4bb2ead96f099b885db3f3acc89985e8ac9b26171e74e`
- `cmu-microduck_V1.20_Orange_Elegoo-Centauri-Carbon_2h22m.gcode` (7.5 MB) Orange plate, Elegoo Centauri Carbon: backpack frame replaced by V1.31; box cap and backpack cap still current.  
  sha256 `db54856a1c3ed00cdd1afa7f15a75b60bc9e5324fa7f121c57e9e5bd6d38c2d8`
- plate picture `V1.20_Orange-plate.png`

## V1.21: printed in black although the plate file says Orange (sole molds for a hot-glue sole route that was dropped on 2026-10-19; not needed for the robot)

- `cmu-microduck_V1.21_Orange_Bambu-X1C_2h39m.gcode.3mf` (2.4 MB) Orange plate, Bambu X1C: all parts current.  
  sha256 `bc0d33a8270f6113d65c08d1d53681526dc0df6f665aeb7066c8834dba68530a`
- `cmu-microduck_V1.21_Orange_Elegoo-Centauri-Carbon_2h52m.gcode` (11.8 MB) Orange plate, Elegoo Centauri Carbon: all parts current.  
  sha256 `230725eb6670354324814edadff4bc836169a0f4f0744628ccacca13551056de`
- plate picture `V1.21_Orange-plate.png`

## V1.22: printed (ankle rework: bases and sides, sleeves, slip-fit feet)

- `cmu-microduck_V1.22_Black_Bambu-X1C_11m.gcode.3mf` (0.1 MB) Black plate, Bambu X1C: right sleeve replaced by the V1.28 link; left sleeve still used.  
  sha256 `e7738e05ce98b3fce3ecc3152b17157217ea543dd725a85c2f88bd2bd345ed94`
- `cmu-microduck_V1.22_Black_Elegoo-Centauri-Carbon_4m.gcode` (0.2 MB) Black plate, Elegoo Centauri Carbon: right sleeve replaced by the V1.28 link; left sleeve still used.  
  sha256 `6d81ecd8015a4e09ef532178763ebe0fcc0d7abea225de0f884dc878a2b6eb95`
- `cmu-microduck_V1.22_Orange_Bambu-X1C_1h4m.gcode.3mf` (0.9 MB) Orange plate, Bambu X1C: ankle bases and sides replaced by V1.24/V1.25.  
  sha256 `4fe828c8b1f5eccd3ea75db7b95fcfd86b29ca607080b1156f074460986bda55`
- `cmu-microduck_V1.22_Orange_Elegoo-Centauri-Carbon_1h7m.gcode` (4.0 MB) Orange plate, Elegoo Centauri Carbon: ankle bases and sides replaced by V1.24/V1.25.  
  sha256 `85552f9a60f3d7992cea758c2a491847b73ca5e76fc3f2d855c0bd87877dc8cc`
- `cmu-microduck_V1.22_Yellow_Bambu-X1C_5h27m.gcode.3mf` (7.1 MB) Yellow plate, Bambu X1C: all parts current.  
  sha256 `8e018a122c0377dc4b3a80cdfdc1a822dd7b940dc5799f27a2c18f7e4aadbe8a`
- `cmu-microduck_V1.22_Yellow_Elegoo-Centauri-Carbon_6h37m.gcode` (26.3 MB) Yellow plate, Elegoo Centauri Carbon: all parts current.  
  sha256 `522ef79528d976405693da293a2304e5184f1487bf1e448f580654210f77cd99`
- plate picture `V1.22_Black-plate.png`
- plate picture `V1.22_Orange-plate.png`
- plate picture `V1.22_Yellow-plate.png`

## V1.24: printed (two-half ankles)

- `cmu-microduck_V1.24_Orange_Bambu-X1C_55m.gcode.3mf` (0.8 MB) Orange plate, Bambu X1C: inner halves replaced by V1.25 (round bore).  
  sha256 `08b9ac3e78bbb1a5b737f8691e20ff2828b7668d899097952ed0e77278d0268a`
- `cmu-microduck_V1.24_Orange_Elegoo-Centauri-Carbon_1h0m.gcode` (3.8 MB) Orange plate, Elegoo Centauri Carbon: inner halves replaced by V1.25 (round bore).  
  sha256 `eb2dbaa06469675bff293fc1d682f78dc911a763e35f4157508d0c60412645dc`
- plate picture `V1.24_Orange-plate.png`

## V1.25: released 2026-10-20, round-bore inner halves; not recorded as printed

- `cmu-microduck_V1.25_Orange_Bambu-X1C_52m.gcode.3mf` (0.7 MB) Orange plate, Bambu X1C: all parts current.  
  sha256 `04cc2d8e8eed4ff21982a7f1e92ef3f9b64a3af94d8d9bf7b7590a411946d3d4`
- `cmu-microduck_V1.25_Orange_Elegoo-Centauri-Carbon_1h0m.gcode` (3.9 MB) Orange plate, Elegoo Centauri Carbon: all parts current.  
  sha256 `844f42b7dc0c4fcffb857137207f49e4547923b75e1bcad871b5bdf1e184465b`
- plate picture `V1.25_Orange-plate.png`

## V1.28: printed (right lower-leg link with the sleeve printed on)

- `cmu-microduck_V1.28_Black_Bambu-X1C.gcode.3mf` (0.8 MB) Black plate, Bambu X1C: all parts current.  
  sha256 `a22d02eddfd8a97df0ef391c205b9f4dc8766f73b0d074d650f06f830777cff8`
- `cmu-microduck_V1.28_Black_Elegoo-Centauri-Carbon.gcode` (2.1 MB) Black plate, Elegoo Centauri Carbon: all parts current.  
  sha256 `ea9beadaa43c470e9af8494af6f85b953d12a1a5f69df2fa024f1426aad72f05`

## V1.31: released 2026-10-23, backpack frame with the wider DFR1202 slot; not printed

- `cmu-microduck_V1.31_Orange_Bambu-X1C_1h38m.gcode.3mf` (1.9 MB) Orange plate, Bambu X1C: all parts current.  
  sha256 `4971754d01739f1efe5707bc8ba9ca2903ab5d7c51c6e00bee380712a550bbab`
- `cmu-microduck_V1.31_Orange_Elegoo-Centauri-Carbon_1h42m.gcode` (5.5 MB) Orange plate, Elegoo Centauri Carbon: all parts current.  
  sha256 `78a05be394ae7bd9c6e937217c6b42afb12b925aef1bda0cce36d2b5ac8d538a`
- plate picture `V1.31_Orange-plate.png`

Total 205 MB in 40 files.
