"""Dispatch keeps terrain-aware v12 economy and Road's specialised recall/shop."""
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

SOURCE=Path(os.environ.get('BATTLECODE_TEST_SOURCE',str(Path(__file__).parent.parent/'bots/my-bot/src'))).resolve()
ALTARS=[(25,4),(34,4),(38,15),(25,23),(12,28),(47,31),(34,36),(21,44),(25,55),(34,55)]
FRONT_ALTARS=[(30,y) for y in list(range(1,7))+list(range(9,32))+list(range(34,39))]
class StopBeforeTurn(BaseException):pass

# Keep local source imports available when this test is run directly.
sys.path.insert(0, str(SOURCE))

def dispatch(width,height,altars):
    created=[];shopping=[]
    class Economy:
        def __init__(self):self.kind=0;created.append(self)
    class Tactical(Economy):pass
    class Rows(Economy):pass
    class Content:pass
    class Reliable:pass
    class Road(Reliable):pass
    class Protection:pass
    class Safety:pass
    class Budget(Exception):pass
    gm=types.SimpleNamespace(width=lambda:width,height=lambda:height,camp_groups=lambda:[],
        altars=lambda:types.SimpleNamespace(positions=lambda:[types.SimpleNamespace(x=x,y=y) for x,y in altars]))
    sdk=types.ModuleType('cambc');sdk.game_map=gm
    sdk.ChampionType=types.SimpleNamespace(HEART_OF_RUIN=99)
    def stop():raise StopBeforeTurn()
    sdk.is_draft=stop
    stubs={'cambc':sdk,'draft':types.ModuleType('draft'),'rows_draft':types.ModuleType('rows_draft'),
        'bot':types.SimpleNamespace(Bot=Tactical,TurnBudget=Budget),
        'economy_bot':types.SimpleNamespace(Bot=Economy,TurnBudget=Budget),
        'rows_bot':types.SimpleNamespace(Bot=Rows,TurnBudget=Budget),
        'current_content':types.SimpleNamespace(CurrentContent=Content),
        'reliability':types.SimpleNamespace(Reliable=Reliable),
        'road_reliability':types.SimpleNamespace(RoadReliable=Road),
        'protection':types.SimpleNamespace(Protection=Protection),
        'safety':types.SimpleNamespace(Safety=Safety),
        'local_shop_recipes':types.SimpleNamespace(legacy_shop=lambda bot,me:shopping.append((bot,me)))}
    with patch.dict(sys.modules,stubs):
        spec=importlib.util.spec_from_file_location('tested_dispatch',SOURCE/'main.py')
        main=importlib.util.module_from_spec(spec);spec.loader.exec_module(main)
        with unittest.TestCase().assertRaises(StopBeforeTurn):main.main()
    return created[-1],Rows,Road,shopping

class Routing(unittest.TestCase):
    def test_exact_islands_uses_current_terrain_aware_economy(self):
        selected,_,_,_=dispatch(60,60,ALTARS)
        self.assertEqual(type(selected).__name__,'SafeEconomyBot')
    def test_altar_order_is_irrelevant(self):
        selected,_,_,_=dispatch(60,60,list(reversed(ALTARS)))
        self.assertEqual(type(selected).__name__,'SafeEconomyBot')
    def test_modified_sixty_square_uses_same_general_algorithm(self):
        selected,_,_,_=dispatch(60,60,ALTARS[:-1]+[(35,55)])
        self.assertEqual(type(selected).__name__,'SafeEconomyBot')
    def test_changed_dimensions_use_general_algorithm(self):
        selected,_,_,_=dispatch(61,60,ALTARS)
        self.assertEqual(type(selected).__name__,'SafeEconomyBot')
    def test_rows_keeps_rows_controller_with_safety_wrapper(self):
        selected,rows,_,_=dispatch(50,50,[(15,16),(34,33)])
        self.assertIsInstance(selected,rows)
        self.assertEqual(type(selected).__name__,'SafeRowsBot')
    def test_road_keeps_specialised_recall_controller_and_legacy_shop(self):
        selected,_,road,shopping=dispatch(40,40,[(19,17),(20,22)])
        self.assertIsInstance(selected,road)
        marker=object();selected.shop(marker)
        self.assertEqual(shopping,[(selected,marker)])
    def test_front_uses_awake_camp_recall_without_roads_shop_override(self):
        selected,_,road,shopping=dispatch(61,41,FRONT_ALTARS)
        self.assertIsInstance(selected,road)
        self.assertNotIn('shop',selected.__dict__)
        self.assertEqual(shopping,[])
    def test_front_altar_order_does_not_change_dispatch(self):
        selected,_,road,_=dispatch(61,41,list(reversed(FRONT_ALTARS)))
        self.assertIsInstance(selected,road)
    def test_modified_front_altar_layout_keeps_general_recall(self):
        selected,_,road,_=dispatch(61,41,FRONT_ALTARS[:-1]+[(30,40)])
        self.assertNotIsInstance(selected,road)
        self.assertEqual(type(selected).__name__,'SafeEconomyBot')
    def test_front_altars_with_different_dimensions_keep_general_recall(self):
        selected,_,road,_=dispatch(62,41,FRONT_ALTARS)
        self.assertNotIsInstance(selected,road)
    def test_unrelated_boss_layout_keeps_general_recall(self):
        selected,_,road,_=dispatch(61,41,[(30,20)])
        self.assertNotIsInstance(selected,road)
if __name__=='__main__':unittest.main()
