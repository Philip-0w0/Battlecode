"""Execute the actual tactical engagement method against movement and channel fixtures."""
import ast
from collections import deque
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent/'bots/my-bot/src/bot.py'

class Point:
    def __init__(self, x, y=3): self.x, self.y = x, y
    def chebyshev_distance(self, other): return max(abs(self.x-other.x), abs(self.y-other.y))
    def __hash__(self): return hash((self.x,self.y))
    def __eq__(self, other): return isinstance(other,Point) and (self.x,self.y)==(other.x,other.y)

class Board:
    searches = 0
    last_blocked = set()
    def __init__(self, cells=()): self.cells = set(cells)
    def __or__(self, other): return Board(self.cells|other.cells)
    def set(self, position, value):
        if value: self.cells.add(position)
        else: self.cells.discard(position)
    def positions(self): return list(self.cells)
    def reachable_tiles(self, origin, moves):
        Board.searches += 1
        Board.last_blocked = self.cells.copy()
        seen={origin};queue=deque([(origin,0)])
        while queue:
            p,n=queue.popleft()
            if n>=moves: continue
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    q=Point(p.x+dx,p.y+dy)
                    if 0<=q.x<=12 and 0<=q.y<=6 and q not in self.cells and q not in seen:
                        seen.add(q);queue.append((q,n+1))
        return Board(seen)

class Champion:
    def __init__(self, x, radius=1, moves=1, gems=0, channel=None, hp=100):
        self.p,self.radius,self.moves,self.gems,self.channel,self.hp=Point(x),radius,moves,gems,channel,hp
    def position(self): return self.p
    def attack_range(self): return self.radius
    def base_stats(self): return NS(base_move_speed=self.moves)
    def gem_count(self): return self.gems
    def is_recalling(self): return self.channel=='recall'
    def is_submitting_gems(self): return self.channel=='bank'
    def is_teleporting(self): return self.channel=='teleport'
    def health(self): return self.hp
    def max_health(self): return 100
    def strength(self): return 100
    def focus(self): return 0
    def is_alive(self): return True
    def is_visible(self): return True

def fixture(ally, gems=10, walls=()):
    tree=ast.parse(SOURCE.read_text(encoding='utf8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Bot')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='engage')
    me=Champion(3,radius=4,gems=gems);enemy=Champion(6)
    occupied=Board([me.p,ally.p,enemy.p])
    empty=Board()
    vision=NS(champion_tiles=lambda:occupied,camp_tiles=lambda:empty,teleport_tiles=lambda:empty)
    env=dict(bc=NS(Bitboard=Board,vision=vision),dist=Point.chebyshev_distance,
             favorable_fight=lambda *args:True,report=lambda *args:None)
    exec(compile(ast.Module(body=[method],type_ignores=[]),str(SOURCE),'exec'),env)
    bot=NS(check_budget=lambda:None,enemies=lambda:[enemy],allies=lambda:[me,ally],
           home_field=NS(get=lambda p:3),enemy_field=NS(get=lambda p:9),terrain=Board(walls),crates=[],centers=[],corners=False,home_center=Point(6),enemy_center=Point(12),
           help_request=False,alert=None,claim=lambda _:None,combat=lambda *args,**kw:None,move=lambda *args:None)
    return lambda defend=False:env['engage'](bot,me,defend)

class SupportTests(unittest.TestCase):
    def setUp(self): Board.searches=0;Board.last_blocked=set()
    def test_distant_ally_is_not_support(self):
        self.assertFalse(fixture(Champion(11))());self.assertEqual(Board.searches,0)
    def test_channeling_allies_are_not_support_even_in_range(self):
        for channel in ('recall','bank','teleport'):
            with self.subTest(channel=channel): self.assertFalse(fixture(Champion(5,channel=channel))())
        self.assertEqual(Board.searches,0)
    def test_in_range_ally_needs_no_path_search(self):
        self.assertTrue(fixture(Champion(5,moves=0))());self.assertEqual(Board.searches,0)
    def test_ally_can_reach_an_attack_tile(self):
        self.assertTrue(fixture(Champion(4))());self.assertEqual(Board.searches,1)
        self.assertIn(Point(3),Board.last_blocked);self.assertNotIn(Point(4),Board.last_blocked)
    def test_wall_separates_apparently_nearby_ally(self):
        self.assertFalse(fixture(Champion(4),walls=[Point(5,y) for y in range(7)])())
    def test_zero_movement_outside_range(self):
        self.assertFalse(fixture(Champion(4,moves=0))());self.assertEqual(Board.searches,0)
    def test_empty_champion_keeps_existing_policy(self):
        self.assertTrue(fixture(Champion(11,channel='recall'),gems=0)());self.assertEqual(Board.searches,0)
    def test_bank_defence_keeps_existing_policy(self):
        self.assertTrue(fixture(Champion(11,channel='recall'))(True));self.assertEqual(Board.searches,0)
    def test_injured_ally_does_not_count(self): self.assertFalse(fixture(Champion(5,hp=64))())

if __name__=='__main__': unittest.main()
