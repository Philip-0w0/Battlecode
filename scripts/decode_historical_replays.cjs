/* Replay metadata through the official v1.0.3 visualiser WASM and snapshot parser.
 * It does not recover opponent source or invent CAMSTAT-only event attribution.
 */
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {WASI}=require('node:wasi');
const {pathToFileURL}=require('node:url');
const ASSET=process.env.CAMBC_VISUALISER_ASSETS;
if(!ASSET)throw Error('Set CAMBC_VISUALISER_ASSETS to the official SDK 4 visualiser assets directory.');
const NAMES=['Ryth','Vesper Vale','Vendetta','Cassi','Issac','Stellar','Prism','Marcella','Willow','Ren','Varg','Tavi','Heart of Ruin'];
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
async function decoder(){
 const parser=await import(pathToFileURL(path.join(ASSET,'PanelChrome-DXwmYkIC.js')).href);
 const module=await WebAssembly.compile(fs.readFileSync(path.join(ASSET,'v1_0_3-DRqNt1t2.wasm')));
 return async function decode(filename,mapCatalog){
  const bytes=fs.readFileSync(filename);
  if(bytes.readUInt32LE(8)!==196609)throw Error('Only engine 1.0.3 ABI is supported by this decoder');
  const wasi=new WASI({version:'preview1',args:[],env:{}});
  const instance=await WebAssembly.instantiate(module,{wasi_snapshot_preview1:wasi.wasiImport,deep_wasm:{on_assert_fail_impl:()=>1}});
  const x=instance.exports;wasi.initialize(instance);
  const v=()=>new DataView(x.memory.buffer);
  const cstring=p=>{const b=new Uint8Array(x.memory.buffer);let end=p;while(b[end])end++;return new TextDecoder().decode(b.subarray(p,end));};
  const check=e=>{if(e)throw Error(`Engine ${e}: ${cstring(x.GetLastErrorMsg())}`);};
  const input=x.Engine_Malloc(bytes.length),out=x.Engine_Malloc(8192);
  new Uint8Array(x.memory.buffer,input,bytes.length).set(bytes);
  check(x.Game_FromReplayFileBytes(input,bytes.length,out));const game=v().getBigUint64(out,true);
  check(x.Game_GetBitboardMetadata(game,out));const width=v().getInt32(out,true),height=v().getInt32(out+4,true);
  check(x.Game_Visualiser_Timeline_GetMain(game,out));const timeline=v().getBigUint64(out,true);
  check(x.Game_Visualiser_Timeline_Info(game,timeline,out,out+8,out+16));const size=v().getUint32(out,true);
  check(x.Game_Visualiser_Timeline_Seek(game,timeline,size,0));
  const snapshot=x.Engine_Malloc(x.Game_Visualiser_SnapshotSize()),perspective=x.Engine_Malloc(8);
  v().setUint32(perspective,2,true);v().setUint32(perspective+4,0xffffffff,true);
  check(x.Game_Visualiser_ReadState(game,perspective,snapshot));const header=parser.P(v(),snapshot),state=parser.N(v(),snapshot,header);
  check(x.Game_Statistics_GetSummary(game,out));const championCount=v().getUint32(out+12,true);
  if(championCount!==state.champions.length)throw Error('Statistics/snapshot roster mismatch');
  const champions=[];
  const u32=offset=>v().getUint32(out+offset,true);
  const u64=offset=>{const n=v().getBigUint64(out+offset,true);if(n>BigInt(Number.MAX_SAFE_INTEGER))throw Error('Unsafe counter');return Number(n);};
  for(let index=0;index<championCount;index++){
   check(x.Game_Statistics_GetChampion(game,index,out));
   const id=u32(0),team=u32(4),type=u32(8);
   const live=state.champions.find(c=>c.entity.index===id);
   const metrics={kills:u32(12),deaths:u32(16),assists:u32(20),earnedGold:u64(24),collectedGems:u64(32),submittedGems:u64(40),spentGold:u64(48),gold:u32(56),gems:u32(60)};
   metrics.lostGems=metrics.collectedGems-metrics.submittedGems-metrics.gems;
   if(metrics.lostGems<0)throw Error('Gem conservation failed');
   champions.push({id,team:team===0?'teamA':'teamB',type,name:NAMES[type]??`Unknown ${type}`,metrics,
     final:{alive:live.alive,position:live.position??null,health:live.health,maxHealth:live.maxHealth,items:live.items,consumables:live.consumables}});
  }
  for(let team=0;team<2;team++){
   const actual=champions.filter(c=>c.team===['teamA','teamB'][team]).reduce((sum,c)=>sum+c.metrics.submittedGems,0);
   if(BigInt(actual)!==header.submittedGems[team])throw Error('Team deposit conservation failed');
  }
  const map=mapCatalog.find(m=>bytes.indexOf(m.bytes)>=0);
  const result={filename:path.basename(filename),sha256:hash(bytes),engineVersion:'1.0.3',map:map?{name:map.name,sha256:map.sha256,width,height}:{name:null,sha256:null,width,height},
   finalRound:header.round,finalRoundNote:'Visualiser current round; may include a partially completed final round.',
   outcome:{1:'teamA',2:'teamB'}[header.outcome]??null,outcomeCode:header.outcome,timelineInputs:size,
   teams:header.submittedGems.map((n,index)=>({team:['teamA','teamB'][index],submittedGems:Number(n)})),
   drafts:header.drafts.map((picks,index)=>({team:['teamA','teamB'][index],picks:picks.slice(0,header.draftCounts[index])})),champions,
   unavailable:['camp-versus-champion death attribution','fuel-exhaustion events','per-champion damage totals','per-round position history']};
  x.Game_Destroy(game);return result;
 };
}
async function main(){
 const [input,output,mapDirectory]=process.argv.slice(2);if(!input||!output)throw Error('Usage: node decode_replays.cjs INPUT_DIR OUTPUT_JSON [MAP_DIR]');
 const maps=mapDirectory?fs.readdirSync(mapDirectory).filter(n=>n.endsWith('.map26a')).map(n=>{const bytes=fs.readFileSync(path.join(mapDirectory,n));return{name:n.slice(0,-7),bytes,sha256:hash(bytes)};}):[];
 const decode=await decoder(),files=fs.readdirSync(input).filter(n=>n.endsWith('.repl26a')).sort(),results=[],failures=[];
 for(const name of files){try{results.push(await decode(path.join(input,name),maps));}catch(error){failures.push({filename:name,error:String(error)});}if((results.length+failures.length)%10===0)console.error(`Decoded ${results.length}; failures ${failures.length}`);}
 fs.writeFileSync(output,JSON.stringify({implementation:'Official visualiser v1.0.3 WASM + official snapshot parser; counters ABI validated against two official CAMSTAT summaries.',results,failures},null,2));
 console.log(JSON.stringify({replays:files.length,decoded:results.length,failures:failures.length}));
}
module.exports={decoder};if(require.main===module)main().catch(e=>{console.error(e.stack);process.exit(1)});
