const fs=require('node:fs'),path=require('node:path');
const {WASI}=require('node:wasi'),{pathToFileURL}=require('node:url');
async function main(){
 const [inputDir,selectionFile,outputDir]=process.argv.slice(2);
 if(!inputDir||!selectionFile||!outputDir)throw Error('Usage: node trace_deaths_v3.cjs INPUT_DIR SELECTION_JSON OUTPUT_DIR');
 fs.mkdirSync(outputDir,{recursive:true});
 const a=process.env.CAMBC_VISUALISER_ASSETS;
 const parser=await import(pathToFileURL(path.join(a,'PanelChrome-DRtW3oWL.js')).href);
 const module=await WebAssembly.compile(fs.readFileSync(path.join(a,'v3_0_0-DBS2ESWO.wasm')));
 const selected=JSON.parse(fs.readFileSync(selectionFile)).filter(x=>x.map!=='03homonoliths');
 for(const item of selected){
  const b=fs.readFileSync(path.join(inputDir,item.filename));
  const wasi=new WASI({version:'preview1',args:[],env:{}}),instance=await WebAssembly.instantiate(module,{wasi_snapshot_preview1:wasi.wasiImport,deep_wasm:{on_assert_fail_impl:()=>1}}),x=instance.exports;wasi.initialize(instance);
  const v=()=>new DataView(x.memory.buffer),check=e=>{if(e)throw Error('Engine error '+e)};
  const ip=x.Engine_Malloc(b.length),out=x.Engine_Malloc(8192);new Uint8Array(x.memory.buffer,ip,b.length).set(b);
  check(x.Game_FromReplayFileBytes(ip,b.length,out));const g=v().getBigUint64(out,true);
  check(x.Game_Visualiser_Timeline_GetMain(g,out));const timeline=v().getBigUint64(out,true);
  check(x.Game_Visualiser_Timeline_Seek(g,timeline,0,0));
  const ptr=x.Engine_Malloc(x.Game_Visualiser_TimelineSnapshotSize());
  let prev=[],substeps=0,damage=[],deaths=[];
  while(true){
   check(x.Game_Visualiser_ReadTimelineState(g,ptr));
   const d=v(),schema=d.getUint32(ptr+4,true),stride=schema===42840?420:252,count=d.getUint32(ptr+172,true),cs=[];
   for(let i=0;i<count;i++){
    const o=ptr+196+i*stride;
    const c={id:d.getUint32(o+4,true),team:d.getUint32(o+8,true),type:d.getUint32(o+12,true),position:{x:d.getInt32(o+16,true),y:d.getInt32(o+20,true)},health:d.getFloat32(o+24,true),alive:!!d.getUint32(o+32,true),gems:d.getUint32(o+40,true)};
    const old=prev.find(x=>x.id===c.id);
    if(old?.alive&&!c.alive){
     const s=parser.I(d,ptr),actor=s.step.actor;
     let source=actor.kind===4?s.spells.find(x=>x.entity.index===actor.index)?.owner:actor;
     const sourceChampion=source?.kind===1?cs.concat(prev).find(x=>x.id===source.index):null;
     deaths.push({round:s.round,input:s.inputPosition,substep:s.step.substep,champion:c.id,team:c.team,type:c.type,oldPosition:old.position,oldHealth:old.health,oldGems:old.gems,step:s.step,actor,source:source??null,sourceTeam:sourceChampion?.team??null});
    }
    cs.push(c);
   }
   prev=cs;
   if(d.getUint32(ptr+28,true)!==0)break;
   check(x.Game_Visualiser_Timeline_ReplayNext(g,1));
   if(++substeps>2000000)throw Error('Unexpected number of substeps');
  }
  fs.writeFileSync(path.join(outputDir,'deaths-'+item.map+'.json'),JSON.stringify({...item,substeps,deaths},null,2));
  console.log(item.map,substeps,deaths.length);x.Game_Destroy(g);
 }
}
main().catch(e=>{console.error(e.stack);process.exit(1)});
