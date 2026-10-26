const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../webui/app.js'),'utf8');
const start=source.indexOf("apply.addEventListener('click',async()=>{");
const end=source.indexOf(' });footer.append(cancel,apply);',start);
assert(start>=0&&end>start,'Metadata apply handler must exist');
const handler=source.slice(start,end+4);

async function scenario(fail=false,stale=false){
 let callback;
 const controls=new Map();
 const get=id=>{if(!controls.has(id))controls.set(id,{value:'unchanged',close(){this.closed=true;}});return controls.get(id);};
 const calls=[];
 const context={
  apply:{addEventListener:(event,cb)=>callback=cb},cancel:{},metadataTarget:'upload',
  images:[{url:'https://thumb.theporndb.net/signed/scene%2Fposter',check:{checked:true}},
          {url:'https://source.example/back',check:{checked:true}},
          {url:'https://source.example/ignored',check:{checked:false}}],
  version:1,metadataPreviewVersion:1,fields:new Proxy({},{get:(_,key)=>({value:'chosen '+key})}),
  usePostTitle:{checked:true},$:get,review:{},livePreview(){},toast(){}
 };
 context.api=async(route,body)=>{
  assert.equal(route,'/api/images/rehost');calls.push(body.url);
  if(stale)context.metadataPreviewVersion++;
  if(fail&&calls.length===2)throw new Error('Host rejected upload');
  return {url:'https://images.example/cover-'+calls.length+'.jpg'};
 };
 vm.runInNewContext(handler,context);
 await callback();
 if(fail||stale){
  assert.equal(get('images').value,'unchanged');
  assert.equal(get('description').value,'unchanged');
  assert.equal(get('post-title').value,'unchanged');
 }else{
  assert.equal(get('images').value,'https://images.example/cover-1.jpg\nhttps://images.example/cover-2.jpg');
  assert.equal(get('post-title').value,'chosen title');
  assert.deepEqual(calls,context.images.slice(0,2).map(i=>i.url));
  assert(!get('images').value.includes('thumb.theporndb.net'));
  assert(get('metadata-dialog').closed);
 }
 assert.equal(context.apply.disabled,false);
}
(async()=>{
 await scenario();await scenario(true);await scenario(false,true);
 console.log('PASS metadata image rehosting: direct host URLs, failure preserves fields, stale modal does not apply.');
})().catch(error=>{console.error(error);process.exitCode=1;});
