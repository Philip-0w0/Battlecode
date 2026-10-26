"""Dispatch turns and preserve useful error locations in replay logs."""
import traceback
import sys
import cambc
import draft
from bot import Bot, TurnBudget
from economy_bot import Bot as EconomyBot, TurnBudget as EconomyTurnBudget
from rows_bot import Bot as RowsBot, TurnBudget as RowsTurnBudget
import rows_draft
from boss_bot import BossBot
from cambc import game_map as gm


def main():
    # Rows uses the validated assignment-only experiment and its original draft.
    # Packs/Eight retain the tactical policy; other maps retain economy policy.
    signature=(gm.width(),gm.height(),frozenset((p.x,p.y) for p in gm.altars().positions()))
    tactical_maps={
        (31,31,frozenset({(2,6),(28,6),(2,15),(28,15),(2,24),(28,24)})),
        (41,30,frozenset({(20,15)})),
    }
    is_rows=signature==(50,50,frozenset({(15,16),(34,33)}))
    is_contest=signature in {(50,50,frozenset({(25,24),(24,25)})),(60,50,frozenset({(31,23),(31,26)}))}
    bot = BossBot() if is_contest else (RowsBot() if is_rows else (Bot() if signature in tactical_maps else EconomyBot()))
    draft_policy=rows_draft if is_rows else draft
    while True:
        try:
            if cambc.is_draft():
                draft_policy.play()
            else:
                bot.play_turn()
        except (TurnBudget,EconomyTurnBudget,RowsTurnBudget):
            print("budget yield", flush=True)
        except Exception as error:
            print(f"bot error: {error}", flush=True)
            traceback.print_exc(file=sys.stdout)
        cambc.end_turn()


if __name__ == '__main__':
    main()
