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
from current_content import CurrentContent


class TacticalBot(CurrentContent, Reliable, Bot): pass
class SafeEconomyBot(CurrentContent, Reliable, EconomyBot): pass
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
    bot = RowsBot() if is_rows else (TacticalBot() if signature in tactical_maps else SafeEconomyBot())
    if signature == (40,40,frozenset({(19,17),(20,22)})):
        from road_reliability import RoadReliable
        class RoadEconomyBot(CurrentContent, RoadReliable, EconomyBot): pass
        bot = RoadEconomyBot()
    draft_policy=rows_draft if is_rows else draft
    while True:
        try:
            if cambc.is_draft():
                draft_policy.play()
            else:
                bot.action_round = cambc.round_number()
                bot.play_turn()
        except (TurnBudget,EconomyTurnBudget,RowsTurnBudget):
            pass  # Expected bounded yield; do not spend fuel on release logging.
        except Exception as error:
            tb=error.__traceback__
            while tb is not None and tb.tb_next is not None: tb=tb.tb_next
            where=f" [{tb.tb_frame.f_code.co_filename}:{tb.tb_lineno}]" if tb is not None else ""
            print(f"bot error: {error}{where}", flush=True)
            if DEBUG: traceback.print_exc(file=sys.stdout)
        cambc.end_turn()


if __name__ == '__main__':
    main()
