"""Analyze official decoded CAMSTAT JSON without inferring unavailable bot source.

Decode .camstat files with cambc 4.0.0 summary FILE -o ranked_MATCH_A_vs_B.json,
then pass their directory and your team UUID to this script. JSON filenames must
retain their original ranked_MATCH_UUID_TEAM_A_UUID_vs_TEAM_B_UUID stem.
"""
import argparse
import collections
import json
import statistics
from pathlib import Path

def number(x): return float(x)
def summarize(d,name):
 result=[]
 for side in ('teamA','teamB'):
  champs=[c for c in d['champions'] if c['team']==side]
  events=[e for e in d['events'] if isinstance(e.get('owner'),dict) and e['owner'].get('team')==side]
  deaths=[x for e in events if e['kind']=='death' for x in e['entries']]
  deposits=[x for e in events if e['kind']=='gemSubmission' for x in e['entries'] if number(x['value'])>0]
  gains=[x for e in events if e['kind']=='gemCollection' for x in e['entries'] if number(x['value'])>0]
  sums={k:sum(number(c['metrics'].get(k,0)) for c in champs) for k in ('earnedGold','spentGold','collectedGems','submittedGems','gems','deaths','kills','championDamageDone','monsterDamageDone')}
  loss=sum(number(x['value']) for e in events if e['kind']=='gemLoss' for x in e['entries'])
  assert loss==sums['collectedGems']-sums['submittedGems']-sums['gems'],(name,side,loss,sums)
  result.append(dict(match=name.split('_')[1],team_id=name.split('_')[2 if side=='teamA' else 4].split('.')[0],side=side,
    width=d['match']['width'],height=d['match']['height'],map_hash=d['match']['mapHash'],engine=d['match']['engineVersion'],rounds=d['match']['roundsCompleted'],win=d['match']['outcome']==side,
    metrics=sums,lost_gems=loss,camp_deaths=sum(x['context']=='camp' for x in deaths),pvp_deaths=sum(x['context']=='champion' for x in deaths),
    fuel_exhaustions=sum(len(e['entries']) for e in events if e['kind']=='fuelExhausted'),
    first_gem=min((x['timestamp']['round'] for x in gains),default=None),first_deposit=min((x['timestamp']['round'] for x in deposits),default=None),
    deposit_sizes=[int(x['value']) for x in deposits],champions=champs))
 return result


def rollup(rows):
    result=dict(team_observations=len(rows),wins=sum(r['win'] for r in rows))
    for key in ('earnedGold','spentGold','collectedGems','submittedGems','gems','deaths','kills'):
        result[key]=sum(r['metrics'][key] for r in rows)
    for key in ('lost_gems','camp_deaths','pvp_deaths','fuel_exhaustions'):
        result[key]=sum(r[key] for r in rows)
    acquired=result['collectedGems']
    result['deposited_fraction']=result['submittedGems']/acquired if acquired else None
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('decoded_directory',type=Path)
    parser.add_argument('--team-id',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    rows=[]
    files=sorted(args.decoded_directory.glob('ranked_*.json'))
    for path in files:
        data=json.loads(path.read_text(encoding='utf8'))
        if not data['diagnostics']['detailedCaptureComplete']:
            raise ValueError('Incomplete event capture: '+path.name)
        pair=summarize(data,path.name)
        for row in pair:
            assert row['metrics']['deaths']==row['camp_deaths']+row['pvp_deaths'],path.name
            assert sum(row['deposit_sizes'])==row['metrics']['submittedGems'],path.name
        rows.extend(pair)
    own=[r for r in rows if r['team_id']==args.team_id]
    other=[r for r in rows if r['team_id']!=args.team_id]
    output=dict(match_count=len(files),unique_teams=len({r['team_id'] for r in rows}),
                own=rollup(own),other_winners=rollup([r for r in other if r['win']]),
                other_losers=rollup([r for r in other if not r['win']]),results=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in output.items() if k!='results'},indent=2))


if __name__=='__main__': main()
