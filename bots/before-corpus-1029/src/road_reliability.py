"""Road of Riches: dormant monsters cannot interrupt a recall."""
import cambc as bc
from reliability import Reliable, dist

class RoadReliable(Reliable):
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
            if camp.is_awake() and camp.strength()>0:
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
