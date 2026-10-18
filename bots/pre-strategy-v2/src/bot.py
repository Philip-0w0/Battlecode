"""Economy-first baseline: coordinated camps, ability use, shopping and banking.

Only public SDK observations are used. Shared bytes 0..5 hold a camp index+1
per allied champion (0 = not farming); the remaining bytes are reserved.
"""
import cambc as bc
from cambc import game_map as gm

T, I, C = bc.Team, bc.ItemType, bc.ChampionType


def dist(a, b):
    return a.chebyshev_distance(b)


def disk(p, r):
    b = bc.Bitboard()
    b.draw_chebyshev(p, r)
    return b


class Bot:
    def __init__(self):
        self.ready = False
        self.target = None
        self.sleep_until = {}
        self.failed_until = {}
        self.recovering = False
        self.turns = 0

    def setup(self, me):
        self.groups = list(gm.camp_groups())
        self.masks = [g.spawn_tiles() for g in self.groups]
        self.centers = [m.positions()[0] for m in self.masks]
        self.altars = gm.altars().positions()
        self.spawn = gm.spawn_region(T.ALLY)
        self.terrain = gm.walls() | gm.holes() | gm.altars() | gm.spawn_region(T.ENEMY)
        self.slot = sorted(int(c) for c in bc.champions(T.ALLY)).index(int(me))
        self.kind = me.champion_name()
        self.ready = True
        me.set_priority(20 - self.slot)

    def claim(self, index):
        self.target = index
        if self.slot < 6:
            value = index + 1 if index is not None and index < 254 else 0
            bc.shared_memory.write(self.slot, bytes([value]))

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
        if me.move(step):
            return True
        # A previously hidden blocker is now visible. Retry with a fresh mask.
        blocked = self.blockers(me)
        goals &= ~blocked
        field.compute_to(blocked, goals, disk(me.position(), 0), bc.Bitboard())
        step = field.next_move_from(me.position())
        return step is not None and me.move(step)

    def shop(self, me):
        if me.gold_count() < 30:
            return
        # Complete each family before moving on. No repeated nonstacking passive.
        focus = self.kind in (C.STELLAR, C.CASSI, C.PRISM)
        stat = "FOCUS" if focus else "STRENGTH"
        build = [("JUNGLE", stat), ("MONSTER", stat),
                 ("BRUISER", "HEALTH"), ("POWER", stat)]
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
                + [c for g in self.groups for c in g if c.is_visible()])

    def attack(self, me, targets):
        if not me.can_attack():
            return False
        mask = me.attack_tiles()
        valid = [x for x in targets if x.is_visible() and x.health() > 0 and mask.is_set(x.position())]
        if not valid:
            return False
        def value(x):
            score = 1000 if x.health() <= me.strength() else 0
            if isinstance(x, bc.Champion):
                score += 150 + min(x.gem_count(), 100)
            if self.kind == C.VARG:
                score += 60 * sum(dist(x.position(), y.position()) <= 1 for y in valid)
            return score - x.health() / 40
        me.attack(max(valid, key=value))
        return True

    def cast(self, me, targets, moved=False, attacked=False):
        if not me.can_cast():
            return False
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
                if threats and me.health() < me.max_health() * .85 and not me.buffs().has_shield():
                    options.append((ability.shield_amount() * .65, ability, None))
            elif ability.is_heal():
                for ally in bc.vision.champions(T.ALLY):
                    if ally != me and dist(me.position(), ally.position()) <= info.range:
                        heal = ability.heal_amount(ally)
                        if heal > 50:
                            options.append((heal, ability, ally))
            elif ability.is_damage() or ability.is_cc() or ability.is_aoe_damage():
                valid = [t for t in targets if t.is_visible() and t.health() > 0
                         and dist(me.position(), t.position()) <= info.range]
                for target in valid:
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
                    options.append((value + (30 if ability.is_cc() else 0), ability, destination))
        if not options:
            return False
        _, ability, target = max(options, key=lambda x: x[0])
        return ability.use(target)

    def combat(self, me, targets, moved=False):
        attacked = self.attack(me, targets)
        self.cast(me, targets, moved, attacked)
        self.attack(me, self.targets())  # A reset or spell may open a new target.

    def bank(self, me):
        # Prefer the nearest altar; remove hostile locks instead of ignoring it.
        for altar in sorted(self.altars, key=lambda p: dist(me.position(), p)):
            if dist(me.position(), altar) <= bc.constants.SUBMIT_GEMS_RANGE:
                me.submit_gems(altar)
                return True
        goals = bc.Bitboard()
        for altar in self.altars:
            goals |= disk(altar, bc.constants.SUBMIT_GEMS_RANGE)
        return self.move(me, goals)

    def choose_group(self, me):
        visible = bc.vision.visible_tiles()
        claims = bytearray(6)
        bc.shared_memory.read(0, claims)
        candidates = []
        for index, group in enumerate(self.groups):
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
            travel = dist(me.position(), position)
            hp = sum(c.health() if c.is_visible() else c.base_stats().base_health for c in group)
            # Do not open a boss while weak. Other camps give much safer growth.
            if any(c.is_monolith() for c in group) and me.strength() < 200:
                continue
            ready = isinstance(state, gm.CampGroupRewardAvailable)
            damage = max(1, me.strength() * (1.6 if self.kind == C.VARG and len(group) > 1 else 1.15))
            clear = 0 if ready else hp / damage
            value = (group.gem_value() + .18 * group.gold_value()) / (travel + clear + 7)
            if ready:
                value *= 2
            if index == self.target:
                value *= 1.35
            if any(s != self.slot and v == index + 1 for s, v in enumerate(claims)):
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
        enemies = [e for e in bc.vision.champions(T.ENEMY) if e.is_alive()]
        if camps:
            self.combat(me, enemies + camps)
            if not me.can_move():
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
            self.combat(me, [c for c in group if c.is_visible() and c.health() > 0], moved=True)

    def retreat(self, me, enemies):
        # Walk out of attack range before starting a damage-interruptible recall.
        threats = [e for e in enemies if dist(me.position(), e.position()) <= e.attack_range() + 1]
        threats += [c for c in bc.vision.camps() if c.strength() > 0
                    and dist(me.position(), c.position()) <= c.attack_range()]
        if threats and me.can_move():
            candidates = self.blockers(me).reachable_tiles(me.position(), 1).positions()
            if candidates:
                safe = max(candidates, key=lambda p: (min(dist(p, t.position()) - t.attack_range() for t in threats),
                                                      -min(dist(p, s) for s in self.spawn.positions())))
                me.move_absolute(safe)
            return
        me.recall()

    def play_turn(self):
        me = bc.me()
        if not self.ready:
            self.setup(me)
        self.turns += 1
        self.shop(me)  # Also shop while dead and use Tavi's remote shop.
        if not me.is_alive():
            self.claim(None)
            self.recovering = True
            return
        if me.is_recalling() or me.is_submitting_gems() or me.is_teleporting():
            return
        if not me.can_move() and not me.can_attack() and not me.can_cast():
            return
        if self.spawn.is_set(me.position()):
            if me.health() < me.max_health():
                return  # Spawn healing is at END of turn.
            self.recovering = False
        enemies = [e for e in bc.vision.champions(T.ENEMY) if e.is_alive()]
        if me.health() < me.max_health() * .32:
            self.recovering = True
        if self.recovering:
            self.claim(None)
            self.retreat(me, enemies)
            return
        # Ward ahead along the route periodically, using legal visible placements.
        if self.turns % 8 == self.slot and me.ward_cooldown() == 0:
            placements = (me.ward_placement_tiles() & ~self.blockers(me)
                          & ~bc.vision.ward_tiles(T.ALLY) & bc.vision.visible_tiles())
            if not placements.is_empty():
                toward = self.centers[self.target] if self.target is not None else self.altars[0]
                me.place_ward(min(placements.positions(), key=lambda p: dist(p, toward)))
        gems = me.gem_count()
        near_altar = min(dist(me.position(), p) for p in self.altars)
        needed = bc.constants.WINNING_GEMS - bc.global_submitted_gems(T.ALLY)
        if gems and (gems >= 40 or near_altar <= 4 or gems >= needed or bc.round_number() > 1900):
            self.claim(None)
            self.bank(me)
            return
        if self.kind != C.TAVI and me.gold_count() >= 150 and not gems:
            self.claim(None)
            self.recovering = True
            self.retreat(me, enemies)
            return
        self.farm(me)
