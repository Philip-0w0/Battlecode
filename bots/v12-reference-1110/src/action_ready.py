"""Revalidate allowances, restrictions and turn identity at the action boundary.

The SDK exposes action slots and buff restrictions separately. Read-only engine
calls may also resume after a fuel yield, so a previously ready spell is not a
promise that it is still usable when the final cast is issued.
"""


def actions_blocked(me,api):
    mask=api.BuffRestrictions.MOVE | api.BuffRestrictions.ATTACK | api.BuffRestrictions.CAST
    return (me.restrictions() & mask)==mask


def can_use_ability(me,action_round,api):
    if api.round_number()!=action_round:return False
    state=me.state();flags=api.ChampionState
    if not state & flags.ALIVE or not state & flags.CAN_CAST:return False
    blocked=flags.RECALLING | flags.SUBMITTING_GEMS | flags.TELEPORTING | flags.COMPLETED_TURN
    if state & blocked:return False
    if me.restrictions() & api.BuffRestrictions.CAST:return False
    return api.round_number()==action_round
