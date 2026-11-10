"""Bounded, personally visible rescue: heal/peel, then self-controlled evacuation.

Nearby bodies are never deducted from predicted enemy damage. PvP has no taunt.
"""
import cambc as bc
from navigation import distance_field
from risk_model import DANGER
from cambc import game_map as gm
from coordination import report

WOUNDED = .35
HEALTHY = .70
HELP_TURNS = 6
MAX_APPROACH = 4
# The forced evacuation + early banking combination regressed the fixed case.
# Keep local cover enabled; use the original controller's recovery/recall trigger.
FORCE_WOUNDED_RECALL = False


def dist(a,b):return a.chebyshev_distance(b)


def recall_clearance(distance,reach,ticks,speed=1,age=0):
    # Extra turn allows for alternating turn order and completion at turn start.
    return distance > reach + speed*(ticks+1+age)


class Protection:
    def setup(self,me):
        self.evacuating=False
        self.escort_id=None;self.escort_until=-1;self.escort_rest=-1
        self.contact_evacuating=False
        self.contact_exit_map=(gm.width(),gm.height(),frozenset((p.x,p.y) for p in gm.altars().positions())) in {(41,30,frozenset({(20,15)})),(40,40,frozenset({(3,27),(19,16),(20,23),(36,12)}))}
        super().setup(me)
        self.regroup_map=(gm.width(),gm.height(),frozenset((p.x,p.y) for p in self.altars),len(self.groups)) in {
            (33,33,frozenset({(3,16)}),5),
            (45,30,frozenset({(21,19),(23,10)}),22),
        }
        self.preserve_escape_walk=(gm.width(),gm.height(),frozenset((p.x,p.y) for p in self.altars),len(self.groups)) in {(71, 71, frozenset({(69, 1), (69, 69), (1, 69), (1, 1), (35, 34)}), 30), (35, 31, frozenset({(18, 15), (33, 1), (33, 29)}), 34), (91, 75, frozenset({(45, 50), (6, 70), (84, 4), (45, 24)}), 11), (45, 35, frozenset({(18, 2), (22, 32), (26, 2)}), 32)}
        self.ready=False
        if self.risk_own_abilities is None:self.risk_own_abilities=tuple(me.abilities())
        self.evac_home=getattr(self,'home_field',None)
        if self.evac_home is None:self.evac_home=distance_field(self.terrain,self.spawn)
        self.ready=True

    def safety_act(self,me):
        try:
            result=self.protective_turn(me)
            if not result and not self.recovering and not self.bank_committed:
                if self.early_counter(me):return True
            return result
        finally:
            self.risk_preact=False
            if hasattr(self,'safety_fuel_start'):
                # Preserve actual combat/movement fuel after the added layer.
                spent=max(0,self.safety_fuel_start-bc.fuel_remaining())
                self.safety_select_reserve=self.safety_base_reserve+min(350000,spent)

    def protective_turn(self,me):
        cached=getattr(self,'risk_preact',False)
        p=self.safety_position if cached else me.position()
        if self.spawn.is_set(p):
            self.evacuating=False;self.escort_id=None;self.contact_evacuating=False
            return super().safety_act(me)
        hp=(self.safety_hp/max(1,self.safety_max)) if cached else me.health()/max(1,me.max_health())
        if (getattr(self,'regroup_map',False) and not self.evacuating
                and not self.recovering and self.regroup_turn(me,hp)):
            return True
        if (getattr(self,'contact_exit_map',False) and not self.evacuating
                and self.contact_unfavorable(me,hp)):
            self.evacuating=True;self.contact_evacuating=True
            report(p.x,p.y,bc.round_number(),True)
        wounded=FORCE_WOUNDED_RECALL and hp<=WOUNDED
        if wounded and not self.safety_active:
            # Preserve solo PvE staging. The raised evacuation threshold is for
            # real grouped support or nearby PvP, rather than every farm injury.
            wounded=any(a!=me and a.health()>=HEALTHY*a.max_health()
                        and dist(me.position(),a.position())<=4 for a in self.allies())
        # Personal emergency has precedence over volunteering to guard someone.
        if wounded or self.evacuating:
            self.evacuating=True;self.recovering=True
            self.bank_committed=bool(me.gem_count())
            self.claim(None)
            if getattr(self,'contact_evacuating',False) and bc.fuel_remaining()>900000:
                # Preserve walking: only spells natively compatible with it.
                # No reset is authorised and no unrelated camp is opened.
                self.cast(me,self.enemies(),moved=True,attacked=False)
                if not me.is_alive():return True
            self.retreat(me,self.enemies())
            return True
        if self.safety_active and self.safety_zone(me)==DANGER:
            return super().safety_act(me)
        # Periodic local scan catches NPC injuries without taxing every farm turn.
        scan=self.safety_active or self.escort_id is not None or bc.round_number()%4==self.slot%4
        if hp>=HEALTHY and not self.recovering and scan and bc.fuel_remaining()>1100000:
            if self.protect(me):return True
        return super().safety_act(me)

    def regroup_turn(self,me,hp_ratio):
        # Safe turns and favorable single-enemy fights keep their current flow.
        if (not self.safety_active or len(self.risk_enemies)<2
                or (hp_ratio>.85 and self.safety_gems<20)):
            return False
        p=self.safety_position
        near=[e for e in self.risk_enemies
              if max(abs(p.x-e[0][0]),abs(p.y-e[0][1]))<=max(4,e[2]+1)]
        if len(near)<2 or bc.fuel_remaining()<1500000:
            return False
        if self.risk_damage(p,turns=2)<=.5*self.safety_hp:
            return False
        friends=[];engaged=0
        for ally in self.allies():
            self.check_budget()
            if ally==me or ally.health()<.65*ally.max_health():continue
            q=ally.position();travel=dist(p,q)
            if travel>6:continue
            if ally.is_recalling() or ally.is_submitting_gems() or ally.is_teleporting():continue
            reach=ally.attack_range()
            if travel<=4 and any(max(abs(q.x-e[0][0]),abs(q.y-e[0][1]))<=reach+1 for e in near):
                engaged+=1
            friends.append((ally,q,travel))
        if engaged+1>=len(near):return False
        # An immediate basic kill can remove the numerical disadvantage.
        strength=me.strength();reach=me.attack_range()
        enemies=self.enemies()
        if me.can_attack():
            for enemy in enemies:
                self.check_budget()
                if dist(p,enemy.position())<=reach and enemy.health()<=strength:
                    return False
        clearance=lambda q:min(max(abs(q.x-e[0][0]),abs(q.y-e[0][1])) for e in near)
        current=clearance(p);choices=[]
        for ally,q,travel in friends:
            self.check_budget()
            if (travel>=2 and clearance(q)>=current
                    and self.risk_damage(q,turns=1)<.3*self.safety_hp):
                choices.append((travel,self.evac_home.get(q),q))
        self.claim(None)
        report(p.x,p.y,bc.round_number(),True)
        if choices:
            destination=min(choices,key=lambda x:(x[0],x[1]))[2]
            self.cast(me,enemies,moved=True,attacked=False)
            if not me.is_alive():return True
            goals=bc.Bitboard();goals.draw_chebyshev(destination,1)
            if self.move(me,goals):return True
        # With no participating ally to regroup around, use the established
        # safe recall/escape path rather than continue the camp/bank approach.
        self.evacuating=True;self.contact_evacuating=True
        return False

    def contact_unfavorable(self,me,hp_ratio):
        # A safe/no-enemy turn performs no new live scan or combat arithmetic.
        if (not self.safety_active or not self.risk_enemies
                or hp_ratio>(.80 if self.safety_gems>=20 else .65)):
            return False
        p=self.safety_position
        if not any(max(abs(p.x-e[0][0]),abs(p.y-e[0][1]))<=max(4,e[2]+1)
                   for e in self.risk_enemies):return False
        if bc.fuel_remaining()<1250000:return False
        enemies=[]
        for e in self.enemies():
            self.check_budget()
            if dist(p,e.position())<=6:enemies.append(e)
        if not enemies:return False
        closest=min(enemies,key=lambda e:dist(p,e.position()))
        target=closest.position()
        # Do not invent support from six-tile ally counts. This conservative
        # solo-exit rule leaves already-in-range healthy groups to the old policy.
        for a in self.allies():
            self.check_budget()
            if (a!=me and a.health()>=.65*a.max_health()
                    and not a.is_recalling() and not a.is_submitting_gems()
                    and not a.is_teleporting()
                    and dist(a.position(),target)<=a.attack_range()):return False
        enemy_hp=0.;enemy_power=0.
        for e in enemies:
            self.check_budget()
            if not e.is_visible():continue
            enemy_hp+=e.health();enemy_power+=e.strength()+.25*e.focus()
        if not enemy_hp:return False
        own_power=me.strength()+.25*me.focus()
        # A clearly losing attrition trade, not proximity or enemy HP alone.
        return self.safety_hp/max(1.,enemy_power)<.8*enemy_hp/max(1.,own_power)

    def protect(self,me):
        now=bc.round_number()
        if now<self.escort_rest:return False
        allies=self.allies()  # Controller filters alive AND personally visible.
        wounded=[a for a in allies if a!=me and not self.spawn.is_set(a.position())
                 and a.health()/max(1,a.max_health())<=
                 (.60 if a.is_recalling() or int(a)==self.escort_id else WOUNDED)
                 and dist(me.position(),a.position())<=4]
        if not wounded:
            self.escort_id=None;return False
        ally=max(wounded,key=lambda a:(a.gem_count(),-a.health()/max(1,a.max_health())))
        # A healer may help immediately without abandoning its own delivery.
        if self.rescue_cast(me,ally,heal_only=True):
            self.claim(None);return True
        if me.gem_count()>20 and me.gem_count()*2>ally.gem_count():return False
        enemies=self.enemies()
        pursuers=[e for e in enemies if dist(e.position(),ally.position())<=6]
        # No threat means no reason to occupy a healthy farmer for six turns.
        if not pursuers:
            self.escort_id=None;return False
        # Peel that can work now precedes movement/election. Waiting nearby with
        # no heal, control or attack cannot force an enemy to change targets.
        if self.rescue_cast(me,ally):
            self.claim(None);return True
        self.check_budget()
        goals=bc.Bitboard();goals.draw_chebyshev(ally.position(),2)
        goals &= ~self.terrain
        field=distance_field(self.terrain,goals)
        travel=field.get(me.position())
        if travel>MAX_APPROACH:return False
        helpers=[a for a in allies if a!=ally and not a.is_recalling()
                 and not a.is_submitting_gems() and not a.is_teleporting()
                 and a.health()>=HEALTHY*a.max_health()
                 and (a.gem_count()<=20 or a.gem_count()*2<=ally.gem_count())]
        # Observers can disagree in fog; this only reduces duplicate local guards.
        if helpers and min((field.get(a.position()),int(a)) for a in helpers)!=(travel,int(me)):
            return False
        damage=self.risk_damage(ally.position()) if self.safety_active else 0
        if travel and damage and travel+1>=ally.health()/max(1,damage/2):return False
        if self.escort_id==int(ally) and now>=self.escort_until:
            self.escort_id=None;self.escort_rest=now+HELP_TURNS;return False
        if self.escort_id!=int(ally):
            self.escort_id=int(ally);self.escort_until=now+HELP_TURNS
        if travel:
            return False  # Existing grouped allies only; no empty escort march.
        # Attack only a pursuer already in reach; never chase away from the ward.
        if not self.attack(me,pursuers):return False
        self.claim(None)
        pursuers=[e for e in self.enemies() if dist(e.position(),ally.position())<=6]
        if not pursuers:return True
        if me.can_move():
            blocked=self.blockers(me)
            # Keep the ally's best homeward tile free. Positioning may obstruct
            # approach, but does not force a human/bot enemy to change targets.
            exits=blocked.reachable_tiles(ally.position(),1).positions()
            exit_tile=min(exits,key=lambda p:self.evac_home.get(p)) if exits else None
            choices=[p for p in blocked.reachable_tiles(me.position(),1).positions()
                     if p!=exit_tile and dist(p,ally.position())<=2
                     and self.safety_zone(me,p)!=DANGER
                     and (not self.safety_active or self.risk_damage(p)<me.health()*.5)]
            if choices:
                p=min(choices,key=lambda p:min(dist(p,e.position()) for e in pursuers))
                self.check_budget()
                if p!=me.position():me.move_absolute(p)
        return True

    def early_counter(self,me):
        # No live scan on empty/far-threat turns. Existing same-turn snapshot.
        p=self.safety_position
        if (self.safety_gems>=20 or self.safety_hp<.70*self.safety_max
                or not any(max(abs(p.x-e[0][0]),abs(p.y-e[0][1]))<=1
                           for e in self.risk_enemies)):return
        if not me.can_attack() or me.attack_range()!=1 or bc.fuel_remaining()<750000:return
        self.check_budget();mask=self.attack_mask(me)
        enemies=[e for e in self.enemies() if mask.is_set(e.position())]
        if self.kind==bc.ChampionType.VARG:
            safe=[]
            for enemy in enemies:
                q=enemy.position()
                if not any(self.group_stats[owner][2] for dx in (-1,0,1) for dy in (-1,0,1)
                           if (owner:=self.risk_camp_tiles.get((q.x+dx,q.y+dy))) is not None):safe.append(enemy)
            enemies=safe
        if enemies:
            self.attack(me,enemies)
            return not me.is_alive()

    def rescue_cast(self,me,ally,heal_only=False):
        if not me.can_cast():return False
        for a in self.risk_own_abilities:
            self.check_budget()
            if not a.is_heal() or not a.is_ready() or not a.can_target_allies():continue
            if dist(me.position(),ally.position())<=a.info().range and a.heal_amount(ally)>0:
                self._pending_enemies=None
                return a.use(ally)
        if heal_only:return False
        for e in sorted(self.enemies(),key=lambda e:dist(e.position(),ally.position())):
            if dist(e.position(),ally.position())>6:continue
            if e.champion_name()==bc.ChampionType.MARCELLA:continue
            for a in self.risk_own_abilities:
                self.check_budget()
                if not a.is_ready():continue
                info=a.info()
                if not (a.is_cc() or (a.is_aoe_damage() and getattr(info,'duration',0)>0)):continue
                if a.is_dash() or not a.can_target_enemies():continue
                if dist(me.position(),e.position())>info.range:continue
                radius=getattr(info,'radius',0)
                if radius and self.safety_collateral((e.position().x,e.position().y),int(radius)):continue
                self._pending_enemies=None
                return a.use(e.position() if a.can_target_ground() else e)
        return False

    def recall_safe(self,me,enemies):
        counts=me.item_count()
        home=any(counts[getattr(bc.ItemType,'HOME_EMBLEM_OF_'+s)] for s in ('STRENGTH','FOCUS','HEALTH'))
        ticks=3 if home else bc.constants.RECALL_TIME
        p=me.position()
        for e in enemies:
            self.check_budget()
            # Reserve resettable dashes; do not treat current cooldown as immunity
            # throughout a five-turn recall. Geometry intentionally overestimates.
            reach=max(4,e.attack_range());speed=1
            for a in self.risk_ability_cache.get(int(e),()):
                info=a.info()
                if a.is_dash():speed=3
                elif a.can_target_enemies():reach=max(reach,getattr(info,'range',0))
            if not recall_clearance(dist(p,e.position()),reach,ticks,speed):return False
        visible={int(e) for e in enemies}
        for ident,(r,q) in self.risk_memory.items():
            if ident not in visible and not recall_clearance(max(abs(p.x-q[0]),abs(p.y-q[1])),6,ticks,3,bc.round_number()-r):
                return False
        for c in self.visible_camps():
            self.check_budget()
            if c.is_awake() and c.strength()>0 and dist(p,c.position())<=c.attack_range()+(ticks+1 if c.is_golem() else 0):
                return False
        return True

    def retreat(self,me,enemies):
        if not self.evacuating:return super().retreat(me,enemies)
        self.check_budget()
        # Ward behind us refreshes only our own vision before recall assessment.
        if me.ward_cooldown()==0 and enemies:
            mask=(me.ward_placement_tiles() & bc.vision.visible_tiles()
                  & ~self.blockers(me) & ~bc.vision.ward_tiles(bc.Team.ALLY))
            if not mask.is_empty():
                # No action occurs while ranking. Read each visible enemy
                # position once, not once per candidate ward placement.
                points=[]
                for e in enemies:
                    self.check_budget()
                    q=e.position();points.append((q.x,q.y))
                self.check_budget()
                q=min(mask.positions(),key=lambda p:min(max(abs(p.x-x),abs(p.y-y)) for x,y in points))
                self.check_budget()
                me.place_ward(q);self._pending_enemies=None;enemies=self.enemies()
        if self.recall_safe(me,enemies):
            self.check_budget();me.recall();return
        if not me.can_move():return
        threats=[(e.position(),max(4,e.attack_range())) for e in enemies]
        threats += [(bc.Vec2(*q),6) for r,q in self.risk_memory.values()]
        threats += [(c.position(),c.attack_range()) for c in self.visible_camps()
                    if c.is_awake() and c.strength()>0]
        blocked=self.blockers(me)
        score=lambda p:(min((dist(p,q)-r for q,r in threats),default=0),-self.evac_home.get(p))
        # Conservative walkable dash path also excludes occupied landings.
        if me.can_cast():
            for a in self.risk_own_abilities:
                if a.is_dash() and a.is_ready():
                    visible=bc.vision.visible_tiles();radius=int(getattr(a.info(),'radius',0));choices=[]
                    for p in blocked.reachable_tiles(me.position(),2).positions():
                        self.check_budget()
                        if visible.is_set(p) and not self.safety_collateral((p.x,p.y),radius):choices.append(p)
                    if choices:
                        ranked=[]
                        for p in choices:
                            self.check_budget();ranked.append((score(p),p))
                        p=max(ranked,key=lambda pair:pair[0])[1]
                        self.check_budget()
                        if score(p)>score(me.position()) and a.use(p):return
                    break
        choices=blocked.reachable_tiles(me.position(),1).positions()
        if choices:
            ranked=[]
            for p in choices:
                self.check_budget();ranked.append((score(p),p))
            p=max(ranked,key=lambda pair:pair[0])[1]
            self.check_budget()
            if p!=me.position():me.move_absolute(p)
