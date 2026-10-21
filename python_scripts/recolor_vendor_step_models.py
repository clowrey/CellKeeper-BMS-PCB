from __future__ import annotations

from pathlib import Path

import numpy as np
from build123d import Color, Compound, GeomType, Solid, export_step, import_step
from OCP.Quantity import Quantity_Color, Quantity_TypeOfColor
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.TopLoc import TopLoc_Location
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool, XCAFDoc_ShapeTool


PROJECT = Path(__file__).resolve().parents[1]
SHAPES_DIR = PROJECT / "lib" / "CellKeeper.3dshapes"

# Vendor STEP files that ship without colors, so KiCad draws them default grey.
# Each is a single solid; give it the real housing color.
MODELS = {
    # J17, TE 173864-1: natural (white) nylon housing.
    "CONN_173864-1_TYC_Empty_Pins.step": (0.94, 0.93, 0.88),
}

# Single solids with the terminals fused into the housing: housing color, plus a metal color for
# the terminal faces (found as thin sheet metal, see metal_faces).
MODELS_WITH_PINS = {
    # J20, Molex 34912-8020: black housing, same as the Hirose ZE05H on J14; tin-plated
    # terminals and hold-downs, the same metal color as the ZE05H pins.
    "CONN_SD-34912-001_02_MOL.step": ((0.10, 0.10, 0.10), (0.80, 0.80, 0.78)),
}

SHEET_MIN, SHEET_MAX = 0.12, 0.42   # stamped terminal thickness range, mm
EDGE_MAX_AREA = 3.0                 # largest edge/bend face joining two sheet faces, mm^2
MIN_PART_FACES, MIN_PART_AREA = 3, 5.0   # smaller connected groups are stray housing faces


def recolor(path: Path, color: tuple[float, float, float]) -> None:
    shape = import_step(path)
    solids = []
    for solid in shape.solids():
        solid.color = Color(*color)
        solids.append(solid)
    export_step(Compound(children=solids), path)
    print(f"Recolored {path.name}: {len(solids)} solid(s)")


def metal_faces(solid) -> set[int]:
    """Indexes of the faces of stamped terminals in a fused solid: planar faces with an
    antiparallel twin SHEET_MIN..SHEET_MAX away that overlaps it, with material between them (the
    two sides of a sheet, not a thin air gap such as the one between a hold-down and the housing
    wall), plus the small edge and bend faces that join such faces."""
    faces = solid.faces()
    planes = []
    for f in faces:
        n = o = None
        if f.geom_type == GeomType.PLANE:
            c = f.center()
            v = f.normal_at(c)
            n = np.array([v.X, v.Y, v.Z])
            o = float(n @ np.array([c.X, c.Y, c.Z]))
        b = f.bounding_box()
        planes.append((n, o, np.array([b.min.X, b.min.Y, b.min.Z]), np.array([b.max.X, b.max.Y, b.max.Z])))

    metal, slabs = set(), {}   # slabs: sheet face -> (axis, near side, far side)
    for i, (n, o, lo, hi) in enumerate(planes):
        if n is None:
            continue
        axis = int(np.argmax(np.abs(n)))
        if abs(abs(n[axis]) - 1) > 1e-3:
            continue
        for j in range(i + 1, len(planes)):
            n2, o2, lo2, hi2 = planes[j]
            if n2 is None or n @ n2 > -0.999:
                continue
            overlap = np.delete(np.minimum(hi, hi2) - np.maximum(lo, lo2), axis)
            # Outward normals: o + o2 is the thickness when material lies between the faces,
            # and minus the gap when they face each other across air.
            if SHEET_MIN < o + o2 < SHEET_MAX and (overlap > 0.05).all():
                metal |= {i, j}
                a, b = o * np.sign(n[axis]), o2 * np.sign(n2[axis])
                slabs[i] = slabs[j] = (axis, min(a, b), max(a, b))

    edges = [{e.wrapped.__hash__() for e in f.edges()} for f in faces]
    corners = [[np.array([v.X, v.Y, v.Z]) for v in f.vertices()] for f in faces]

    def within_neighbours(i, neighbours, tol=0.02):
        # An edge or bend face of a sheet lies wholly inside the extent of the metal faces it
        # joins; a housing face next to a terminal always reaches past them somewhere.
        boxes = [(planes[m][2] - tol, planes[m][3] + tol) for m in neighbours]
        return all(any((lo <= c).all() and (c <= hi).all() for lo, hi in boxes) for c in corners[i])

    def across_sheet(i, neighbours, tol=0.02):
        # ...or it runs exactly across the thickness of a neighbouring sheet, side to side (an
        # end face, where the sheet's own side face is fused into the housing).
        for m in neighbours:
            if m in slabs:
                axis, near, far = slabs[m]
                c = [p[axis] for p in corners[i]]
                if near - tol <= min(c) and max(c) <= far + tol and max(c) - min(c) > (far - near) / 2:
                    return True
        return False

    for _ in range(3):
        grown = set()
        for i, f in enumerate(faces):
            if i in metal or f.area >= EDGE_MAX_AREA:
                continue
            neighbours = [m for m in metal if edges[i] & edges[m]]
            if len(neighbours) >= 2 and (within_neighbours(i, neighbours) or across_sheet(i, neighbours)):
                grown.add(i)
        if not grown:
            break
        metal |= grown

    # Keep only connected groups big enough to be a terminal or hold-down.
    kept, seen = set(), set()
    for start in metal:
        if start in seen:
            continue
        group, stack = set(), [start]
        seen.add(start)
        while stack:
            i = stack.pop()
            group.add(i)
            for j in metal - seen:
                if edges[i] & edges[j]:
                    seen.add(j)
                    stack.append(j)
        if len(group) >= MIN_PART_FACES and sum(faces[i].area for i in group) >= MIN_PART_AREA:
            kept |= group
    return kept


