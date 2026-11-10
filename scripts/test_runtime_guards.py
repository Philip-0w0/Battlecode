"""Behavioral tests for the imported runtime guards and bounded setup.

BC_BOT_SOURCE selects the candidate/installed source without importing the WASM SDK.
"""
import ast
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace as NS, MethodType
import unittest

LOCAL_SOURCE = Path(__file__).parent / "src"
SOURCE = Path(os.environ.get("BC_BOT_SOURCE", str(LOCAL_SOURCE if LOCAL_SOURCE.is_dir() else Path(__file__).resolve().parents[1]/"bots/my-bot/src")))
POLICIES = ("bot.py", "economy_bot.py", "rows_bot.py")


def load_file(name, env=None):
    scope = {} if env is None else env
    tree = ast.parse((SOURCE / name).read_text(encoding="utf-8"))
    # Helpers have one SDK import; supply the same explicit API as fixtures.
    tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    exec(compile(tree, str(SOURCE / name), "exec"), scope)
    return scope


def methods(name, names, env):
    tree = ast.parse((SOURCE / name).read_text(encoding="utf-8"))
    bot = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Bot")
    selected = [n for n in bot.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE / name), "exec"), env)
    return env


FLAGS = NS(ALIVE=1, RECALLING=2, SUBMITTING_GEMS=4, COMPLETED_TURN=32,
           CAN_CAST=2048, TELEPORTING=4096)
RESTRICTIONS = NS(MOVE=1, ATTACK=2, CAST=4)


def api():
    result = NS(round=10, fuel=3_000_000, ChampionState=FLAGS, BuffRestrictions=RESTRICTIONS)
    result.round_number = lambda: result.round
    result.fuel_remaining = lambda: result.fuel
    return result


class ActionGuardTests(unittest.TestCase):
    def setUp(self):
        self.api = api()
        self.me = NS(state=lambda: FLAGS.ALIVE | FLAGS.CAN_CAST, restrictions=lambda: 0)
        self.guards = load_file("action_ready.py")

    def test_allowed_spell_remains_allowed(self):
        self.assertTrue(self.guards["can_use_ability"](self.me, 10, self.api))

    def test_slot_without_permission_does_not_cast(self):
        self.me.restrictions = lambda: RESTRICTIONS.CAST
        self.assertFalse(self.guards["can_use_ability"](self.me, 10, self.api))

    def test_all_channel_or_dead_states_prevent_cast(self):
        for state in (FLAGS.CAN_CAST, FLAGS.ALIVE, FLAGS.ALIVE | FLAGS.CAN_CAST | FLAGS.RECALLING,
                      FLAGS.ALIVE | FLAGS.CAN_CAST | FLAGS.SUBMITTING_GEMS,
                      FLAGS.ALIVE | FLAGS.CAN_CAST | FLAGS.TELEPORTING,
                      FLAGS.ALIVE | FLAGS.CAN_CAST | FLAGS.COMPLETED_TURN):
            with self.subTest(state=state):
                self.me.state = lambda: state
                self.assertFalse(self.guards["can_use_ability"](self.me, 10, self.api))

    def test_round_change_during_final_live_read_prevents_cast(self):
        def restrictions():
            self.api.round += 1
            return 0
        self.me.restrictions = restrictions
        self.assertFalse(self.guards["can_use_ability"](self.me, 10, self.api))

    def test_fully_stunned_and_partial_restrictions_differ(self):
        for mask, expected in ((7, True), (3, False), (4, False), (0, False)):
            self.me.restrictions = lambda: mask
            self.assertEqual(self.guards["actions_blocked"](self.me, self.api), expected)


class Point:
    def __init__(self, x=0, y=0): self.x, self.y = x, y
    def chebyshev_distance(self, other): return max(abs(self.x-other.x), abs(self.y-other.y))


class Camp:
    def __init__(self, health=100, x=0): self.hp, self.p = health, Point(x, 0)
    def __int__(self): return self.p.x
    def health(self): return self.hp
    def is_visible(self): return True
    def position(self): return self.p
    def spawn_position(self): return self.p
    def base_stats(self): return NS(base_health=100, base_strength=10)
    def is_monolith(self): return False
    def is_gem_cluster(self): return False


class Champion(Camp):
    def champion_name(self): return 9
    def gem_count(self): return 0
    def is_submitting_gems(self): return False


class Board:
    def positions(self): return [Point()]
    def is_set(self, point): return True
    def __or__(self, other): return self
    def __and__(self, other): return self
    def __invert__(self): return self
    def draw_chebyshev(self, p, r): pass


KINDS = NS(VARG=1, CASSI=2, WILLOW=3, REN=4)


def combat_fixture(name):
    game = api()
    game.Camp, game.Champion = Camp, Champion
    game.Error = RuntimeError
    guards = load_file("action_ready.py")
    env = methods(name, {"attack", "cast", "combat"}, dict(bc=game, C=KINDS,
        dist=lambda a,b: a.chebyshev_distance(b), can_use_ability=guards["can_use_ability"]))
    bot = NS(kind=9, rows=False, crates=[], centers=[], action_round=10,
             check_budget=lambda:None, attack_mask=lambda me:Board(), enemies=lambda:[])
    for key in ("attack", "cast", "combat"): setattr(bot, key, MethodType(env[key], bot))
    me = NS(available=True, cast_available=True, attacks=[], casts=0)
    me.can_attack = lambda: me.available
    me.can_cast = lambda: me.cast_available
    me.is_alive = lambda: True
    me.strength = lambda: 20
    me.position = Point
    me.state = lambda: FLAGS.ALIVE | (FLAGS.CAN_CAST if me.cast_available else 0)
    me.restrictions = lambda: 0
    def attack(target):
        me.attacks.append(target)
        target.hp -= 20
        me.available = False
        return True
    me.attack = attack
    class Reset:
        def is_ready(self): return True
        def info(self): return NS(exclusive_with_movement=False)
        def is_attack_reset(self): return True
        def use(self, target):
            me.casts += 1
            me.available = True
            me.cast_available = False
            return True
    me.abilities = lambda: [Reset()]
    return bot, me, game


