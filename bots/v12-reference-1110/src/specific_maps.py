"""Methods extracted from frozen measured map-specific components."""
"""Economy-first baseline: coordinated camps, ability use, shopping and banking.

Only public SDK observations are used. Bytes 0..4 hold six packed camp claims; bytes 5..7 hold an expiring enemy alert.
"""
import cambc as bc
from risk_model import NORMAL_BANK
from equipment import has_jungle
from action_ready import actions_blocked,can_use_ability
from initialization import advance_setup
from coordination import read_claims, write_claim, report, read_report
from cambc import game_map as gm
from navigation import distance_field, spawn_distances, nearest_groups
from tactics import lethal_recent_loss

T, I, C = bc.Team, bc.ItemType, bc.ChampionType


def dist(a, b):
    return a.chebyshev_distance(b)


def disk(p, r):
    b = bc.Bitboard()
    b.draw_chebyshev(p, r)
    return b


from economy_bot import Bot as EconomyBase
from bot import Bot as TacticalBase

class PreviousEconomy(EconomyBase):

    def attack(self, me, targets):
        if not me.can_attack():
            return False
        mask = self.attack_mask(me)
        valid = [x for x in targets if x.is_visible() and x.health() > 0 and mask.is_set(x.position())]
        if not valid:
            return False

        def value(x):
            self.check_budget()
            score = 1000 if x.health() <= me.strength() else 0
            if isinstance(x, bc.Champion):
                score += 150 + min(x.gem_count(), 100)
                if x.is_submitting_gems():
                    score += 200
                if x.champion_name() in (C.WILLOW, C.CASSI):
                    score += 60
            if self.kind == C.VARG:
                score += 60 * sum((dist(x.position(), y.position()) <= 1 for y in valid))
            return score - x.health() / 40
        target = max(valid, key=value)
        if isinstance(target, bc.Champion) and target.champion_name() == C.REN and (me.health() <= 0.2 * target.focus() + 20):
            return False
        self.check_budget()
        me.attack(target)
        if not me.is_alive():
            self.previous_health = None
            return False
        return target.is_visible() and target.health() > 0

    def combat(self, me, targets, moved=False):
        attacked = self.attack(me, targets)
        if not me.is_alive():
            return
        self.check_budget()
        self.cast(me, targets, moved, attacked)
        if not me.is_alive():
            return
        if me.can_attack():
            self.check_budget()
            self.attack(me, self.targets())

class PreviousTactical(TacticalBase):

    def attack(self, me, targets):
        if not me.can_attack():
            return False
        mask = self.attack_mask(me)
        valid = [x for x in targets if x.is_visible() and x.health() > 0 and mask.is_set(x.position()) and (not self.rows or self.boss_allowed(me, x))]
        if not valid:
            return False

        def value(x):
            self.check_budget()
            score = 1000 if x.health() <= me.strength() else 0
            if isinstance(x, bc.Champion):
                contested = any((crate and dist(x.position(), p) <= 3 for crate, p in zip(self.crates, self.centers)))
                score += (1200 if contested else 150) + min(x.gem_count(), 100)
                if x.is_submitting_gems():
                    score += 200
                if x.champion_name() in (C.WILLOW, C.CASSI):
                    score += 60
            if self.kind == C.VARG:
                score += 60 * sum((dist(x.position(), y.position()) <= 1 for y in valid))
            return score - x.health() / 40
        target = max(valid, key=value)
        if isinstance(target, bc.Champion) and target.champion_name() == C.REN and (me.health() <= 0.2 * target.focus() + 20):
            return False
        self.check_budget()
        me.attack(target)
        if not me.is_alive():
            return False
        return target.is_visible() and target.health() > 0

    def combat(self, me, targets, moved=False):
        self.check_budget()
        attacked = self.attack(me, targets)
        if not me.is_alive():
            return
        self.cast(me, targets, moved, attacked)
        if not me.is_alive():
            return
        self.check_budget()
        if me.can_attack():
            self.check_budget()
            self.attack(me, self.targets())

