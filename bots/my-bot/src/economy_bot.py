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


class TurnBudget(Exception):
    """Yield before a live observation or action crosses an engine turn."""


class Bot:
    def __init__(self):
        self.ready = False
        self.target = None
        self.sleep_until = {}
        self.failed_until = {}
        self.recovering = False
        self.turns = 0
        self.report_token = None
        self.report_seen = -100
        self.return_from_inner = False
        self.previous_health = None
        self.previous_round = -1

    def setup(self, me):
        advance_setup(self, me, TurnBudget)

    def setup_steps(self, me):
        self.groups = list(gm.camp_groups())
        self.camp_by_tile = {(c.spawn_position().x,c.spawn_position().y):c for g in self.groups for c in g}
        self.group_stats = [(sum(c.base_stats().base_health for c in g),
                             sum(c.base_stats().base_strength for c in g),
                             any(c.is_monolith() for c in g)) for g in self.groups]
        self.masks = [g.spawn_tiles() for g in self.groups]
        self.centers = [m.positions()[0] for m in self.masks]
        self.altars = gm.altars().positions()
        self.spawn = gm.spawn_region(T.ALLY)
        self.static_terrain = gm.walls() | gm.holes() | gm.altars()
        self.terrain = self.static_terrain | gm.spawn_region(T.ENEMY)
        self.allies_by_slot = sorted(bc.champions(T.ALLY), key=int)
        self.slot = [int(c) for c in self.allies_by_slot].index(int(me))
        self.kind = me.champion_name()
        self.collision = gm.width() == 41 and gm.height() == 41 and {(p.x,p.y) for p in self.altars} == {(27,20),(39,20)}
        self.home_bottom = min(p.y for p in self.spawn.positions()) < 10
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

    def claim(self, index):
        self.target = index
        write_claim(self.slot, index)

    def blockers(self, me):
        mask = (self.terrain | bc.vision.champion_tiles() | bc.vision.camp_tiles()
                | bc.vision.teleport_tiles())
        mask.set(me.position(), False)
        return mask

    def move(self, me, goals):
        if not me.can_move() or goals.is_set(me.position()):
            return True
        blocked = self.blockers(me)
        goals = goals & ~blocked
        if goals.is_empty():
            return False
        field = bc.DistanceField()
        field.compute_to(blocked, goals, disk(me.position(), 0), bc.Bitboard())
        step = field.next_move_from(me.position())
        if step is None:
            return False
        self.check_budget()
        if hasattr(self,"safety_step") and not self.safety_step(me,me.position()+step): return False
        if not self.blockers(me).is_set(me.position() + step) and me.can_move() and me.move(step):
            return True
        # A previously hidden blocker is now visible. Retry with a fresh mask.
        blocked = self.blockers(me)
        goals &= ~blocked
        field.compute_to(blocked, goals, disk(me.position(), 0), bc.Bitboard())
        step = field.next_move_from(me.position())
        self.check_budget()
        return (step is not None and me.can_move()
                and not self.blockers(me).is_set(me.position() + step)
                and (not hasattr(self,"safety_step") or self.safety_step(me,me.position()+step)) and me.move(step))

    def shop(self, me):
        # Recycle existing equipment as temporary cash; retain no field reserve.
        if (self.kind == C.TAVI and me.is_alive() and self.spawn.is_set(me.position())
                and bc.fuel_remaining() >= 1200000 and me.can_sell() and me.health() < me.max_health()):
            temporary = I.HOME_SHARD_OF_HEALTH
            inventory = me.item_count()
            if inventory[temporary] == 0:
                borrowed = -1
                if me.gold_count() < 30:
                    # Prefer a shard, then an emblem. Never borrow the temporary bucket.
                    for tier in (0, 1):
                        for index in range(tier, len(inventory), 2):
                            if inventory[index] and index != temporary and index != temporary + 1:
                                borrowed = index
                                break
                        if borrowed >= 0:
                            break
                    if borrowed >= 0:
                        me.sell(bc.ItemType(borrowed))
                try:
                    for _ in range(12):
                        if bc.fuel_remaining() < 1000000 or bc.round_number() != self.action_round:
                            break
                        before = me.health()
                        if before >= me.max_health():
                            break
                        count = min(4, me.gold_count() // 30)
                        if count <= 0 or not me.can_buy(temporary, count):
                            break
                        me.buy(temporary, count)
                        me.sell(temporary, count)
                        if me.health() <= before:
                            break
                finally:
                    if borrowed >= 0:
                        shard = bc.ItemType(borrowed - borrowed % 2)
                        count = 5 if borrowed % 2 else 1
                        me.buy(shard, count)
        if me.gold_count() < 30:
            return
        # Complete each family before moving on. No repeated nonstacking passive.
        focus = self.kind in (C.STELLAR, C.CASSI, C.PRISM, C.WILLOW)
        stat = "FOCUS" if focus else "STRENGTH"
        if not hasattr(self,'resource_shopping'):
            self.check_budget()
            camps=[c for group in getattr(self,'groups',()) for c in group]
            resources=sum(c.is_gem_cluster() or c.is_gold_cluster() for c in camps)
            signature=(gm.width(),gm.height(),frozenset((p.x,p.y) for p in self.altars))
            self.anvil_capture_first=(signature[0],signature[1],signature[2],len(self.groups)) in {(37,31,frozenset({(18,8)}),13),(31,31,frozenset({(5,25),(25,5)}),7)}
            self.resource_shopping=(bool(camps) and resources*3>=len(camps) and signature not in {
                (51,40,frozenset({(13,19),(13,20)})),
                (50,40,frozenset({(17,19),(17,20),(32,19),(32,20)})),
                (33,33,frozenset({(3,16)})),
            })
        second="CAPTURE" if self.resource_shopping else "MONSTER"
        build = [("JUNGLE", stat), (second, stat),
                 ("BRUISER", "HEALTH"), ("BRUISER", stat)]
        if self.anvil_capture_first:
            build[0],build[1]=build[1],build[0]
        if self.kind == C.WILLOW and not self.collision:
            # Base heal already scales from 140 focus; survival first, followed
            # by the same resource/camp throughput family and focus scaling.
            build = [("DURABILITY", "HEALTH"), (second, "FOCUS"),
                     ("BRUISER", "HEALTH"), ("BRUISER", "FOCUS")]
        # A delivery crystal is a planned purchase, not a universal tax on income.
        crystal = bc.ConsumableType.TP_CRYSTAL
        if self.collision and self.kind in (C.VARG, C.TAVI) and me.gold_count() >= 160 and me.can_buy(crystal):
            me.buy(crystal)
        lock = bc.ConsumableType.ALTAR_LOCK
        if me.gold_count() >= 310 and me.can_buy(lock):
            me.buy(lock)
        counts = me.item_count()
        for index, (family, s) in enumerate(build):
            shard = getattr(I, family + "_SHARD_OF_" + s)
            emblem = getattr(I, family + "_EMBLEM_OF_" + s)
            if counts[emblem] and index != len(build) - 1:
                continue
            count = me.gold_count() // 30
            if index != len(build) - 1:
                count = min(count, 5 - counts[shard])
            if count > 0 and me.can_buy(shard, count):
                me.buy(shard, count)
            else:
                break

    def targets(self):
        # Occupancy masks can retain a just-killed entity within this turn.
        return ([x for x in bc.champions(T.ENEMY) if x.is_alive() and x.is_visible()]
                + self.visible_camps())

    def attack_mask(self,me):
        self.check_budget()
        p=me.position()
        radius=me.attack_range()
        self.check_budget()
        result=bc.Bitboard()
        result.draw_chebyshev(bc.Vec2(p.x,p.y),radius)
        return result

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
                if x.is_submitting_gems(): score += 200
                if x.champion_name() in (C.WILLOW, C.CASSI): score += 60
            if self.kind == C.VARG:
                score += 60 * sum(dist(x.position(), y.position()) <= 1 for y in valid)
            return score - x.health() / 40
        target = max(valid, key=value)
        if isinstance(target, bc.Champion) and target.champion_name() == C.REN and me.health() <= .2 * target.focus() + 20:
            return False
        self.check_budget()
        me.attack(target)
        self.attack_executed=True
        if not me.is_alive():
            self.previous_health = None
            return False
        # A kill can change action state; do not reset against stale state.
        return target.is_visible() and target.health() > 0

    def cast(self, me, targets, moved=False, attacked=False):
        self.check_budget()
        if not me.can_cast():
            return False
        options = []
        for ability in me.abilities():
            self.check_budget()
            if not ability.is_ready():
                continue
            info = ability.info()
            if hasattr(self, 'safety_cast_allowed') and (not self.safety_cast_allowed(me, ability, targets)):
                continue
            if moved and info.exclusive_with_movement:
                continue
            if ability.is_attack_reset():
                reset_spent = attacked and not me.can_attack()
                if reset_spent:
                    attack_tiles = self.attack_mask(me)
                    in_range = [t for t in targets if t.is_visible() and t.health() > 0 and attack_tiles.is_set(t.position())]
                    if in_range:
                        options.append((me.strength() * (2 if self.kind == C.VARG else 1), ability, None))
            elif ability.is_shield():
                threat_damage = 0
                origin = me.position()
                for threat in targets:
                    if bc.fuel_remaining() < 350000 or bc.round_number() != self.action_round:
                        self.check_budget()
                    if not threat.is_visible():
                        continue
                    if bc.fuel_remaining() < 350000 or bc.round_number() != self.action_round:
                        self.check_budget()
                    strength = threat.strength()
                    if strength <= 0:
                        continue
                    if bc.fuel_remaining() < 350000 or bc.round_number() != self.action_round:
                        self.check_budget()
                    if not threat.is_visible():
                        continue
                    position = threat.position()
                    reach = threat.attack_range()
                    if dist(origin, position) <= reach:
                        threat_damage += strength
                if bc.fuel_remaining() < 350000 or bc.round_number() != self.action_round:
                    self.check_budget()
                if threat_damage and (not me.buffs().has_shield()):
                    options.append((min(ability.shield_amount(), threat_damage * 5), ability, None))
            elif ability.is_heal():
                for ally in self.allies():
                    if ally != me and dist(me.position(), ally.position()) <= info.range:
                        heal = ability.heal_amount(ally)
                        if heal > 50:
                            danger = self.pressure(ally.position())
                            urgency = 3 if ally.health() < danger * 2 + 60 else 1
                            options.append((heal * urgency, ability, ally))
            elif ability.is_damage() or ability.is_cc() or ability.is_aoe_damage():
                origin = me.position()
                damage = me.focus() * info.modifier
                live = []
                for unit in targets:
                    if bc.fuel_remaining() < 350000 or bc.round_number() != self.action_round:
                        self.check_budget()
                    if not unit.is_visible():
                        continue
                    if bc.fuel_remaining() < 350000 or bc.round_number() != self.action_round:
                        self.check_budget()
                    health = unit.health()
                    if health > 0:
                        if bc.fuel_remaining() < 350000 or bc.round_number() != self.action_round:
                            self.check_budget()
                        if not unit.is_visible():
                            continue
                        live.append((unit, unit.position(), health))
                for target, position, health in live:
                    if bc.fuel_remaining() < 350000 or bc.round_number() != self.action_round:
                        self.check_budget()
                    if dist(origin, position) > info.range:
                        continue
                    if isinstance(target, bc.Camp) and (not ability.can_target_camps()):
                        continue
                    if isinstance(target, bc.Champion) and (not ability.can_target_enemies()):
                        continue
                    immune = isinstance(target, bc.Champion) and target.champion_name() == C.MARCELLA
                    if ability.is_cc() and immune and (info.modifier == 0):
                        continue
                    if ability.is_aoe_damage():
                        value = sum((min(hp, damage) for _, point, hp in live if dist(point, position) <= info.radius))
                        destination = position
                    else:
                        value = min(health, damage)
                        destination = target
                    if isinstance(target, bc.Champion):
                        value *= 1.5
                    options.append((value + (0 if immune or not ability.is_cc() else 250 if isinstance(target, bc.Champion) and target.is_submitting_gems() else 30), ability, destination))
        if not options:
            return False
        _, ability, target = max(options, key=lambda x: x[0])
        try:
            self.check_budget()
            if not can_use_ability(me, self.action_round, bc):
                return False
            return ability.use(target)
        except bc.Error as error:
            if ability.is_attack_reset() and str(error) == 'An available attack cannot be reset.':
                print('guarded reset: already available', flush=True)
                return False
            raise

    def combat(self, me, targets, moved=False):
        self.attack_executed=False
        self.attack(me, targets)
        if not me.is_alive(): return
        self.check_budget()
        self.cast(me, targets, moved, self.attack_executed)
        if not me.is_alive(): return
        if me.can_attack():
            self.check_budget()  # A cast may have consumed the remaining budget.
            # Newly revealed enemies remain eligible; newly seen unrelated
            # NPCs do not become an accidental second farming objective.
            followup=self.enemies()+[c for c in targets if isinstance(c,bc.Camp)
                                     and c.is_visible() and c.health()>0]
            self.check_budget()
            self.attack(me,followup)

    def bank(self, me):
        # Collision crystal delivery includes a recall/resupply exit plan.
        if self.collision and self.crystal_delivery(me): return True
        for altar in sorted(self.altars, key=lambda p: dist(me.position(), p)):
            if dist(me.position(), altar) <= bc.constants.SUBMIT_GEMS_RANGE:
                locks = bc.vision.altar_lock_tiles(T.ENEMY)
                if locks.is_set(altar):
                    self.check_budget()
                    if me.can_attack() and self.attack_mask(me).is_set(altar):
                        enemy_lock = next((lock for lock in bc.vision.altar_locks(T.ENEMY)
                                           if lock.position() == altar), None)
                        self.check_budget()
                        if enemy_lock is not None: me.attack(enemy_lock)
                    return True
                lock = me.consumables()[int(bc.ConsumableType.ALTAR_LOCK)]
                if lock.count() and self.enemies() and not bc.vision.altar_lock_tiles().is_set(altar):
                    lock.use(altar)
                self.check_budget()
                me.submit_gems(altar)
                return True
        goals = bc.Bitboard()
        for altar in self.altars: goals |= disk(altar, bc.constants.SUBMIT_GEMS_RANGE)
        return self.move(me, goals)

    def choose_group(self, me):
        visible = bc.vision.visible_tiles()
        # Reuse a live assignment between staggered planning turns. Risk and
        # retreat are still evaluated every turn by the shared safety layer.
        if (self.target is not None and bc.round_number()%8 != self.slot%8
                and self.failed_until.get(self.target,0)<=bc.round_number()):
            if (self.masks[self.target]&visible).is_empty():return self.target
            state=self.groups[self.target].state()
            if not isinstance(state,gm.CampGroupRespawning):return self.target
            self.sleep_until[self.target]=bc.round_number()+state.timer+1
        claims = read_claims()
        jungle = has_jungle(me.item_count())
        candidates = []
        # Bound live queries after ranking cached terrain-aware travel costs.
        shortlist = nearest_groups(self.path_fields, me.position(), self.target, self.check_budget)
        if not hasattr(self,'_willow_planning_team'):
            self._willow_planning_team=(not self.collision and any(
                ally.champion_name()==C.WILLOW for ally in self.allies_by_slot))
        planning_reserve=getattr(self,"safety_select_reserve",900000)
        if self._willow_planning_team:planning_reserve+=200000
        for index in shortlist:
            if bc.fuel_remaining() < planning_reserve and candidates: break
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
            ready = isinstance(state, gm.CampGroupRewardAvailable)
            if boss and not ready and me.strength() < 200:
                continue
            if hasattr(self,"safe_camp") and not self.safe_camp(me,index,ready,hp,incoming): continue
            damage = max(1, me.strength() * (1.6 if self.kind == C.VARG and len(group) > 1 else 1.15))
            clear = 0 if ready else hp / damage
            value = (group.gem_value() + .18 * group.gold_value()) / (travel + clear + 7)
            if jungle: incoming *= .7
            # Conservative long-clear estimate; later monsters die before the last.
            reserve = incoming * clear * .55
            if not ready and reserve > me.health() * .75: value *= .15
            if boss and not ready: value *= .15
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

    def farm(self, me):
        index = self.choose_group(me)
        self.claim(index)
        if index is None:
            return
        group = self.groups[index]
        camps = [c for c in group if c.is_visible() and c.health() > 0]
        enemies = self.enemies()
        if camps:
            self.combat(me, enemies + camps)
            if not me.is_alive() or not me.can_move():
                return
            camps = [c for c in group if c.is_visible() and c.health() > 0]
        goals = bc.Bitboard()
        if camps:
            for camp in camps:
                if camp.is_golem():
                    self.check_budget()
                    if not camp.is_visible():continue
                    position=camp.position()
                else:
                    position=camp.spawn_position()
                goals |= disk(position, me.attack_range())
        else:
            goals |= self.masks[index]
        self.check_budget()
        before = me.position()
        if not self.move(me, goals):
            self.failed_until[index] = bc.round_number() + 8
            self.claim(None)
            return
        if me.position() != before:
            self.combat(me, [c for c in group if c.is_visible() and c.health() > 0], moved=True)

    def retreat(self, me, enemies):
        # Walk out of attack range before starting a damage-interruptible recall.
        # Ward relocation or combat may have changed personal vision this turn.
        threats = [e for e in self.enemies() if dist(me.position(), e.position()) <= e.attack_range() + 1]
        threats += [c for c in self.visible_camps() if c.strength() > 0
                    and dist(me.position(), c.position()) <= c.attack_range()]
        if threats and me.can_move():
            if self.escape_dash(me, threats): return
            candidates = self.blockers(me).reachable_tiles(me.position(), 1).positions()
            if candidates:
                safe = max(candidates, key=lambda p: (min(dist(p, t.position()) - t.attack_range() for t in threats),
                                                      -min(dist(p, s) for s in self.spawn.positions())))
                self.check_budget()
                if safe != me.position() and not self.blockers(me).is_set(safe):
                    me.move_absolute(safe)
            return
        self.check_budget()
        me.recall()

    def play_turn(self):
        me = bc.me()
        if not self.ready:
            self.setup(me)
        self.action_round = bc.round_number()
        self.turns += 1
        self.shop(me)  # Also shop while dead and use Tavi's remote shop.
        if not me.is_alive():
            self.previous_health = None
            self.claim(None)
            self.recovering = True
            return
        burst = lethal_recent_loss(self.previous_health,self.previous_round,me.health(),bc.round_number())
        self.previous_health,self.previous_round = me.health(),bc.round_number()
        self.safety_begin(me)
        if self.safety_channel(me):
            return
        if not me.can_move() and not me.can_attack() and not me.can_cast():
            return
        if actions_blocked(me,bc):return
        if self.spawn.is_set(me.position()):
            if me.health() < me.max_health():
                return  # Spawn healing is at END of turn.
            self.recovering = False
        if self.safety_act(me): return
        enemies = self.enemies()
        # Conservative danger snapshot, used only for scoring, never targeting.
        self.threats = [(c.spawn_position(), c.base_stats().base_strength, c.attack_range())
                        for c in self.visible_camps() if c.base_stats().base_strength>0]
        self.threats += [(e.position(),e.strength()+.3*e.focus(),4) for e in enemies]
        self.alert = self.communicate(me)
        self.safety_threat_round = self.action_round
        pressure = self.pressure(me.position())
        if burst or me.health() < max(me.max_health() * .14, pressure * 2.5 + 30):
            self.recovering = True
        if self.return_from_inner and not self.spawn.is_set(me.position()) and not me.gem_count():
            self.recovering = True
        if self.spawn.is_set(me.position()): self.return_from_inner = False
        if self.recovering:
            self.claim(None)
            self.defend(me)
            self.retreat(me, self.enemies())
            return
        # Ward ahead along the route periodically, using legal visible placements.
        if self.turns % 8 == self.slot and me.ward_cooldown() == 0:
            placements = (me.ward_placement_tiles() & ~self.blockers(me)
                          & ~bc.vision.ward_tiles(T.ALLY) & bc.vision.visible_tiles())
            if not placements.is_empty():
                toward = self.centers[self.target] if self.target is not None else self.altars[0]
                self.check_budget()
                me.place_ward(min(placements.positions(), key=lambda p: dist(p, toward)))
        gems = me.gem_count()
        near_altar = self.bank_field.get(me.position()) + bc.constants.SUBMIT_GEMS_RANGE
        needed = bc.constants.WINNING_GEMS - bc.global_submitted_gems(T.ALLY)
        if gems and (self.bank_committed or gems >= NORMAL_BANK or near_altar <= 4 or gems >= needed or bc.round_number() > 1900):
            self.claim(None)
            self.bank(me)
            return
        if self.kind != C.TAVI and me.gold_count() >= 150 and not gems:
            self.claim(None)
            self.recovering = True
            self.retreat(me, enemies)
            return
        if self.support(me): return
        self.farm(me)

    def enemies(self):
        return [e for e in bc.champions(T.ENEMY) if e.is_alive() and e.is_visible()]

    def allies(self):
        return [a for a in bc.champions(T.ALLY) if a.is_alive() and a.is_visible()]

    def visible_camps(self):
        camps = [self.camp_by_tile.get((p.x,p.y)) for p in bc.vision.camp_tiles().positions()]
        return [c for c in camps if c is not None and c.is_visible() and c.health()>0]

    def pressure(self, p):
        return sum(damage for position,damage,radius in self.threats if dist(position,p)<=radius)

    def communicate(self, me):
        enemies = self.enemies()
        if enemies:
            enemy = min(enemies, key=lambda e: dist(me.position(), e.position()))
            report(enemy.position().x, enemy.position().y, bc.round_number(), self.pressure(me.position()) * 3 > me.health())
        token, position, age = read_report(bc.round_number())
        if token != self.report_token:
            self.report_token, self.report_seen = token, bc.round_number()
        if position and age <= 8 and bc.round_number() - self.report_seen <= 8:
            return bc.Vec2(*position)
        return None

    def defend(self, me):
        if me.can_cast(): self.cast(me, self.targets())

    def support(self, me):
        if self.kind != C.WILLOW: return False
        allies = [a for a in self.allies() if a != me]
        if not allies: return False
        ally = max(allies, key=lambda a: (a.max_health()-a.health()) + self.pressure(a.position()) * 2)
        if ally.health() < ally.max_health() * .85 or self.pressure(ally.position()) > 30:
            self.claim(None)
            self.cast(me, self.targets())
            if dist(me.position(), ally.position()) > 3:
                self.move(me, disk(ally.position(), 3))
            self.attack(me, self.targets())
            return True
        return False

    def escape_dash(self, me, threats):
        if not me.can_cast(): return False
        ability = next((a for a in me.abilities() if a.is_dash() and a.is_ready()), None)
        if ability is None: return False
        # Use a conservative walkable two-step path: never dash through walls.
        candidates = self.blockers(me).reachable_tiles(me.position(), 2).positions()
        if not candidates: return False
        score = lambda p: min(dist(p,t.position())-t.attack_range() for t in threats)
        target = max(candidates, key=score)
        self.check_budget()
        return score(target) > score(me.position()) and ability.use(target)

    def crystal_delivery(self, me):
        p = me.position()
        y = p.y if self.home_bottom else 40-p.y
        # Inside the pocket, finish normal banking; afterward recall to restock.
        if 8 <= y <= 32 and p.x >= 37:
            self.return_from_inner = True
            return False
        crystal = me.consumables()[int(bc.ConsumableType.TP_CRYSTAL)]
        if not crystal.count() or p.x < 29 or y > 7 or me.gem_count() < 36:
            return False
        takeoff = bc.Vec2(36,5 if self.home_bottom else 35)
        landing = bc.Vec2(33,8 if self.home_bottom else 32)
        if self.alert and dist(self.alert, landing) < 7: return False
        if p != takeoff:
            return self.move(me,disk(takeoff,0))
        if self.blockers(me).is_set(landing): return False
        if self.pressure(p) * 3 + 60 >= me.health(): return False
        self.check_budget()
        if crystal.use(landing):
            self.return_from_inner = True
            return True
        return False

    def check_budget(self):
        if bc.fuel_remaining() < 350000 or bc.round_number() != self.action_round:
            raise TurnBudget()