def recolor_with_pins(path: Path, body: tuple[float, float, float], pins: tuple[float, float, float]) -> None:
    solid = import_step(path).solids()[0]
    # Bake the vendor placement into the geometry so the file holds one plain solid: KiCad looks
    # face colors up on the placed faces, which a referenced (placed) shape doesn't match.
    loc = solid.wrapped.Location()
    solid = Solid(BRepBuilderAPI_Transform(solid.wrapped.Located(TopLoc_Location()), loc.Transformation(), True).Shape())
    metal = metal_faces(solid)
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    XCAFApp_Application.GetApplication_s().InitDocument(doc)
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    colors = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    rgb = lambda c: Quantity_Color(*c, Quantity_TypeOfColor.Quantity_TOC_sRGB)  # noqa: E731
    # Same layout as the housing-only models KiCad already colors: an assembly holding the
    # solid as one component.
    top = shapes.NewShape()
    TDataStd_Name.Set_s(top, TCollection_ExtendedString(path.stem))
    shape_label = shapes.AddShape(solid.wrapped, False)
    TDataStd_Name.Set_s(shape_label, TCollection_ExtendedString("body"))
    shapes.AddComponent(top, shape_label, TopLoc_Location())
    colors.SetColor(shape_label, rgb(body), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
    stored = Solid(XCAFDoc_ShapeTool.GetShape_s(shape_label)).faces()
    assert len(stored) == len(solid.faces())
    # Every face gets its own color: KiCad doesn't fall back to the solid's color for faces
    # without one once any face has a color.
    for i, face in enumerate(stored):
        sub = shapes.AddSubShape(shape_label, face.wrapped)
        if sub.IsNull():
            raise RuntimeError(f"face {i} not found in {path.name}")
        colors.SetColor(sub, rgb(pins if i in metal else body), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
    shapes.UpdateAssemblies()
    writer = STEPCAFControl_Writer()
    writer.SetNameMode(True)
    writer.SetColorMode(True)
    writer.Transfer(doc, STEPControl_AsIs)
    writer.Write(str(path))
    print(f"Recolored {path.name}: {len(metal)} of {len(solid.faces())} faces metal")


def main() -> None:
    for name, color in MODELS.items():
        recolor(SHAPES_DIR / name, color)
    for name, (body, pins) in MODELS_WITH_PINS.items():
        recolor_with_pins(SHAPES_DIR / name, body, pins)


if __name__ == "__main__":
    main()
