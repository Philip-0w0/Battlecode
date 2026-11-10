"""Personal-view safety layer used by all three dispatched controllers.

No new shared-memory layout. Enemy snapshots contain primitives and expire.
"""
import cambc as bc
from cambc import game_map as gm
from equipment import has_jungle
from navigation import distance_field
from risk_model import (SAFE,CAUTION,DANGER,UNKNOWN,NORMAL_BANK,MEMORY_TTL,
                        distance,fast_enemy_damage,zone,bank_limit,camp_feasible)


def xy(p): return (p.x,p.y)


# Full PvE budgeting regressed uncontested farming in the local comparison.
# Default: lightweight existing-camp pressure, enhanced model on fresh PvP intel.
FULL_PVE_SAFETY = False
# Keep routing/combat delegation cheap. The richer replacement regressed scores.
ADVANCED_ACTIONS = False


class Safety:
    safety_active=True  # Standalone model fixtures; setup sets the runtime mode.

    def visible_camps(self):
        if not FULL_PVE_SAFETY:return super().visible_camps()
        # Camp tiles are live positions, including Golems away from their spawn.
        result=[]
        for p in bc.vision.camp_tiles().positions():
            self.check_budget()
            c=self.camp_by_tile.get(xy(p))
            if c is None or c.is_golem(): c=bc.vision.camp_at(p)
            if c is not None and c.is_visible() and c.health()>0: result.append(c)
        return result

    def setup(self,me):
        self._pending_enemies=None;self._pending_enemy_round=-1
        self.risk_memory = {}
        self.risk_round = -1
        self.bank_committed = False
        self.bank_choice = None
        self.risk_cache = {}
        self.camp_risk_cache = {}
        self.risk_ability_cache={}
        self.risk_own_abilities=None
        self.risk_stats=None
        self.safety_active=False
        super().setup(me)
        self.ready = False
        self.risk_camp_owner={int(c):i for i,g in enumerate(self.groups) for c in g}
        self.risk_camp_tiles={xy(p):i for i,m in enumerate(self.masks) for p in m.positions()}
        self.risk_mobile_groups={i for i,g in enumerate(self.groups) if any(c.is_golem() for c in g)}
        self.risk_walls = set(xy(p) for p in gm.walls().positions())
        self.safety_altar_fields = []
        for index,altar in enumerate(self.altars):
            if hasattr(self,'altar_fields'):
                field=self.altar_fields[index]
            else:
                mask=bc.Bitboard();mask.draw_chebyshev(altar,bc.constants.SUBMIT_GEMS_RANGE)
                field=distance_field(self.terrain,mask)
            self.safety_altar_fields.append((altar,field))
        self.safety_banking=False
        self.safety_base_reserve=1100000 if hasattr(self,'engage') else 900000
        self.safety_select_reserve=self.safety_base_reserve
        self.ready = True

    def safety_begin(self,me):
        self.safety_fuel_start=bc.fuel_remaining()
        self.risk_round=bc.round_number()
        self._pending_enemies=None
        self.risk_preact=True
        self.safety_position=me.position()
        self.safety_hp=me.health();self.safety_max=me.max_health();self.safety_gems=me.gem_count()
        self.risk_cache={};self.camp_risk_cache={}
        self.risk_visible=bc.vision.visible_tiles()
        self.risk_enemies=[];self.risk_camps=[]
        self.safety_threat_round=-1
        enemies=self.enemies()
        self._pending_enemies=enemies;self._pending_enemy_round=self.risk_round
        self.risk_memory={k:v for k,v in self.risk_memory.items() if self.risk_round-v[0]<=MEMORY_TTL}
        recent_near=any(distance(xy(me.position()),p)<=self.risk_round-r+8 for r,p in self.risk_memory.values())
        self.safety_active=FULL_PVE_SAFETY or bool(enemies) or recent_near
        self.safety_select_reserve=1550000 if FULL_PVE_SAFETY else self.safety_base_reserve
        if not self.safety_active:
            self.risk_recent=[]
            if not self.safety_gems:self.bank_committed=False;self.bank_choice=None
            return
        # Dash paths may cross holes/altars, but final landing may not.
        walk_blocked=self.static_terrain | gm.spawn_region(bc.Team.ALLY)
        for enemy in enemies:
            self.check_budget()
            p=enemy.position();origin=xy(p)
            near=distance(origin,xy(me.position()))<=10
            origins=[(origin,0)]
            if near and ADVANCED_ACTIONS:
                one=walk_blocked.reachable_tiles(p,1)
                origins=[(xy(q),0 if q==p else 1) for q in one.positions()]
            skills=[];dashes=[]
            abilities=self.risk_ability_cache.get(int(enemy))
            if abilities is None:
                abilities=tuple(enemy.abilities())
                self.risk_ability_cache[int(enemy)]=abilities
            for a in abilities:
                self.check_budget()
                info=a.info()
                if info is None: continue
                cooldown=a.cooldown()
                if cooldown>2: continue
                if a.is_dash():
                    if near and cooldown<=1:
                        # Static geometric dash envelope; avoid enumerating a
                        # large landing set in every enemy/point calculation.
                        dashes=[origin] if not ADVANCED_ACTIONS else [(origin[0]+dx,origin[1]+dy) for dx,dy in
                                [(-2,0),(2,0),(0,-2),(0,2),(-2,-2),(-2,2),(2,-2),(2,2)]
                                if 0<=origin[0]+dx<gm.width() and 0<=origin[1]+dy<gm.height()
                                and not walk_blocked.is_set(bc.Vec2(origin[0]+dx,origin[1]+dy))]
                    # Landing damage is treated as a ranged envelope as well.
                    amount=a.damage_amount()
                    if amount>0:
                        skills.append((info.range,getattr(info,'radius',0),amount,cooldown,False,False,False))
                elif a.is_attack_reset() or a.is_damage() or a.is_aoe_damage() or a.is_cc():
                    skills.append((getattr(info,'range',enemy.attack_range()),getattr(info,'radius',0),
                                   a.damage_amount(),cooldown,info.exclusive_with_movement,
                                   a.is_attack_reset(),a.is_cc() and self.kind!=bc.ChampionType.MARCELLA))
            record=(origin,enemy.strength(),enemy.attack_range(),origins,skills,dashes)
            self.risk_enemies.append(record)
            self.risk_memory[int(enemy)]=(self.risk_round,origin)
        visible_ids={int(e) for e in enemies}
        self.risk_recent=[(r,p) for k,(r,p) in self.risk_memory.items()
                          if k not in visible_ids and self.risk_round-r<=MEMORY_TTL]
        self.risk_memory={k:v for k,v in self.risk_memory.items() if self.risk_round-v[0]<=MEMORY_TTL}
        if not FULL_PVE_SAFETY:
            # Keep the original controller's single PvE scan/recovery. Repeating
            # it here used the action budget before actual farming could run.
            self.risk_jungle=1.0
            if not me.gem_count():self.bank_committed=False;self.bank_choice=None
            return
        for c in self.visible_camps():
            self.check_budget()
            self.risk_camps.append((self.risk_camp_owner.get(int(c)),xy(c.position()),c.strength(),
                                    c.attack_range(),c.is_awake()))
        self.risk_jungle=.7 if has_jungle(me.item_count()) else 1.0
        if self.risk_own_abilities is None:self.risk_own_abilities=tuple(me.abilities())
        strength=me.strength();stats=(strength,me.focus())
        if stats!=self.risk_stats:
            self.risk_dps=strength;self.risk_shield=0;self.risk_shield_ability=None
            for a in self.risk_own_abilities:
                if a.is_attack_reset(): self.risk_dps+=strength/8
                elif a.is_shield():
                    self.risk_shield=a.shield_amount();self.risk_shield_ability=a
                elif a.can_target_camps() and (a.is_damage() or a.is_aoe_damage() or a.is_cc()):
                    self.risk_dps+=a.damage_amount()/8
            self.risk_stats=stats
        self.risk_shield_cd=self.risk_shield_ability.cooldown() if self.risk_shield_ability is not None else 8
        if me.gem_count()==0:
            self.bank_committed=False;self.bank_choice=None

    def enemies(self):
        # One reuse before any successful action. Subsequent calls refresh live
        # visibility, including after a kill, move or ward; no persistent vision.
        if (getattr(self,'_pending_enemies',None) is not None
                and self._pending_enemy_round==bc.round_number()):
            result=self._pending_enemies;self._pending_enemies=None
            return result
        return super().enemies()

    def risk_damage(self,p,turns=2):
        point=xy(p);key=(point,turns)
        if key in self.risk_cache: return self.risk_cache[key]
        self.check_budget()
        damage=sum(fast_enemy_damage(e,point,turns,self.risk_walls) for e in self.risk_enemies)
        # One camp phase precedes the next own turn. No invented camp attacks twice.
        damage+=sum(s*self.risk_jungle for group,q,s,r,awake in self.risk_camps
                    if awake and distance(q,point)<=r)
        self.risk_cache[key]=damage
        return damage

    def safety_zone(self,me,p=None):
        self.check_budget()
        p=p or me.position();point=xy(p)
        if not self.safety_active:
            if self.safety_threat_round!=self.risk_round:return UNKNOWN
            damage=2*sum(power for position,power,radius in self.threats if distance(xy(position),point)<=radius)
            return zone(self.safety_hp,self.safety_max,damage,not self.risk_visible.is_set(p),self.safety_gems)
        uncertain=(not self.risk_visible.is_set(p) or
                   any(distance(point,q)<=self.risk_round-r+4 for r,q in self.risk_recent))
        preact=getattr(self,'risk_preact',False)
        gems=self.safety_gems if preact else me.gem_count()
        hp=self.safety_hp if preact else me.health()
        maximum=self.safety_max if preact else me.max_health()
        level=zone(hp,maximum,self.risk_damage(p,turns=1),uncertain,gems)
        # Proximity alone is not an unfavourable matchup. On compact maps it
        # made every healthy carrier abandon farming at 20 gems indefinitely.
        return level

    def safety_channel(self,me):
        if not self.safety_active or not ADVANCED_ACTIONS:
            return me.is_teleporting() or me.is_recalling() or me.is_submitting_gems()
        if me.is_teleporting(): return True
        if not (me.is_recalling() or me.is_submitting_gems()): return False
        # Keep a viable tribute running through ordinary damage. Cancel only for
        # predicted lethal exposure AND a strictly safer unoccupied walking tile.
        damage=self.risk_damage(me.position())
        candidates=self.blockers(me).reachable_tiles(me.position(),1).positions()
        safer=any(self.risk_damage(p)<damage*.5 for p in candidates if p!=me.position())
        if damage>=me.health() and safer:
            if me.is_recalling(): me.cancel_recall()
            else: me.cancel_submit_gems()
            self.recovering=True;self.claim(None);self.retreat(me,self.enemies())
        return True

    def safety_act(self,me):
        if not self.safety_active:
            # Original recovery check must run before an uncontested bank plan.
            # The controller's later bank condition honours the commitment.
            return False
        if self.spawn.is_set(me.position()): return False
        level=self.safety_zone(me)
        self.safety_level=level
        if level==DANGER:
            if not ADVANCED_ACTIONS:
                # Parent recovery includes defensive attack/heal/CC, then its
                # escape. Returning early here silently removed that counterplay.
                self.recovering=True
                return False
            self.recovering=True;self.claim(None)
            self.retreat(me,self.enemies())
            return True
        travel=self.bank_field.get(me.position())
        limit=bank_limit(level,me.health()/max(1,me.max_health()),travel,NORMAL_BANK)
        if getattr(self,'collision',False) and travel>2:
            p=me.position();y=p.y if self.home_bottom else 40-p.y
            if not (p.x>=37 and 8<=y<=32):
                # Original crystal entry requires 36 gems. A global 20-gem
                # return breaks that delivery plan; red-zone escape stays first.
                limit=max(limit,36)
        # Unknown alone is not a reason to run home; recent nearby enemies are.
        if level==UNKNOWN and self.risk_recent and me.health()<.65*me.max_health():limit=min(limit,20)
        if me.gem_count() and (self.bank_committed or me.gem_count()>=limit):
            if not ADVANCED_ACTIONS:
                # The parent still needs its fresh NPC/burst recovery check.
                # Its later banking branch consumes this commitment safely.
                self.bank_committed=True
                return False
            self.claim(None);self.bank(me);return True
        return False

    def safety_step(self,me,p):
        # Escape movement is allowed to cross a red estimate to leave danger.
        if self.recovering: return True
        if not self.safety_active:
            allowed=self.safety_zone(me,p)!=DANGER
            if not allowed:self.recovering=True
            return allowed
        if not self.risk_enemies and not any(c[4] for c in self.risk_camps): return True
        allowed=self.safety_zone(me,p)!=DANGER
        if not allowed:self.recovering=True
        return allowed

    def safe_camp(self,me,index,ready=False,hp=None,incoming=None):
        if not self.safety_active or not FULL_PVE_SAFETY:return True
        key=(index,ready)
        if key in self.camp_risk_cache: return self.camp_risk_cache[key]
        self.check_budget()
        if self.path_fields[index].get(me.position())>7: return True
        total,rate,boss=self.group_stats[index]
        hp=total if hp is None else hp
        incoming=rate if incoming is None else incoming
        count=max(1,len(self.groups[index]))
        if index not in self.risk_mobile_groups and (self.masks[index] & ~self.risk_visible).is_empty():
            live=[c for c in self.risk_camps if c[0]==index]
            incoming=sum(c[2] for c in live)
            count=max(1,len(live))
        # Equal-HP serial-kill approximation, with bounded cleave credit. Reuse
        # already queried live HP; do not re-read every camp during ranking.
        cleave=1.6 if self.kind==bc.ChampionType.VARG and count>1 else 1.0
        clear=hp/max(1,self.risk_dps*cleave)
        rate=incoming*self.risk_jungle
        loss=clear*rate*(count+1)/(2*count)
        loss=max(0,loss-max(0,clear-self.risk_shield_cd)/8*self.risk_shield)
        if ready: loss=0
        point=self.centers[index]
        exit_damage=self.risk_damage(point)+(0 if ready else rate)
        feasible=camp_feasible(me.health(),me.max_health(),loss,exit_damage,me.gem_count())
        if not feasible and not boss and me.gem_count()<20:
            feasible=me.health()>max(me.max_health()*.14,rate*2+30)
        if self.risk_damage(point)>0 and self.safety_zone(me,point)==DANGER: feasible=False
        self.camp_risk_cache[key]=feasible
        return feasible

    def farm(self,me):
        if not ADVANCED_ACTIONS:return super().farm(me)
        result=super().farm(me)
        if not self.safety_active:
            if self.target is None and me.is_alive() and me.health()<me.max_health()*.4:
                self.recovering=True;self.claim(None)
                self.defend(me);self.retreat(me,self.enemies())
            return result
        if self.target is None and me.is_alive() and me.gem_count():
            self.bank(me)
            return result
        if self.target is None and me.is_alive() and me.health()<me.max_health()*.8:
            self.recovering=True
            self.retreat(me,self.enemies())
        return result

    def combat(self,me,targets,moved=False):
        if not self.safety_active or not ADVANCED_ACTIONS:return super().combat(me,targets,moved)
        # Stops fallback attacks/reset follow-ups from waking unrelated bosses.
        previous=self.target
        # Original tactical banking can authorise a small, damaged altar guard.
        # It has already checked its health/clear-time budget before calling us.
        guards=[t for t in targets if isinstance(t,bc.Camp)]
        if self.safety_banking and previous is None and guards:
            self.target=self.risk_camp_owner.get(int(guards[0]))
        try:
            targets=[t for t in targets if not isinstance(t,bc.Camp) or
                     (self.target is not None and self.risk_camp_owner.get(int(t))==self.target)]
            return super().combat(me,targets,moved)
        finally:
            self.target=previous

    def attack(self,me,targets):
        self._pending_enemies=None
        if not self.safety_active or not ADVANCED_ACTIONS:return super().attack(me,targets)
        safe=[]
        for t in targets:
            if isinstance(t,bc.Camp) and (self.target is None or self.risk_camp_owner.get(int(t))!=self.target): continue
            if self.kind==bc.ChampionType.VARG and t.is_visible():
                if self.safety_collateral(xy(t.position()),1): continue
            safe.append(t)
        return super().attack(me,safe)

    def safety_cast_allowed(self,me,ability,targets):
        if not ADVANCED_ACTIONS:return True
        if self.recovering and not (ability.is_heal() or ability.is_shield()):return False
        if not self.safety_active or not ADVANCED_ACTIONS:return True
        if ability.is_heal() or ability.is_shield() or ability.is_attack_reset(): return True
        info=ability.info();radius=getattr(info,'radius',0)
        if not radius: return True
        return not any(t.is_visible() and self.safety_collateral(xy(t.position()),int(radius)) for t in targets)

    def move(self,me,goals):
        self._pending_enemies=None
        return super().move(me,goals)

    def cast(self,me,targets,moved=False,attacked=False):
        self._pending_enemies=None
        return super().cast(me,targets,moved,attacked)

    def safety_collateral(self,p,radius):
        for dx in range(-radius,radius+1):
            for dy in range(-radius,radius+1):
                owner=self.risk_camp_tiles.get((p[0]+dx,p[1]+dy))
                if owner is not None and owner!=self.target: return True
        return False

    def defend(self,me):
        if getattr(self,'preserve_escape_walk',False) and self.recovering:
            if me.can_cast():
                self.cast(me,self.targets(),moved=True,attacked=False)
            return
        # The subsequent retreat owns the one cast/move; no generic offence first.
        if not self.safety_active or not ADVANCED_ACTIONS:return super().defend(me)
        if self.recovering: return
        return super().defend(me)

    def retreat(self,me,enemies):
        # Retain the established controller's path/escape behaviour. Generic
        # offensive casts were suppressed by defend() before reaching here.
        if not self.safety_active or not ADVANCED_ACTIONS:return super().retreat(me,enemies)
        self.check_budget()
        abilities=self.risk_own_abilities
        if me.can_cast() and not any(a.is_dash() and a.is_ready() for a in abilities):
            shield=next((a for a in abilities if a.is_shield() and a.is_ready()
                         and not a.info().exclusive_with_movement),None)
            if shield is not None and self.risk_damage(me.position())>0 and not me.buffs().has_shield():
                shield.use()
        return super().retreat(me,enemies)

    def bank(self,me):
        self.bank_committed=True
        if not self.safety_active or not ADVANCED_ACTIONS:
            self.safety_banking=True
            try:return super().bank(me)
            finally:self.safety_banking=False
        # Preserve the established specialised crystal entry/exit mechanism.
        if self.collision and self.crystal_delivery(me): return True
        options=[];locks=bc.vision.altar_lock_tiles(bc.Team.ENEMY)
        for index,(altar,field) in enumerate(self.safety_altar_fields):
            self.check_budget()
            if options and bc.fuel_remaining()<1100000: break
            cost=field.get(me.position())
            if cost>=65535: continue
            p=me.position();risk=0.0
            # Rolling next-step check; expensive full route search is deliberately
            # not run in Python on every turn.
            for k in range(min(cost,1)):
                step=field.next_move_from(p)
                if step is None: break
                p=p+step;risk=max(risk,self.risk_damage(p))
            channel=max(1,(me.gem_count()+9)//10)
            adjacent=bc.Bitboard();adjacent.draw_chebyshev(altar,bc.constants.SUBMIT_GEMS_RANGE)
            cells=(adjacent & ~self.terrain).positions()
            terminal=self.risk_damage(min(cells,key=lambda q:distance(xy(q),xy(me.position())))) if cells else risk
            # More bag means longer stationary exposure. This is a risk score,
            # not a guarantee or a calibrated probability of death.
            score=(max(risk,terminal*max(1,channel/2)),locks.is_set(altar),cost)
            if index==self.bank_choice: score=(score[0],score[1],score[2]-.75)
            options.append((score,index,altar))
        if not options: return False
        score,index,altar=min(options,key=lambda x:x[0])
        self.bank_choice=index
        if zone(me.health(),me.max_health(),score[0],False,me.gem_count())==DANGER:
            self.recovering=True;self.retreat(me,self.enemies());return True
        return self.execute_bank_plan(me,index,altar)

    def execute_bank_plan(self,me,index,altar):
        # Scope the parent's existing execution to the chosen altar; preserve
        # defensive PvP, damaged guards, locks and special delivery mechanics.
        old_altars=self.altars
        old_fields=getattr(self,'altar_fields',None)
        old_home=getattr(self,'altar_home',None)
        old_target=getattr(self,'bank_target',None)
        self.altars=[altar]
        if old_fields is not None:self.altar_fields=[old_fields[index]]
        if old_home is not None:self.altar_home=[old_home[index]]
        if hasattr(self,'bank_target'):self.bank_target=0
        self.safety_banking=True
        try:
            return super().bank(me)
        finally:
            self.safety_banking=False;self.altars=old_altars
            if old_fields is not None:self.altar_fields=old_fields
            if old_home is not None:self.altar_home=old_home
            if hasattr(self,'bank_target'):self.bank_target=old_target
