"""Regression tests for replay-diagnosed stalls and unsafe resumed decisions."""
import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path(__file__).resolve().parents[1]/'bots'/'my-bot'/'src'
sys.path.insert(0,str(SOURCE))
from progress import Progress

class ProgressChecks(unittest.TestCase):
    def test_two_tile_loop_reassigns_without_resource_gain(self):
        p=Progress()
        triggered=[]
        for r in range(10):
            triggered.append(p.observe(r,1,(0,r%2),10,(0,8,0,100)))
        self.assertTrue(any(triggered))

    def test_stationary_fighting_and_capture_are_productive(self):
        p=Progress()
        for r in range(40):
            self.assertFalse(p.observe(r,1,(0,0),0,(r//10,0,0,100-r)))

    def test_movement_toward_goal_is_productive(self):
        p=Progress()
        for r in range(40):
            self.assertFalse(p.observe(r,1,(r,0),80-r,(0,0,0,100)))

    def test_goal_churn_does_not_hide_stationary_stall(self):
        p=Progress()
        self.assertTrue(any(p.observe(r,r%2,(0,0),10,(0,0,0,100+r%2)) for r in range(30)))

    def test_channel_or_respawn_gap_clears_stale_history(self):
        p=Progress()
        for r in range(5): p.observe(r,1,(0,0),10,(0,0,0,100))
        self.assertFalse(p.observe(90,1,(0,0),10,(0,0,0,100)))
        self.assertEqual(p.idle,0)

class SafetyChecks(unittest.TestCase):
    def setUp(self):
        self.fake=types.SimpleNamespace(Team=types.SimpleNamespace(ALLY=0,ENEMY=1),
                                      ChampionType=object(), ItemType=object())
        self.saved={k:sys.modules.get(k) for k in ('cambc','coordination','economy_bot')}
        self.fake.game_map=types.SimpleNamespace()
        sys.modules['cambc']=self.fake
        sys.modules['coordination']=types.SimpleNamespace(read_claims=lambda:[])
        self.spec=importlib.util.spec_from_file_location('tested_reliability',SOURCE/'reliability.py')
        self.mod=importlib.util.module_from_spec(self.spec)
        self.spec.loader.exec_module(self.mod)

    def tearDown(self):
        for name,value in self.saved.items():
            if value is None: sys.modules.pop(name,None)
            else: sys.modules[name]=value

    def test_release_reassigns_only_after_sustained_no_progress(self):
        class Base:
            def farm(self,me): pass
        class Bot(self.mod.Reliable,Base):
            def check_budget(self): pass
            def claim(self,goal): self.target=goal
        b=Bot();b.progress=Progress();b.target=0;b.failed_until={}
        camp=types.SimpleNamespace(is_visible=lambda:True,health=lambda:100)
        b.groups=[[camp]];b.path_fields=[types.SimpleNamespace(get=lambda p:10)]
        now=[0]
        self.fake.round_number=lambda:now[0]
        self.fake.global_submitted_gems=lambda team:0
        position=types.SimpleNamespace(x=0,y=0)
        me=types.SimpleNamespace(position=lambda:position,gold_count=lambda:0,gem_count=lambda:0)
        for r in range(60):
            now[0]=r;b.farm(me)
            self.assertEqual(b.target,0)
        now[0]=60;b.farm(me)
        self.assertIsNone(b.target)
        self.assertEqual(b.failed_until[0],90)

    def test_dead_actor_rejects_resumed_decision(self):
        class Budget(Exception): pass
        sys.modules['economy_bot']=types.SimpleNamespace(TurnBudget=Budget)
        class Base:
            def check_budget(self): pass
        class Bot(self.mod.Reliable,Base): pass
        self.fake.me=lambda:types.SimpleNamespace(is_alive=lambda:False)
        with self.assertRaises(Budget): Bot().check_budget()

    def test_enemy_lock_selected_when_both_teams_share_altar(self):
        fake_coord = sys.modules['coordination']
        for name in ('write_claim','report','read_report'):
            setattr(fake_coord,name,lambda *args:None)
        spec=importlib.util.spec_from_file_location('tested_economy_lock',SOURCE/'economy_bot.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        class P:
            def chebyshev_distance(self,other): return 1
        altar=P()
        ally=types.SimpleNamespace(position=lambda:altar)
        enemy=types.SimpleNamespace(position=lambda:altar)
        mask=types.SimpleNamespace(is_set=lambda p:True)
        teams=[]
        def locks(team):
            teams.append(team)
            return [enemy] if team==1 else [ally,enemy]
        self.fake.vision=types.SimpleNamespace(altar_lock_tiles=lambda team:mask,
                                             altar_locks=locks,
                                             altar_lock_at=lambda p:ally)
        self.fake.constants=types.SimpleNamespace(SUBMIT_GEMS_RANGE=1)
        attacked=[]
        me=types.SimpleNamespace(position=lambda:altar, can_attack=lambda:True,
                                 attack_tiles=lambda:mask,attack=attacked.append)
        b=module.Bot();b.collision=False;b.altars=[altar];b.check_budget=lambda:None
        self.assertTrue(b.bank(me))
        self.assertEqual(teams,[1])
        self.assertEqual(attacked,[enemy])

    def test_retreat_scores_only_primitive_snapshots(self):
        class P:
            def __init__(self,x): self.x=x
            def chebyshev_distance(self,p): return abs(self.x-p.x)
        origin, safe, danger = P(0),P(-1),P(1)
        class Mask:
            def reachable_tiles(self,p,r): return self
            def positions(self): return [origin,safe,danger]
            def is_set(self,p): return False
        class Bot(self.mod.Reliable):
            def check_budget(self): pass
            def blockers(self,me): return Mask()
            def escape_dash(self,me,threats): return False
        b=Bot();b.spawn=Mask()
        b.enemies=lambda:[]
        b.visible_camps=lambda:[types.SimpleNamespace(position=lambda:P(1),attack_range=lambda:1,strength=lambda:280)]
        moves=[]
        me=types.SimpleNamespace(position=lambda:origin,can_move=lambda:True,
                                 move_absolute=lambda p:moves.append(p),recall=lambda:self.fail('unsafe recall'))
        b.retreat(me,[])
        self.assertEqual(moves,[safe])

if __name__=='__main__': unittest.main()
