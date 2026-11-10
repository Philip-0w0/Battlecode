"""Same-turn numeric snapshots, installed only on Fracture/Great Wall."""
import cambc as bc
from action_ready import can_use_ability
C=bc.ChampionType
def dist(a,b):return a.chebyshev_distance(b)


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
            attack_tiles = self.attack_mask(me)
            in_range = [t for t in targets if t.is_visible() and t.health() > 0 and attack_tiles.is_set(t.position())]
            if attacked and (not me.can_attack()) and in_range:
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
