"""Map roles derive from reward and camp data, not downloaded filenames."""
import cambc as bc
from cambc import game_map as gm

_cached = None

def classify(groups):
    gold = sum(g['gold'] for g in groups)
    gems = sum(g['gems'] for g in groups)
    gem_groups = [g for g in groups if g['gems'] > 0]
    return dict(gold=gold, gems=gems, zero_gold=gold==0,
                boss_only=bool(gem_groups) and all(g['boss'] for g in gem_groups),
                clustered=sum(g['size']>=3 and g['incoming']>0 for g in groups), has_groups=any(g['size']>1 for g in groups),
                golems=any(g['golem'] for g in groups))

def profile():
    global _cached
    if _cached is None:
        groups=[dict(gold=g.gold_value(), gems=g.gem_value(), size=len(g),
                     incoming=sum(c.base_stats().base_strength for c in g),
                     boss=any(c.is_monolith() for c in g),
                     golem=any(c.is_golem() for c in g)) for g in gm.camp_groups()]
        _cached=classify(groups)
    return _cached

def draft_order(chosen, enemy, info, rows=False, collision=False):
    D=bc.ChampionDraft
    if rows: return [D.VARG,D.TAVI,D.VENDETTA,D.RYTH,D.WILLOW,D.HEART_OF_RUIN]
    if collision: return [D.VARG,D.WILLOW,D.CASSI_AND_ISSAC,D.TAVI,D.MARCELLA,D.HEART_OF_RUIN]
    if info.get('has_groups',info['clustered']>0):
        order=[D.VARG,D.TAVI,D.VENDETTA,D.RYTH,D.VESPER_VALE,D.HEART_OF_RUIN]
    else:
        order=[D.VENDETTA,D.TAVI,D.VESPER_VALE,D.RYTH,D.VARG,D.HEART_OF_RUIN]
    # A sustained healer replaces one grouped-map farmer. Three-pick and
    # separate Collision/Rows policies keep their original rosters.
    if bc.draft.team_size() >= 4 and info.get('has_groups',info['clustered']>0):
        order = [D.WILLOW if c == D.RYTH else c for c in order]
    control=sum(e in (D.TAVI,D.PRISM,D.REN,D.RYTH,D.CASSI_AND_ISSAC,D.HEART_OF_RUIN) for e in enemy)
    if len(chosen)>=2 and control>=2: order=[D.MARCELLA]+order
    return order
