"""Shared replay-analysis fixes layered over the three existing map policies.

Only primitive threat snapshots survive route searches. All searches and retries
are bounded. DEBUG enables short goal-change diagnostics in replay stdout.
"""
import cambc as bc
from cambc import game_map as gm
from coordination import read_claims
from progress import Progress

T, C, I = bc.Team, bc.ChampionType, bc.ItemType
DEBUG = False

def dist(a, b): return a.chebyshev_distance(b)

def disk(p, r):
    mask = bc.Bitboard()
    mask.draw_chebyshev(p, r)
    return mask

class Reliable:
    objective_tuning = False

    def setup(self, me):
        super().setup(me)
        self.progress = Progress()
        self.detour_until = -1
        self.avoid = []
        self.last_live_target = None
        self.objectives = [i for i,g in enumerate(self.groups) if g.gem_value() > 0]
        self.objective_group = None

    def check_budget(self):
        # The base exception type is already handled by main.py.
        super().check_budget()
        if not bc.me().is_alive():
            from economy_bot import TurnBudget
            raise TurnBudget()

    def play_turn(self):
        # setup() also does pathfinding; its checks need this round established.
        self.action_round = bc.round_number()
        me = bc.me()
        if self.ready and not me.is_alive():
            if self.last_live_target is not None:
                self.failed_until[self.last_live_target] = bc.round_number() + 75
            self.progress.reset()
            self.avoid = []
        super().play_turn()
        if me.is_alive():
            if self.target is not None: self.last_live_target = self.target

    def move(self, me, goals):
        self.check_budget()
        origin = me.position()
        if not me.can_move() or goals.is_set(origin): return True
        blocked = self.blockers(me)
        if bc.round_number() < self.detour_until:
            for p in self.avoid:
                if p != origin: blocked.set(p, True)
        goals &= ~blocked
        if goals.is_empty(): return False
        field = bc.DistanceField()
        # Exactly two attempts, with a fresh occupancy check before each action.
        for attempt in range(2):
            self.check_budget()
            field.compute_to(blocked, goals, disk(origin, 0), bc.Bitboard())
            self.check_budget()
            step = field.next_move_from(origin)
            if step is None: return False
            destination = origin + step
            current = self.blockers(me)
            self.check_budget()
            if not current.is_set(destination) and me.can_move():
                if me.move(step): return True
            blocked |= current
        return False

    def communicate(self, me):
        # Snapshot live values before any path search or candidate scoring.
        self.threats = []
        for camp in self.visible_camps():
            self.check_budget()
            strength = camp.strength()
            if strength > 0:
                self.threats.append((camp.position(), strength, camp.attack_range()))
        for enemy in self.enemies():
            self.check_budget()
            position = enemy.position()
            self.threats.append((position, enemy.strength(), enemy.attack_range() + 1))
            for ability in enemy.abilities():
                self.check_budget()
                info = ability.info()
                if info is not None and (ability.is_damage() or ability.is_aoe_damage()) and ability.cooldown() <= 1:
                    reach = getattr(info, 'range', 0) + getattr(info, 'radius', 0) + 1
                    self.threats.append((position, enemy.focus() * max(0, info.modifier), reach))
        pressure = self.pressure(me.position())
        if not self.spawn.is_set(me.position()) and pressure * 3 + 50 >= me.health():
            self.recovering = True
        return super().communicate(me)

    def retreat(self, me, enemies):
        self.check_budget()
        origin = me.position()
        # Include the whole visible group, not just the nearest attacker.
        threats = tuple(self.threats)
        def risk(p):
            return sum(damage for position,damage,reach in threats if dist(p,position) <= reach)
        if risk(origin) > 0:
            if me.can_move():
                if self.escape_dash(me, threats): return
                candidates = self.blockers(me).reachable_tiles(origin, 1).positions()
                # Prefer lower combined damage, then clearance and homeward travel.
                def score(p):
                    clearance = min((dist(p,t)-r for t,d,r in threats if d > 0), default=99)
                    return (-risk(p), clearance, -dist(p,self.spawn.positions()[0]))
                if candidates:
                    best = max(candidates, key=score)
                    self.check_budget()
                    if best != origin and not self.blockers(me).is_set(best):
                        me.move_absolute(best)
            return
        self.check_budget()
        me.recall()

    def escape_dash(self, me, threats):
        self.check_budget()
        if not me.can_cast(): return False
        ability = next((a for a in me.abilities() if a.is_dash() and a.is_ready()), None)
        if ability is None: return False
        candidates = self.blockers(me).reachable_tiles(me.position(), 2).positions()
        def score(p):
            return (-sum(d for t,d,r in threats if dist(p,t)<=r),
                    min((dist(p,t)-r for t,d,r in threats if d>0), default=99))
        if not candidates: return False
        target = max(candidates, key=score)
        self.check_budget()
        return score(target) > score(me.position()) and ability.use(target)

    def farm(self, me):
        self.check_budget()
        # Track resources and target health; cooldown waits and captures are useful.
        goal = self.target
        hp = None
        if goal is not None:
            hp = sum(c.health() if c.is_visible() else c.base_stats().base_health for c in self.groups[goal])
        p = me.position()
        distance = self.path_fields[goal].get(p) if goal is not None else 0
        resources = (me.gold_count(), me.gem_count(), bc.global_submitted_gems(T.ALLY), hp)
        stalled = self.progress.observe(bc.round_number(), goal, (p.x,p.y), distance, resources)
        if stalled:
            if goal is not None: self.failed_until[goal] = bc.round_number() + 30
            self.avoid = [bc.Vec2(x,y) for x,y in set(self.progress.positions) if (x,y)!=(p.x,p.y)]
            self.detour_until = bc.round_number() + 6
            self.claim(None)
            self.progress.reset()
            if DEBUG: print('goal fallback: no useful progress', goal, flush=True)
            if me.gem_count():
                self.bank(me)
                return
        if self.objective_tuning:
            index = self.choose_group(me)
            if index is not None and index == self.objective_group and not getattr(self, 'objective_safe', True):
                self.claim(index)
                goals = disk(self.centers[index], 6)
                for camp in self.groups[index]:
                    goals &= ~disk(camp.spawn_position(), camp.attack_range() + 1)
                self.move(me, goals)
                return
        super().farm(me)

    def choose_group(self, me):
        if not self.objective_tuning: return super().choose_group(me)
        # After initial farming items, explicitly consider all scoring sources.
        counts = me.item_count()
        funded = (counts[I.JUNGLE_EMBLEM_OF_STRENGTH] or counts[I.JUNGLE_EMBLEM_OF_FOCUS])
        if not funded or not self.objectives: return super().choose_group(me)
        claims = read_claims()
        candidates = []
        visible = bc.vision.visible_tiles()
        for index in self.objectives:
            self.check_budget()
            if self.failed_until.get(index, 0) > bc.round_number(): continue
            group = self.groups[index]
            if not (self.masks[index] & visible).is_empty():
                state = group.state()
                if isinstance(state, gm.CampGroupRespawning):
                    self.sleep_until[index] = bc.round_number() + state.timer + 1
                    continue
            else: state = None
            if self.sleep_until.get(index, 0) > bc.round_number(): continue
            travel = self.path_fields[index].get(me.position())
            if travel > 10000: continue
            hp,incoming,boss = self.group_stats[index]
            ready = isinstance(state, gm.CampGroupRewardAvailable)
            # All farmers rank the same expensive gem source for rendezvous.
            team = [a for a in self.allies() if a.health() >= a.max_health()*.65
                    and dist(a.position(), self.centers[index]) <= 7]
            power = sum(a.strength()*1.2 for a in team)
            health = sum(a.health() for a in team)
            clear = hp / max(power, me.strength(), 1)
            safe = ready or (len(team) >= (3 if boss else 2) and incoming*clear*.55 < health*.65)
            solo = incoming * hp / max(me.strength()*1.2, 1) * .55 < me.health()*.6
            if not safe and not solo:
                # Rendezvous outside camp reach; farm() will wait for sufficient help.
                if bc.round_number() < 200: continue
            delivery = min(dist(self.centers[index], a) for a in self.altars)
            score = group.gem_value()/(travel + clear + delivery + 8)
            if index == self.target: score *= 1.3
            if ready: score *= 2
            candidates.append((score,index,safe or solo or ready))
        if not candidates: return super().choose_group(me)
        _, index, safe = max(candidates)
        self.objective_group = index
        self.objective_safe = safe
        return index

    def combat(self, me, targets, moved=False):
        # Do not pull an objective while the rendezvous group is still too weak.
        if self.objective_tuning and self.target == self.objective_group and not getattr(self,'objective_safe',True):
            targets = [t for t in targets if not isinstance(t,bc.Camp) or t.camp_group()!=self.groups[self.target]]
        self.check_budget()
        return super().combat(me, targets, moved)
