/* Round-boundary observations from the exact official engine 3 visualiser.
 * Omniscient replay states are analysis data, never inputs to a competition bot.
 */
const fs=require('node:fs'), path=require('node:path');
const {WASI}=require('node:wasi');
const {pathToFileURL}=require('node:url');
async function main(){
 const root=__dirname, asset=process.env.CAMBC_VISUALISER_ASSETS;
 const [inputDir, selectionFile, outputDir]=process.argv.slice(2);
 if(!inputDir||!selectionFile||!outputDir)throw Error('Usage: node trace_replays_v3.cjs INPUT_DIR SELECTION_JSON OUTPUT_DIR');
 fs.mkdirSync(outputDir,{recursive:true});
 if(!asset)throw Error('Set CAMBC_VISUALISER_ASSETS to SDK5 visualiser/assets.');
 const parser=await import(pathToFileURL(path.join(asset,'PanelChrome-DRtW3oWL.js')).href);
 const module=await WebAssembly.compile(fs.readFileSync(path.join(asset,'v3_0_0-DBS2ESWO.wasm')));
 const selected=JSON.parse(fs.readFileSync(selectionFile));
 for(const item of selected){
  const bytes=fs.readFileSync(path.join(inputDir,item.filename));
  if(bytes.readUInt32LE(8)!==3)throw Error('Only engine 3.0.0');
  const wasi=new WASI({version:'preview1',args:[],env:{}});
  const instance=await WebAssembly.instantiate(module,{wasi_snapshot_preview1:wasi.wasiImport,deep_wasm:{on_assert_fail_impl:()=>1}});
  const x=instance.exports; wasi.initialize(instance);
  const v=()=>new DataView(x.memory.buffer);
  const cstring=p=>{const b=new Uint8Array(x.memory.buffer);let e=p;while(b[e])e++;return new TextDecoder().decode(b.subarray(p,e));};
  const check=e=>{if(e)throw Error(`${e}: ${cstring(x.GetLastErrorMsg())}`);};
  const input=x.Engine_Malloc(bytes.length),out=x.Engine_Malloc(8192);
  new Uint8Array(x.memory.buffer,input,bytes.length).set(bytes);
  check(x.Game_FromReplayFileBytes(input,bytes.length,out));const game=v().getBigUint64(out,true);
  check(x.Game_GetBitboardMetadata(game,out));
  const width=v().getInt32(out,true),height=v().getInt32(out+4,true),stride=v().getUint32(out+16,true);
  const terrain={width,height};
  for(const name of ['Wall','Hole','Altar','Bush']){
   check(x[`Game_Get${name}Buffer`](game,out));const ptr=v().getUint32(out,true),points=[];
   for(let y=0;y<height;y++)for(let xx=0;xx<width;xx++){
    const offset=(y>>3)*stride+(xx>>3),bit=((y&7)<<3)+(xx&7);
    if(v().getBigUint64(ptr+offset*8,true)&(1n<<BigInt(bit)))points.push([xx,y]);
   }
   terrain[name.toLowerCase()]=points;
  }
  check(x.Game_GetTeamASpawnArea(game,out));
  terrain.teamASpawn=[0,4,8,12].map(o=>v().getInt32(out+o,true));
  check(x.Game_Visualiser_Timeline_GetMain(game,out));const timeline=v().getBigUint64(out,true);
  check(x.Game_Visualiser_Timeline_Info(game,timeline,out,out+8,out+16));const size=v().getUint32(out,true);
  const ptr=x.Engine_Malloc(x.Game_Visualiser_TimelineSnapshotSize());
  const read=()=>{check(x.Game_Visualiser_ReadTimelineState(game,ptr));return parser.I(v(),ptr);};
  const rounds=[],deaths=[],losses=[],changes=[];let prev=null,lastRound=-1;
  check(x.Game_Visualiser_Timeline_Seek(game,timeline,0,0));
  for(let i=0;i<=size;i++){
   if(i)check(x.Game_Visualiser_Timeline_ReplayNext(game,0));
   const s=read();
   if(s.round!==lastRound){
    if(prev)rounds.push(prev);
    lastRound=s.round;
   }
   if(prev){
    for(const c of s.champions){
     const old=prev.champions.find(o=>o.entity.index===c.entity.index);
     if(!old)continue;
     if(old.alive&&!c.alive)deaths.push({round:s.round,input:i,champion:c.entity.index,team:c.team,type:c.type,oldPosition:old.position,oldHealth:old.health,oldGems:old.gems,lastStep:s.step,others:prev.champions.map(o=>({id:o.entity.index,team:o.team,position:o.position,alive:o.alive,health:o.health}))});
     if(c.gems<old.gems)losses.push({round:s.round,input:i,champion:c.entity.index,team:c.team,type:c.type,oldGems:old.gems,newGems:c.gems,oldPosition:old.position,alive:c.alive,submitted:s.submittedGems.map(Number),oldSubmitted:prev.submittedGems.map(Number)});
    }
   }
   prev={round:s.round,input:i,submittedGems:s.submittedGems.map(Number),step:s.step,champions:s.champions,camps:s.camps,groups:s.groups};
  }
  if(prev)rounds.push(prev);
  const result={...item,scope:'Last snapshot at each observed round boundary; death/loss transitions observed per input, not every combat substep.',inputs:size,terrain,rounds,deaths,losses};
  fs.writeFileSync(path.join(outputDir,`trace-${item.map}.json`),JSON.stringify(result));
  x.Game_Destroy(game);
  console.log(item.map,rounds.length,deaths.length,losses.length);
 }
}
main().catch(e=>{console.error(e.stack);process.exit(1)});
