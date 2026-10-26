"""Urban grid: the building catalog and which lots each placed building covers.

The grid is 3 x 3 blocks of 2 x 2 lots. Building images live in static/img/<lots>/<name>.png,
where <lots> is how many lots the building covers (1, 2 or 4).
"""

from dataclasses import dataclass
from functools import cache

from django.conf import settings
from django.templatetags.static import static

IMAGE_DIR = settings.BASE_DIR / "static" / "img"
BLOCK_IMAGE = "img/settlement-base.png"
BUILDING_SIZES = (1, 2, 4)
BLOCKS = range(9)
LOTS = range(4)
ROTATIONS = (0, 90, 180, 270)
SIDES = [("north", "North"), ("east", "East"), ("south", "South"), ("west", "West")]
BORDER_FEATURES = [
    ("water", "Water"),
    ("bridge", "Bridge"),
    ("wall_wood", "Wall (wood)"),
    ("wall_stone", "Wall (stone)"),
]
# File names that do not read well as labels.
LABEL_FIXES = {"tmple": "Temple"}


@dataclass(frozen=True)
class Building:
    key: str
    label: str
    lots: int

    @property
    def url(self):
        return static(f"img/{self.key}.png")


@cache
def catalog():
    """Every building image, keyed like "2/keep"."""
    buildings = {}
    for lots in BUILDING_SIZES:
        for path in sorted((IMAGE_DIR / str(lots)).glob("*.png")):
            label = LABEL_FIXES.get(path.stem, path.stem.replace("-", " ").capitalize())
            buildings[f"{lots}/{path.stem}"] = Building(f"{lots}/{path.stem}", label, lots)
    return buildings


def catalog_by_size():
    """[(lots, [buildings sorted by label])] for the building picker."""
    buildings = catalog().values()
    return [
        (lots, sorted((b for b in buildings if b.lots == lots), key=lambda b: b.label))
        for lots in BUILDING_SIZES
    ]


def covered_lots(lots, lot, rotation):
    """Return the lots a building covers, or None if it does not fit from that lot."""
    column, row = lot % 2, lot // 2
    if lots == 1:
        return {lot}
    if lots == 4:
        return {0, 1, 2, 3} if lot == 0 else None
    if rotation in (0, 180):
        return {lot, lot + 1} if column == 0 else None
    return {lot, lot + 2} if row == 0 else None


def blocked_lots(placements, block, ignore=None):
    """Map each taken lot in a block to the placement covering it."""
    taken = {}
    for placement in placements:
        building = catalog().get(placement.building)
        if placement.block != block or placement == ignore or building is None:
            continue
        for lot in covered_lots(building.lots, placement.lot, placement.rotation) or ():
            taken[lot] = placement
    return taken


def build_grid(settlement):
    """Return the 9 blocks with their buildings and free lots, ready for the template."""
    placements = list(settlement.placements.all())
    blocks = []
    for block in BLOCKS:
        items, taken = [], blocked_lots(placements, block)
        for placement in placements:
            building = catalog().get(placement.building)
            if placement.block != block or building is None:
                continue
            vertical = building.lots == 2 and placement.rotation in (90, 270)
            items.append(
                {
                    "placement": placement,
                    "building": building,
                    "column": placement.lot % 2 + 1,
                    "row": placement.lot // 2 + 1,
                    "column_span": 2
                    if building.lots == 4 or (building.lots == 2 and not vertical)
                    else 1,
                    "row_span": 2 if building.lots == 4 or vertical else 1,
                    "vertical": vertical,
                    "rotation": placement.rotation,
                }
            )
        free = [
            {"lot": lot, "column": lot % 2 + 1, "row": lot // 2 + 1}
            for lot in LOTS
            if lot not in taken
        ]
        blocks.append({"number": block, "items": items, "free": free})
    return blocks


def border_labels(settlement):
    """{side: "Water, Bridge"} for the read-only sheet."""
    labels = dict(BORDER_FEATURES)
    return {
        side: ", ".join(labels[f] for f in settlement.borders.get(side, []) if f in labels)
        for side, _ in SIDES
    }
