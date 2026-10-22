"""Boundary and protocol tests for annotation-driven decisions."""
import importlib.util
import pathlib
import sys
import types
import unittest

SOURCE = pathlib.Path(__file__).parent / 'src'
if not SOURCE.exists(): SOURCE = pathlib.Path(__file__).resolve().parents[1] / 'bots' / 'my-bot' / 'src'
sys.path.insert(0,str(SOURCE))
from tactics import lethal_recent_loss, winning_load, favorable_fight


class Decisions(unittest.TestCase):
    def test_burst_threshold_and_stale_samples(self):
        self.assertTrue(lethal_recent_loss(300,19,140,20))
        self.assertTrue(lethal_recent_loss(280,19,140,20))
        self.assertFalse(lethal_recent_loss(279,19,140,20))
        self.assertFalse(lethal_recent_loss(300,18,140,20))
        self.assertFalse(lethal_recent_loss(None,19,140,20))
        self.assertFalse(lethal_recent_loss(100,19,750,20))

    def test_team_total_and_exact_target(self):
        self.assertTrue(winning_load(891,[40,40,29,0]))
        self.assertFalse(winning_load(891,[40,40,28,0]))
        self.assertTrue(winning_load(990,[10]))

    def test_numbers_do_not_override_overwhelming_enemy_stats(self):
        self.assertTrue(favorable_fight(1500,160,750,80))
        self.assertFalse(favorable_fight(1500,80,2000,400))


class Memory:
    def __init__(self): self.data=bytearray(8)
    def read(self,offset,target):
        assert offset+len(target)<=8
        target[:]=self.data[offset:offset+len(target)]
    def write(self,offset,data):
        assert offset+len(data)<=8
        self.data[offset:offset+len(data)]=data


class EndgameProtocol(unittest.TestCase):
    def setUp(self):
        self.memory=Memory()
        old=sys.modules.get('cambc')
        sys.modules['cambc']=types.SimpleNamespace(shared_memory=self.memory)
        spec=importlib.util.spec_from_file_location('tested_coordination',SOURCE/'coordination.py')
        self.p=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.p)
        if old is None: del sys.modules['cambc']
        else: sys.modules['cambc']=old

    def test_transition_clears_old_claims_and_alerts(self):
        for slot in range(6): self.p.write_claim(slot,slot+2)
        self.p.report(99,99,255,True)
        self.assertFalse(self.p.banking_mode())
        self.p.publish_gems(3,112)
        self.assertEqual(self.p.read_gems(),[0,0,0,112,0,0])
        self.p.write_claim(0,5);self.p.report(2,3,0,True)
        self.assertEqual(self.p.read_gems(),[0,0,0,112,0,0])
        self.assertEqual(self.p.read_claims(),[0]*6)
        self.assertIsNone(self.p.read_report(0)[1])

    def test_all_slots_preserved_death_and_deposit_reset(self):
        expected=[1,1023,44,109,200,999]
        for slot,gems in enumerate(expected): self.p.publish_gems(slot,gems)
        self.assertEqual(self.p.read_gems(),expected)
        self.p.publish_gems(2,0);expected[2]=0
        self.assertEqual(self.p.read_gems(),expected)
        self.assertEqual(len(self.memory.data),8)


class BossGuard(unittest.TestCase):
    def test_rows_requires_selected_boss_and_healthy_vendetta_tavi(self):
        class Position:
            def chebyshev_distance(self,other): return 1
        class Camp:
            def __int__(self): return 42
            def spawn_position(self): return Position()
        class Ally:
            def __init__(self,kind,health=100): self.kind,self.hp=kind,health
            def health(self): return self.hp
            def max_health(self): return 100
            def position(self): return Position()
            def champion_name(self): return self.kind
        names=['cambc','coordination','camp_policy']
        saved={name:sys.modules.get(name) for name in names}
        fake=types.SimpleNamespace(Team=object(),ItemType=object(),
            ChampionType=types.SimpleNamespace(VENDETTA=2,TAVI=11),
            Camp=Camp,game_map=types.SimpleNamespace())
        try:
            sys.modules['cambc']=fake
            for name in ['coordination','camp_policy']:
                sys.modules.pop(name,None)
            spec=importlib.util.spec_from_file_location('tested_bot',SOURCE/'bot.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            bot=module.Bot();bot.rows=True;bot.boss_camps={42}
            bot.group_stats=[(40000,400,True)]
            bot.allies=lambda:[Ally(2),Ally(11)]
            self.assertFalse(bot.boss_allowed(None,Camp()))
            bot.target=0
            self.assertTrue(bot.boss_allowed(None,Camp()))
            bot.allies=lambda:[Ally(11)]
            self.assertFalse(bot.boss_allowed(None,Camp()))
            bot.allies=lambda:[Ally(2,30),Ally(11)]
            self.assertFalse(bot.boss_allowed(None,Camp()))
            bot.allies=lambda:[Ally(0),Ally(10)]
            self.assertFalse(bot.boss_allowed(None,Camp()))
        finally:
            for name,old in saved.items():
                if old is None: sys.modules.pop(name,None)
                else: sys.modules[name]=old


if __name__=='__main__': unittest.main()
