import cambc as bc
from cambc import game_map as gm
from coordination import read_claims
from assignments import assign_home_camps
from economy_bot import Bot as EconomyBot, dist
T,I,C=bc.Team,bc.ItemType,bc.ChampionType

class RouteBot(EconomyBot):
    def setup(self, me):
        super().setup(me)
        self.rows_owners={}
        self.rows_home=set()
        home=self.spawn.positions()[0]
        away=gm.spawn_region(T.ENEMY).positions()[0]
        camps=[]
        for index,center in enumerate(self.centers):
            hp,incoming,boss=self.group_stats[index]
            if not boss and dist(center,home)<dist(center,away):
                distance=self.path_fields[index].get(home)
                if distance<10000:
                    self.rows_home.add(index)
                    camps.append((index,distance,incoming>0 and len(self.groups[index])>1))
        self.rows_owners=assign_home_camps([(slot,a.champion_name()==C.VARG) for slot,a in enumerate(self.allies_by_slot)],camps)

    def choose_group(self, me):
        visible = bc.vision.visible_tiles()
        claims = read_claims()
        candidates = []
        # Bound tactical work: prefilter geometrically before live queries.
        shortlist = sorted(range(len(self.groups)), key=lambda i: dist(me.position(),self.centers[i]))[:10]
        if self.target is not None and self.target not in shortlist: shortlist.append(self.target)
        for index in shortlist:
            if bc.fuel_remaining() < 900000 and candidates: break
            self.check_budget()
            group = self.groups[index]
            owner=self.rows_owners.get(index)
            borrowed=False
            if owner is not None and owner!=self.slot and self.allies_by_slot[owner].is_alive():
                # Preserve opening routes. Later, an owner explicitly releasing
                # its claim (banking/recovery) makes its home camp available.
                if bc.round_number()<40 or claims[owner]!=0:
                    # Preserve only a capture already in progress, not a long
                    # borrowed fight when the owner's normal route resumes.
                    if self.target!=index or not self.masks[index].is_set(me.position()): continue
                    if not isinstance(group.state(),gm.CampGroupRewardAvailable): continue
                borrowed=True
            if self.rows_home and any(slot!=self.slot and value==index+1 and self.allies_by_slot[slot].is_alive()
                                      for slot,value in enumerate(claims) if slot<len(self.allies_by_slot)):
                continue  # Do not interrupt a borrower already clearing/capturing.
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
            if borrowed: value *= .6
            if self.rows_home and index not in self.rows_home:
                value *= .25  # Distant fallback only while the home route is unavailable.
            if me.item_count()[I.JUNGLE_EMBLEM_OF_STRENGTH]: incoming *= .7
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

