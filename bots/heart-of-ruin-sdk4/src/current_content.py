"""SDK 4 content support: awake camps, live camp lookup and Heart of Ruin."""
import cambc as bc
from map_profile import profile

T,C,I=bc.Team,bc.ChampionType,bc.ItemType

def dist(a,b): return a.chebyshev_distance(b)

class CurrentContent:
    def setup(self,me):
        super().setup(me)
        self.map_info=profile()

    def visible_camps(self):
        self.check_budget()
        live=[]
        for n,p in enumerate(bc.vision.camp_tiles().positions()):
            if n%4==0: self.check_budget()
            camp=self.camp_by_tile.get((p.x,p.y))
            if camp is None: camp=bc.vision.camp_at(p)
            if camp.is_visible() and camp.health()>0: live.append(camp)
        return live

    def communicate(self,me):
        self.threats=[]
        for n,camp in enumerate(self.visible_camps()):
            if n%4==0: self.check_budget()
            if camp.is_awake() and camp.strength()>0:
                self.threats.append((camp.position(),camp.strength(),camp.attack_range()))
        for enemy in self.enemies():
            self.check_budget()
            self.threats.append((enemy.position(),enemy.strength()+.3*enemy.focus(),max(4,enemy.attack_range()+1)))
        return super().communicate(me)

    def shop(self,me):
        if self.map_info['zero_gold'] and self.map_info['gems']>0:
            focus=self.kind in (C.PRISM,C.HEART_OF_RUIN,C.TAVI,C.STELLAR,C.WILLOW,C.CASSI)
            shard=I.POWER_SHARD_OF_FOCUS if focus else I.POWER_SHARD_OF_STRENGTH
            n=me.gold_count()//30
            if n and me.can_buy(shard,n): me.buy(shard,n)
            return
        if self.kind!=C.HEART_OF_RUIN: return super().shop(me)
        counts=me.item_count()
        for family,stat in [('JUNGLE','FOCUS'),('MONSTER','FOCUS'),('BRUISER','HEALTH'),('POWER','FOCUS')]:
            shard=getattr(I,family+'_SHARD_OF_'+stat)
            emblem=getattr(I,family+'_EMBLEM_OF_'+stat)
            if family!='POWER' and counts[emblem]: continue
            count=me.gold_count()//30
            if family!='POWER': count=min(count,5-counts[shard])
            if count>0 and me.can_buy(shard,count): me.buy(shard,count)
            else: break

    def cast(self,me,targets,moved=False,attacked=False):
        if self.kind!=C.HEART_OF_RUIN: return super().cast(me,targets,moved,attacked)
        self.check_budget()
        if not me.can_cast(): return False
        units=[]
        incoming=0
        forbidden=[]
        for t in targets:
            self.check_budget()
            if not t.is_visible() or t.health()<=0: continue
            p=t.position()
            awake=isinstance(t,bc.Champion) or t.is_awake()
            if awake and dist(p,me.position())<=t.attack_range()+1: incoming+=t.strength()
            if isinstance(t,bc.Camp) and (self.target is None or t.camp_group()!=self.groups[self.target]):
                forbidden.append(p)
                continue
            units.append((p,t.health(),isinstance(t,bc.Champion)))
        shield=next((a for a in me.abilities() if a.is_shield() and a.is_ready()),None)
        if shield is not None and incoming and not me.buffs().has_shield():
            self.check_budget()
            return shield.use()
        if self.recovering or self.target is None: return False
        dash=next((a for a in me.abilities() if a.is_dash() and a.is_ready()),None)
        if dash is None or not units: return False
        info=dash.info()
        if moved and info.exclusive_with_movement: return False
        blocked=self.blockers(me)
        candidates=(blocked.reachable_tiles(me.position(),int(info.range)) & dash.valid_tiles() & bc.vision.visible_tiles()).positions()
        candidates=sorted(candidates,key=lambda p:min(dist(p,pos) for pos,hp,enemy in units))[:9]
        damage=dash.damage_amount()
        current_risk=self.pressure(me.position())
        best=None;best_score=0
        for p in candidates:
            self.check_budget()
            if bc.fuel_remaining()<650000: break
            if p==me.position() or any(dist(p,boss)<=info.radius for boss in forbidden): continue
            hits=[(hp,enemy) for pos,hp,enemy in units if dist(p,pos)<=info.radius]
            if not hits: continue
            risk=self.pressure(p)
            if risk*3+50>=me.health(): continue
            score=sum(min(hp,damage)*(1.3 if enemy else 1)+ (200 if hp<=damage else 0) for hp,enemy in hits)-3*max(0,risk-current_risk)
            if score>best_score: best_score,best=score,p
        if best is None: return False
        self.check_budget()
        if self.blockers(me).is_set(best): return False
        return dash.use(best)

    def retreat(self,me,enemies):
        # Snapshot only awake camps; dormant camps cannot interrupt a recall.
        self.check_budget()
        threats=[];origin=me.position()
        for enemy in self.enemies():
            self.check_budget()
            p,r=enemy.position(),max(enemy.attack_range(),3 if enemy.champion_name()==C.HEART_OF_RUIN else 0)
            if dist(origin,p)<=r+1: threats.append((p,r))
        for n,camp in enumerate(self.visible_camps()):
            if n%4==0: self.check_budget()
            if camp.is_awake() and camp.strength()>0:
                p,r=camp.position(),camp.attack_range()
                if dist(origin,p)<=r: threats.append((p,r))
        if threats:
            if not me.can_move(): return
            if self.escape_dash(me,threats): return
            candidates=self.blockers(me).reachable_tiles(origin,1).positions()
            if candidates:
                home=self.spawn.positions()[0]
                best=max(candidates,key=lambda p:(min(dist(p,t)-r for t,r in threats),-dist(p,home)))
                self.check_budget()
                if best!=origin and not self.blockers(me).is_set(best): me.move_absolute(best)
            return
        self.check_budget()
        me.recall()
