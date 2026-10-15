"""Economy-first draft. All choices are among the published champions."""
import cambc as bc
from cambc import game_map as gm


def play():
    chosen = bc.draft.current_draft(bc.Team.ALLY)
    groups = gm.camp_groups()
    clustered = sum(len(g) > 1 for g in groups)
    D = bc.ChampionDraft
    # Splash for grouped camps; sustained damage and remote shopping otherwise.
    order = ([D.VARG, D.VENDETTA, D.TAVI, D.VESPER_VALE, D.RYTH]
             if clustered else
             [D.VENDETTA, D.TAVI, D.VESPER_VALE, D.VARG, D.RYTH])
    bc.draft_memory.submit(b"FARM1" + bytes(order))
    bc.draft.pick(next(p for p in order if p not in chosen))
