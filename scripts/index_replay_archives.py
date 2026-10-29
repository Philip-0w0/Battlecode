"""Index ZIP replay inventories and extract only one team's named matches."""
import argparse
import collections
import hashlib
import json
import pathlib
import re
import zipfile

NAME = re.compile(r'(ranked|unranked|tournament)_([0-9a-f-]{36})_([0-9a-f-]{36})_vs_([0-9a-f-]{36})\.repl26a')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archives', nargs='+', type=pathlib.Path)
    p.add_argument('--team-id', required=True)
    p.add_argument('--output', type=pathlib.Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    replay_dir = args.output/'own-replays'
    replay_dir.mkdir(exist_ok=True)
    seen, selected, inventories = {}, [], []
    total = 0
    for archive in args.archives:
        counts = collections.Counter()
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                match = NAME.fullmatch(item.filename)
                if not match:
                    continue
                total += 1
                counts[match[1]] += 1
                identity = (item.file_size, item.CRC)
                if item.filename in seen:
                    if seen[item.filename] != identity:
                        raise ValueError('Conflicting duplicate replay: ' + item.filename)
                    continue
                seen[item.filename] = identity
                if args.team_id not in (match[3], match[4]):
                    continue
                data = z.read(item)  # ZIP verifies the selected entry's CRC.
                digest = hashlib.sha256(data).hexdigest()
                target = replay_dir/item.filename
                if target.exists():
                    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                        raise ValueError('Existing extracted replay differs: ' + str(target))
                else:
                    target.write_bytes(data)
                selected.append(dict(archive=archive.name, entry=item.filename,
                                     match=match[2], own_side='teamA' if match[3] == args.team_id else 'teamB',
                                     size=len(data), crc=item.CRC, sha256=digest))
        inventories.append(dict(archive=archive.name, size=archive.stat().st_size,
                                replay_entries=sum(counts.values()), kinds=dict(counts)))
    result = dict(archives=inventories, replay_entries=total, unique_replays=len(seen),
                  own_team=args.team_id, selected_count=len(selected), selected=selected,
                  scope='All named entries indexed; only the selected team replays extracted and CRC/SHA256 checked.')
    (args.output/'corpus-manifest.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('archives','selected')},indent=2))


if __name__ == '__main__':
    main()
