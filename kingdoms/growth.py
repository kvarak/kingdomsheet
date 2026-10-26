"""Settlement growth rules (PF2e Kingmaker).

- A village builds in one block only.
- When the village's block is full (4 lots), a building in an adjacent block makes it a town.
- A town has 2 to 4 contiguous blocks (any shape: line, L, T or S).
- When each of the town's 4 blocks has at least 2 lots built, the next building may go anywhere on
  the grid, and the settlement becomes a city.
- A settlement's level is the number of blocks with at least one building, at most 20.
- A city builds anywhere. A metropolis is never reached automatically: it needs kingdom level 15,
  at least 2 lots in every block and no overcrowding, and is chosen by hand.

Blocks are numbered 0-8, left to right and top to bottom.
"""

VILLAGE, TOWN, CITY, METROPOLIS = "village", "town", "city", "metropolis"
ORDER = (VILLAGE, TOWN, CITY, METROPOLIS)
LOTS_PER_BLOCK = 4
MAX_TOWN_BLOCKS = 4
CITY_LOTS_PER_BLOCK = 2
METROPOLIS_KINGDOM_LEVEL = 15
BLOCK_COUNT = 9
MAX_SETTLEMENT_LEVEL = 20


class PlacementNotAllowed(Exception):
    """The message explains the rule and is safe to show the user."""


def building_lots(building_key):
    """Lots a building covers, from its key such as "2/keep"."""
    return int(building_key.split("/", 1)[0])


def lots_per_block(placements):
    counts = {}
    for placement in placements:
        counts[placement.block] = counts.get(placement.block, 0) + building_lots(placement.building)
    return counts


def adjacent(a, b):
    """Blocks sharing a side. Diagonal blocks are not adjacent."""
    row_a, col_a = divmod(a, 3)
    row_b, col_b = divmod(b, 3)
    return abs(row_a - row_b) + abs(col_a - col_b) == 1


def contiguous(blocks):
    blocks = set(blocks)
    if not blocks:
        return True
    reached, frontier = set(), [next(iter(blocks))]
    while frontier:
        block = frontier.pop()
        if block in reached:
            continue
        reached.add(block)
        frontier.extend(b for b in blocks if adjacent(block, b) and b not in reached)
    return reached == blocks


def rank(settlement_type):
    return ORDER.index(settlement_type)


def higher(a, b):
    return a if rank(a) >= rank(b) else b


def settlement_level(counts):
    """A settlement's level is the number of blocks with at least one building, at most 20."""
    return min(MAX_SETTLEMENT_LEVEL, sum(1 for lots in counts.values() if lots))


def type_from_layout(counts):
    """The smallest type whose shape fits these buildings."""
    used = [block for block, lots in counts.items() if lots]
    if len(used) <= 1:
        return VILLAGE
    if len(used) <= MAX_TOWN_BLOCKS and contiguous(used):
        return TOWN
    return CITY


def ready_for_city(counts):
    used = [block for block, lots in counts.items() if lots]
    return len(used) == MAX_TOWN_BLOCKS and all(
        counts[block] >= CITY_LOTS_PER_BLOCK for block in used
    )


def effective_type(stored_type, counts):
    """Rules follow the higher of the saved type and what the buildings already show."""
    return higher(stored_type, type_from_layout(counts))


