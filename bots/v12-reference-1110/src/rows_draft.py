"""Map-aware drafting using revealed picks only."""
import cambc as bc
from cambc import game_map as gm

def play():
    D=bc.ChampionDraft
    chosen=bc.draft.current_draft(bc.Team.ALLY)
    enemy=bc.draft.current_draft(bc.Team.ENEMY)
    collision=gm.width()==41 and gm.height()==41 and {(p.x,p.y) for p in gm.altars().positions()}=={(27,20),(39,20)}
    clustered=any(len(g)>1 for g in gm.camp_groups())
    if collision:
        order=[D.VARG,D.WILLOW,D.CASSI_AND_ISSAC,D.TAVI,D.MARCELLA]
    else:
        order=([D.VARG,D.TAVI,D.VENDETTA,D.VESPER_VALE,D.RYTH] if clustered else [D.VENDETTA,D.TAVI,D.VESPER_VALE,D.RYTH,D.VARG])
        control=sum(e in (D.TAVI,D.PRISM,D.REN,D.RYTH,D.CASSI_AND_ISSAC) for e in enemy)
        if len(chosen)>=2 and control>=2: order=[D.MARCELLA]+order
    bc.draft.pick(next(c for c in order if c not in chosen))
