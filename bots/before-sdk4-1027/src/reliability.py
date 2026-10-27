"""Conservative replay fixes shared by the existing map controllers.

Long-stall fallback waits for sixty unproductive turns. Short combat cooldowns,
capture channels and shopping are not treated as navigation failures.
"""
import cambc as bc
from progress import Progress

DEBUG = False

def dist(a,b): return a.chebyshev_distance(b)

class Reliable:
    def setup(self,me):
        super().setup(me)
        self.progress = Progress()
        self.route_progress = Progress()
        self.last_live_target = None
        self.detour_until = -1
        self.detour_tiles = []

    def check_budget(self):
        super().check_budget()
        if not bc.me().is_alive():
            from economy_bot import TurnBudget
            raise TurnBudget()

    def play_turn(self):
        self.action_round = bc.round_number()
        me = bc.me()
        if self.ready and not me.is_alive():
            self.progress.reset()
            self.route_progress.reset()
        super().play_turn()

    def blockers(self,me):
        mask = super().blockers(me)
        if bc.round_number() < self.detour_until:
            origin = me.position()
            for p in self.detour_tiles:
                if p != origin: mask.set(p,True)
        return mask

    def move(self,me,goals):
        self.check_budget()
        if me.can_move() and not goals.is_set(me.position()):
            p=me.position()
            # The cached static camp distance is cheap; banking uses distance to
            # the nearest altar. Goal changes alone do not reset productivity.
            distance = (self.path_fields[self.target].get(p) if self.target is not None
                        else min(dist(p,a) for a in self.altars))
            key=(self.target,bool(me.gem_count()))
            resources=(me.gold_count(),me.gem_count(),bc.global_submitted_gems(bc.Team.ALLY),None)
            self.route_progress.observe(bc.round_number(),key,(p.x,p.y),distance,resources)
            if self.route_progress.idle>=60:
                self.detour_tiles=[bc.Vec2(x,y) for x,y in set(self.route_progress.positions) if (x,y)!=(p.x,p.y)]
                self.detour_until=bc.round_number()+6
                self.route_progress.reset()
                if DEBUG: print('route fallback: sixty turns without progress',flush=True)
        return super().move(me,goals)

    def farm(self,me):
        self.check_budget()
        goal=self.target
        hp=None
        if goal is not None:
            hp=sum(c.health() if c.is_visible() else c.base_stats().base_health for c in self.groups[goal])
        p=me.position()
        distance=self.path_fields[goal].get(p) if goal is not None else 0
        resources=(me.gold_count(),me.gem_count(),bc.global_submitted_gems(bc.Team.ALLY),hp)
        self.progress.observe(bc.round_number(),goal,(p.x,p.y),distance,resources)
        if self.progress.idle>=60:
            if goal is not None: self.failed_until[goal]=bc.round_number()+30
            self.claim(None)
            self.progress.reset()
            if DEBUG: print('goal fallback: sixty turns without progress',goal,flush=True)
            if me.gem_count():
                self.bank(me)
                return
        return super().farm(me)

    def retreat(self,me,enemies):
        # Preserve the original threat selection and clearance scoring, but take
        # primitive snapshots before route enumeration can exhaust a turn.
        self.check_budget()
        threats=[]
        origin=me.position()
        for enemy in self.enemies():
            self.check_budget()
            position,reach=enemy.position(),enemy.attack_range()
            if dist(origin,position)<=reach+1: threats.append((position,reach))
        for camp in self.visible_camps():
            self.check_budget()
            if camp.strength()>0:
                position,reach=camp.position(),camp.attack_range()
                if dist(origin,position)<=reach: threats.append((position,reach))
        if threats and me.can_move():
            if self.escape_dash(me,threats): return
            candidates=self.blockers(me).reachable_tiles(origin,1).positions()
            if candidates:
                spawn=tuple(self.spawn.positions())
                safe=max(candidates,key=lambda p:(min(dist(p,t)-r for t,r in threats),
                                                  -min(dist(p,s) for s in spawn)))
                self.check_budget()
                if safe!=origin and not self.blockers(me).is_set(safe): me.move_absolute(safe)
            return
        self.check_budget()
        me.recall()

    def escape_dash(self,me,threats):
        self.check_budget()
        if not me.can_cast(): return False
        ability=next((a for a in me.abilities() if a.is_dash() and a.is_ready()),None)
        if ability is None: return False
        candidates=self.blockers(me).reachable_tiles(me.position(),2).positions()
        if not candidates: return False
        score=lambda p:min(dist(p,t)-r for t,r in threats)
        target=max(candidates,key=score)
        self.check_budget()
        return score(target)>score(me.position()) and ability.use(target)
