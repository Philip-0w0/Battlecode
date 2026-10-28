"""Test both sides of the recorded published map pool in SDK 4 release mode."""
import argparse
import csv
import hashlib
import json
import pathlib
import subprocess
from review_results import read, summarize


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bot', default='my-bot')
    p.add_argument('--opponent', default='pre-strategy-v2')
    p.add_argument('--label', default='pool-benchmark')
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--maps', nargs='+')
    p.add_argument('--pool-manifest', type=pathlib.Path)
    args = p.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    pool = args.pool_manifest or root/'benchmarks/published-pool-2026-10-28.json'
    manifest = json.loads(pool.read_text())
    maps = {pathlib.Path(m['file']).stem: m for m in manifest['maps']}
    selected = args.maps or sorted(maps)
    if set(selected) - set(maps):
        p.error('Unknown map names: ' + ', '.join(sorted(set(selected)-set(maps))))
    if not 1 <= args.jobs <= 8:
        p.error('--jobs must be between 1 and 8')
    for bot in [args.bot, args.opponent]:
        if not (root/'bots'/bot/'src').is_dir():
            p.error('Missing bot source: ' + bot)
    output = root/'replays'/args.label
    if output.resolve().parent != (root/'replays').resolve():
        p.error('--label must be a single folder name')
    if output.exists():
        p.error('Choose a fresh --label so previous evidence is preserved')
    output.mkdir(parents=True)
    lines = []
    for name in selected:
        entry = maps[name]
        path = root/'maps'/entry['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            p.error('Map differs from the recorded pool: ' + name)
        for side in [0, 1]:
            a, b = (args.bot,args.opponent) if side == 0 else (args.opponent,args.bot)
            # The CLI resolves relative paths against the manifest's folder.
            prefix = (output/f'{name}-{side}').as_posix()
            tokens = [(root/'bots'/a).as_posix(),(root/'bots'/b).as_posix(),path.as_posix(),prefix+'.repl26a',
                      '--statistics',prefix+'.json','--json']
            if any(any(c.isspace() for c in token) for token in tokens):
                p.error('Bot names and label must not contain whitespace')
            lines.append(' '.join(tokens))
    batch = output/'manifest.txt'
    batch.write_text('\n'.join(lines),encoding='utf8')
    with (output/'run.log').open('w',encoding='utf8') as log:
        result = subprocess.run([str(root/'tools/cambc.exe'),'run-batch',str(batch),
                                 '--jobs',str(args.jobs),'--release'],cwd=root,stdout=log,stderr=subprocess.STDOUT)
    rows = read(output)
    expected = {(name,side) for name in selected for side in 'AB'}
    if result.returncode or len(rows) != len(expected) or {(r['map'],r['side']) for r in rows} != expected:
        raise RuntimeError('Incomplete benchmark; inspect ' + str(output/'run.log'))
    report = dict(summary=summarize(rows),results=rows)
    (output/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    with (output/'results.csv').open('w',newline='',encoding='utf8') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(report['summary'],indent=2))


if __name__ == '__main__':
    main()
