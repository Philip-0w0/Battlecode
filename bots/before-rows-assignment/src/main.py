"""Dispatch turns and preserve useful error locations in replay logs."""
import traceback
import sys
import cambc
import draft
from bot import Bot, TurnBudget
from economy_bot import Bot as EconomyBot, TurnBudget as EconomyTurnBudget
from cambc import game_map as gm


def main():
    # Scope the new team policy to the three maps it was developed against.
    # Other maps retain the established economy policy plus burst retreat.
    signature=(gm.width(),gm.height(),frozenset((p.x,p.y) for p in gm.altars().positions()))
    tactical_maps={
        (31,31,frozenset({(2,6),(28,6),(2,15),(28,15),(2,24),(28,24)})),
        (41,30,frozenset({(20,15)})),
        (50,50,frozenset({(15,16),(34,33)})),
    }
    bot = Bot() if signature in tactical_maps else EconomyBot()
    while True:
        try:
            if cambc.is_draft():
                draft.play()
            else:
                bot.play_turn()
        except (TurnBudget,EconomyTurnBudget):
            print("budget yield", flush=True)
        except Exception as error:
            print(f"bot error: {error}", flush=True)
            traceback.print_exc(file=sys.stdout)
        cambc.end_turn()


if __name__ == '__main__':
    main()
