"""Index SDK 4 batch summaries and replay logs for either starting side."""
import argparse
import collections
import json
import pathlib
import re
import zipfile


def read(directory):
    rows = []
    for path in sorted(pathlib.Path(directory).glob('*.json')):
        if not re.search(r'-[01]$', path.stem):
            continue
        data = json.loads(path.read_text(encoding='utf8'))
        side = int(path.stem[-1])
        team = ('teamA', 'teamB')[side]
        champions = [c for c in data['champions'] if c['team'] == team]
        events = [e for e in data['events'] if e.get('owner', {}).get('team') == team]
        def entries(kind):
            return [v for e in events if e['kind'] == kind for v in e['entries']]
        def total(metric):
            return sum(float(c['metrics'][metric]) for c in champions)
        with zipfile.ZipFile(path.with_suffix('.repl26a')) as archive:
            log = archive.read('team-' + 'ab'[side] + '.stdout')
        errors = collections.Counter(x.decode('utf8', 'replace') for x in re.findall(rb'bot error:[^\n\x00]+', log))
        rows.append(dict(map=path.stem[:-2], side='AB'[side],
                         win=data['match']['outcome'] == team,
                         rounds=data['match']['roundsCompleted'], gems=total('submittedGems'),
                         opponent_gems=float(data['teams'][1-side]['submittedGems']),
                         collected=total('collectedGems'), deaths=total('deaths'),
                         camp_deaths=sum(e['context'] == 'camp' for e in entries('death')),
                         pvp_deaths=sum(e['context'] == 'champion' for e in entries('death')),
                         lost=sum(int(e['value']) for e in entries('gemLoss')),
                         hard_fuel=len(entries('fuelExhausted')),
                         faults=data['diagnostics']['botFaults'][team], errors=dict(errors),
                         yields=log.count(b'budget yield'),
                         first_gem=min((e['timestamp']['round'] for e in entries('gemCollection') if int(e['value']) > 0), default=None),
                         first_deposit=min((e['timestamp']['round'] for e in entries('gemSubmission') if int(e['value']) > 0), default=None)))
    return rows


def summarize(rows):
    return dict(matches=len(rows), wins=sum(r['win'] for r in rows),
                target_wins=sum(r['win'] and r['gems'] >= 1000 for r in rows),
                errors=sum(sum(r['errors'].values()) for r in rows),
                faults=sum(r['faults'] for r in rows), hard_fuel=sum(r['hard_fuel'] for r in rows),
                deaths=sum(r['deaths'] for r in rows), lost=sum(r['lost'] for r in rows))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=pathlib.Path)
    parser.add_argument('--output', type=pathlib.Path)
    args = parser.parse_args()
    rows = read(args.directory)
    result = dict(summary=summarize(rows), results=rows)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result['summary'], indent=2))
