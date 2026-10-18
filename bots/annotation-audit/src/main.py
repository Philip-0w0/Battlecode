import cambc as bc
from cambc import game_map as gm
import json

def points(mask):
    return [[p.x, p.y] for p in mask.positions()]

printed = False
while True:
    if bc.is_draft():
        if not printed:
            data = dict(width=gm.width(), height=gm.height(), walls=points(gm.walls()),
                        holes=points(gm.holes()), altars=points(gm.altars()),
                        ally=points(gm.spawn_region(bc.Team.ALLY)),
                        enemy=points(gm.spawn_region(bc.Team.ENEMY)), groups=[])
            for group in gm.camp_groups():
                data['groups'].append(dict(tiles=points(group.spawn_tiles()), gems=group.gem_value(),
                    gold=group.gold_value(), camps=[dict(kind=int(c.kind()),
                    pos=[c.spawn_position().x,c.spawn_position().y],
                    strength=c.base_stats().base_strength, health=c.base_stats().base_health,
                    range=c.attack_range()) for c in group]))
            print('MAP_AUDIT='+json.dumps(data), flush=True)
            printed = True
        chosen = bc.draft.current_draft(bc.Team.ALLY)
        bc.draft.pick(next(c for c in [bc.ChampionDraft.VARG,bc.ChampionDraft.TAVI,
                     bc.ChampionDraft.RYTH,bc.ChampionDraft.VENDETTA,bc.ChampionDraft.VESPER_VALE] if c not in chosen))
    bc.end_turn()