class TerritoryEconomy(PreviousEconomy):

    def setup_steps(self, me):
        self.groups = list(gm.camp_groups())
        self.camp_by_tile = {(c.spawn_position().x, c.spawn_position().y): c for g in self.groups for c in g}
        self.group_stats = [(sum((c.base_stats().base_health for c in g)), sum((c.base_stats().base_strength for c in g)), any((c.is_monolith() for c in g))) for g in self.groups]
        self.masks = [g.spawn_tiles() for g in self.groups]
        self.centers = [m.positions()[0] for m in self.masks]
        self.altars = gm.altars().positions()
        self.spawn = gm.spawn_region(T.ALLY)
        self.static_terrain = gm.walls() | gm.holes() | gm.altars()
        self.terrain = self.static_terrain | gm.spawn_region(T.ENEMY)
        self.allies_by_slot = sorted(bc.champions(T.ALLY), key=int)
        self.slot = [int(c) for c in self.allies_by_slot].index(int(me))
        self.kind = me.champion_name()
        self.collision = gm.width() == 41 and gm.height() == 41 and ({(p.x, p.y) for p in self.altars} == {(27, 20), (39, 20)})
        self.home_bottom = min((p.y for p in self.spawn.positions())) < 10
        yield
        _, home_costs = spawn_distances(self.static_terrain, self.spawn, self.masks)
        yield
        _, enemy_costs = spawn_distances(self.static_terrain, gm.spawn_region(T.ENEMY), self.masks)
        self.home_groups = [home < 65535 and home <= enemy for home, enemy in zip(home_costs, enemy_costs)]
        yield
        self.path_fields = []
        for mask in self.masks:
            f = bc.DistanceField()
            f.compute(self.terrain, mask & ~self.terrain, bc.Bitboard())
            self.path_fields.append(f)
            yield
        tribute_goals = bc.Bitboard()
        for altar in self.altars:
            tribute_goals |= disk(altar, bc.constants.SUBMIT_GEMS_RANGE)
        self.bank_field = distance_field(self.terrain, tribute_goals)
        me.set_priority(20 - self.slot)
        self.ready = True

    def choose_group(self, me):
        visible = bc.vision.visible_tiles()
        if self.target is not None and bc.round_number() % 8 != self.slot % 8 and (self.failed_until.get(self.target, 0) <= bc.round_number()):
            if (self.masks[self.target] & visible).is_empty():
                return self.target
            state = self.groups[self.target].state()
            if not isinstance(state, gm.CampGroupRespawning):
                return self.target
            self.sleep_until[self.target] = bc.round_number() + state.timer + 1
        claims = read_claims()
        jungle = has_jungle(me.item_count())
        candidates = []
        shortlist = nearest_groups(self.path_fields, me.position(), self.target, self.check_budget)
        for index in shortlist:
            if bc.fuel_remaining() < getattr(self, 'safety_select_reserve', 900000) and candidates:
                break
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
            if travel > 10000:
                continue
            hp, incoming, boss = self.group_stats[index]
            if index == self.target and len(group) <= 4:
                hp = sum((c.health() if c.is_visible() else c.base_stats().base_health for c in group))
            if boss and me.strength() < 200:
                continue
            ready = isinstance(state, gm.CampGroupRewardAvailable)
            if hasattr(self, 'safe_camp') and (not self.safe_camp(me, index, ready, hp, incoming)):
                continue
            damage = max(1, me.strength() * (1.6 if self.kind == C.VARG and len(group) > 1 else 1.15))
            clear = 0 if ready else hp / damage
            value = (group.gem_value() + 0.18 * group.gold_value()) / (travel + clear + 7)
            value *= 1.35 if self.home_groups[index] else 0.65
            if jungle:
                incoming *= 0.7
            reserve = incoming * clear * 0.55
            if not ready and reserve > me.health() * 0.75:
                value *= 0.15
            if boss:
                value *= 0.15
            if self.alert and dist(position, self.alert) <= 6:
                value *= 0.45
            if ready:
                value *= 2
                if index == self.target and self.masks[index].is_set(me.position()):
                    value *= 20
            if index == self.target:
                value *= 1.35
            if self.kind == C.CASSI and incoming == 0:
                value *= 1.5
            if any((slot != self.slot and v == index + 1 and self.allies_by_slot[slot].is_alive() for slot, v in enumerate(claims) if slot < len(self.allies_by_slot))):
                value *= 0.25
            candidates.append((value, index))
        return max(candidates)[1] if candidates else None

