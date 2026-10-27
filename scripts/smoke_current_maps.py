"""Bounded release-mode compatibility checks for every refreshed platform map."""
import argparse,concurrent.futures,json,pathlib,re,subprocess,zipfile
root=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--bot',default='my-bot');p.add_argument('--rounds',type=int,default=30);p.add_argument('--jobs',type=int,default=1);p.add_argument('--label',default='current-map-smoke');p.add_argument('--maps',nargs='*');a=p.parse_args()
out=root/'replays'/a.label;out.mkdir(parents=True,exist_ok=True)
def run(path):
 folder=out/path.stem;folder.mkdir(exist_ok=True)
 try:
  r=subprocess.run([str(root/'tools/cambc.exe'),'run',a.bot,'sdk4-map-probe','--map',str(path),'--rounds',str(a.rounds),'--release','--out-dir',str(folder)],cwd=root,capture_output=True,text=True,timeout=240)
 except subprocess.TimeoutExpired:
  return dict(map=path.stem,returncode=-1,errors=['timeout'],profile=None)
 (folder/'run.log').write_text(r.stdout+r.stderr,encoding='utf8')
 match=re.search(r'replay bundle: (.+)',r.stdout+r.stderr,re.I)
 files=[pathlib.Path(match.group(1).strip())] if match else []
 if not files: return dict(map=path.stem,returncode=r.returncode,errors=[r.stderr[-400:]],profile=None)
 with zipfile.ZipFile(files[-1]) as z:
  own=z.read('team-a.stdout').decode('utf8','replace').replace('\0','')
  other=z.read('team-b.stdout').decode('utf8','replace').replace('\0','')
 line=next((l[10:] for l in other.splitlines() if l.startswith('CATALOGUE ')),None)
 return dict(map=path.stem,returncode=r.returncode,errors=[l for l in own.splitlines() if 'bot error:' in l],profile=json.loads(line) if line else None)
manifest=root/'.cambc/map-pool.json'
allowed={m['file'] for m in json.loads(manifest.read_text())['maps']} if manifest.exists() else None
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
 for row in pool.map(run,[p for p in sorted((root/'maps').glob('*.map26a')) if (not a.maps and (allowed is None or p.name in allowed)) or (a.maps and p.stem in a.maps)]):
  rows.append(row);(out/'results.json').write_text(json.dumps(rows,indent=2))
  if row['errors']: print('FAIL',row['map'],row['errors'],flush=True)
  if len(rows)%10==0: print('Checked',len(rows),'maps',flush=True)
print('Complete',len(rows),'failed',sum(bool(r['errors']) or r['returncode'] for r in rows),flush=True)
