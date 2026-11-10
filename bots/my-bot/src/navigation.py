"""Terrain-aware travel costs for planning; combat ranges remain geometric."""
import cambc as bc

UNREACHABLE = 65535


def distance_field(blocked, goals):
    field = bc.DistanceField()
    field.compute(blocked, goals & ~blocked, bc.Bitboard())
    return field


def spawn_distances(terrain, spawn, camp_masks):
    # Ownership compares both teams on neutral terrain. An actor's movement
    # mask blocks enemy spawn and must not be reused to query that spawn.
    field = distance_field(terrain, spawn)
    costs = [min((field.get(p) for p in (mask & ~terrain).positions()),
                 default=UNREACHABLE) for mask in camp_masks]
    return field, costs


def nearest_groups(fields, position, current=None, check_budget=None, limit=10):
    # Fields are already cached; read travel costs before truncating candidates.
    ranked = []
    for index, field in enumerate(fields):
        if check_budget is not None and index % 8 == 0:
            check_budget()
        cost = field.get(position)
        if cost < UNREACHABLE:
            ranked.append((cost, index))
    result = [index for cost, index in sorted(ranked)[:limit]]
    if current is not None and current not in result:
        if fields[current].get(position) < UNREACHABLE:
            result.append(current)
    return result