class FragmentEconomy(PreviousEconomy):

    def setup_steps(self, me):
        self.groups = list(gm.camp_groups())
        self.camp_by_tile = {(c.spawn_position().x, c.spawn_position().y): c for g in self.groups for c in g}
        self.group_stats = [(sum((c.base_stats().base_health for c in g)), sum((c.base_stats().base_strength for c in g)), any((c.is_monolith() for c in g))) for g in self.groups]
        self.masks = [g.spawn_tiles() for g in self.groups]
        self.centers = [m.positions()[0] for m in self.masks]
        self.altars = gm.altars().positions()
        self.spawn = gm.spawn_region(T.ALLY)
        self.static_terrain = gm.walls() | gm.holes() | gm.altars()
        self.terrain = self.static_terrain | gm.spawn_region(T.ENEMY)
        self.allies_by_slot = sorted(bc.champions(T.ALLY), key=int)
        self.slot = [int(c) for c in self.allies_by_slot].index(int(me))
        self.kind = me.champion_name()
        self.collision = gm.width() == 41 and gm.height() == 41 and ({(p.x, p.y) for p in self.altars} == {(27, 20), (39, 20)})
        self.home_bottom = min((p.y for p in self.spawn.positions())) < 10
        signature = (gm.width(), gm.height(), frozenset(((p.x, p.y) for p in self.altars)))
        self.specific_fragment = signature == (30, 30, frozenset({(14, 5), (15, 24)}))
        self.specific_tangle = signature == (100, 80, frozenset({(23, 68), (41, 54), (58, 25), (76, 11)}))
        self.specific_wall = signature == (50, 40, frozenset({(17, 19), (17, 20), (32, 19), (32, 20)}))
        yield
        self.path_fields = []
        for mask in self.masks:
            f = bc.DistanceField()
            f.compute(self.terrain, mask & ~self.terrain, bc.Bitboard())
            self.path_fields.append(f)
            yield
        tribute_goals = bc.Bitboard()
        for altar in self.altars:
            tribute_goals |= disk(altar, bc.constants.SUBMIT_GEMS_RANGE)
        self.bank_field = distance_field(self.terrain, tribute_goals)
        me.set_priority(20 - self.slot)
        self.ready = True

    def choose_group(self, me):
        visible = bc.vision.visible_tiles()
        if self.target is not None and bc.round_number() % 8 != self.slot % 8 and (self.failed_until.get(self.target, 0) <= bc.round_number()):
            if (self.masks[self.target] & visible).is_empty():
                return self.target
            state = self.groups[self.target].state()
            if not isinstance(state, gm.CampGroupRespawning):
                return self.target
            self.sleep_until[self.target] = bc.round_number() + state.timer + 1
        claims = read_claims()
        jungle = has_jungle(me.item_count())
        candidates = []
        shortlist = nearest_groups(self.path_fields, me.position(), self.target, self.check_budget)
        for index in shortlist:
            if bc.fuel_remaining() < getattr(self, 'safety_select_reserve', 900000) and candidates:
                break
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
            if travel > 10000:
                continue
            hp, incoming, boss = self.group_stats[index]
            if index == self.target and len(group) <= 4:
                hp = sum((c.health() if c.is_visible() else c.base_stats().base_health for c in group))
            if boss and me.strength() < 200:
                continue
            ready = isinstance(state, gm.CampGroupRewardAvailable)
            if hasattr(self, 'safe_camp') and (not self.safe_camp(me, index, ready, hp, incoming)):
                continue
            damage = max(1, me.strength() * (1.6 if self.kind == C.VARG and len(group) > 1 else 1.15))
            clear = 0 if ready else hp / damage
            value = (group.gem_value() + 0.18 * group.gold_value()) / (travel + clear + 7)
            if jungle:
                incoming *= 0.7
            reserve = incoming * clear * 0.55
            if not ready and reserve > me.health() * 0.75:
                value *= 0.15
            if boss:
                value *= 0.15
            if self.alert and dist(position, self.alert) <= 6:
                value *= 0.45
            if ready:
                value *= 2
                if index == self.target and self.masks[index].is_set(me.position()):
                    value *= 20
            if index == self.target:
                value *= 1.35
            if self.kind == C.CASSI and incoming == 0:
                value *= 1.5
            if any((slot != self.slot and v == index + 1 and self.allies_by_slot[slot].is_alive() for slot, v in enumerate(claims) if slot < len(self.allies_by_slot))):
                share = False
                if self.specific_fragment:
                    for slot, v in enumerate(claims):
                        if slot == self.slot or v != index + 1 or slot >= len(self.allies_by_slot):
                            continue
                        ally = self.allies_by_slot[slot]
                        if ally.is_alive() and ally.is_visible() and (ally.health() >= 0.65 * ally.max_health()) and (self.path_fields[index].get(ally.position()) <= 6):
                            share = True
                            break
                value *= 0.9 if share else 0.25
            candidates.append((value, index))
        return max(candidates)[1] if candidates else None

    def play_turn(self):
        me = bc.me()
        if not self.ready:
            self.setup(me)
        self.action_round = bc.round_number()
        self.turns += 1
        self.shop(me)
        if not me.is_alive():
            self.previous_health = None
            self.claim(None)
            self.recovering = True
            return
        burst = lethal_recent_loss(self.previous_health, self.previous_round, me.health(), bc.round_number())
        self.previous_health, self.previous_round = (me.health(), bc.round_number())
        self.safety_begin(me)
        if self.safety_channel(me):
            return
        if not me.can_move() and (not me.can_attack()) and (not me.can_cast()):
            return
        if actions_blocked(me, bc):
            return
        if self.spawn.is_set(me.position()):
            if me.health() < me.max_health():
                return
            self.recovering = False
        if self.safety_act(me):
            return
        enemies = self.enemies()
        self.threats = [(c.spawn_position(), c.base_stats().base_strength, c.attack_range()) for c in self.visible_camps() if c.base_stats().base_strength > 0]
        self.threats += [(e.position(), e.strength() + 0.3 * e.focus(), 4) for e in enemies]
        self.alert = self.communicate(me)
        self.safety_threat_round = self.action_round
        pressure = self.pressure(me.position())
        if burst or me.health() < max(me.max_health() * 0.14, pressure * 2.5 + 30):
            self.recovering = True
        if self.return_from_inner and (not self.spawn.is_set(me.position())) and (not me.gem_count()):
            self.recovering = True
        if self.spawn.is_set(me.position()):
            self.return_from_inner = False
        if self.recovering:
            self.claim(None)
            self.defend(me)
            self.retreat(me, self.enemies())
            return
        if self.turns % 8 == self.slot and me.ward_cooldown() == 0:
            placements = me.ward_placement_tiles() & ~self.blockers(me) & ~bc.vision.ward_tiles(T.ALLY) & bc.vision.visible_tiles()
            if not placements.is_empty():
                toward = self.centers[self.target] if self.target is not None else self.altars[0]
                self.check_budget()
                me.place_ward(min(placements.positions(), key=lambda p: dist(p, toward)))
        gems = me.gem_count()
        near_altar = self.bank_field.get(me.position()) + bc.constants.SUBMIT_GEMS_RANGE
        needed = bc.constants.WINNING_GEMS - bc.global_submitted_gems(T.ALLY)
        bank_threshold = NORMAL_BANK
        if self.specific_tangle and bc.global_submitted_gems(T.ALLY) >= 800:
            bank_threshold = 20
        if self.specific_wall and (not self.safety_active) and (not self.recovering) and (me.health() >= 0.7 * me.max_health()):
            bank_threshold = 80
        if gems and (self.bank_committed or gems >= bank_threshold or near_altar <= 4 or (gems >= needed) or (bc.round_number() > 1900)):
            self.claim(None)
            self.bank(me)
            return
        if self.kind != C.TAVI and me.gold_count() >= 150 and (not gems):
            self.claim(None)
            self.recovering = True
            self.retreat(me, enemies)
            return
        if self.support(me):
            return
        self.farm(me)

