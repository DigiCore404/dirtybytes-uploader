'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const app=fs.readFileSync(path.join(__dirname,'../webui/app.js'),'utf8'),library=fs.readFileSync(path.join(__dirname,'../webui/library.js'),'utf8');
function node(){return{hidden:false,disabled:false,value:'',textContent:'',dataset:{},children:[],events:{},classList:{toggle(){}},addEventListener(event,callback){this.events[event]=callback;},click(){return this.events.click?.();},close(){this.closed=true;},replaceChildren(...items){this.children=items;},append(...items){this.children.push(...items);}};}
function environment(){
 const nodes=new Map(),requests=[];const $=id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);};
 const dialogBack=node();dialogBack.dataset.backDialog='example-dialog';
 const context=vm.createContext({$,document:{body:{classList:{toggle(){}}},querySelectorAll:selector=>selector==='[data-back-dialog]'?[dialogBack]:[],createElement:node},
   currentStep:1,selectedJob:null,closeJobDetails(){context.selectedJob=null;},refreshActivity:async()=>{},loadSecurity:async()=>{},loadDeliveryClients:async()=>{},loadLibrary:async()=>{},refreshImports:async()=>{},refreshClients:async()=>{},toast(){},
   api:url=>new Promise((resolve,reject)=>requests.push({url,resolve,reject})),element:node,Option:function(text,value){this.text=text;this.value=value;},state:{categories:[]},prettySize:String});
 return{context,$,requests,dialogBack,run:code=>vm.runInContext(code,context)};
}
const listing=(path,parent=null)=>({path,parent,root:'/content',saved_folders:[],folders:[],files:[]});
(async()=>{
 const pages=environment();const {context,$,run}=pages;
 vm.runInContext(app.slice(app.indexOf("let workspacePage='upload'"),app.indexOf('function updateState(')),context);
 run('refreshBackNavigation()');assert.equal($('workspace-back').disabled,true);
 run("page('settings');page('guide');backWorkspace()");assert.equal(run('workspacePage'),'settings');assert.equal(run('pageTrail.length'),1);
 run('backWorkspace()');assert.equal(run('workspacePage'),'upload');assert.equal($('workspace-back').disabled,true);
 run('step(3);backWorkspace()');assert.equal(context.currentStep,2);run('backWorkspace()');assert.equal(context.currentStep,1);
 let detailsClosed=false;$('back-activity').events.click=()=>{detailsClosed=true;context.selectedJob=null;};run("page('activity')");context.selectedJob='job';run('backWorkspace()');assert.equal(detailsClosed,true);assert.equal(run('workspacePage'),'activity');
 context.libraryCanGoBack=()=>true;let folderBack=0;context.backLibrary=()=>folderBack++;run("page('library');backWorkspace()");assert.equal(folderBack,1);assert.equal(run('workspacePage'),'library');
 pages.dialogBack.click();assert.equal($('example-dialog').closed,true);
 const folders=environment();folders.context.refreshBackNavigation=()=>{};
 vm.runInContext(library.slice(0,library.indexOf('async function uploadFromLibrary(')),folders.context);
 const load=async(target,data)=>{const promise=folders.run(`loadLibrary(${JSON.stringify(target)})`);folders.requests.shift().resolve(data);await promise;};
 await load('/content',listing('/content'));assert.equal(folders.$('library-back').disabled,true);
 await load('/content/one',listing('/content/one','/content'));
 await load('/content/two',listing('/content/two','/content'));
 let pending=folders.run('backLibrary()');assert.match(folders.requests[0].url,/one$/);folders.requests.shift().resolve(listing('/content/one','/content'));await pending;
 assert.equal(folders.run('libraryPath'),'/content/one','Back must return to the previous visited folder, not always Parent');
 const depth=folders.run('libraryBackPaths.length');await load('/content/one',listing('/content/one','/content'));assert.equal(folders.run('libraryBackPaths.length'),depth,'Refresh must not add another Back entry');
 pending=folders.run("loadLibrary('/content/denied')");folders.requests.shift().reject(new Error('Unavailable'));await pending;assert.equal(folders.run('libraryPath'),'/content/one');assert.equal(folders.run('libraryBackPaths.length'),depth);
 const old=folders.run("loadLibrary('/content/old')"),oldResponse=folders.requests.shift();const recent=folders.run("loadLibrary('/content/new')"),newResponse=folders.requests.shift();newResponse.resolve(listing('/content/new','/content'));await recent;oldResponse.resolve(listing('/content/old','/content'));await old;assert.equal(folders.run('libraryPath'),'/content/new','A late folder response must not change navigation');
 const picker=environment();vm.runInContext('let folder=null,folderBackPaths=[],folderRequest=0;'+app.slice(app.indexOf('async function openFolder('),app.indexOf("for(const id of ['choose-folder'")),picker.context);
 const pick=async(target,data)=>{const pending=picker.run(`openFolder(${JSON.stringify(target)})`);picker.requests.shift().resolve(data);await pending;};
 await pick('/content',listing('/content'));await pick('/content/first',listing('/content/first','/content'));await pick('/content/second',listing('/content/second','/content'));
 pending=picker.run("openFolder(folderBackPaths[folderBackPaths.length-1],true)");picker.requests.shift().resolve(listing('/content/first','/content'));await pending;assert.equal(picker.run('folder.path'),'/content/first');assert.equal(picker.run('folderBackPaths.length'),1);
 const html=fs.readFileSync(path.join(__dirname,'../webui/index.html'),'utf8');
 for(const id of ['workspace-back','library-back','folder-back'])assert(html.includes('id="'+id+'"'));
 for(const id of ['folder-dialog','metadata-dialog','client-dialog','library-add-dialog','library-metadata-dialog','metadata-image-dialog','update-dialog'])assert(html.includes('data-back-dialog="'+id+'"'));
 console.log('Back navigation: pages, upload steps, activity, previous folders, refresh, failed requests, late responses and dialog returns passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
