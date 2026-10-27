"""Dispatch turns and preserve useful error locations in replay logs."""
import traceback
import sys
import cambc
import draft
from bot import Bot, TurnBudget
from economy_bot import Bot as EconomyBot, TurnBudget as EconomyTurnBudget
from rows_bot import Bot as RowsBot, TurnBudget as RowsTurnBudget
import rows_draft
from reliability import Reliable


class TacticalBot(Reliable, Bot): pass
class SafeEconomyBot(Reliable, EconomyBot):
    objective_tuning = True
class SafeRowsBot(Reliable, RowsBot): pass
from cambc import game_map as gm


DEBUG = False


def main():
    # Rows uses the validated assignment-only experiment and its original draft.
    # Packs/Eight retain the tactical policy; other maps retain economy policy.
    signature=(gm.width(),gm.height(),frozenset((p.x,p.y) for p in gm.altars().positions()))
    tactical_maps={
        (31,31,frozenset({(2,6),(28,6),(2,15),(28,15),(2,24),(28,24)})),
        (41,30,frozenset({(20,15)})),
    }
    is_rows=signature==(50,50,frozenset({(15,16),(34,33)}))
    bot = SafeRowsBot() if is_rows else (TacticalBot() if signature in tactical_maps else SafeEconomyBot())
    draft_policy=rows_draft if is_rows else draft
    while True:
        try:
            if cambc.is_draft():
                draft_policy.play()
            else:
                bot.play_turn()
        except (TurnBudget,EconomyTurnBudget,RowsTurnBudget):
            pass  # Expected bounded yield; do not spend fuel on release logging.
        except Exception as error:
            print(f"bot error: {error}", flush=True)
            if DEBUG: traceback.print_exc(file=sys.stdout)
        cambc.end_turn()


if __name__ == '__main__':
    main()
