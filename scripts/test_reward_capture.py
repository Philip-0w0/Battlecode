"""Exercise the actual selectors against cleared, alive and unseen boss groups."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

SOURCE = Path(os.environ.get('BC_BOT_SOURCE', str(Path(__file__).resolve().parents[1]/'bots/my-bot/src')))
POLICIES = ('economy_bot.py', 'rows_bot.py', 'bot.py', 'camp_policy.py')

class Ready: pass
class Alive: pass
class Respawning: pass
class Point:
    x = y = 0
    def chebyshev_distance(self, other): return 0
class Mask:
    def __init__(self, visible=True): self.visible = visible
    def __and__(self, other): return self
    def is_empty(self): return not self.visible
    def is_set(self, point): return False
class Group(list):
    def __init__(self, state, reward):
        super().__init__([NS(is_visible=lambda:False, base_stats=lambda:NS(base_health=20000))])
        self._state, self.reward = state, reward
    def state(self): return self._state
    def gem_value(self): return self.reward
    def gold_value(self): return 0

def selector(filename):
    tree = ast.parse((SOURCE/filename).read_text())
    if filename == 'camp_policy.py':
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'choose_economy_group')
    else:
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Bot')
        node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'choose_group')
    env = dict(bc=NS(vision=NS(visible_tiles=lambda:Mask()), fuel_remaining=lambda:3_000_000,
                     round_number=lambda:100),
               gm=NS(CampGroupRewardAvailable=Ready, CampGroupRespawning=Respawning),
               C=NS(VARG=1, CASSI=2, VENDETTA=3, TAVI=4, RYTH=5, WILLOW=6),
               read_claims=lambda:[], has_jungle=lambda counts:False,
               dist=lambda a,b:0)
    helpers = ast.parse((SOURCE/'navigation.py').read_text())
    helper = next(n for n in helpers.body if isinstance(n,ast.FunctionDef) and n.name=='nearest_groups')
    env['UNREACHABLE']=65535
    exec(compile(ast.Module(body=[helper],type_ignores=[]),str(SOURCE/'navigation.py'),'exec'),env)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE/filename), 'exec'), env)
    return env[node.name]

def fixture(state, strength=30, visible=True, competitor=False):
    groups = [Group(state, 200)] + ([Group(Ready(), 50)] if competitor else [])
    n = len(groups)
    bot = NS(groups=groups, target=None, masks=[Mask(visible) for _ in groups],
             centers=[Point() for _ in groups], group_stats=[(20000,200,True)]+([(100,0,False)] if competitor else []),
             path_fields=[NS(get=lambda point:1) for _ in groups], group_rewards=[g.reward for g in groups],
             failed_until={}, sleep_until={}, check_budget=lambda:None, kind=1, alert=None,
             slot=0, allies_by_slot=[], allies=lambda:[], rows=False, corners=False, collision=False,
             home_groups=[True]*n, crates=[False]*n, altar_groups=[False]*n,
             rows_owners={}, rows_home=[])
    me=NS(position=Point, strength=lambda:strength, health=lambda:100, max_health=lambda:1000, item_count=lambda:[])
    return bot, me

class RewardCaptureTests(unittest.TestCase):
    def test_weak_solo_champion_can_collect_cleared_boss(self):
        for filename in POLICIES:
            with self.subTest(policy=filename):
                self.assertEqual(selector(filename)(*fixture(Ready())), 0)

    def test_live_boss_keeps_its_combat_gate(self):
        for filename in POLICIES:
            with self.subTest(policy=filename):
                self.assertIsNone(selector(filename)(*fixture(Alive())))

    def test_unseen_boss_is_not_assumed_cleared(self):
        for filename in POLICIES:
            with self.subTest(policy=filename):
                self.assertIsNone(selector(filename)(*fixture(Ready(), visible=False)))

    def test_cleared_reward_is_not_penalized_as_a_live_boss(self):
        for filename in POLICIES:
            with self.subTest(policy=filename):
                self.assertEqual(selector(filename)(*fixture(Ready(), strength=250, competitor=True)), 0)

    def test_existing_capture_does_not_require_a_new_combat_squad(self):
        for filename in POLICIES:
            with self.subTest(policy=filename):
                bot, me = fixture(Ready())
                bot.target = 0
                self.assertEqual(selector(filename)(bot, me), 0)

    def test_tactical_rows_collector_can_capture_without_a_boss_fighting_role(self):
        bot, me = fixture(Ready())
        bot.rows = True
        self.assertEqual(selector('bot.py')(bot, me), 0)

if __name__ == '__main__': unittest.main()
