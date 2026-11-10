"""Execute actual cover repositioning near a wall, without importing the SDK."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

HERE=Path(__file__).resolve().parent
DEFAULT=HERE/'final-merge/src' if (HERE/'final-merge/src').is_dir() else HERE.parent/'bots/my-bot/src'
SOURCE=Path(os.environ.get('BC_BOT_SOURCE',str(DEFAULT)))

class P:
    def __init__(self,x,y):self.x,self.y=x,y
    def chebyshev_distance(self,other):return max(abs(self.x-other.x),abs(self.y-other.y))
    def __eq__(self,other):return isinstance(other,P) and (self.x,self.y)==(other.x,other.y)
    def __hash__(self):return hash((self.x,self.y))

class Board:
    """A bounded eight-neighbour grid with immutable set operations."""
    def __init__(self,cells=()):self.cells=set(cells)
    def __and__(self,other):return Board(self.cells & other.cells)
    def __invert__(self):return Board({P(x,y) for x in range(7) for y in range(5)}-self.cells)
    def is_set(self,p):return p in self.cells
    def reachable_tiles(self,p,radius):
        seen={p};front={p}
        for _ in range(radius):
            nxt={P(q.x+dx,q.y+dy) for q in front for dx in (-1,0,1) for dy in (-1,0,1)}
            nxt={q for q in nxt if 0<=q.x<7 and 0<=q.y<5 and q not in self.cells}-seen
            seen|=nxt;front=nxt
        return Board(seen)
    def positions(self):return sorted(self.cells,key=lambda p:(p.x,p.y))

class Actor:
    def __init__(self,p,identity,health=1000):self.p,self.identity,self.hp=p,identity,health
    def position(self):return self.p
    def health(self):return self.hp
    def max_health(self):return 1000
    def is_recalling(self):return False
    def is_submitting_gems(self):return False
    def is_teleporting(self):return False
    def gem_count(self):return 0 if self.identity==1 else 80
    def can_move(self):return True
    def __int__(self):return self.identity

class CoverRepositionTests(unittest.TestCase):
    def test_post_attack_step_stays_inside_reachable_ally_cover(self):
        terrain=Board(P(3,y) for y in range(1,4))
        me=Actor(P(3,0),1);ally=Actor(P(4,2),2,health=200);enemy=Actor(P(1,0),3)
        goals=terrain.reachable_tiles(ally.position(),2)
        self.assertTrue(goals.is_set(me.position()))
        # The tempting tile is close geometrically but lies around the wall.
        self.assertEqual(P(2,0).chebyshev_distance(ally.position()),2)
        self.assertFalse(goals.is_set(P(2,0)))
        moved=[]
        def move(p):moved.append(p);me.p=p
        me.move_absolute=move
        occupied=terrain.cells|{ally.position(),enemy.position()}
        env=dict(bc=NS(Bitboard=Board,round_number=lambda:10),
            distance_field=lambda blocked,targets:NS(get=lambda p:0 if targets.is_set(p) else 65535),
            dist=P.chebyshev_distance,HEALTHY=.70,WOUNDED=.35,MAX_APPROACH=4,HELP_TURNS=6,DANGER=2)
        tree=ast.parse((SOURCE/'protection.py').read_text(encoding='utf8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Protection')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='protect')
        exec(compile(ast.Module(body=[method],type_ignores=[]),str(SOURCE/'protection.py'),'exec'),env)
        bot=NS(terrain=terrain,escort_rest=-1,escort_id=None,escort_until=-1,
            allies=lambda:[ally],spawn=Board(),rescue_cast=lambda *a,**k:False,
            enemies=lambda:[enemy],check_budget=lambda:None,safety_active=False,
            risk_damage=lambda *a,**k:0,claim=lambda *a:None,attack=lambda *a:True,
            blockers=lambda actor:Board(occupied),safety_zone=lambda *a:0,
            evac_home=NS(get=lambda p:0 if p==P(5,2) else 10))
        self.assertTrue(env['protect'](bot,me))
        self.assertTrue(goals.is_set(me.position()),'helper stepped behind the wall and lost reachable cover')
        self.assertTrue(all(goals.is_set(p) for p in moved))
        self.assertNotIn(P(5,2),moved,'helper occupied the protected ally homeward exit')

if __name__=='__main__':unittest.main()
