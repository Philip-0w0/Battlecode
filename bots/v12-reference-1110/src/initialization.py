"""Resume immutable map precomputation without exhausting a live turn."""
import cambc as bc

def advance_setup(bot, me, budget_error):
    if not hasattr(bot, '_setup_work'):
        bot._setup_work = bot.setup_steps(me)
    while True:
        if bc.round_number() != bot.action_round or bc.fuel_remaining() < 1000000:
            raise budget_error()
        try:
            next(bot._setup_work)
        except StopIteration:
            del bot._setup_work
            return
