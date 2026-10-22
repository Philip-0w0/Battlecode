import pathlib
import sys
import unittest

root=pathlib.Path(__file__).parent/'src'
if not root.exists(): root=pathlib.Path(__file__).resolve().parents[1]/'bots'/'rows-assignment-v1'/'src'
sys.path.insert(0,str(root))
from assignments import assign_home_camps


class Assignments(unittest.TestCase):
    def test_unique_ownership_and_varg_monsters(self):
        camps=[(0,10,False),(1,12,True),(2,20,True),(3,30,True)]
        result=assign_home_camps([(0,False),(1,True),(2,False),(3,False)],camps)
        self.assertEqual(result,{1:1,0:0,2:2,3:3})
        self.assertEqual(len(set(result.values())),4)

    def test_deterministic_when_input_order_changes(self):
        champions=[(0,False),(1,True),(2,False)]
        camps=[(0,10,False),(1,12,True),(2,20,True)]
        self.assertEqual(assign_home_camps(champions,camps),
                         assign_home_camps(list(reversed(champions)),list(reversed(camps))))

    def test_empty_and_short_pools(self):
        self.assertEqual(assign_home_camps([(0,True)],[]),{})
        self.assertEqual(assign_home_camps([(0,False),(1,True)],[(4,3,False)]),{4:1})


if __name__=='__main__': unittest.main()
