"""Render the README images with kicad-cli:

    graphics/CellKeeper_top.png        bare board, top-down (the ENC1 case footprint left out)
    graphics/CellKeeper_enclosure.png  board in its case, from the right front

    python python_scripts/render_readme_images.py

Run enclosure/cellkeeper_case.py first if the case changed, so ENC1's models are current. Close
nothing in KiCad: the board is only read. Set KICAD_CLI if kicad-cli is not at the KiCad 10 path.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

PROJECT = Path(__file__).resolve().parents[1]
BOARD = PROJECT / "CellKeeper" / "CellKeeper.kicad_pcb"
GRAPHICS = PROJECT / "graphics"
KICAD_CLI = Path(os.environ.get("KICAD_CLI", r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"))
ENCLOSURE_FP = '(footprint "CellKeeper_Local:CellKeeper_Enclosure"'

VIEWS = {
    # name: (board file, kicad-cli render arguments)
    "CellKeeper_top.png": ("bare", ["--side", "top", "--width", "4000", "--height", "2200"]),
    "CellKeeper_enclosure.png": ("full", ["--side", "top", "--rotate", "-52,0,-32", "--width", "3200", "--height", "2000"]),
}


def without_enclosure(text: str) -> str:
    """The board file text with the ENC1 footprint block removed."""
    i = text.index(ENCLOSURE_FP)
    start = text.rfind("\n", 0, i) + 1
    depth, j = 0, i
    while True:
        c = text[j]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        elif c == '"':
            j = text.index('"', j + 1)
        j += 1
    return text[:start] + text[j + 1:]


def render(board: Path, args: list[str], out: Path) -> None:
    """Render on a transparent background, then crop to the board and flatten onto white."""
    raw = out.with_suffix(".raw.png")
    subprocess.run([str(KICAD_CLI), "pcb", "render", "-o", str(raw), "--background", "transparent",
                    "--quality", "high", "--define-var", f"KIPRJMOD={BOARD.parent}", *args, str(board)],
                   check=True)
    im = Image.open(raw).convert("RGBA")
    raw.unlink()
    left, top, right, bottom = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    pad = 40
    im = im.crop((max(left - pad, 0), max(top - pad, 0), min(right + pad, im.width), min(bottom + pad, im.height)))
    flat = Image.new("RGBA", im.size, (255, 255, 255, 255))
    flat.alpha_composite(im)
    flat.convert("RGB").save(out)
    print(f"wrote {out.relative_to(PROJECT)} {flat.size[0]}x{flat.size[1]}")


def main() -> None:
    text = BOARD.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        bare = Path(tmp) / "bare.kicad_pcb"
        bare.write_text(without_enclosure(text), encoding="utf-8", newline="")
        boards = {"bare": bare, "full": BOARD}
        for name, (which, args) in VIEWS.items():
            render(boards[which], args, GRAPHICS / name)


if __name__ == "__main__":
    main()
