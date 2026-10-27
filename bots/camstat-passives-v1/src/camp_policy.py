"""Preserved economy scoring for Corners, where broad tactical scoring regressed."""
import cambc as bc
from equipment import has_jungle
from cambc import game_map as gm
from coordination import read_claims
I,C=bc.ItemType,bc.ChampionType
def dist(a,b): return a.chebyshev_distance(b)

def choose_economy_group(self, me):
    visible = bc.vision.visible_tiles()
    claims = read_claims()
    jungle = has_jungle(me.item_count())
    candidates = []
    # Bound tactical work: prefilter geometrically before live queries.
    shortlist = sorted(range(len(self.groups)), key=lambda i: dist(me.position(),self.centers[i]))[:10]
    if self.target is not None and self.target not in shortlist: shortlist.append(self.target)
    for index in shortlist:
        if bc.fuel_remaining() < 900000 and candidates: break
        self.check_budget()
        group = self.groups[index]
        if self.failed_until.get(index, 0) > bc.round_number():
            continue
        state = None
        if not (self.masks[index] & visible).is_empty():
            state = group.state()
            if isinstance(state, gm.CampGroupRespawning):
                self.sleep_until[index] = bc.round_number() + state.timer + 1
            else:
                self.sleep_until.pop(index, None)
        if self.sleep_until.get(index, 0) > bc.round_number():
            continue
        position = self.centers[index]
        travel = self.path_fields[index].get(me.position())
        if travel > 10000: continue
        hp, incoming, boss = self.group_stats[index]
        if index == self.target and len(group) <= 4:
            hp = sum(c.health() if c.is_visible() else c.base_stats().base_health for c in group)
        # Do not open a boss while weak. Other camps give much safer growth.
        if boss and me.strength() < 200:
            continue
        ready = isinstance(state, gm.CampGroupRewardAvailable)
        damage = max(1, me.strength() * (1.6 if self.kind == C.VARG and len(group) > 1 else 1.15))
        clear = 0 if ready else hp / damage
        value = (group.gem_value() + .18 * group.gold_value()) / (travel + clear + 7)
        if jungle: incoming *= .7
        # Conservative long-clear estimate; later monsters die before the last.
        reserve = incoming * clear * .55
        if not ready and reserve > me.health() * .75: value *= .15
        if boss: value *= .15
        if self.alert and dist(position, self.alert) <= 6: value *= .45
        if ready:
            value *= 2
            if index == self.target and self.masks[index].is_set(me.position()): value *= 20
        if index == self.target:
            value *= 1.35
        if self.kind == C.CASSI and incoming == 0: value *= 1.5
        if any(slot != self.slot and v == index + 1 and self.allies_by_slot[slot].is_alive()
               for slot, v in enumerate(claims) if slot < len(self.allies_by_slot)):
            value *= .25
        candidates.append((value, index))
    return max(candidates)[1] if candidates else None

