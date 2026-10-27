const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../webui/app.js'),'utf8');
const start=source.indexOf('async function requestUploadRetry('),end=source.indexOf('function renderActivity(',start);
assert(start>=0&&end>start);
function setup(confirm=true){
 const calls=[],opened=[];
 const context={state:{active:null},api:async(endpoint,data)=>{calls.push([endpoint,data]);return data.confirmed?{id:'new',state:'started'}:{id:'old',state:'confirmation_required',message:'Check the site first'};},
 window:{confirm:()=>confirm},toast(){},page(){},openJob(id){opened.push(id);},
 element(tag,classes,label){return {label,disabled:false,addEventListener(event,handler){this[event]=handler;}}}};
 vm.createContext(context);vm.runInContext(source.slice(start,end),context);
 return {context,calls,opened};
}
(async()=>{
 let x=setup(false);
 assert.equal(await x.context.requestUploadRetry('/api/uploads/retry','old'),null);
 assert.equal(x.calls.length,1);
 x=setup(true);await x.context.requestUploadRetry('/api/uploads/retry','old');
 assert.equal(x.calls.length,2);assert.equal(x.calls[1][1].confirmed,true);
 x=setup();
 assert.equal(x.context.uploadRetryButton({status:'completed'}),null);
 x.context.state.active='active';assert.equal(x.context.uploadRetryButton({status:'running'}),null);
 x.context.state.active=null;assert.equal(x.context.uploadRetryButton({status:'running'}).label,'Check & retry');
 let button=x.context.uploadRetryButton({id:'old',status:'needs_review',retry_id:'new'});
 await button.click({stopPropagation(){}});assert.equal(x.calls.length,0);assert.deepEqual(x.opened,['new']);
 assert.equal(button.disabled,false);
 assert.equal(x.context.uploadRetryButton({status:'needs_review',site_status:'accepted'}).label,'Retry delivery');
 console.log('PASS upload retry UI: confirmation, active-worker guard, existing retry navigation and delivery label.');
})().catch(error=>{console.error(error);process.exitCode=1;});
