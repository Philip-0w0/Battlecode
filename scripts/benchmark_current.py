"""SDK 4 release-mode benchmark with actual summary event metrics."""
import argparse,collections,csv,json,pathlib,re,subprocess,zipfile

def run_match(root,bot,opponent,map_path,side,out):
    players=[bot,opponent] if side==0 else [opponent,bot]
    prefix=out/f'{map_path.stem}-{side}'
    result=subprocess.run([str(root/'tools/cambc.exe'),'run',*players,'--map',str(map_path),'--release','--statistics',str(prefix.with_suffix('.json')),'--json','--out-dir',str(out)],cwd=root,capture_output=True,text=True)
    prefix.with_suffix('.log').write_text(result.stdout+result.stderr,encoding='utf8')
    if result.returncode: raise RuntimeError('Failed match: '+str(prefix))
    data=json.loads(prefix.with_suffix('.json').read_text(encoding='utf8'))
    key='teamA' if side==0 else 'teamB'
    champs=[c['metrics'] for c in data['champions'] if c['team']==key]
    events=[e for e in data['events'] if isinstance(e.get('owner'),dict) and e['owner'].get('team')==key]
    def entries(kind): return [v for e in events if e['kind']==kind for v in e['entries']]
    replay=re.search(r'replay bundle: (.+)',result.stdout+result.stderr,re.I)
    if not replay: raise RuntimeError('Missing replay bundle')
    with zipfile.ZipFile(replay.group(1).strip()) as z: log=z.read(f'team-{"a" if side==0 else "b"}.stdout')
    def total(k): return sum(float(c[k]) for c in champs)
    return dict(map=map_path.stem,side='AB'[side],win=data['match']['outcome']==key,rounds=data['match']['roundsCompleted'],engine=data['match']['engineVersion'],gems=total('submittedGems'),opponent_gems=float(next(t['submittedGems'] for t in data['teams'] if t['team']!=key)),collected=total('collectedGems'),lost=sum(int(v['value']) for v in entries('gemLoss')),deaths=total('deaths'),camp_deaths=sum(v['context']=='camp' for v in entries('death')),pvp_deaths=sum(v['context']=='champion' for v in entries('death')),hard_fuel=len(entries('fuelExhausted')),faults=data['diagnostics']['botFaults'][key],errors=log.count(b'bot error:'),first_gem=min((v['timestamp']['round'] for v in entries('gemCollection') if int(v['value'])>0),default=None),first_deposit=min((v['timestamp']['round'] for v in entries('gemSubmission') if int(v['value'])>0),default=None),picks=';'.join(d['champion'] for d in data['roster']['draft'] if d['team']==key))

def main(default_opponent="before-sdk4-1027"):
    p=argparse.ArgumentParser();p.add_argument('--bot',default='my-bot');p.add_argument('--opponent',default=default_opponent);p.add_argument('--maps',nargs='*');p.add_argument('--map-dir',type=pathlib.Path);p.add_argument('--label',default='benchmark');a=p.parse_args()
    root=pathlib.Path(__file__).resolve().parents[1];out=root/'replays'/a.label;out.mkdir(parents=True,exist_ok=True);rows=[]
    directory=a.map_dir or root/'maps'
    names=a.maps
    if not names:
        manifest=root/'.cambc/map-pool.json'
        if manifest.exists() and a.map_dir is None:
            names=[pathlib.Path(m['file']).stem for m in json.loads(manifest.read_text())['maps']]
        else: names=[m.stem for m in sorted(directory.glob('*.map26a'))]
    for name in names:
        path=directory/(pathlib.Path(name).stem+'.map26a')
        for side in (0,1):
            row=run_match(root,a.bot,a.opponent,path,side,out);rows.append(row)
            with (out/'results.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerows(rows)
            print(row,flush=True)
    print('Wins',sum(r['win'] for r in rows),'/',len(rows),flush=True)
if __name__=='__main__': main()
