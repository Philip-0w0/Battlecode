"""Recall must distinguish dormant monsters from active incoming threats."""
import importlib.util
import os
from unittest.mock import patch
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parent
SOURCE = Path(os.environ.get('BATTLECODE_TEST_SOURCE',
    str(ROOT.parent/'bots/my-bot/src'))).resolve()

def load_source(name, filename):
    spec = importlib.util.spec_from_file_location(name, SOURCE/filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

# These modules perform no actions at import time. Use their real retreat code
# with a deliberately minimal SDK so any accidental runtime API use fails.
fake_sdk = types.ModuleType('cambc')
with patch.dict(sys.modules, {'cambc': fake_sdk}):
    sys.path.insert(0, str(SOURCE))
    try:
        reliability = load_source('tested_road_base', 'reliability.py')
        with patch.dict(sys.modules, {'reliability': reliability}):
            module = load_source('tested_road_reliability', 'road_reliability.py')
    finally:
        sys.path.pop(0)


class Point:
    def __init__(self, x, y): self.x, self.y = x, y
    def chebyshev_distance(self, other):
        return max(abs(self.x-other.x), abs(self.y-other.y))


class Unit:
    def __init__(self, awake=True, strength=40, x=1, visible=True):
        self.awake, self.power, self.x, self.visible = awake, strength, x, visible
    def is_awake(self): return self.awake
    def strength(self): return self.power
    def position(self): return Point(self.x, 0)
    def attack_range(self): return 2


class Me:
    def __init__(self): self.recalls = 0
    def position(self): return Point(0, 0)
    def can_move(self): return True
    def recall(self): self.recalls += 1


class Controller(module.RoadReliable):
    def __init__(self, camps=(), enemies=()):
        self.camps, self.foes = camps, enemies
        self.escapes = []
    def check_budget(self): pass
    def enemies(self): return self.foes
    def visible_camps(self): return [c for c in self.camps if c.visible]
    def escape_dash(self, me, threats):
        self.escapes.append(threats)
        return True


class AwakeRetreat(unittest.TestCase):
    def test_sleeping_positive_strength_camp_allows_recall(self):
        controller, me = Controller([Unit(awake=False)]), Me()
        controller.retreat(me, [])
        self.assertEqual(me.recalls, 1)
        self.assertEqual(controller.escapes, [])

    def test_awake_in_range_camp_preserves_escape(self):
        controller, me = Controller([Unit()]), Me()
        controller.retreat(me, [])
        self.assertEqual(me.recalls, 0)
        self.assertEqual(len(controller.escapes), 1)
        self.assertEqual(controller.escapes[0][0][1], 2)

    def test_awake_distant_or_zero_strength_camps_allow_recall(self):
        controller, me = Controller([Unit(x=4), Unit(strength=0)]), Me()
        controller.retreat(me, [])
        self.assertEqual(me.recalls, 1)
        self.assertEqual(controller.escapes, [])

    def test_hidden_camp_is_not_observed(self):
        class Hidden(Unit):
            def is_awake(self): raise AssertionError('hidden camp was queried')
        controller, me = Controller([Hidden(visible=False)]), Me()
        controller.retreat(me, [])
        self.assertEqual(me.recalls, 1)

    def test_enemy_path_still_escapes_even_beside_sleeping_camp(self):
        controller, me = Controller([Unit(awake=False)], [Unit(x=3)]), Me()
        controller.retreat(me, [])
        self.assertEqual(me.recalls, 0)
        self.assertEqual(len(controller.escapes), 1)

    def test_unknown_query_error_is_not_suppressed(self):
        class Unknown(Unit):
            def is_awake(self): raise RuntimeError('unknown camp state')
        controller, me = Controller([Unknown()]), Me()
        with self.assertRaisesRegex(RuntimeError, 'unknown camp state'):
            controller.retreat(me, [])
        self.assertEqual(me.recalls, 0)





class StopBeforeTurn(BaseException):
    pass


class Routing(unittest.TestCase):
    def selected_class(self, width, height, altars):
        created = []
        class Economy:
            def __init__(self): created.append(self)
        class Tactical:
            def __init__(self): created.append(self)
        class Rows:
            def __init__(self): created.append(self)
        class Content: pass
        class Budget(Exception): pass
        gm = types.SimpleNamespace(width=lambda: width, height=lambda: height,
            altars=lambda: types.SimpleNamespace(
                positions=lambda: [Point(x,y) for x,y in altars]))
        sdk = types.ModuleType('cambc')
        sdk.game_map = gm
        def stop(): raise StopBeforeTurn()
        sdk.is_draft = stop
        stubs = {
            'cambc': sdk,
            'draft': types.ModuleType('draft'),
            'rows_draft': types.ModuleType('rows_draft'),
            'bot': types.SimpleNamespace(Bot=Tactical, TurnBudget=Budget),
            'economy_bot': types.SimpleNamespace(Bot=Economy, TurnBudget=Budget),
            'rows_bot': types.SimpleNamespace(Bot=Rows, TurnBudget=Budget),
            'current_content': types.SimpleNamespace(CurrentContent=Content),
            'reliability': reliability,
            'road_reliability': module,
        }
        with patch.dict(sys.modules, stubs):
            main = load_source('tested_road_main', 'main.py')
            with self.assertRaises(StopBeforeTurn): main.main()
        self.assertTrue(created)
        return created[-1].__class__

    def test_road_layout_selects_special_retreat(self):
        selected = self.selected_class(40,40,[(19,17),(20,22)])
        self.assertTrue(issubclass(selected, module.RoadReliable))

    def test_altar_order_does_not_change_selection(self):
        selected = self.selected_class(40,40,[(20,22),(19,17)])
        self.assertTrue(issubclass(selected, module.RoadReliable))

    def test_other_forty_square_layout_keeps_normal_controller(self):
        selected = self.selected_class(40,40,[(19,18),(20,22)])
        self.assertFalse(issubclass(selected, module.RoadReliable))
        self.assertEqual(selected.__name__, 'SafeEconomyBot')

    def test_matching_altars_with_different_size_keep_normal_controller(self):
        selected = self.selected_class(41,40,[(19,17),(20,22)])
        self.assertFalse(issubclass(selected, module.RoadReliable))

    def test_rows_keeps_rows_controller(self):
        selected = self.selected_class(50,50,[(15,16),(34,33)])
        self.assertEqual(selected.__name__, 'Rows')

    def test_unknown_map_keeps_normal_controller(self):
        selected = self.selected_class(100,100,[(1,1)])
        self.assertEqual(selected.__name__, 'SafeEconomyBot')


if __name__ == '__main__': unittest.main()
