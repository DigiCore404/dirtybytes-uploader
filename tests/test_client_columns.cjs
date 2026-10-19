'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../webui/client-controls.js'),'utf8').split('const torrentColumnStorageKey=')[1];
function node(tag='div'){
 return {tag,dataset:{},style:{},attrs:{},children:[],events:{},captures:new Set(),append(...items){this.children.push(...items);},prepend(item){this.children.unshift(item);},setAttribute(key,value){this.attrs[key]=value;},addEventListener(key,fn){this.events[key]=fn;},removeEventListener(key,fn){if(this.events[key]===fn)delete this.events[key];},setPointerCapture(id){this.captures.add(id);},hasPointerCapture(id){return this.captures.has(id);},releasePointerCapture(id){this.captures.delete(id);},fire(key,extra={}){const event={button:0,pointerId:1,clientX:0,preventDefault(){this.prevented=true;},stopPropagation(){this.stopped=true;},...extra};this.events[key]?.(event);return event;}};
}
function harness(storage=new Map(),throws=false){
 const reset=node(),body={classList:{values:new Set(),add(key){this.values.add(key);},remove(key){this.values.delete(key);}}};
 const context={document:{createElement:tag=>node(tag),body},localStorage:{getItem:key=>{if(throws)throw Error('disabled');return storage.get(key);},setItem:(key,value)=>{if(throws)throw Error('disabled');storage.set(key,value);}},$:id=>id==='reset-torrent-columns'?reset:{querySelector:()=>null}};
 vm.createContext(context);vm.runInContext('const torrentColumnStorageKey='+code,context);
 function table(keys=['name','client','size']){const table=node('table');table.headers=keys.map(key=>{const h=node('th');h.dataset.columnKey=key;h.textContent=key;return h;});table.querySelectorAll=()=>table.headers;context.installTorrentColumns(table);return table;}
 return {table,context,reset,body,storage};
}
const store=new Map(),h=harness(store),table=h.table(),handle=table.headers[0].children[0];
assert.equal(table.children[0].tag,'colgroup');assert.equal(table.style.width,'100%');
handle.fire('pointerdown',{clientX:100});handle.fire('pointermove',{clientX:220});assert.equal(handle.attrs['aria-valuenow'],'410');handle.fire('pointerup');assert(!h.body.classList.values.size);
assert.equal(JSON.parse(store.values().next().value).name,410);
const reloaded=harness(store),sorted=reloaded.table(['size','name','client']);assert.equal(sorted.headers[1].children[0].attrs['aria-valuenow'],'410');
const keyboard=sorted.headers[1].children[0];keyboard.fire('keydown',{key:'ArrowLeft'});assert.equal(keyboard.attrs['aria-valuenow'],'400');keyboard.fire('keydown',{key:'ArrowRight',shiftKey:true});assert.equal(keyboard.attrs['aria-valuenow'],'410');
keyboard.fire('keydown',{key:'Home'});assert.equal(keyboard.attrs['aria-valuenow'],'320');
keyboard.fire('pointerdown',{clientX:0});keyboard.fire('pointermove',{clientX:-9999});keyboard.fire('pointercancel');assert.equal(keyboard.attrs['aria-valuenow'],'120');
keyboard.fire('dblclick');assert.equal(keyboard.attrs['aria-valuenow'],'320');const click=keyboard.fire('click');assert(click.prevented&&click.stopped);
keyboard.fire('pointerdown');keyboard.fire('pointermove',{clientX:80});reloaded.table();assert(!reloaded.body.classList.values.size);assert.equal(JSON.parse(store.values().next().value).name,400);
reloaded.reset.fire('click');assert.equal(JSON.parse(store.values().next().value).name,320);
const invalid=harness(new Map([['uploader.client-column-widths.v1',JSON.stringify({name:1,client:'999',size:99999})]])).table();assert.equal(invalid.style.width,'100%');
const disabled=harness(new Map(),true).table();disabled.headers[0].children[0].fire('keydown',{key:'ArrowRight'});assert.equal(disabled.headers[0].children[0].attrs['aria-valuenow'],'330');
for(const available of [1000,1920,3000]){const widths=h.context.fitTorrentColumns(['name','client','size'],{name:320,client:150,size:100},available);assert(Math.abs(widths.reduce((a,b)=>a+b,0)-available)<.001);assert(widths[0]>=120&&widths[1]>=60);}
console.log('PASS: resizing, limits, pointer cancellation, keyboard controls, reset, persistence, sorting, redraw and unavailable storage.');
