"""Paired metrics for SDK5 tests; both teams are measured in the same games."""
import collections
import json
import pathlib
import re
import sys
import zipfile

reference = pathlib.Path(__file__).resolve().parents[1] / 'match-review-1026'
if reference.is_dir():
    sys.path.insert(0, str(reference))
from review_results import read, summarize


def team_row(path, side):
    data = json.loads(path.read_text(encoding='utf8'))
    name = ('teamA', 'teamB')[side]
    champs = [c for c in data['champions'] if c['team'] == name]
    events = [e for e in data['events'] if e.get('owner', {}).get('team') == name]
    def entries(kind):
        return [v for e in events if e['kind'] == kind for v in e['entries']]
    with zipfile.ZipFile(path.with_suffix('.repl26a')) as z:
        stdout = z.read('team-' + 'ab'[side] + '.stdout')
    errors = collections.Counter(x.decode('utf8', 'replace') for x in re.findall(rb'bot error:[^\n\x00]+', stdout))
    return dict(win=data['match']['outcome'] == name,
                target_win=data['match']['outcome'] == name and int(data['teams'][side]['submittedGems']) >= 1000,
                submitted=sum(int(c['metrics']['submittedGems']) for c in champs),
                collected=sum(int(c['metrics']['collectedGems']) for c in champs),
                deaths=sum(int(c['metrics']['deaths']) for c in champs),
                camp_deaths=sum(e['context'] == 'camp' for e in entries('death')),
                pvp_deaths=sum(e['context'] == 'champion' for e in entries('death')),
                lost=sum(int(e['value']) for e in entries('gemLoss')),
                hard_fuel=len(entries('fuelExhausted')),
                faults=data['diagnostics']['botFaults'][name], errors=dict(errors))


def paired(directory):
    rows = []
    for path in sorted(directory.glob('*.json')):
        if not re.search(r'-[01]$', path.stem):
            continue
        side = int(path.stem[-1])
        rows.append(dict(map=path.stem[:-2], side='AB'[side],
                         candidate=team_row(path, side), opponent=team_row(path, 1-side)))
    totals = {}
    for team in ('candidate', 'opponent'):
        totals[team] = {k: sum(r[team][k] for r in rows) for k in rows[0][team] if k != 'errors'}
        totals[team]['errors'] = dict(sum((collections.Counter(r[team]['errors']) for r in rows), collections.Counter()))
    return dict(matches=len(rows), totals=totals, results=rows)


if __name__ == '__main__':
    directory = pathlib.Path(sys.argv[1])
    output = pathlib.Path(sys.argv[2])
    rows = read(directory)
    report = dict(summary=summarize(rows), results=rows, paired=paired(directory))
    output.write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(dict(summary=report['summary'], paired=report['paired']['totals']), indent=2))