def check_placement(stored_type, counts, block):
    """Raise PlacementNotAllowed if a new building may not go in `block`."""
    current = effective_type(stored_type, counts)
    used = sorted(b for b, lots in counts.items() if lots)
    if current in (CITY, METROPOLIS) or not used or block in used:
        return
    if current == VILLAGE:
        home = used[0]
        if counts[home] < LOTS_PER_BLOCK:
            raise PlacementNotAllowed(
                f"A village builds in one block only (block {home + 1}). Fill all "
                f"{LOTS_PER_BLOCK} lots there, then build next to it to become a town."
            )
        if not adjacent(home, block):
            raise PlacementNotAllowed(
                f"To grow into a town, build in a block next to block {home + 1}."
            )
        return
    if ready_for_city(counts):
        return
    if len(used) >= MAX_TOWN_BLOCKS:
        raise PlacementNotAllowed(
            f"A town has at most {MAX_TOWN_BLOCKS} blocks. Build at least "
            f"{CITY_LOTS_PER_BLOCK} lots in each of them, then the next building can go "
            "anywhere and the town becomes a city."
        )
    if not any(adjacent(block, b) for b in used):
        raise PlacementNotAllowed(
            f"A town grows into blocks next to its own ({_block_list(used)}). "
            f"Block {block + 1} is not next to any of them."
        )


def allowed_blocks(stored_type, counts):
    allowed = set()
    for block in range(BLOCK_COUNT):
        try:
            check_placement(stored_type, counts, block)
        except PlacementNotAllowed:
            continue
        allowed.add(block)
    return allowed


def type_after_placement(stored_type, counts_before, counts_after):
    """Placing never lowers the type. Building once a town is ready for city makes a city."""
    new_type = higher(effective_type(stored_type, counts_before), type_from_layout(counts_after))
    if new_type == TOWN and ready_for_city(counts_before):
        new_type = CITY
    return new_type


def type_after_removal(stored_type, counts_after):
    """Recalculate from the remaining buildings. A metropolis is a deliberate choice and stays."""
    if stored_type == METROPOLIS:
        return METROPOLIS
    return type_from_layout(counts_after)


def status(stored_type, counts, kingdom_level, overcrowded):
    """A short hint about where the settlement may build and how it grows next."""
    current = effective_type(stored_type, counts)
    used = sorted(b for b, lots in counts.items() if lots)
    if current == VILLAGE:
        if not used:
            return ["Village: the first building decides the village's block."]
        home = used[0]
        if counts[home] < LOTS_PER_BLOCK:
            return [
                f"Village: build only in block {home + 1} "
                f"({counts[home]} of {LOTS_PER_BLOCK} lots built). When it is full, build in "
                "a block next to it to become a town."
            ]
        return [f"Block {home + 1} is full: build in a block next to it to become a town."]
    if current == TOWN:
        if not used:
            return ["Town with no buildings yet: the first building can go in any block."]
        if ready_for_city(counts):
            return ["Ready to become a city: the next building can go anywhere."]
        return [
            f"Town in blocks {_block_list(used)}: build in these blocks or next to them, up to "
            f"{MAX_TOWN_BLOCKS} blocks. With at least {CITY_LOTS_PER_BLOCK} lots in each of 4 "
            "blocks, the next building makes it a city."
        ]
    full_enough = sum(1 for b in range(BLOCK_COUNT) if counts.get(b, 0) >= CITY_LOTS_PER_BLOCK)
    checks = [
        (
            kingdom_level >= METROPOLIS_KINGDOM_LEVEL,
            f"kingdom level {METROPOLIS_KINGDOM_LEVEL}+ (now {kingdom_level})",
        ),
        (
            full_enough == BLOCK_COUNT,
            f"at least {CITY_LOTS_PER_BLOCK} lots in every block ({full_enough} of {BLOCK_COUNT})",
        ),
        (not overcrowded, "not overcrowded"),
    ]
    if current == METROPOLIS:
        return ["Metropolis: build anywhere. Extra urban grids are not supported yet."]
    lines = ["City: build anywhere."]
    if all(ok for ok, _ in checks):
        lines.append("Ready to become a metropolis: choose Metropolis as the type.")
    else:
        missing = "; ".join(text for ok, text in checks if not ok)
        lines.append(f"Metropolis needs: {missing}.")
    return lines


def _block_list(blocks):
    numbers = [str(b + 1) for b in sorted(blocks)]
    return numbers[0] if len(numbers) == 1 else f"{', '.join(numbers[:-1])} and {numbers[-1]}"
