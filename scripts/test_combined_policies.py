"""Behavioral compatibility: ready rewards and cover across walls/holes."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace as NS, MethodType
import unittest

LOCAL_SOURCE=Path(__file__).parent/'src'
SOURCE=Path(os.environ.get('BC_BOT_SOURCE',str(LOCAL_SOURCE if LOCAL_SOURCE.is_dir() else Path(__file__).resolve().parents[1]/'bots/my-bot/src')))

class P:
    def __init__(self,x=0,y=0):self.x,self.y=x,y
    def chebyshev_distance(self,q):return max(abs(self.x-q.x),abs(self.y-q.y))
    def __eq__(self,q):return isinstance(q,P) and (self.x,self.y)==(q.x,q.y)
    def __hash__(self):return hash((self.x,self.y))

class Board:
    def __init__(self,cells=()):self.cells=set(cells)
    def __and__(self,other):return Board(self.cells & other.cells)
    def __invert__(self):return Board({P(x,y) for x in range(7) for y in range(5)}-self.cells)
    def is_set(self,p):return p in self.cells
    def is_empty(self):return not self.cells
    def draw_chebyshev(self,p,r):
        self.cells|={P(x,y) for x in range(7) for y in range(5) if p.chebyshev_distance(P(x,y))<=r}
    def reachable_tiles(self,p,r):
        reached={p};front={p}
        for _ in range(r):
            next_={P(q.x+dx,q.y+dy) for q in front for dx in (-1,0,1) for dy in (-1,0,1)}
            next_={q for q in next_ if 0<=q.x<7 and 0<=q.y<5 and q not in self.cells}-reached
            reached|=next_;front=next_
        return Board(reached)
    def positions(self):return list(self.cells)


def function(file,name,env,cls=None):
    tree=ast.parse((SOURCE/file).read_text(encoding='utf-8'))
    body=tree.body
    if cls:body=next(n for n in body if isinstance(n,ast.ClassDef) and n.name==cls).body
    node=next(n for n in body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(SOURCE/file),'exec'),env)
    return env[name]

class Actor:
    def __init__(self,p,health=1000,maximum=1000,kind=1):self.p,self.hp,self.maximum,self.kind=p,health,maximum,kind
    def position(self):return self.p
    def health(self):return self.hp
    def max_health(self):return self.maximum
    def is_alive(self):return True
    def is_visible(self):return True
    def is_recalling(self):return False
    def is_submitting_gems(self):return False
    def is_teleporting(self):return False
    def gem_count(self):return 80
    def attack_range(self):return 1
    def strength(self):return 30
    def can_move(self):return False
    def can_attack(self):return False
    def can_cast(self):return False
    def champion_name(self):return self.kind
    def __int__(self):return self.kind


def cover_fixture():
    terrain=Board(P(3,y) for y in range(5))
    me=Actor(P(2,2));me.gem_count=lambda:0
    ally=Actor(P(4,2),200,1000,2);enemy=Actor(P(5,2),1000,1000,3)
    calls=[]
    env=dict(bc=NS(Bitboard=Board,round_number=lambda:10,fuel_remaining=lambda:3_000_000),
        distance_field=lambda terrain,goals:NS(get=lambda p:0 if goals.is_set(p) else 65535),
        dist=lambda p,q:p.chebyshev_distance(q),HEALTHY=.70,WOUNDED=.35,
        MAX_APPROACH=4,HELP_TURNS=6,DANGER=2)
    bot=NS(terrain=terrain,escort_rest=-1,escort_id=None,escort_until=-1,
        allies=lambda:[ally],spawn=Board(),rescue_cast=lambda *a,**k:False,
        enemies=lambda:[enemy],check_budget=lambda:None,safety_active=False,
        risk_damage=lambda *a,**k:0,claim=lambda *a:None,
        attack=lambda *a:calls.append('attack') or True)
    return env,bot,me,ally,calls

class CoverTopologyTests(unittest.TestCase):
    def test_geometric_proximity_across_wall_is_not_actual_close_cover(self):
        env,bot,me,ally,calls=cover_fixture()
        geometric=Board();geometric.draw_chebyshev(ally.position(),2)
        self.assertTrue(geometric.is_set(me.position())) # Demonstrates old failure.
        protect=function('protection.py','protect',env,'Protection')
        self.assertFalse(protect(bot,me))
        self.assertEqual(calls,[])

    def test_close_cover_on_same_side_still_works(self):
        env,bot,me,ally,calls=cover_fixture()
        me.p=P(5,2)
        bot.evac_home=NS(get=lambda p:0)
        protect=function('protection.py','protect',env,'Protection')
        self.assertTrue(protect(bot,me))
        self.assertEqual(calls,['attack'])

    def test_final_guard_step_stays_in_the_connected_ally_ring(self):
        env,bot,me,ally,calls=cover_fixture()
        # The ally ring reaches the bottom of this wall in two steps. A third
        # step on its far side still looks Chebyshev-close but cannot give cover.
        terrain=Board(P(3,y) for y in range(4))
        bot.terrain=terrain;me.p=P(3,4)
        pursuer=Actor(P(1,3),1000,1000,3)
        bot.enemies=lambda:[pursuer]
        bot.blockers=lambda actor:terrain
        bot.evac_home=NS(get=lambda p:0 if p==P(5,2) else 1)
        bot.safety_zone=lambda *args:0
        me.can_move=lambda:True
        moved=[];me.move_absolute=lambda p:moved.append(p)
        geometric=Board();geometric.draw_chebyshev(ally.position(),2)
        outside=P(2,3)
        self.assertTrue(geometric.is_set(outside))
        self.assertFalse(terrain.reachable_tiles(ally.position(),2).is_set(outside))
        protect=function('protection.py','protect',env,'Protection')
        self.assertTrue(protect(bot,me))
        self.assertNotIn(outside,moved)
        self.assertTrue(all(terrain.reachable_tiles(ally.position(),2).is_set(p) for p in moved))

    def test_regroup_goal_does_not_cross_wall_even_when_ally_looks_near(self):
        env,bot,me,ally,calls=cover_fixture()
        ally.hp=1000
        bot.safety_active=True;bot.safety_position=me.position();bot.safety_hp=500;bot.safety_gems=20
        bot.risk_enemies=[((1,3),100,1),((1,1),100,1)]
        bot.risk_damage=lambda p,turns=2:400 if p==me.position() else 0
        bot.evac_home=NS(get=lambda p:1)
        bot.cast=lambda *a,**k:None
        bot.move=lambda actor,goals:calls.append(goals) or True
        env['report']=lambda *a:None
        regroup=function('protection.py','regroup_turn',env,'Protection')
        self.assertTrue(regroup(bot,me,.60))
        self.assertEqual(len(calls),1)
        self.assertFalse(calls[0].is_set(me.position()))
        self.assertTrue(calls[0].is_set(ally.position()))

    def test_crater_partner_attempts_route_around_obstacle_inside_two_tile_disk(self):
        env,bot,me,ally,calls=cover_fixture()
        tree=ast.parse((SOURCE/'main.py').read_text(encoding='utf-8'))
        literal=next(n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call)
            and isinstance(n.func,ast.Name) and n.func.id=='exec' and n.args
            and isinstance(n.args[0],ast.Constant) and '_crater_partner_support' in str(n.args[0].value))
        bot.kind=2;ally.kind=1;bot.allies_by_slot=[ally];bot.safety_active=True
        bot._crater_heal_ability=None
        bot.move=lambda actor,goals:calls.append(goals) or True
        bot.visible_camps=lambda:[]
        bot.attack=lambda *args:None
        bot.enemies=lambda:[]
        env['Bot']=NS(support=lambda *a:False)
        env['C']=NS(WILLOW=2,VARG=1)
        env['bc'].vision=NS(awake_camp_tiles=Board)
        exec(compile(literal,'<crater support literal>','exec'),env)
        self.assertTrue(env['_crater_partner_support'](bot,me))
        self.assertEqual(len(calls),1)
        self.assertFalse(calls[0].is_set(me.position()))
        self.assertTrue(calls[0].is_set(ally.position()))

class Ready:pass
class Alive:pass
class Respawning:pass
class SelectorMask:
    def __init__(self,visible=True):self.visible=visible
    def __and__(self,other):return self
    def is_empty(self):return not self.visible
    def is_set(self,p):return False
class CampGroup(list):
    def __init__(self,state,reward):
        super().__init__([NS(is_visible=lambda:False,base_stats=lambda:NS(base_health=20000))])
        self.live_state,self.reward=state,reward
    def state(self):return self.live_state
    def gem_value(self):return self.reward
    def gold_value(self):return 0

SELECTORS=[('economy_bot.py','Bot'),('rows_bot.py','Bot'),('bot.py','Bot'),
           ('legacy_tactical.py','Bot'),('camp_policy.py',None),
           ('specific_maps.py','TerritoryEconomy'),('specific_maps.py','FragmentEconomy'),
           ('specific_maps.py','GiftEconomy'),('specific_maps.py','CooperativeEconomy')]

def selector_fixture(file,cls,state,strength=30,visible=True,competitor=False):
    env=dict(bc=NS(vision=NS(visible_tiles=SelectorMask),fuel_remaining=lambda:3_000_000,round_number=lambda:100),
        gm=NS(CampGroupRewardAvailable=Ready,CampGroupRespawning=Respawning),
        C=NS(VARG=1,CASSI=2,VENDETTA=3,TAVI=4,RYTH=5,WILLOW=6),
        read_claims=lambda:[],has_jungle=lambda counts:False,dist=lambda a,b:0,UNREACHABLE=65535)
    function('navigation.py','nearest_groups',env)
    name='choose_group' if cls else 'choose_economy_group'
    select=function(file,name,env,cls)
    groups=[CampGroup(state,200)]+([CampGroup(Ready(),50)] if competitor else [])
    n=len(groups)
    bot=NS(groups=groups,target=None,masks=[SelectorMask(visible) for g in groups],centers=[P() for g in groups],
        group_stats=[(20000,200,True)]+([(100,0,False)] if competitor else []),
        path_fields=[NS(get=lambda p:1) for g in groups],group_rewards=[g.reward for g in groups],
        failed_until={},sleep_until={},check_budget=lambda:None,kind=1,alert=None,slot=0,allies_by_slot=[],
        allies=lambda:[],rows=False,corners=False,collision=False,home_groups=[True]*n,crates=[False]*n,
        altar_groups=[False]*n,rows_owners={},rows_home=[],specific_fragment=False,cooperative_map=False,gift_completion=False)
    me=NS(position=P,strength=lambda:strength,health=lambda:100,max_health=lambda:1000,item_count=lambda:[])
    return select,bot,me

class BossRewardTests(unittest.TestCase):
    def test_cleared_boss_can_be_collected_by_weak_solo_farmer(self):
        for file,cls in SELECTORS:
            with self.subTest(policy=(file,cls)):
                fn,b,m=selector_fixture(file,cls,Ready())
                self.assertEqual(fn(b,m),0)

    def test_live_and_unseen_bosses_keep_combat_gate(self):
        for file,cls in SELECTORS:
            for state,visible in ((Alive(),True),(Ready(),False)):
                with self.subTest(policy=(file,cls),visible=visible):
                    fn,b,m=selector_fixture(file,cls,state,visible=visible)
                    self.assertIsNone(fn(b,m))

    def test_ready_boss_reward_is_not_ranked_as_dangerous_boss(self):
        for file,cls in SELECTORS:
            with self.subTest(policy=(file,cls)):
                fn,b,m=selector_fixture(file,cls,Ready(),strength=250,competitor=True)
                self.assertEqual(fn(b,m),0)

    def test_non_boss_role_on_rows_can_collect_already_cleared_reward(self):
        fn,b,m=selector_fixture('bot.py','Bot',Ready())
        b.rows=True
        self.assertEqual(fn(b,m),0)

if __name__=='__main__':unittest.main()
