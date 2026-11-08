const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../webui/requests.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../webui/index.html'),'utf8');
assert(html.indexOf('src="/app.js')<html.indexOf('src="/requests.js'),'Requests depend on the main UI helpers');
const nodes=new Map(),calls=[],nav=[];
function node(tag='div'){return {tag,children:[],value:'',textContent:'',disabled:false,hidden:false,dataset:{},options:[],append(...x){this.children.push(...x);},replaceChildren(...x){this.children=[...x];},addEventListener(event,fn){this[event]=fn;},setAttribute(){},set innerHTML(value){throw Error('Request data must not be inserted as HTML');}};}
const $=id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);};
$('category').options=[{value:'25'}];
const row={id:17,title:'<img onerror=evil()>',category:25,reward:500,votes:2,added:'2026-11-08',description:'Requested format',url:'https://tracker.example/requests/17'};
const context={$,source:'/media/Release',review:{},state:{categories:[{id:25,name:'Example'}]},URLSearchParams,
 document:{createElement:node,querySelectorAll:()=>[]},toast(){},page(x){nav.push(x);},step(x){nav.push(x);},
 api:async url=>{calls.push(url);return url.startsWith('/api/requests?')?{requests:[row],total:1}:row;}};
vm.createContext(context);vm.runInContext(source,context);
const app=fs.readFileSync(path.join(__dirname,'../webui/app.js'),'utf8');
vm.runInContext(app.slice(app.indexOf('function jobInput()'),app.indexOf('function reviewRow(')),context);
(async()=>{
 await context.loadTrackerRequests(true);
 assert.equal($('requests-rows').children.length,1);assert.equal($('requests-rows').children[0].children[0].textContent,'#17 · '+row.title);
 assert.equal($('requests-next').disabled,true);assert.equal($('requests-previous').disabled,true);
 await context.chooseTrackerRequest(17);assert.equal($('request-id').value,17);assert.equal($('request-requirements').textContent,'Requested format');assert.equal($('category').value,'25');assert.deepEqual(nav,['upload',2]);assert.equal(context.jobInput().request_id,17);
 assert(calls.every(x=>x.startsWith('/api/requests')),'Selection never publishes an upload or fills a request');
 context.setTrackerRequest(null);assert.equal($('request-id').value,'');assert.equal($('request-requirements').hidden,true);assert.equal(context.jobInput().request_id,0);
 console.log('PASS request list, escaped content, explicit selection, requirements and pagination.');
})().catch(error=>{console.error(error);process.exitCode=1;});