class GiftEconomy(PreviousEconomy):

    def setup_steps(self, me):
        self.groups = list(gm.camp_groups())
        self.camp_by_tile = {(c.spawn_position().x, c.spawn_position().y): c for g in self.groups for c in g}
        self.group_stats = [(sum((c.base_stats().base_health for c in g)), sum((c.base_stats().base_strength for c in g)), any((c.is_monolith() for c in g))) for g in self.groups]
        self.masks = [g.spawn_tiles() for g in self.groups]
        self.centers = [m.positions()[0] for m in self.masks]
        self.altars = gm.altars().positions()
        self.spawn = gm.spawn_region(T.ALLY)
        self.static_terrain = gm.walls() | gm.holes() | gm.altars()
        self.terrain = self.static_terrain | gm.spawn_region(T.ENEMY)
        self.allies_by_slot = sorted(bc.champions(T.ALLY), key=int)
        self.slot = [int(c) for c in self.allies_by_slot].index(int(me))
        self.kind = me.champion_name()
        self.collision = gm.width() == 41 and gm.height() == 41 and ({(p.x, p.y) for p in self.altars} == {(27, 20), (39, 20)})
        self.home_bottom = min((p.y for p in self.spawn.positions())) < 10
        self.gift_completion = (gm.width(), gm.height(), frozenset(((p.x, p.y) for p in self.altars))) == (45, 45, frozenset({(12, 20), (14, 28), (30, 16), (32, 24)}))
        yield
        self.path_fields = []
        for mask in self.masks:
            f = bc.DistanceField()
            f.compute(self.terrain, mask & ~self.terrain, bc.Bitboard())
            self.path_fields.append(f)
            yield
        tribute_goals = bc.Bitboard()
        for altar in self.altars:
            tribute_goals |= disk(altar, bc.constants.SUBMIT_GEMS_RANGE)
        self.bank_field = distance_field(self.terrain, tribute_goals)
        me.set_priority(20 - self.slot)
        self.ready = True

    def choose_group(self, me):
        visible = bc.vision.visible_tiles()
        if self.target is not None and bc.round_number() % 8 != self.slot % 8 and (self.failed_until.get(self.target, 0) <= bc.round_number()):
            if (self.masks[self.target] & visible).is_empty():
                return self.target
            state = self.groups[self.target].state()
            if not isinstance(state, gm.CampGroupRespawning):
                return self.target
            self.sleep_until[self.target] = bc.round_number() + state.timer + 1
        claims = read_claims()
        jungle = has_jungle(me.item_count())
        candidates = []
        shortlist = nearest_groups(self.path_fields, me.position(), self.target, self.check_budget)
        for index in shortlist:
            if bc.fuel_remaining() < getattr(self, 'safety_select_reserve', 900000) and candidates:
                break
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
            if travel > 10000:
                continue
            hp, incoming, boss = self.group_stats[index]
            if index == self.target and len(group) <= 4:
                hp = sum((c.health() if c.is_visible() else c.base_stats().base_health for c in group))
            elif index == self.target and self.gift_completion and (bc.fuel_remaining() > 1550000):
                remaining = 0
                for camp in group:
                    self.check_budget()
                    remaining += camp.health() if camp.is_visible() else camp.base_stats().base_health
                hp = remaining
            if boss and me.strength() < 200:
                continue
            ready = isinstance(state, gm.CampGroupRewardAvailable)
            if hasattr(self, 'safe_camp') and (not self.safe_camp(me, index, ready, hp, incoming)):
                continue
            damage = max(1, me.strength() * (1.6 if self.kind == C.VARG and len(group) > 1 else 1.15))
            clear = 0 if ready else hp / damage
            value = (group.gem_value() + 0.18 * group.gold_value()) / (travel + clear + 7)
            if jungle:
                incoming *= 0.7
            reserve = incoming * clear * 0.55
            if not ready and reserve > me.health() * 0.75:
                value *= 0.15
            if boss:
                value *= 0.15
            if self.alert and dist(position, self.alert) <= 6:
                value *= 0.45
            if ready:
                value *= 2
                if index == self.target and self.masks[index].is_set(me.position()):
                    value *= 20
            if index == self.target:
                value *= 1.35
            if self.kind == C.CASSI and incoming == 0:
                value *= 1.5
            if any((slot != self.slot and v == index + 1 and self.allies_by_slot[slot].is_alive() for slot, v in enumerate(claims) if slot < len(self.allies_by_slot))):
                value *= 0.25
            candidates.append((value, index))
        return max(candidates)[1] if candidates else None

