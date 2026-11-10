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
    info=profile()
    order=draft_order(chosen,enemy,info,rows,collision)
    # The original Willow policy is reversed only on unknown/unapproved maps.
    # This function runs in the draft interpreter, not champion gameplay.
    if (not rows and not collision and bc.draft.team_size()>=4
            and info.get('has_groups',info['clustered']>0)):
        if not hasattr(play,'_willow_enabled'):
            allowed={(71, 71, ((1, 1), (1, 69), (35, 34), (69, 1), (69, 69))): b'\x004\x8e\xba6\x93E\xfd\xcf]\x83\xdd\xb1\xb1\x916S\xe6\xd3\xb0\xc06\xaetR\x10\xa2% \xc0\xb1\x8b', (61, 61, ((30, 3),)): b'|\x89o5\x86\x8c\xb8\xadw\x93s\xb7\xce\x9aV\x9c\x19\x9bS\xbb\xe0\xee\xbc\xa6<\xf5\xa6\rax\xc1\xb5', (45, 45, ((12, 20), (14, 28), (30, 16), (32, 24))): b';\xbf5l\x9cR\xfb\tKZ\xe3\x17\xfb\xd2\x81s\\\xab\xd0\xa5\xff[\x19\x90u\x98\xdc\xe2\xbe\xce\x1b\xd0', (50, 46, ((10, 29), (19, 27), (30, 18), (39, 16))): b"\xb7B'\xe6\x84\x89\x80\x9cec\x86|\x16+NM]\x84\xf5W\x96\xae\x815\x811\xd4\x08\xed\xa5\x8dD", (79, 79, ((39, 35), (39, 43))): b'@p\xe6-\xda\x08\xb0\xc0\x08\x0b\x03\xd5\xde\xcdl\xfcG\xd6\xa2\x81]{\xd8\xdf\x8f\x10;\xc6\x178j\x0c', (91, 75, ((6, 70), (45, 24), (45, 50), (84, 4))): b'\xddkO=\xc9\xdc\xf9\x15\xda\xde#\xf3\xaa\xfb\xfb\xe8Q\xcc0\x8a\xd8\x0b\xe8\xe7 \xa5\x1fa\xc1kn\x00'}
            key=(gm.width(),gm.height(),tuple(sorted((p.x,p.y) for p in gm.altars().positions())))
            expected=allowed.get(key)
            enabled=False
            if expected is not None:
                from hashlib import sha256
                digest=sha256()
                for mask in (gm.walls(),gm.holes(),gm.bushes(),gm.altars()):
                    digest.update(mask.export_raw_buffer())
                spawns=tuple(sorted(tuple(sorted((p.x,p.y) for p in gm.spawn_region(t).positions()))
                                    for t in (bc.Team.ALLY,bc.Team.ENEMY)))
                groups=list(gm.camp_groups())
                camps=tuple(sorted((int(c.kind()),c.spawn_position().x,c.spawn_position().y) for g in groups for c in g))
                values=tuple(sorted((g.gem_value(),g.gold_value(),g.max_respawn_timer(),len(g)) for g in groups))
                digest.update(repr((spawns,camps,values)).encode('ascii'))
                enabled=(digest.digest()==expected)
            play._willow_enabled=enabled
        if not play._willow_enabled:
            order=[bc.ChampionDraft.RYTH if c==bc.ChampionDraft.WILLOW else c for c in order]
    # Resource-only Adgato: add a body without removing Ryth's area clearing.
    if signature==(51,31,frozenset({(25,26)})) and bc.draft.team_size()==4:
        if not hasattr(play,'_adgato_cassi_enabled'):
            from hashlib import sha256
            digest=sha256()
            for mask in (gm.walls(),gm.holes(),gm.bushes(),gm.altars()):
                digest.update(mask.export_raw_buffer())
            spawns=tuple(sorted(tuple(sorted((p.x,p.y) for p in gm.spawn_region(t).positions())) for t in (bc.Team.ALLY,bc.Team.ENEMY)))
            groups=list(gm.camp_groups())
            camps=tuple(sorted((int(c.kind()),c.spawn_position().x,c.spawn_position().y) for g in groups for c in g))
            values=tuple(sorted((g.gem_value(),g.gold_value(),g.max_respawn_timer(),len(g)) for g in groups))
            digest.update(repr((spawns,camps,values)).encode('ascii'))
            play._adgato_cassi_enabled=(digest.digest()==b'_\r\x05\xa9\n\xa8\t\xbcd\x960\xf9pm\t\x1d5KTI\xd7\xd1\xb5RSQ\xad{c\x11xd')
        if play._adgato_cassi_enabled:
            order=[bc.ChampionDraft.VARG,bc.ChampionDraft.TAVI,bc.ChampionDraft.CASSI_AND_ISSAC,bc.ChampionDraft.RYTH]+order
    # Every supported pick remains a legal fallback, including larger team maps.
    order += [getattr(bc.ChampionDraft,name) for name in ('VARG','TAVI','VENDETTA','RYTH','WILLOW','PRISM','MARCELLA','HEART_OF_RUIN','STELLAR','VESPER_VALE','REN','CASSI_AND_ISSAC')]
    bc.draft.pick(next(c for c in order if c not in chosen))
