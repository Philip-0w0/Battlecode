"""Regression checks for installed AoE planning and bounded live observations."""
import ast
import collections
import pathlib
import os
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
REPOSITORY_SOURCE = ROOT.parent/'bots/my-bot/src'
SOURCE = pathlib.Path(os.environ.get('BATTLECODE_TEST_SOURCE',
    str(REPOSITORY_SOURCE if REPOSITORY_SOURCE.is_dir() else pathlib.Path('C:/battlecode/bots/my-bot/src'))))


class Point:
    def __init__(self, x, y): self.x, self.y = x, y
    def chebyshev_distance(self, other):
        return max(abs(self.x-other.x), abs(self.y-other.y))
    def __eq__(self, other): return isinstance(other, Point) and (self.x,self.y)==(other.x,other.y)
    def __repr__(self): return f'Point({self.x},{self.y})'


class Unit:
    def __init__(self, identity, point, health=100, visible=True):
        self.identity, self.point, self.hp, self.visible = identity, point, health, visible
        self.calls = collections.Counter()
    def __int__(self): return self.identity
    def is_visible(self): self.calls['visible']+=1; return self.visible
    def health(self): self.calls['health']+=1; return self.hp
    def position(self): self.calls['position']+=1; return self.point


class Camp(Unit): pass


class Champion(Unit):
    def champion_name(self): return 1
    def is_submitting_gems(self): return False


class Ability:
    def __init__(self, range_=4, radius=1, modifier=1.5):
        self.details = types.SimpleNamespace(range=range_,radius=radius,modifier=modifier,exclusive_with_movement=False)
        self.used = []
    def is_ready(self): return True
    def info(self): return self.details
    def is_attack_reset(self): return False
    def is_shield(self): return False
    def is_heal(self): return False
    def is_damage(self): return False
    def is_cc(self): return False
    def is_aoe_damage(self): return True
    def can_target_camps(self): return True
    def can_target_enemies(self): return True
    def use(self, target): self.used.append(target); return True


class Me:
    def __init__(self, abilities=None): self.spells = abilities or [Ability()]; self.focus_queries=0
    def can_cast(self): return True
    def abilities(self): return self.spells
    def position(self): return Point(0,0)
    def focus(self): self.focus_queries+=1; return 100


class YieldTurn(Exception): pass


class Controller:
    def __init__(self, stop_after=None): self.checks=0; self.stop_after=stop_after
    def check_budget(self):
        self.checks+=1
        if self.stop_after is not None and self.checks>=self.stop_after: raise YieldTurn()


def load(path):
    tree=ast.parse(path.read_text(encoding='utf8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Bot')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='cast')
    context={'bc':types.SimpleNamespace(Camp=Camp,Champion=Champion,Vec2=Point,Error=RuntimeError),
             'C':types.SimpleNamespace(MARCELLA=99),'dist':lambda a,b:a.chebyshev_distance(b)}
    exec(compile(ast.Module(body=[method],type_ignores=[]),str(path),'exec'),context)
    return context['cast']


CAST=load(SOURCE/'economy_bot.py')


def evaluate(method, specifications, abilities=None, stop_after=None):
    units=[kind(i,Point(x,y),hp,visible) for i,(kind,x,y,hp,visible) in enumerate(specifications)]
    me=Me(abilities)
    controller=Controller(stop_after)
    result=method(controller,me,units)
    return result,me,units,controller


class AoePlanning(unittest.TestCase):
    def test_dense_camps_choose_best_centre_with_linear_live_reads(self):
        specs=[(Camp,x,y,100,True) for x in range(-3,4) for y in range(-3,4)]
        result,me,units,_=evaluate(CAST,specs)
        self.assertTrue(result)
        self.assertEqual(me.spells[0].used,[Point(-2,-2)])
        # Forty-nine equal camps have many overlapping candidate blast areas.
        # SDK observations should scale with targets, not target pairs.
        for property_name in ['visible','health','position']:
            self.assertLessEqual(sum(u.calls[property_name] for u in units),3*len(units))
        self.assertLessEqual(me.focus_queries,len(units))

    def test_champion_weight_and_fresh_state_on_next_cast(self):
        specs=[(Camp,1,0,100,True),(Camp,2,0,100,True),
               (Champion,-2,0,220,True),(Camp,4,4,10,True)]
        _,me,units,controller=evaluate(CAST,specs)
        self.assertEqual(me.spells[0].used,[Point(-2,0)])
        # Reuse the same unit handles on the next planning call. The moved,
        # healthier champion must be observed again rather than from old cache.
        units[2].point,units[2].hp=Point(4,4),1000
        self.assertTrue(CAST(controller,me,units))
        self.assertEqual(me.spells[0].used,[Point(-2,0),Point(4,4)])

    def test_invisible_dead_and_out_of_range_targets_do_not_set_centre(self):
        specs=[(Camp,1,0,100,True),(Camp,-1,0,2000,False),
               (Camp,-2,0,0,True),(Champion,7,0,2000,True)]
        result,me,units,_=evaluate(CAST,specs)
        self.assertTrue(result)
        self.assertEqual(me.spells[0].used,[Point(1,0)])
        self.assertEqual(units[1].calls['position'],0)
        self.assertEqual(units[2].calls['position'],0)

    def test_empty_target_list_does_not_cast(self):
        result,me,_,_=evaluate(CAST,[])
        self.assertFalse(result)
        self.assertEqual(me.spells[0].used,[])

    def test_each_ability_uses_its_own_radius_and_damage_modifier(self):
        specs=[(Camp,x,0,20+x*30,True) for x in range(1,5)]
        abilities=[Ability(modifier=.2),Ability(radius=2,modifier=2)]
        result,me,_,_=evaluate(CAST,specs,abilities)
        self.assertTrue(result)
        self.assertEqual([a.used for a in me.spells],[[],[Point(2,0)]])

    def test_budget_boundary_aborts_before_ability_use(self):
        units=[Camp(x,Point(x,0)) for x in range(-3,4)]
        me=Me()
        with self.assertRaises(YieldTurn):
            CAST(Controller(stop_after=5),me,units)
        self.assertEqual(me.spells[0].used,[])


if __name__=='__main__': unittest.main()