class CombatTests(unittest.TestCase):
    def test_lethal_first_attack_still_enables_reset_against_remaining_target(self):
        for name in POLICIES:
            with self.subTest(policy=name):
                bot, me, game = combat_fixture(name)
                dead, remaining = Camp(10), Camp(100)
                bot.combat(me, [dead, remaining])
                self.assertEqual(me.attacks, [dead, remaining])
                self.assertEqual(me.casts, 1)

    def test_reset_is_not_wasted_when_only_target_dies(self):
        for name in POLICIES:
            with self.subTest(policy=name):
                bot, me, game = combat_fixture(name)
                bot.combat(me, [Camp(10)])
                self.assertEqual(me.casts, 0)
                self.assertEqual(len(me.attacks), 1)

    def test_followup_refreshes_enemy_but_never_opens_unrelated_camp(self):
        for name in POLICIES:
            with self.subTest(policy=name):
                bot, me, game = combat_fixture(name)
                original, unrelated, revealed = Camp(100), Camp(100), Champion(100)
                seen = []
                def attack(me, targets): seen.append(list(targets))
                bot.attack = attack
                bot.cast = lambda *args: None
                bot.enemies = lambda: [revealed]
                bot.targets = lambda: [revealed, unrelated]  # Old broad fallback.
                bot.combat(me, [original])
                self.assertEqual(seen, [[original], [revealed, original]])
                self.assertNotIn(unrelated, seen[-1])

    def test_cast_boundary_rejects_stale_round_even_if_old_plan_looks_ready(self):
        for name in POLICIES:
            with self.subTest(policy=name):
                bot, me, game = combat_fixture(name)
                me.available = False
                game.round = 11
                self.assertFalse(bot.cast(me, [Camp(100)], attacked=True))
                self.assertEqual(me.casts, 0)


class Budget(Exception): pass


class Group(list):
    def spawn_tiles(self): return Board()
    def gem_value(self): return 30
    def gold_value(self): return 10


def setup_fixture(name):
    game = api()
    game.constants = NS(SUBMIT_GEMS_RANGE=1)
    game.Team = NS(ALLY=1, ENEMY=2)
    game.Bitboard = Board
    computed = []
    class Field:
        def compute(self, terrain, goals, extra):
            computed.append(self)
            game.fuel -= 550_000
        def get(self, p): return 1
    game.DistanceField = Field
    groups = [Group([Camp(x=i)]) for i in range(5)]
    gm = NS(camp_groups=lambda:groups, altars=Board, spawn_region=lambda team:Board(),
            walls=Board, holes=Board, width=lambda:31, height=lambda:31)
    me = NS(champion_name=lambda:9, priorities=[])
    # int(me) is used in the real roster. A tiny concrete object supplies identity.
    class Me:
        def __int__(self): return 0
        def champion_name(self): return 9
        def set_priority(self, value): me.priorities.append(value)
    live = Me()
    game.champions = lambda team:[live]
    helpers = load_file("initialization.py", {"bc":game})
    navigation = load_file("navigation.py", {"bc":game})
    env = methods(name, {"__init__", "setup", "setup_steps"}, dict(bc=game, gm=gm,
        distance_field=navigation["distance_field"],spawn_distances=navigation["spawn_distances"],
        T=game.Team, C=KINDS, TurnBudget=Budget, advance_setup=helpers["advance_setup"],
        disk=lambda p,r:Board(), dist=lambda a,b:a.chebyshev_distance(b)))
    bot = NS(action_round=10)
    for key in ("__init__", "setup", "setup_steps"):setattr(bot,key,MethodType(env[key],bot))
    bot.__init__()
    return bot, live, me, game, computed


class SetupTests(unittest.TestCase):
    def test_precomputation_resumes_without_rebuilding_fields(self):
        for name in POLICIES:
            with self.subTest(policy=name):
                bot, live, me, game, computed = setup_fixture(name)
                yields = 0
                while not bot.ready:
                    game.fuel = 2_200_000
                    try: bot.setup(live)
                    except Budget:
                        yields += 1
                        self.assertFalse(bot.ready)
                        game.round += 1
                        bot.action_round = game.round
                    self.assertLess(yields, 10)
                self.assertGreater(yields, 0)
                self.assertEqual(len(computed), {"bot.py":9,"economy_bot.py":6,"rows_bot.py":8}[name])
                self.assertEqual(len({id(x) for x in computed}), len(computed))
                self.assertEqual(len(bot.path_fields), 5)
                self.assertEqual(me.priorities, [20])
                self.assertFalse(hasattr(bot, "_setup_work"))

    def test_round_yield_defers_completion_without_losing_work(self):
        for name in POLICIES:
            with self.subTest(policy=name):
                bot, live, me, game, computed = setup_fixture(name)
                game.round += 1
                with self.assertRaises(Budget): bot.setup(live)
                self.assertEqual(len(computed), 0)
                bot.action_round = game.round
                game.fuel = 20_000_000
                bot.setup(live)
                self.assertTrue(bot.ready)
                self.assertEqual(len(bot.path_fields), 5)


if __name__ == "__main__": unittest.main()
