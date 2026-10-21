"""Copy the CellKeeper logo (battery icons + lettering) from the board's front silkscreen into
cellkeeper_logo.json, for cellkeeper_case.py to put on the lid (which refits it as curves).

    python extract_logo.py [../CellKeeper/CellKeeper.kicad_pcb]

The logo is the filled F.SilkS polygons inside LOGO_BOX. Output points are in mm, centred on the
logo, y pointing up (KiCad y is flipped).
"""

import json
import sys
from pathlib import Path

import sexpdata
from sexpdata import Symbol

LOGO_BOX = (170.0, 76.0, 210.0, 96.5)   # KiCad x0, y0, x1, y1 around the logo on Rev 1.1


def name(n):
    return n[0].value() if isinstance(n, list) and n and isinstance(n[0], Symbol) else None


def child(n, key):
    return next((c for c in n if name(c) == key), None)


def area(ring):
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]))


def clean(pts):
    """Drop repeated neighbours and zero-width spikes (a, b, a)."""
    changed = True
    while changed:
        changed = False
        out = [p for i, p in enumerate(pts) if p != pts[i - 1]] if len(pts) > 1 else pts
        for i in range(len(out)):
            if len(out) > 3 and out[i - 2] == out[i]:
                del out[i - 1]
                changed = True
                break
        pts = out
    return pts


def split_keyholes(pts):
    """KiCad fills holes by bridging them to the outline with a zero-width slit, so a hole shows
    up as a run between two visits of the same point. Cut those runs out as separate rings and
    return (outer, holes)."""
    pts, rings = clean([tuple(p) for p in pts]), []
    while True:
        seen, best = {}, None
        for i, p in enumerate(pts):
            if p in seen and (best is None or i - seen[p] < best[1] - best[0]):
                best = (seen[p], i)
            seen[p] = i
        if best is None:
            break
        i, j = best
        if j - i >= 3:
            rings.append(pts[i:j])
        pts = clean(pts[:i] + pts[j:])
    rings.append(pts)
    rings.sort(key=lambda r: abs(area(r)), reverse=True)
    return rings[0], rings[1:]


def main():
    here = Path(__file__).resolve().parent
    pcb_path = Path(sys.argv[1]) if len(sys.argv) > 1 else here.parent / "CellKeeper" / "CellKeeper.kicad_pcb"
    pcb = sexpdata.loads(pcb_path.read_text(encoding="utf-8"))
    x0, y0, x1, y1 = LOGO_BOX
    polys = []
    for g in pcb:
        if name(g) != "gr_poly" or child(g, "layer")[1] != "F.SilkS":
            continue
        pts = [(p[1], p[2]) for p in child(g, "pts") if name(p) == "xy"]
        if all(x0 <= x <= x1 and y0 <= y <= y1 for x, y in pts):
            polys.append(pts)
    xs = [x for p in polys for x, _ in p]
    ys = [y for p in polys for _, y in p]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    local = lambda ring: [[round(x - cx, 4), round(cy - y, 4)] for x, y in ring]  # noqa: E731
    shapes = []
    for p in polys:
        outer, holes = split_keyholes(p)
        shapes.append({"outer": local(outer), "holes": [local(h) for h in holes]})
    out = {
        "source": pcb_path.name,
        "size": [round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3)],
        "shapes": shapes,
    }
    (here / "cellkeeper_logo.json").write_text(json.dumps(out), encoding="utf-8")
    print(f"logo: {len(shapes)} shapes, {out['size'][0]} x {out['size'][1]} mm -> cellkeeper_logo.json")


if __name__ == "__main__":
    main()
