"""Bounded, SDK-independent risk arithmetic. Estimates, not a combat simulator."""
import math

SAFE, CAUTION, DANGER, UNKNOWN = range(4)
NORMAL_BANK = 40
CAUTIOUS_BANK = 20
MEMORY_TTL = 6


def distance(a, b):
    return max(abs(a[0]-b[0]), abs(a[1]-b[1]))


def clear_line(a, b, walls):
    """Cheap wall ray, deliberately separate from movement and engine targeting."""
    x, y = a
    dx, dy = abs(b[0]-x), abs(b[1]-y)
    sx, sy = (1 if x < b[0] else -1), (1 if y < b[1] else -1)
    error = dx-dy
    while (x, y) != b:
        e = error*2
        if e > -dy:
            error -= dy
            x += sx
        if e < dx:
            error += dx
            y += sy
        if (x, y) in walls:
            return False
    return True


def enemy_damage(enemy, point, turns, walls):
    """Upper envelope across reachable origins; does not sum two casts in one turn.

    enemy=(position,strength,attack_range,walk_origins,skills,dash_origins).
    skills=(range,radius,damage,cooldown,exclusive_with_movement,reset,cc).
    Origins are static legal (position, walk_cost) pairs, not hidden unit queries.
    """
    origin, strength, reach, origins, skills, dashes = enemy
    if distance(origin, point) > max([reach+turns] + [s[0]+s[1]+turns for s in skills] +
                                     [distance(origin,p)+reach+turns for p in dashes]):
        return 0.0
    basic = 0.0
    for p, cost in origins:
        hits = turns-max(0, cost-1) if reach == 1 else turns-cost
        if hits > 0 and distance(p,point) <= reach and clear_line(p,point,walls):
            basic = max(basic, strength*hits)
    casts = []
    for radius, area, damage, cooldown, exclusive, reset, cc in skills:
        if cooldown >= turns:
            continue
        for p, cost in origins:
            available = turns-cost if exclusive else turns-max(0,cost-1)
            if available <= cooldown:
                continue
            if reset:
                possible = distance(p,point) <= reach
                value = strength
            else:
                possible = distance(p,point) <= radius+area
                # A landed stun can cost a response opportunity; one basic hit
                # is a deliberately conservative reserve, not extra spell damage.
                value = damage + (strength if cc else 0)
            if possible and clear_line(p,point,walls):
                casts.append(value)
                break
    # The two slots can each cast on a different opportunity, never both in one.
    result = basic + sum(sorted(casts,reverse=True)[:turns])
    for p in dashes:
        if distance(p,point) <= reach+(turns-1) and clear_line(p,point,walls):
            # Dash consumes a cast. Only one later cast can follow in two turns.
            result = max(result, strength*turns + (max(casts,default=0) if turns>1 else 0))
    return result


def zone(health, maximum, damage, uncertain=False, gems=0):
    reserve = maximum*(.20 if gems >= CAUTIOUS_BANK else .08)
    if damage > 0 and health <= damage+reserve:
        return DANGER
    if damage > 0 and health <= 2*damage+reserve:
        return CAUTION
    if uncertain:
        return UNKNOWN
    return SAFE


def fast_enemy_damage(enemy,point,turns,walls):
    """Constant-size conservative envelope for the live fuel budget.

    The detailed origin model above remains available for offline checks. This
    envelope may combine incompatible maxima; it is a risk bound, never an action.
    """
    origin,strength,reach,origins,skills,dashes=enemy
    d=distance(origin,point)
    maximum=max([reach+turns+2]+[s[0]+s[1]+turns for s in skills])
    if d>maximum: return 0.0
    if not clear_line(origin,point,walls):
        if not any(clear_line(p,point,walls) for p,c in origins[:3]): return 0.0
    advance=turns if reach==1 else max(0,turns-1)
    basic=strength*turns if d<=reach+advance+(2 if dashes else 0) else 0
    casts=[]
    for radius,area,damage,cooldown,exclusive,reset,cc in skills:
        if cooldown>=turns: continue
        if reset:
            if basic: casts.append(strength)
        elif d<=radius+area+max(0,turns-int(exclusive)):
            casts.append(damage+(strength if cc else 0))
    return basic+sum(sorted(casts,reverse=True)[:turns])


def bank_limit(level, health_ratio, travel, normal=NORMAL_BANK):
    """Regular bank line; red-zone survival takes priority outside this function."""
    if level in (CAUTION,DANGER) or health_ratio < .4:
        return min(normal,CAUTIOUS_BANK)
    # Only already travelling near an altar gets the cheap small-bag exception.
    if travel <= 2:
        return 10
    return normal


def camp_loss(monsters, dps, splash=False, mitigation=1.0):
    """Serial kill-order integration; local Varg splash is credited only in radius.

    Each monster: (health, strength, x, y). Rates are an average over cooldowns.
    Constant-rate approximation; never claims exact skill timing or aggro sharing.
    """
    remaining = [[float(h),float(s),(x,y)] for h,s,x,y in monsters if h>0]
    elapsed, loss = 0.0, 0.0
    while remaining:
        # Minimise weighted completion time: remove high damage per HP first.
        target = max(remaining,key=lambda m:sum(n[1] for n in remaining
                         if n is m or (splash and distance(n[2],m[2])<=1))/max(m[0],1))
        affected = [m for m in remaining if m is target or (splash and distance(m[2],target[2])<=1)]
        duration = min(m[0]/max(dps,1) for m in affected)
        loss += sum(m[1] for m in remaining)*duration*mitigation
        elapsed += duration
        for m in affected:
            m[0] -= duration*max(dps,1)
        remaining = [m for m in remaining if m[0]>.001]
    return loss, math.ceil(elapsed)


def camp_feasible(health, maximum, loss, exit_damage, gems=0):
    # Empty bags still have a survival floor; reward multipliers cannot override.
    margin = maximum*(.20 if gems >= CAUTIOUS_BANK else .12)
    return health > loss+exit_damage+margin
