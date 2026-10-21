# README update notes

How the README is put together, how to refresh its images, and a review of the README against
the Rev 1.1 schematic and board (2026-10-20) with suggested changes.

## What was changed on 2026-10-20

- Title and safety note now say **v1.1** (were "Rev1").
- Top image replaced: `graphics/CellKeeper_top.png` is the current bare v1.1 board, top-down.
  The old panelised render `graphics/CellKeeperPCB.png` is no longer used by the README (it still
  shows the precharge and isoSPI boards attached; delete it if nothing else needs it).
- New **Enclosure** section with `graphics/CellKeeper_enclosure.png` (case and board from the
  right front), and an `enclosure/` row in Repository Contents.
- **Getting Started** section removed (KiCad install/open steps and the KiKit panelising note).

## Refreshing the README images

```
python enclosure/cellkeeper_case.py          # only if the case changed: updates ENC1's 3D models
python python_scripts/render_readme_images.py
```

`render_readme_images.py` drives `kicad-cli pcb render` and writes both images:

| Image | View | How |
|-------|------|-----|
| `graphics/CellKeeper_top.png` | bare board, top-down | renders a temporary copy of the board with the ENC1 enclosure footprint removed |
| `graphics/CellKeeper_enclosure.png` | board in its case, right front | renders the real board with `--rotate -52,0,-32` |

Both are rendered on a transparent background, cropped to the board with a 40 px margin and
flattened onto white. The board file is only read, so KiCad can stay open (it renders the last
saved state). `KIPRJMOD` is passed to kicad-cli so the temporary copy still finds the project's
3D models. Set `KICAD_CLI` if kicad-cli isn't at `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`.

Notes:

- The ENC1 footprint (board-only, at 0,0) carries the case models from `enclosure/output/kicad/`;
  without the removal step every top-down render shows the closed case instead of the board.
- `kicad-cli pcb render --pan` moves the camera in its own units, which made zoomed close-ups go
  blank; crop a full render instead.
- The KiCad renders include the soft floor shadow (semi-transparent), which reads fine on white.

## README vs the Rev 1.1 design

Sources: `CellKeeper/CellKeeper.kicad_sch` (notes, labels), `CellKeeper/CellKeeper.kicad_pcb`
(pad nets, silkscreen), `CellKeeper/production/CellKeeper_REV1.1_bom.csv`.
U14 is the main BMS MCU, U20 the supervisor (silkscreen "BMS" and "Supervisor").

### Intro

README: "a replacement BMS controller for battery packs using the isoSPI protocol."

The board is laid out as a drop-in for the Tesla penthouse controller: OEM connectors for the
vehicle harness (J6, JST S44B-RAD1AK), HV sense (J17, TE 173864-1), shunt (J14, Hirose ZE05H) and
isoSPI to the BMBs (J20, Molex 34912), and H3/H4 sit where the original controller's mounting
brackets screw down ("H3, H4 fit mount in penthouse"). Suggest saying so, e.g. "a drop-in
replacement for the Tesla battery's penthouse controller (HVC/HVP), using the pack's original
connectors and mounting points". Confirm the exact pack/vehicle wording.

### Overview bullets

