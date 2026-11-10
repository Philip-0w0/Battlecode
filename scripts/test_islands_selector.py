"""Terrain-aware shortlist works on Islands and other obstacle-heavy maps."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
SOURCE=Path(os.environ.get('BATTLECODE_TEST_SOURCE',str(Path(__file__).parent.parent/'bots/my-bot/src'))).resolve()
context={'UNREACHABLE':65535}
tree=ast.parse((SOURCE/'navigation.py').read_text(encoding='utf-8'))
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='nearest_groups')
exec(compile(ast.Module(body=[node],type_ignores=[]),str(SOURCE/'navigation.py'),'exec'),context)
nearest=context['nearest_groups']
def fields(costs):return [NS(get=lambda p,cost=c:cost) for c in costs]
class Navigation(unittest.TestCase):
    def test_unreachable_camps_cannot_fill_the_shortlist(self):
        self.assertEqual(nearest(fields([65535]*12+[22]),None),[12])
    def test_path_cost_ranks_before_geometric_appearance(self):
        self.assertEqual(nearest(fields([90,1,30,2]),None,limit=2),[1,3])
    def test_bound_limits_live_candidate_work(self):
        self.assertEqual(nearest(fields(list(range(20))),None),list(range(10)))
    def test_reachable_current_target_is_retained_beyond_shortlist(self):
        self.assertEqual(nearest(fields(list(range(12))),None,current=11),list(range(10))+[11])
    def test_unreachable_current_target_is_not_reintroduced(self):
        self.assertEqual(nearest(fields([1,2,65535]),None,current=2),[0,1])
    def test_zero_distance_capture_goal_is_valid(self):
        self.assertEqual(nearest(fields([5,0]),None),[1,0])
    def test_map_scan_yields_at_bounded_intervals(self):
        checks=[]
        nearest(fields(list(range(25))),None,check_budget=lambda:checks.append(1))
        self.assertEqual(len(checks),4)
if __name__=='__main__':unittest.main()
