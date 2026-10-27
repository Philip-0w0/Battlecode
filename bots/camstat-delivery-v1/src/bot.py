"""Economy-first baseline: coordinated camps, ability use, shopping and banking.

Only public SDK observations are used. Bytes 0..4 hold six packed camp claims; bytes 5..7 hold an expiring enemy alert.
"""
import cambc as bc
from coordination import read_claims, write_claim, report, read_report, banking_mode, publish_gems, read_gems
from cambc import game_map as gm
from tactics import lethal_recent_loss, winning_load, favorable_fight
from camp_policy import choose_economy_group

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
        self.bag_since = None
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
        self.bank_target = None
        self.help_request = False
        self.stalled = 0
        self.last_position = None
        self.last_target = None

    def setup(self, me):
        self.groups = list(gm.camp_groups())
        self.camp_by_tile = {(c.spawn_position().x,c.spawn_position().y):c for g in self.groups for c in g}
        self.group_stats = [(sum(c.base_stats().base_health for c in g),
                             sum(c.base_stats().base_strength for c in g),
                             any(c.is_monolith() for c in g)) for g in self.groups]
        self.boss_camps={int(c) for index,g in enumerate(self.groups) if self.group_stats[index][2] for c in g}
        self.masks = [g.spawn_tiles() for g in self.groups]
        self.centers = [m.positions()[0] for m in self.masks]
        self.altars = gm.altars().positions()
        self.spawn = gm.spawn_region(T.ALLY)
        self.terrain = gm.walls() | gm.holes() | gm.altars() | gm.spawn_region(T.ENEMY)
        self.allies_by_slot = sorted(bc.champions(T.ALLY), key=int)
        self.slot = [int(c) for c in self.allies_by_slot].index(int(me))
        self.kind = me.champion_name()
        self.collision = gm.width() == 41 and gm.height() == 41 and {(p.x,p.y) for p in self.altars} == {(27,20),(39,20)}
        self.home_bottom = min(p.y for p in self.spawn.positions()) < 10
        self.rows = gm.width() == 50 and gm.height() == 50 and {(p.x,p.y) for p in self.altars} == {(15,16),(34,33)}
        self.corners = gm.width()==71 and gm.height()==71 and len(self.altars)==5
        self.home_field = bc.DistanceField()
        self.home_field.compute(self.terrain, self.spawn, bc.Bitboard())
        self.home_center = self.spawn.positions()[0]
        self.enemy_center = gm.spawn_region(T.ENEMY).positions()[0]
        self.home_distances = [min(dist(p, self.home_center) for p in m.positions()) for m in self.masks]
        self.home_groups = [dist(p,self.home_center) <= dist(p,self.enemy_center) for p in self.centers]
        self.crates = [any(c.is_gem_cluster() for c in g) for g in self.groups]
        self.group_rewards = [g.gem_value()+.18*g.gold_value() for g in self.groups]
        self.altar_groups = [any(dist(p,a)<=4 for a in self.altars) for p in self.centers]
        self.altar_fields = []
        self.altar_home = []
        for altar in self.altars:
            self.altar_home.append(min(self.home_field.get(p) for p in (disk(altar,1)&~self.terrain).positions()))
            field = bc.DistanceField()
            field.compute(self.terrain, disk(altar,bc.constants.SUBMIT_GEMS_RANGE) & ~self.terrain,bc.Bitboard())
            self.altar_fields.append(field)
        self.path_fields = []
        for mask in self.masks:
            f = bc.DistanceField()
            f.compute(self.terrain, mask & ~self.terrain, bc.Bitboard())
            self.path_fields.append(f)
        self.ready = True
        me.set_priority(20 - self.slot)

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
        if not self.blockers(me).is_set(me.position() + step) and me.can_move() and me.move(step):
            return True
        # A previously hidden blocker is now visible. Retry with a fresh mask.
        blocked = self.blockers(me)
        goals &= ~blocked
        field.compute_to(blocked, goals, disk(me.position(), 0), bc.Bitboard())
        step = field.next_move_from(me.position())
        self.check_budget()
        return (step is not None and me.can_move()
                and not self.blockers(me).is_set(me.position() + step) and me.move(step))

    def shop(self, me):
        if me.gold_count() < 30:
            return
        # Complete each family before moving on. No repeated nonstacking passive.
        focus = self.kind in (C.STELLAR, C.CASSI, C.PRISM, C.WILLOW)
        stat = "FOCUS" if focus else "STRENGTH"
        build = [("JUNGLE", stat), ("MONSTER", stat),
                 ("BRUISER", "HEALTH"), ("POWER", stat)]
        # A delivery crystal is a planned purchase, not a universal tax on income.
        crystal = bc.ConsumableType.TP_CRYSTAL
        if self.collision and self.kind in (C.VARG, C.TAVI) and me.gold_count() >= 160 and me.can_buy(crystal):
            me.buy(crystal)
        lock = bc.ConsumableType.ALTAR_LOCK
        if me.gold_count() >= 310 and me.can_buy(lock):
            me.buy(lock)
        counts = me.item_count()
        for family, s in build:
            shard = getattr(I, family + "_SHARD_OF_" + s)
            emblem = getattr(I, family + "_EMBLEM_OF_" + s)
            if counts[emblem] and family != "POWER":
                continue
            count = me.gold_count() // 30
            if family != "POWER":
                count = min(count, 5 - counts[shard])
            if count > 0 and me.can_buy(shard, count):
                me.buy(shard, count)
            else:
                break

    def targets(self):
        # Occupancy masks can retain a just-killed entity within this turn.
        return ([x for x in bc.champions(T.ENEMY) if x.is_alive() and x.is_visible()]
                + self.visible_camps())

    def attack(self, me, targets):
        if not me.can_attack():
            return False
        mask = me.attack_tiles()
        valid = [x for x in targets if x.is_visible() and x.health() > 0 and mask.is_set(x.position()) and (not self.rows or self.boss_allowed(me,x))]
        if not valid:
            return False
        def value(x):
            self.check_budget()
            score = 1000 if x.health() <= me.strength() else 0
            if isinstance(x, bc.Champion):
                # Deny contested rewards before resuming neutral camp damage.
                contested=any(crate and dist(x.position(),p)<=3 for crate,p in zip(self.crates,self.centers))
                score += (1200 if contested else 150) + min(x.gem_count(), 100)
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
        if not me.is_alive():
            return False
        # A kill can change action state; do not reset against stale state.
        return target.is_visible() and target.health() > 0

    def cast(self, me, targets, moved=False, attacked=False):
        if not me.can_cast():
            return False
        if self.rows: targets=[t for t in targets if self.boss_allowed(me,t)]
        options = []
        for ability in me.abilities():
            if not ability.is_ready():
                continue
            info = ability.info()
            if moved and info.exclusive_with_movement:
                continue
            if ability.is_attack_reset():
                in_range = [t for t in targets if t.is_visible() and t.health() > 0
                            and me.attack_tiles().is_set(t.position())]
                if attacked and not me.can_attack() and in_range:
                    options.append((me.strength() * (2 if self.kind == C.VARG else 1), ability, None))
            elif ability.is_shield():
                threats = [t for t in targets if t.is_visible() and t.strength() > 0
                           and dist(me.position(), t.position()) <= t.attack_range()]
                if threats and not me.buffs().has_shield():
                    options.append((min(ability.shield_amount(), sum(t.strength() for t in threats) * 5), ability, None))
            elif ability.is_heal():
                for ally in self.allies():
                    if ally != me and dist(me.position(), ally.position()) <= info.range:
                        heal = ability.heal_amount(ally)
                        if heal > 50:
                            danger = self.pressure(ally.position())
                            urgency = 3 if ally.health() < danger * 2 + 60 else 1
                            options.append((heal * urgency, ability, ally))
            elif ability.is_damage() or ability.is_cc() or ability.is_aoe_damage():
                valid = [t for t in targets if t.is_visible() and t.health() > 0
                         and dist(me.position(), t.position()) <= info.range]
                for target in valid:
                    self.check_budget()
                    if isinstance(target, bc.Camp) and not ability.can_target_camps(): continue
                    if isinstance(target, bc.Champion) and not ability.can_target_enemies(): continue
                    immune = isinstance(target, bc.Champion) and target.champion_name() == C.MARCELLA
                    if ability.is_cc() and immune and info.modifier == 0: continue
                    if ability.is_aoe_damage():
                        affected = [t for t in targets if t.is_visible() and t.health() > 0
                                    and dist(t.position(), target.position()) <= info.radius]
                        value = sum(min(t.health(), me.focus() * info.modifier) for t in affected)
                        destination = target.position()
                    else:
                        value = min(target.health(), me.focus() * info.modifier)
                        destination = target
                    if isinstance(target, bc.Champion):
                        value *= 1.5
                    options.append((value + (0 if immune or not ability.is_cc() else (250 if isinstance(target, bc.Champion) and target.is_submitting_gems() else 30)), ability, destination))
        if not options:
            return False
        _, ability, target = max(options, key=lambda x: x[0])
        try:
            self.check_budget()
            return ability.use(target)
        except bc.Error as error:
            if ability.is_attack_reset() and str(error) == "An available attack cannot be reset.":
                print("guarded reset: already available", flush=True)
                return False
            raise

    def combat(self, me, targets, moved=False):
        self.check_budget()
        attacked = self.attack(me, targets)
        if not me.is_alive(): return
        self.cast(me, targets, moved, attacked)
        if not me.is_alive(): return
        self.check_budget()
        self.attack(me, self.targets())  # A reset or spell may open a new target.

    def bank(self, me):
        # Clear an immediate, favorable enemy threat before a long channel.
        if self.engage(me,defend_only=True): return True
        # Collision crystal delivery includes a recall/resupply exit plan.
        if self.collision and self.crystal_delivery(me): return True
        enemies = self.enemies()
        ranked = []
        for index, altar in enumerate(self.altars):
            distance = self.altar_fields[index].get(me.position())
            if distance > 10000: continue
            risk = sum(30 for enemy in enemies if dist(enemy.position(),altar) <= 6)
            if self.alert and dist(self.alert,altar) <= 5: risk += 15
            score = distance + risk + .12 * self.altar_home[index]
            if index == self.bank_target: score -= 3
            ranked.append((score,index))
        if not ranked: return False
        self.bank_target = min(ranked)[1]
        altar = self.altars[self.bank_target]
        # Clear a visible, manageable guard that covers the chosen tribute tile.
        guards = [c for c in self.visible_camps() if c.strength()>0 and c.health()<c.max_health() and dist(c.position(),altar)<=c.attack_range()+1]
        if guards and not enemies and dist(me.position(),altar)<=5:
            damage = sum(c.strength() for c in guards)
            rounds = sum(c.health() for c in guards)/max(me.strength()*1.5,1)
            if rounds <= 8 and damage*rounds < me.health()*.45:
                self.combat(me,guards)
                if me.is_alive():
                    goals=bc.Bitboard()
                    for c in guards:
                        if c.is_visible() and c.health()>0: goals |= disk(c.position(),me.attack_range())
                    if not goals.is_empty(): self.move(me,goals)
                return True
        for altar in [altar]:
            if dist(me.position(), altar) <= bc.constants.SUBMIT_GEMS_RANGE:
                locks = bc.vision.altar_lock_tiles(T.ENEMY)
                if locks.is_set(altar):
                    self.check_budget()
                    if me.can_attack() and me.attack_tiles().is_set(altar):
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
        return self.move(me, disk(altar,bc.constants.SUBMIT_GEMS_RANGE))

    def choose_group(self, me):
        visible = bc.vision.visible_tiles()
        # Reconsider routes periodically, rather than re-scoring the full map
        # before every step. Still observe depletion and retreat every turn.
        if self.target is not None and bc.round_number()%4 != self.slot%4 and not self.group_stats[self.target][2] and self.failed_until.get(self.target,0)<=bc.round_number():
            if (self.masks[self.target]&visible).is_empty(): return self.target
            state=self.groups[self.target].state()
            if not isinstance(state,gm.CampGroupRespawning): return self.target
            self.sleep_until[self.target]=bc.round_number()+state.timer+1
        if self.corners: return choose_economy_group(self,me)
        claims = read_claims()
        strength,health=me.strength(),me.health()
        jungle=bool(me.item_count()[I.JUNGLE_EMBLEM_OF_STRENGTH])
        candidates = []
        # Bound tactical work: prefilter geometrically before live queries.
        shortlist = sorted(range(len(self.groups)), key=lambda i: dist(me.position(),self.centers[i]))[:10]
        if self.target is not None and self.target not in shortlist: shortlist.append(self.target)
        for index in shortlist:
            if bc.fuel_remaining() < 1100000 and candidates: break
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
            partners = ([a for a in self.allies() if a != me and a.health() >= .65*a.max_health()
                        and dist(a.position(),position)<=7] if boss else [])
            if boss and self.rows:
                if self.kind not in (C.VENDETTA,C.TAVI): continue
                partners=[a for a in partners if a.champion_name() in (C.VENDETTA,C.TAVI)]
            if boss and (not partners or me.health()<.65*me.max_health()): continue
            ready = isinstance(state, gm.CampGroupRewardAvailable)
            damage = max(1, strength * (1.6 if self.kind == C.VARG and len(group) > 1 else 1.15))
            clear = 0 if ready else hp / damage
            if boss:
                damage += sum(a.strength()*1.3 for a in partners)
                clear = 0 if ready else hp/damage
                if incoming*clear*.55 > me.health()+sum(a.health() for a in partners): continue
            value = self.group_rewards[index] / (travel + clear + 7)
            if not self.corners:
                if self.home_groups[index]: value *= 1.35
                else: value *= .65
            if bc.round_number()<90 and self.crates[index] and not self.corners: value *= 1.8
            if self.altar_groups[index]: value *= 1.15
            if self.rows:
                if self.kind in (C.VARG,C.RYTH,C.WILLOW):
                    if incoming and self.home_groups[index]: value *= 2
                    elif self.crates[index]: value *= .65
                elif self.kind in (C.VENDETTA,C.TAVI) and self.crates[index]:
                    value *= 2
            if jungle: incoming *= .7
            # Conservative long-clear estimate; later monsters die before the last.
            reserve = incoming * clear * .55
            if not ready and reserve > health * .75: value *= .15
            if boss: value *= .15
            if self.alert and dist(position, self.alert) <= 6: value *= .45
            if ready:
                value *= 2
                if index == self.target and self.masks[index].is_set(me.position()): value *= 20
            if index == self.target:
                value *= 1.35 if self.corners else 1.8
            if self.kind == C.CASSI and incoming == 0: value *= 1.5
            if any(slot != self.slot and v == index + 1 and self.allies_by_slot[slot].is_alive()
                   for slot, v in enumerate(claims) if slot < len(self.allies_by_slot)):
                value *= .8 if boss else .25
            candidates.append((value, index))
        return max(candidates)[1] if candidates else None

    def farm(self, me):
        index = self.choose_group(me)
        self.claim(index)
        if index is None:
            return
        group = self.groups[index]
        if self.last_position == me.position() and self.last_target == index:
            self.stalled += 1
        else: self.stalled = 0
        self.last_position, self.last_target = me.position(), index
        # Capture needs six phases. Only abandon a long wait outside its tiles.
        if self.stalled >= 8 and not self.masks[index].is_set(me.position()):
            self.failed_until[index] = bc.round_number()+12
            self.claim(None)
            self.stalled = 0
            return
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
                goals |= disk(camp.position(), me.attack_range())
        else:
            goals |= self.masks[index]
        before = me.position()
        if not self.move(me, goals):
            self.failed_until[index] = bc.round_number() + 8
            self.claim(None)
            return
        if me.position() != before:
            self.combat(me, self.enemies()+[c for c in group if c.is_visible() and c.health() > 0], moved=True)

    def retreat(self, me, enemies):
        # Walk out of attack range before starting a damage-interruptible recall.
        # Ward relocation or combat may have changed personal vision this turn.
        threats = [e for e in self.enemies() if dist(me.position(), e.position()) <= e.attack_range() + 1]
        threats += [c for c in self.visible_camps() if c.strength() > 0
                    and dist(me.position(), c.position()) <= c.attack_range()]
        if threats and me.can_move():
            self.check_budget()
            threat_positions=[(t.position(),t.attack_range()) for t in threats]
            if self.escape_dash(me, threats): return
            candidates = self.blockers(me).reachable_tiles(me.position(), 1).positions()
            if candidates:
                safe = max(candidates, key=lambda p: (min(dist(p, position)-radius for position,radius in threat_positions),
                                                      -self.home_field.get(p)))
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
        # Spend scarce team memory on exact carried totals in the endgame.
        if banking_mode() or bc.global_submitted_gems(T.ALLY)>=800 or (me.is_alive() and bc.global_submitted_gems(T.ALLY)+me.gem_count()>=900):
            publish_gems(self.slot,me.gem_count() if me.is_alive() else 0)
        if not me.is_alive():
            self.bag_since = None
            self.previous_health = None
            self.claim(None)
            self.recovering = True
            return
        burst = lethal_recent_loss(self.previous_health,self.previous_round,me.health(),bc.round_number())
        self.previous_health,self.previous_round = me.health(),bc.round_number()
        if not me.gem_count(): self.bag_since = None
        elif self.bag_since is None: self.bag_since = bc.round_number()
        if me.is_recalling() or me.is_submitting_gems() or me.is_teleporting():
            return
        if not me.can_move() and not me.can_attack() and not me.can_cast():
            return
        if self.spawn.is_set(me.position()):
            if me.health() < me.max_health():
                return  # Spawn healing is at END of turn.
            self.recovering = False
        enemies = self.enemies()
        # Conservative danger snapshot, used only for scoring, never targeting.
        self.threats = [(c.spawn_position(), c.base_stats().base_strength, c.attack_range())
                        for c in self.visible_camps() if c.base_stats().base_strength>0]
        self.threats += [(e.position(),e.strength()+.3*e.focus(),4) for e in enemies]
        self.alert = self.communicate(me)
        pressure = self.pressure(me.position())
        if burst or me.health() < max(me.max_health() * .14, pressure * 2.5 + 30):
            self.recovering = True
        if self.return_from_inner and not self.spawn.is_set(me.position()) and not me.gem_count():
            self.recovering = True
        if self.spawn.is_set(me.position()): self.return_from_inner = False
        if self.recovering:
            if enemies or pressure:
                report(me.position().x,me.position().y,bc.round_number(),True)
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
        near_altar = min(dist(me.position(), p) for p in self.altars)
        needed = bc.constants.WINNING_GEMS - bc.global_submitted_gems(T.ALLY)
        team_finish = False
        if gems:
            carried = read_gems()
            for slot,ally in enumerate(self.allies_by_slot):
                if not ally.is_alive(): carried[slot]=0
                elif ally.is_visible(): carried[slot]=ally.gem_count()
            team_finish = winning_load(bc.global_submitted_gems(T.ALLY),carried,bc.constants.WINNING_GEMS)
        if gems and (team_finish or gems >= 40 or (self.bag_since is not None and bc.round_number()-self.bag_since>=120) or near_altar <= 4 or gems >= needed or bc.round_number() > 1900) and not (not team_finish and self.finish_camp(me)):
            self.claim(None)
            self.bank(me)
            return
        if self.engage(me): return
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
        self.check_budget()
        camps = [self.camp_by_tile.get((p.x,p.y)) for p in bc.vision.camp_tiles().positions()]
        live=[]
        for c in camps:
            if c is not None and c.is_visible() and c.health()>0: live.append(c)
        return live

    def pressure(self, p):
        return sum(damage for position,damage,radius in self.threats if dist(position,p)<=radius)

    def communicate(self, me):
        enemies = self.enemies()
        old, _, old_age = read_report(bc.round_number())
        if enemies:
            enemy = min(enemies, key=lambda e: dist(me.position(), e.position()))
            danger = self.pressure(me.position()) * 3 > me.health()
            if danger or not (old & (1<<23) and old_age <= 3):
                report(enemy.position().x, enemy.position().y, bc.round_number(), danger)
        token, position, age = read_report(bc.round_number())
        if token != self.report_token:
            self.report_token, self.report_seen = token, bc.round_number()
        if position and age <= 8 and bc.round_number() - self.report_seen <= 8:
            self.help_request = bool(token & (1<<23)) and age <= 3
            return bc.Vec2(*position)
        self.help_request = False
        return None

    def finish_camp(self, me):
        """Finish a nearly dead group/capture before an optional small deposit."""
        if self.target is None or self.enemies(): return False
        group = self.groups[self.target]
        if (self.masks[self.target]&bc.vision.visible_tiles()).is_empty(): return False
        if isinstance(group.state(),gm.CampGroupRewardAvailable):
            return self.masks[self.target].is_set(me.position())
        remaining = [c for c in group if c.is_visible() and c.health()>0]
        return bool(remaining) and all(c.is_visible() for c in group) and sum(c.health() for c in remaining) <= me.strength()*3 and me.health() > 4*sum(c.strength() for c in remaining)+100

    def boss_allowed(self, me, target):
        if not isinstance(target,bc.Camp) or int(target) not in self.boss_camps: return True
        # Do not incidentally open a boss via fallback attack or defensive spell.
        if self.target is None or not self.group_stats[self.target][2]: return False
        friends=[a for a in self.allies() if a.health()>=.65*a.max_health() and dist(a.position(),target.spawn_position())<=7]
        if len(friends)<2: return False
        if self.rows:
            return {C.VENDETTA,C.TAVI}.issubset({a.champion_name() for a in friends})
        return True

    def engage(self, me, defend_only=False):
        """Defend home resources and focus isolated enemies with nearby allies."""
        enemies = self.enemies()
        for enemy in sorted(enemies,key=lambda e:e.health()):
            self.check_budget()
            p=enemy.position()
            if dist(me.position(),p)>7: continue
            if defend_only and dist(me.position(),p)>me.attack_range()+1: continue
            contest=any(crate and dist(p,center)<=3 for crate,center in zip(self.crates,self.centers))
            if self.corners and not contest and not defend_only: continue
            home=dist(p,self.home_center)<=dist(p,self.enemy_center)
            friends=[a for a in self.allies() if dist(a.position(),p)<=6 and a.health()>=a.max_health()*.65]
            foes=[e for e in enemies if dist(e.position(),p)<=6]
            if not contest and len(friends)<2: continue
            good=favorable_fight(sum(a.health() for a in friends),sum(a.strength()+.25*a.focus() for a in friends),
                                 sum(e.health() for e in foes),sum(e.strength()+.25*e.focus() for e in foes))
            if not (home or contest or len(friends)>len(foes)): continue
            if not good:
                if contest: report(p.x,p.y,bc.round_number(),True)
                continue
            self.claim(None)
            self.combat(me,[enemy])
            if me.is_alive() and enemy.is_visible() and enemy.health()>0 and dist(me.position(),enemy.position())>me.attack_range():
                self.move(me,disk(enemy.position(),me.attack_range()))
                if me.is_alive(): self.combat(me,self.enemies(),moved=True)
            return True
        if not defend_only and self.help_request and self.alert and me.health()>=.8*me.max_health() and me.gem_count()<40 and dist(me.position(),self.alert)<=10:
            if dist(me.position(),self.alert)>3:
                self.claim(None)
                return self.move(me,disk(self.alert,3))
        return False

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
        snapshot=[(t.position(),t.attack_range()) for t in threats]
        score = lambda p: min(dist(p,position)-radius for position,radius in snapshot)
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
        if bc.round_number() != self.action_round or bc.fuel_remaining() < 250000:
            raise TurnBudget()
