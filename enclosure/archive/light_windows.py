"""Archived: clear-filament fills for the lid's LED tunnels (not used by cellkeeper_case.py).

Two versions were tried, each exported as an extra part in the lid STEPs for a clear filament:

- light_pipes():   a clear rod down the whole tunnel, tube bottom to lid top. The long tunnel
                   wall diffused the light too much.
- light_windows(): only a 0.4 mm (two-layer) clear disc closing the top of each tunnel, the tunnel
                   below hollow. Superseded too: the lid now leaves the tunnels open.

To bring one back, import it into cellkeeper_case.py and pass its result (flipped for printing,
and split with halves() for the split lids) to save() as an extra part, the way the inlay is
passed: save() writes one STEP part per body via export_parts_step(), e.g.

    parts.append(("light_windows", flip(light_windows()), (0.80, 0.90, 1.00)))

Both functions build in the case script's coordinates (KiCad x, -KiCad y, z from the PCB bottom).
"""

from cellkeeper_case import (LED_GAP, LED_HOLE_D, LED_TOP, LED_TUBE_FIT, LED_TUBE_OD, LEDS, Z_TOP,
                             Compound, cyl)

LIGHT_WINDOW = 0.4   # window thickness at the top of each tunnel (two 0.2 mm layers)


def light_pipes():
    """The LED tunnels filled solid, from each tube's bottom to the lid top, as one part."""
    return Compound([cyl(x, -y, LED_HOLE_D, LED_TUBE_FIT.get((x, y), (LED_TUBE_OD, LED_TOP + LED_GAP))[1], Z_TOP)
                     for x, y in LEDS])


def light_windows():
    """A clear disc closing the top LIGHT_WINDOW of each LED tunnel, as one part."""
    return Compound([cyl(x, -y, LED_HOLE_D, Z_TOP - LIGHT_WINDOW, Z_TOP) for x, y in LEDS])
