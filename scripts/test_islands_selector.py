"""Exercise the actual selector on a disconnected-map shortlist regression."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

HERE = Path(__file__).parent
SOURCE = Path(os.environ.get('BATTLECODE_TEST_SOURCE',
    str(HERE.parent/'bots/my-bot/src'))).resolve()


class Point:
    def __init__(self, x, y=0): self.x, self.y = x, y
    def chebyshev_distance(self, other):
        return max(abs(self.x-other.x), abs(self.y-other.y))


class EmptyMask:
    def __and__(self, other): return self
    def is_empty(self): return True
    def is_set(self, position): return False


class Group:
    def __init__(self, gems): self.gems = gems
    def __len__(self): return 1
    def __iter__(self): return iter(())
    def gem_value(self): return self.gems
    def gold_value(self): return 0


class Me:
    def __init__(self): self.position_calls = 0
    def position(self):
        self.position_calls += 1
        return Point(0)
    def item_count(self): return []
    def strength(self): return 100
    def health(self): return 1000


class Field:
    def __init__(self, value): self.value = value
    def get(self, origin): return self.value


class Budget(Exception): pass


def load_selector(path):
    tree = ast.parse(path.read_text(encoding='utf8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name=='Bot')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name=='choose_group')
    module = ast.Module(body=[method], type_ignores=[])
    constants = SimpleNamespace(VARG=1, CASSI=2)
    context = dict(bc=SimpleNamespace(vision=SimpleNamespace(visible_tiles=EmptyMask),
                                      fuel_remaining=lambda: 10_000_000, round_number=lambda: 0),
                   gm=SimpleNamespace(CampGroupRespawning=type('Respawning',(),{}),
                                      CampGroupRewardAvailable=type('Available',(),{})),
                   read_claims=lambda: [], has_jungle=lambda inventory: False,
                   dist=lambda a,b:a.chebyshev_distance(b), C=constants)
    exec(compile(ast.fix_missing_locations(module),str(path),'exec'),context)
    return context['choose_group']


def controller(count, unreachable=(), gems=None):
    return SimpleNamespace(groups=[Group(10 if gems is None else gems[i]) for i in range(count)],
        centers=[Point(i+1) for i in range(count)],
        path_fields=[Field(65535 if i in unreachable else i+1) for i in range(count)],
        masks=[EmptyMask() for _ in range(count)], group_stats=[(0,0,False)]*count,
        target=None, failed_until={}, sleep_until={}, alert=None, slot=0,
        allies_by_slot=[], kind=0, check_budget=lambda: None)


class SelectorReachability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = staticmethod(load_selector(SOURCE/'islands_bot.py'))

    def test_ten_disconnected_camps_cannot_hide_reachable_gem_camp(self):
        state = controller(11,unreachable=set(range(10)))
        self.assertEqual(self.current(state,Me()),10)

    def test_reachable_only_pool_preserves_existing_choice(self):
        state = controller(14,gems=[10]*13+[1000])
        # The deliberately bounded ten-camp policy is retained; this is not a
        # global value-score rewrite or an expansion of the tactical shortlist.
        self.assertEqual(self.current(state,Me()),0)

    def test_current_target_outside_shortlist_is_retained(self):
        state = controller(14,gems=[10]*13+[1000])
        state.target = 13
        self.assertEqual(self.current(state,Me()),13)

    def test_empty_pool_has_no_target(self):
        self.assertIsNone(self.current(controller(0),Me()))

    def test_all_disconnected_has_no_target(self):
        self.assertIsNone(self.current(controller(12,unreachable=set(range(12))),Me()))

    def test_static_path_boundary_retains_old_acceptance(self):
        state = controller(1)
        state.path_fields[0].value = 10000
        self.assertEqual(self.current(state,Me()),0)
        state.path_fields[0].value = 10001
        self.assertIsNone(self.current(state,Me()))

    def test_prefilter_yields_before_getting_stale_live_state(self):
        state = controller(12)
        def exhausted(): raise Budget()
        state.check_budget = exhausted
        me = Me()
        with self.assertRaises(Budget): self.current(state,me)
        self.assertEqual(me.position_calls,1)


if __name__=='__main__': unittest.main()
