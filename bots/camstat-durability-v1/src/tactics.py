"""Small, deterministic tactical rules, independently testable without the SDK."""


def lethal_recent_loss(previous_health, previous_round, health, round_number):
    # Only consecutive observations count; death/respawn must reset the sample.
    return (previous_health is not None and previous_round == round_number - 1
            and previous_health - health >= health and health > 0)


def winning_load(submitted, carried, target=1000):
    return submitted + sum(carried) >= target


def favorable_fight(own_health, own_power, enemy_health, enemy_power):
    # Compare estimated time to defeat each side, with a safety margin.
    return own_health / max(enemy_power, 1) > 1.35 * enemy_health / max(own_power, 1)
