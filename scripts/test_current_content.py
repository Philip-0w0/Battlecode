"""Current-content regressions: map roles, legal Heart casts and bounded paths."""
import importlib.util,pathlib,sys,types,unittest
SOURCE=pathlib.Path(__file__).resolve().parents[1]/'bots'/'my-bot'/'src'
sys.path.insert(0,str(SOURCE))
class P:
    def __init__(self,x,y=0): self.x,self.y=x,y
    def chebyshev_distance(self,p): return max(abs(self.x-p.x),abs(self.y-p.y))
    def __eq__(self,p): return isinstance(p,P) and (self.x,self.y)==(p.x,p.y)
class CurrentTests(unittest.TestCase):
    def setUp(self):
        self.saved={k:sys.modules.get(k) for k in ['cambc','map_profile']}
        class Camp:
            def position(self): return P(2)
            def health(self): return 100
            def strength(self): return 20
            def attack_range(self): return 1
            def is_visible(self): return True
            def is_awake(self): return True
            def camp_group(self): return self.group
        self.Camp=Camp
        names='VARG TAVI VENDETTA RYTH WILLOW PRISM MARCELLA HEART_OF_RUIN STELLAR VESPER_VALE REN CASSI_AND_ISSAC'.split()
        self.fake=types.SimpleNamespace(Team=types.SimpleNamespace(ALLY=0,ENEMY=1),ChampionType=types.SimpleNamespace(HEART_OF_RUIN=12,PRISM=6,TAVI=11,STELLAR=5,WILLOW=8,CASSI=3),ItemType=object(),ChampionDraft=types.SimpleNamespace(**{n:i for i,n in enumerate(names)}),game_map=object(),Camp=Camp,Champion=type('Champion',(),{}),fuel_remaining=lambda:2000000)
        self.fake.draft=types.SimpleNamespace(team_size=lambda:4)
        self.fake.round_number=lambda:10
        self.fake.ChampionState=types.SimpleNamespace(ALIVE=1,CAN_CAST=2048,RECALLING=2,
            SUBMITTING_GEMS=4,TELEPORTING=4096,COMPLETED_TURN=32)
        self.fake.BuffRestrictions=types.SimpleNamespace(CAST=4)
        sys.modules['cambc']=self.fake
        sys.modules['map_profile']=types.SimpleNamespace(profile=lambda:{})
        self.content=self.load('current_content')
        self.roles=self.load('map_profile')
    def tearDown(self):
        for k,v in self.saved.items():
            if v is None: sys.modules.pop(k,None)
            else: sys.modules[k]=v
    def load(self,name):
        spec=importlib.util.spec_from_file_location('tested_'+name,SOURCE/(name+'.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    def test_content_state_survives_interrupted_parent_setup(self):
        self.fake.champions=lambda team:[]
        class Base:
            def setup(self,me): raise ValueError('simulated setup interruption')
        class Bot(self.content.CurrentContent,Base): pass
        b=Bot()
        with self.assertRaises(ValueError): b.setup(None)
        self.assertEqual(b._enemy_hearts,[])
        self.assertFalse(b._heart_emergency)
        self.assertIsNone(b._heart_threat)
    def test_gem_rewards_decide_boss_only_role(self):
        boss=dict(gold=100,gems=200,boss=True,size=1,incoming=200,golem=False)
        gold=dict(gold=80,gems=0,boss=False,size=1,incoming=20,golem=False)
        self.assertTrue(self.roles.classify([boss,gold])['boss_only'])
        gem=dict(gold=0,gems=10,boss=False,size=1,incoming=0,golem=False)
        self.assertFalse(self.roles.classify([boss,gem])['boss_only'])
    def test_default_draft_preserves_primary_farmers(self):
        info=dict(zero_gold=True,gems=10,boss_only=False,golems=False,clustered=1,has_groups=True)
        D=self.fake.ChampionDraft
        order=self.roles.draft_order([],[],info)
        self.assertEqual(order[:3],[D.VARG,D.TAVI,D.VENDETTA])
    def test_heart_remains_a_legal_roster_fallback(self):
        info=dict(zero_gold=False,gems=10,boss_only=False,golems=True,clustered=1,has_groups=True)
        D=self.fake.ChampionDraft
        self.assertIn(D.HEART_OF_RUIN,self.roles.draft_order([],[],info))
    def test_heart_build_uses_focus_shards(self):
        self.content.I=types.SimpleNamespace(JUNGLE_SHARD_OF_FOCUS=0,JUNGLE_EMBLEM_OF_FOCUS=1,
            MONSTER_SHARD_OF_FOCUS=2,MONSTER_EMBLEM_OF_FOCUS=3,BRUISER_SHARD_OF_HEALTH=4,
            BRUISER_EMBLEM_OF_HEALTH=5,POWER_SHARD_OF_FOCUS=6,POWER_EMBLEM_OF_FOCUS=7)
        b=self.content.CurrentContent();b.kind=12
        bought=[];gold=[150]
        def buy(item,n): bought.append((item,n));gold[0]-=30*n
        me=types.SimpleNamespace(gold_count=lambda:gold[0],item_count=lambda:[0]*8,
                                can_buy=lambda item,n:True,buy=buy)
        b.shop(me)
        self.assertEqual(bought,[(0,5)])
    def test_enemy_heart_burst_uses_actual_damage_and_movement_horizon(self):
        self.fake.Vec2=P
        ability=types.SimpleNamespace(is_dash=lambda:True,cooldown=lambda:0,
            info=lambda:types.SimpleNamespace(range=2,radius=1),damage_amount=lambda me:850)
        enemy=types.SimpleNamespace(is_alive=lambda:True,is_visible=lambda:True,
            abilities=lambda:[ability],base_stats=lambda:types.SimpleNamespace(base_move_speed=1),position=lambda:P(5))
        class Bot(self.content.CurrentContent):
            def check_budget(self): pass
        b=Bot();b._enemy_hearts=[enemy];b.threats=[]
        me=types.SimpleNamespace(health=lambda:1000,position=lambda:P(0))
        b.observe_heart_burst(me)
        self.assertTrue(b._heart_emergency)
        self.assertEqual(b.threats[0][1:],(850,6))
    def cast_fixture(self,recovering=False,risk=0,selected=True):
        used=[];group=object();camp=self.Camp();camp.group=group if selected else object()
        class Board:
            def __and__(self,other): return self
            def reachable_tiles(self,*a): return self
            def positions(self): return [P(1)]
            def is_set(self,p): return False
        board=Board();self.fake.vision=types.SimpleNamespace(visible_tiles=lambda:board)
        ability=types.SimpleNamespace(is_shield=lambda:False,is_dash=lambda:True,is_ready=lambda:True,
            info=lambda:types.SimpleNamespace(range=2,radius=1,exclusive_with_movement=False),
            valid_tiles=lambda:board,damage_amount=lambda:150,use=lambda p:used.append(p) or True)
        me=types.SimpleNamespace(state=lambda:2049,restrictions=lambda:0,can_cast=lambda:True,position=lambda:P(0),health=lambda:1000,
                                 abilities=lambda:[ability],buffs=lambda:types.SimpleNamespace(has_shield=lambda:True))
        class Bot(self.content.CurrentContent):
            def check_budget(self): pass
            def blockers(self,me): return board
            def pressure(self,p): return risk
        b=Bot();b.kind=12;b.action_round=10;b.recovering=recovering;b.target=0;b.groups=[group]
        return b,me,camp,used
    def test_nonworsening_dash_is_used_under_existing_pressure(self):
        b,me,camp,used=self.cast_fixture(risk=100)
        self.assertTrue(b.cast(me,[camp]));self.assertEqual(used,[P(1)])
    def test_recovery_never_uses_offensive_dash(self):
        b,me,camp,used=self.cast_fixture(recovering=True)
        self.assertFalse(b.cast(me,[camp]));self.assertEqual(used,[])
    def test_dash_does_not_pull_an_unselected_camp(self):
        b,me,camp,used=self.cast_fixture(selected=False)
        self.assertFalse(b.cast(me,[camp]));self.assertEqual(used,[])
    def test_unsafe_landing_is_rejected(self):
        b,me,camp,used=self.cast_fixture(risk=400)
        self.assertFalse(b.cast(me,[camp]));self.assertEqual(used,[])
    def test_setup_installs_recovery_state_before_parent_can_yield(self):
        mod=self.load('reliability')
        class Base:
            def setup(self,me): raise ValueError('simulated setup interruption')
        class Bot(mod.Reliable,Base): pass
        b=Bot()
        with self.assertRaises(ValueError): b.setup(None)
        self.assertTrue(hasattr(b,'progress'))
        self.assertTrue(hasattr(b,'detour_until'))
if __name__=='__main__': unittest.main()
