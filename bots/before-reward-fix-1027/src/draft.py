"""Reward-aware drafts, including Heart of Ruin and the complete current roster."""
import cambc as bc
from cambc import game_map as gm
from map_profile import profile, draft_order

def play():
    chosen=bc.draft.current_draft(bc.Team.ALLY)
    enemy=bc.draft.current_draft(bc.Team.ENEMY)
    signature=(gm.width(),gm.height(),frozenset((p.x,p.y) for p in gm.altars().positions()))
    rows=signature==(50,50,frozenset({(15,16),(34,33)}))
    collision=signature==(41,41,frozenset({(27,20),(39,20)}))
    order=draft_order(chosen,enemy,profile(),rows,collision)
    # Every supported pick remains a legal fallback, including larger team maps.
    order += [getattr(bc.ChampionDraft,name) for name in ('VARG','TAVI','VENDETTA','RYTH','WILLOW','PRISM','MARCELLA','HEART_OF_RUIN','STELLAR','VESPER_VALE','REN','CASSI_AND_ISSAC')]
    bc.draft.pick(next(c for c in order if c not in chosen))
