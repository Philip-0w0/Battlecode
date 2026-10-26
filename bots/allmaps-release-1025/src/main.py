"""Dispatch turns and preserve useful error locations in replay logs."""
import traceback
import sys
import cambc
import draft
from bot import Bot, TurnBudget
from economy_bot import Bot as EconomyBot, TurnBudget as EconomyTurnBudget
from rows_bot import Bot as RowsBot, TurnBudget as RowsTurnBudget
import rows_draft
from cambc import game_map as gm
from map_policy import select_policy


def main():
    policy=select_policy(gm.width(),gm.height(),[(p.x,p.y) for p in gm.altars().positions()])
    if policy=='rows': bot=RowsBot()
    elif policy=='tactical': bot=Bot()
    elif policy=='siege':
        from boss_bot import BossBot
        bot=BossBot()
    elif policy=='routes':
        from route_bot import RouteBot
        bot=RouteBot()
    else: bot=EconomyBot()
    draft_policy=rows_draft if policy=='rows' else draft
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
