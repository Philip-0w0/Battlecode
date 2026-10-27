"""Deterministic primary camp ownership, independent of champion execution order."""


def assign_home_camps(champions, camps):
    """champions: (slot, is_varg); camps: (index, home_distance, grouped_monsters).

    Assign Varg first to grouped monsters, then give each other slot its nearest
    unassigned camp. Remaining camps stay available to everyone.
    """
    remaining = list(camps)
    owners = {}
    for slot, is_varg in sorted(champions, key=lambda c: (not c[1], c[0])):
        if not remaining:
            break
        pool = [c for c in remaining if c[2]] if is_varg else remaining
        selected = min(pool or remaining, key=lambda c: (c[1], c[0]))
        owners[selected[0]] = slot
        remaining.remove(selected)
    return owners
