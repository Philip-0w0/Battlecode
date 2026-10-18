"""Run both sides of every local map; inspect replay stdout as well as crashes."""
import argparse
import collections
import csv
import json
import pathlib
import re
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bot', default='my-bot')
    parser.add_argument('--opponent', default='starter-python')
    parser.add_argument('--label', default='benchmark')
    parser.add_argument('--maps', nargs='*')
    parser.add_argument('--map-dir', type=pathlib.Path)
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    output = root / 'replays' / args.label
    output.mkdir(parents=True, exist_ok=True)
    maps = sorted((args.map_dir or (root / 'maps')).glob('*.map26a'))
    rows = []
    for game_map in maps:
        if args.maps and game_map.stem not in args.maps:
            continue
        for side in (0, 1):
            players = [args.bot, args.opponent] if side == 0 else [args.opponent, args.bot]
            prefix = output / f'{game_map.stem}-{side}'
            command = [str(root / 'tools' / 'cambc.exe'), 'run', *players,
                       '--map', str(game_map), '--statistics', str(prefix.with_suffix('.json')),
                       '--out-dir', str(output)]
            result = subprocess.run(command, cwd=root, capture_output=True, text=True)
            prefix.with_suffix('.log').write_text(result.stdout + result.stderr, encoding='utf8')
            if result.returncode:
                raise RuntimeError(f'Match failed; see {prefix}.log')
            stats = json.loads(prefix.with_suffix('.json').read_text())
            replay_match = re.search(r'replay bundle: (.+)', result.stdout + result.stderr)
            if not replay_match:
                raise RuntimeError('Missing replay bundle')
            replay = pathlib.Path(replay_match.group(1).strip())
            with zipfile.ZipFile(replay) as bundle:
                stdout = bundle.read(f'team-{"a" if side == 0 else "b"}.stdout')
            errors = collections.Counter(x.decode('utf8', 'replace') for x in re.findall(rb'bot error: [^\n\x00]+', stdout))
            allies = [c for c in stats['champions'] if c['team'] == side]
            row = dict(map=game_map.stem, side='AB'[side],
                       win=stats['outcome'] == ('teamA' if side == 0 else 'teamB'),
                       rounds=stats['round'], gems=stats['teams'][side]['submittedGems'],
                       opponent_gems=stats['teams'][1-side]['submittedGems'],
                       deaths=sum(c['deaths'] for c in allies),
                       gold=sum(c['earnedGold'] for c in allies),
                       faults=stats['botFaults'][side], errors=sum(errors.values()), guarded_resets=stdout.count(b'guarded reset:'), budget_yields=stdout.count(b'budget yield'))
            rows.append(row)
            prefix.with_suffix('.errors.json').write_text(json.dumps(errors, indent=2), encoding='utf8')
            with (output / 'results.csv').open('w', newline='', encoding='utf8') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(row))
                writer.writeheader()
                writer.writerows(rows)
            print(row, flush=True)
    print(f"Wins: {sum(r['win'] for r in rows)}/{len(rows)}; errors: {sum(r['errors'] for r in rows)}", flush=True)


if __name__ == '__main__':
    main()