| README says | Rev 1.1 has | Suggested |
|-------------|-------------|-----------|
| MCU: RP2354B (dual Cortex-M33 @ 150 MHz) | **two** RP2354B: main BMS (U14) and supervisor (U20), each with its own crystal, 3.3 V LDO, USB-C and RST/BOOT buttons; UART link between them (MAIN-SUP / SUP-MAIN); the supervisor also sees the isoSPI receive line and the E-stop input | "Two RP2354B: main BMS controller plus an independent supervisor" |
| Current sensing: TI INA228 (20-bit, shunt-based) | INA228 (U17) on a **galvanically isolated** domain: ISO1540 I2C isolator (U16) and an isolated 5 V DC-DC (U15, F0505S-1WR3; footprint also takes the 6 kV H0505S-1WR2). Also reads the shunt NTC. Schematic note: in Tesla packs the shunt is at the pack midpoint and always live | add "isolated" and "shunt temperature" |
| Pack voltage: 6-channel monitoring via precision dividers | 6 HV sense points (BAT+, BAT-, LINK+, LINK-, FC/OUT+, FC/OUT-) through 501:1 dividers (400 V reads 0.798 V) into **two ADS1115** (U18, U19), read differentially: battery, link and output voltage and the voltage across each contactor | "6 HV sense points into two ADS1115 ADCs; measures pack, link and output voltage and each contactor" |
| BMB communication: isoSPI master with galvanic isolation (Manchester encoding via PIO) | discrete isoSPI: SP3485 driver (U21), AM26LV32 receiver (U22), HM2113 transformer (TR1); BMB-side centre tap floating for ESD | add the part numbers / "transformer-isolated" |
| CAN bus: 500 kbps, hardware transceiver | **two** CAN interfaces, both ISO1050: inverter CAN (U5) is isolated with its own DC-DC (U4) and shares RJ45 J4 with the E-stop/aux lines (default jumpers suit Deye/BYD pinout; Foxess swaps CANH/L); inter-BMS CAN2 (U10) runs from board 5 V and GND (not isolated, silkscreen "NON ISOLATED") on dual pass-through RJ45 J5. The bit rate is firmware, not hardware | "Two CAN buses: isolated inverter CAN and inter-BMS CAN" |
| Contactor control: 4-channel PWM outputs with inrush limiting | 4 low-side channels (FC+, FC-, Link+, Link-): BSC0805LS MOSFETs (Q1-Q4) driven by two UCC27524 gate drivers (U1, U11) with a shared enable `CTR_EN` (silkscreen "Supervisor Enable"; verify what drives it); FC negative also controls the precharge bypass; contactor supply sensed on an ADC (VContactor Sense). "Inrush limiting" isn't visible in hardware: verify whether that means firmware PWM economising or the precharge | drop or reword "inrush limiting"; mention the enable and the precharge role |
| Input: 12 V nominal; up to 400 V DC pack voltage (**updated**: now "Input: 13–16 V logic and contactor supplies (separate inputs)" and "HV battery: 400 V nominal") | J1 has separate **logic** and **contactor** supply inputs (GND, GND, CTR, LOGIC), both sensed; TPS5430 5 V 3 A buck (36 V max, intended for 10-16 V); silkscreen says **12-16 V** (the printed case lid says 13-16 V); chassis ground terminal J2 ("IMPORTANT connect chassis GND first") | "12-16 V logic and contactor supplies (separate inputs)"; settle 12-16 V vs 13-16 V |

### Missing from the README

- **USB-C x3**: supervisor, BMS, and "HMI link". The HMI link is not for a computer: it powers an
  external ESP32 display/HMI (typically an ESP32-P4 LCD board, 5 V 1 A) and carries the HMI serial.
- **Inputs/outputs**: E-stop input (optocoupler; external NC switch, or jumper JP37 "E-STOP
  DISABLE"), extra input (opto, 3-5 V), extra outputs on J4, FC contactor aux-contact inputs
  (J7, opto) for weld detection, SX serial (J3: GND, RX, TX, 3V3; "SX 2012-2021 serial interface").
- **PCS signals** (PCS Enable/Charge/DC-DC, PCS IPC CAN) on experimental jumpers JP30-JP35.
- **Board identification**: revision strap on GPIO44-46.
- **Indicators**: 21 status LEDs.
- **Mounting**: H1/H2/H7/H8 (3.7 mm) for the board, H3/H4 (5 mm) for the penthouse brackets.
- **Enclosure**: now covered by its own section.

### Repository Contents

- `docs/` (design plans, these notes) isn't listed.
- `CellKeeper/production/` holds both REV1 and REV1.1 outputs; say which is current.
- `python_scripts/` now includes `render_readme_images.py` (README images) and
  `recolor_vendor_step_models.py` (3D model colours).

### Safety

Now says v1.1. Several schematic notes still say "Not tested as of now" and "Not used for standard
setup" (PCS/experimental parts); keep the "untested" wording until those are verified.

## Checklist for the next README update

1. Re-render the images (above) after board or case changes, and check them before committing.
2. Re-check the Overview against the BOM (`production/*_bom.csv`) for part changes.
3. Keep the version in the title, the safety note and the image alt text in step.
4. Confirm the open questions above: what drives `CTR_EN`, "inrush limiting", the Tesla
   pack/vehicle wording. (Supply range settled as 13-16 V; the board silkscreen still says 12-16V.)
