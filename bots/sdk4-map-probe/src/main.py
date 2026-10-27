import cambc as bc
from cambc import game_map as gm
import json

def main():
    printed=False
    while True:
        if bc.is_draft():
            if not printed:
                groups=list(gm.camp_groups())
                print('CATALOGUE '+json.dumps(dict(width=gm.width(),height=gm.height(),team_size=bc.draft.team_size(),altars=[(p.x,p.y) for p in gm.altars().positions()],groups=[dict(gems=g.gem_value(),gold=g.gold_value(),size=len(g),hp=sum(c.base_stats().base_health for c in g),attack_range=max(c.attack_range() for c in g),incoming=sum(c.base_stats().base_strength for c in g),golem=any(c.is_golem() for c in g),boss=any(c.is_monolith() for c in g)) for g in groups])),flush=True)
                for kind in [bc.ChampionType.HEART_OF_RUIN,bc.ChampionType.VARG,bc.ChampionType.PRISM,bc.ChampionType.STELLAR]:
                    c=bc.Champion.design(kind)
                    print('DESIGN',kind,c.base_stats(),[a.info() for a in c.abilities()],flush=True)
                printed=True
            chosen=bc.draft.current_draft(bc.Team.ALLY)
            order=[bc.ChampionDraft.HEART_OF_RUIN,bc.ChampionDraft.TAVI,bc.ChampionDraft.WILLOW,bc.ChampionDraft.PRISM,bc.ChampionDraft.MARCELLA]
            bc.draft.pick(next(c for c in order if c not in chosen))
        bc.end_turn()

main()
