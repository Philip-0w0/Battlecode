"""Exercise actual dispatch and Islands subclass loading with a minimal SDK."""
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent
SOURCE = Path(os.environ.get('BATTLECODE_TEST_SOURCE',
    str(HERE.parent/'bots/my-bot/src'))).resolve()
ALTARS = [(25,4),(34,4),(38,15),(25,23),(12,28),(47,31),
          (34,36),(21,44),(25,55),(34,55)]


class StopBeforeTurn(BaseException): pass


def load_source(name, filename):
    spec = importlib.util.spec_from_file_location(name,SOURCE/filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Routing(unittest.TestCase):
    def selected(self,width,height,altars):
        created=[]
        class Economy:
            def __init__(self): created.append(self)
        class Tactical:
            def __init__(self): created.append(self)
        class Rows:
            def __init__(self): created.append(self)
        class Content: pass
        class Budget(Exception): pass
        gm=types.SimpleNamespace(width=lambda:width,height=lambda:height,
            altars=lambda:types.SimpleNamespace(
                positions=lambda:[types.SimpleNamespace(x=x,y=y) for x,y in altars]))
        sdk=types.ModuleType('cambc')
        sdk.game_map=gm
        sdk.ChampionType=types.SimpleNamespace(VARG=1,CASSI=2)
        def stop(): raise StopBeforeTurn()
        sdk.is_draft=stop
        stubs={
            'cambc':sdk,
            'draft':types.ModuleType('draft'),
            'rows_draft':types.ModuleType('rows_draft'),
            'bot':types.SimpleNamespace(Bot=Tactical,TurnBudget=Budget),
            'economy_bot':types.SimpleNamespace(Bot=Economy,TurnBudget=Budget,
                dist=lambda a,b:0),
            'rows_bot':types.SimpleNamespace(Bot=Rows,TurnBudget=Budget),
            'current_content':types.SimpleNamespace(CurrentContent=Content),
            'coordination':types.SimpleNamespace(read_claims=lambda:[]),
            'equipment':types.SimpleNamespace(has_jungle=lambda items:False),
            'progress':load_source('tested_islands_progress','progress.py'),
        }
        with patch.dict(sys.modules,stubs):
            reliability=load_source('tested_islands_reliability','reliability.py')
            with patch.dict(sys.modules,{'reliability':reliability}):
                road=load_source('tested_islands_road','road_reliability.py')
                islands=load_source('tested_islands_controller','islands_bot.py')
                with patch.dict(sys.modules,{'road_reliability':road,'islands_bot':islands}):
                    main=load_source('tested_islands_main','main.py')
                    with self.assertRaises(StopBeforeTurn): main.main()
        self.assertTrue(created)
        return created[-1].__class__,islands.Bot,road.RoadReliable

    def test_exact_islands_layout_selects_reachable_controller(self):
        selected,islands,_=self.selected(60,60,ALTARS)
        self.assertTrue(issubclass(selected,islands))

    def test_altar_order_is_irrelevant(self):
        selected,islands,_=self.selected(60,60,list(reversed(ALTARS)))
        self.assertTrue(issubclass(selected,islands))

    def test_other_sixty_square_layout_keeps_economy(self):
        selected,islands,_=self.selected(60,60,ALTARS[:-1]+[(35,55)])
        self.assertFalse(issubclass(selected,islands))
        self.assertEqual(selected.__name__,'SafeEconomyBot')

    def test_changed_dimensions_keep_economy(self):
        selected,islands,_=self.selected(61,60,ALTARS)
        self.assertFalse(issubclass(selected,islands))
        self.assertEqual(selected.__name__,'SafeEconomyBot')

    def test_rows_controller_is_preserved(self):
        selected,islands,_=self.selected(50,50,[(15,16),(34,33)])
        self.assertFalse(issubclass(selected,islands))
        self.assertEqual(selected.__name__,'Rows')

    def test_road_controller_is_preserved(self):
        selected,islands,road=self.selected(40,40,[(19,17),(20,22)])
        self.assertFalse(issubclass(selected,islands))
        self.assertTrue(issubclass(selected,road))


if __name__=='__main__': unittest.main()
