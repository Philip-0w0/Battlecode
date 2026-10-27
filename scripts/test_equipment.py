"""Regression tests for stat-independent Jungle passives."""
import importlib.util
import pathlib
import sys
import types
import unittest

SOURCE=pathlib.Path(__file__).resolve().parents[1]/'bots'/'my-bot'/'src'

class JunglePassiveTests(unittest.TestCase):
    def setUp(self):
        previous=sys.modules.get('cambc')
        fake=types.SimpleNamespace(ItemType=types.SimpleNamespace(
            JUNGLE_EMBLEM_OF_STRENGTH=0,JUNGLE_EMBLEM_OF_FOCUS=1,JUNGLE_EMBLEM_OF_HEALTH=2))
        sys.modules['cambc']=fake
        try:
            spec=importlib.util.spec_from_file_location('tested_equipment',SOURCE/'equipment.py')
            self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        finally:
            if previous is None: sys.modules.pop('cambc',None)
            else: sys.modules['cambc']=previous

    def test_each_stat_variant_has_the_same_family_passive(self):
        for index in range(3):
            counts=[0,0,0];counts[index]=1
            self.assertTrue(self.module.has_jungle(counts))

    def test_no_completed_emblem_has_no_passive(self):
        self.assertFalse(self.module.has_jungle([0,0,0]))

    def test_multiple_emblems_are_a_single_boolean_passive(self):
        self.assertIs(self.module.has_jungle([2,1,3]),True)

if __name__=='__main__': unittest.main()