class CooperativeEconomy(PreviousEconomy):

    def setup_steps(self, me):
        self.groups = list(gm.camp_groups())
        self.camp_by_tile = {(c.spawn_position().x, c.spawn_position().y): c for g in self.groups for c in g}
        self.group_stats = [(sum((c.base_stats().base_health for c in g)), sum((c.base_stats().base_strength for c in g)), any((c.is_monolith() for c in g))) for g in self.groups]
        self.masks = [g.spawn_tiles() for g in self.groups]
        self.centers = [m.positions()[0] for m in self.masks]
        self.altars = gm.altars().positions()
        self.spawn = gm.spawn_region(T.ALLY)
        self.static_terrain = gm.walls() | gm.holes() | gm.altars()
        self.terrain = self.static_terrain | gm.spawn_region(T.ENEMY)
        self.allies_by_slot = sorted(bc.champions(T.ALLY), key=int)
        self.slot = [int(c) for c in self.allies_by_slot].index(int(me))
        self.kind = me.champion_name()
        self.collision = gm.width() == 41 and gm.height() == 41 and ({(p.x, p.y) for p in self.altars} == {(27, 20), (39, 20)})
        self.home_bottom = min((p.y for p in self.spawn.positions())) < 10
        self.cooperative_map = (gm.width(), gm.height(), frozenset(((p.x, p.y) for p in self.altars))) in {(51, 51, frozenset({(25, 2), (25, 48), (25, 25)})), (67, 73, frozenset({(33, 36)})), (51, 51, frozenset({(30, 25)}))}
        yield
        self.path_fields = []
        for mask in self.masks:
            f = bc.DistanceField()
            f.compute(self.terrain, mask & ~self.terrain, bc.Bitboard())
            self.path_fields.append(f)
            yield
        tribute_goals = bc.Bitboard()
        for altar in self.altars:
            tribute_goals |= disk(altar, bc.constants.SUBMIT_GEMS_RANGE)
        self.bank_field = distance_field(self.terrain, tribute_goals)
        me.set_priority(20 - self.slot)
        self.ready = True

    def choose_group(self, me):
        visible = bc.vision.visible_tiles()
        if self.target is not None and bc.round_number() % 8 != self.slot % 8 and (self.failed_until.get(self.target, 0) <= bc.round_number()):
            if (self.masks[self.target] & visible).is_empty():
                return self.target
            state = self.groups[self.target].state()
            if not isinstance(state, gm.CampGroupRespawning):
                return self.target
            self.sleep_until[self.target] = bc.round_number() + state.timer + 1
        claims = read_claims()
        jungle = has_jungle(me.item_count())
        candidates = []
        shortlist = nearest_groups(self.path_fields, me.position(), self.target, self.check_budget)
        for index in shortlist:
            if bc.fuel_remaining() < getattr(self, 'safety_select_reserve', 900000) and candidates:
                break
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
            if travel > 10000:
                continue
            hp, incoming, boss = self.group_stats[index]
            if index == self.target and len(group) <= 4:
                hp = sum((c.health() if c.is_visible() else c.base_stats().base_health for c in group))
            if boss and me.strength() < 200:
                continue
            ready = isinstance(state, gm.CampGroupRewardAvailable)
            if hasattr(self, 'safe_camp') and (not self.safe_camp(me, index, ready, hp, incoming)):
                continue
            damage = max(1, me.strength() * (1.6 if self.kind == C.VARG and len(group) > 1 else 1.15))
            clear = 0 if ready else hp / damage
            value = (group.gem_value() + 0.18 * group.gold_value()) / (travel + clear + 7)
            if jungle:
                incoming *= 0.7
            reserve = incoming * clear * 0.55
            if not ready and reserve > me.health() * 0.75:
                value *= 0.15
            if boss:
                value *= 0.15
            if self.alert and dist(position, self.alert) <= 6:
                value *= 0.45
            if ready:
                value *= 2
                if index == self.target and self.masks[index].is_set(me.position()):
                    value *= 20
            if index == self.target:
                value *= 1.35
            if self.kind == C.CASSI and incoming == 0:
                value *= 1.5
            if any((slot != self.slot and v == index + 1 and self.allies_by_slot[slot].is_alive() for slot, v in enumerate(claims) if slot < len(self.allies_by_slot))):
                share = False
                if self.cooperative_map:
                    for slot, v in enumerate(claims):
                        if slot == self.slot or v != index + 1 or slot >= len(self.allies_by_slot):
                            continue
                        ally = self.allies_by_slot[slot]
                        if ally.is_alive() and ally.is_visible() and (ally.health() >= 0.65 * ally.max_health()) and (self.path_fields[index].get(ally.position()) <= 6):
                            share = True
                            break
                value *= 0.9 if share else 0.25
            candidates.append((value, index))
        return max(candidates)[1] if candidates else None
