const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const context={window:{},URL};vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../webui/catalogue.js'),'utf8'),context);
const {sameRelease,combine}=context.window.CatalogMetadata;
const jeedoo={source:'catalogue',site:'Jeedoo',title:'Example Movie 10',url:'https://www.jeedoo.com/example',metadata:{studio:'Example Studio',release_year:'2024',content_tags:'Classic, Drama'},description:'Jeedoo description',images:['https://example.com/cover.jpg']};
const ade={source:'catalogue',site:'ADE',title:'Example Movie Vol. 10',url:'https://www.adultdvdempire.com/example',metadata:{studio:'Example Studio',release_year:'2024',performers:'Actor A, Actor B',content_tags:'Drama, Romance'},description:'ADE description',images:['https://example.com/cover.jpg','https://example.com/back.jpg']};
assert(sameRelease(jeedoo,ade));
assert(!sameRelease(jeedoo,{...ade,title:'Example Movie 11'}));
assert(!sameRelease(jeedoo,{...ade,title:'Other Movie 10'}));
assert(!sameRelease(jeedoo,{...ade,metadata:{...ade.metadata,release_year:'2020'}}));
assert(!sameRelease(jeedoo,{...ade,metadata:{...ade.metadata,studio:'Different Studio'}}));
const merged=combine([jeedoo,ade]);assert.equal(merged.metadata.performers,'Actor A, Actor B');assert.equal(merged.metadata.studio,'Example Studio');assert.equal(merged.metadata.content_tags,'Classic, Drama, Romance');assert.equal(merged.images.length,2);assert.equal(merged.fieldSources.performers.join(','),'ADE');assert.equal(merged.imageSources['https://example.com/cover.jpg'].join(','),'Jeedoo,ADE');assert.equal(merged.choices.description.length,2);assert.equal(jeedoo.metadata.performers,undefined);
const alone=combine([jeedoo]);assert.equal(alone.metadata.performers,'');assert.equal(alone.images.length,1);assert.equal(combine([]).images.length,0);
const conflict=combine([jeedoo,{...ade,metadata:{...ade.metadata,release_year:'2020'}}]);assert.equal(conflict.choices.release_year.length,2);
console.log('Cross-source merge: matching, conflicts, provenance, selection and image deduplication passed.');
// A strong match on the first source must not suppress later source metadata.
context.SearchTitles={normalize:value=>value};
context.DOMParser=class{parseFromString(text){return {images:[],title:text,body:{textContent:text},querySelector:selector=>selector==='h1'?{textContent:text}:null,querySelectorAll:()=>[]};}};
(async()=>{
 const calls=[],urls={ 'www.jeedoo.com':'https://www.jeedoo.com/stream-download/vod_ms_1-The-Game/','www.adultdvdempire.com':'https://www.adultdvdempire.com/123/the-game-porn-videos.html','store.freeones.com':'https://store.freeones.com/123/the-game-porn-videos.html','en.erotik.com':'https://en.erotik.com/example-studio/the-game'};
 const result=await context.window.CatalogMetadata.search('The Game','auto',async url=>{const host=new URL(url).hostname;calls.push(host);return {html:'The Game',url:urls[host]};},()=>{});
 assert.equal(calls.length,4);assert.equal(result.results.length,4,JSON.stringify(result.errors));assert.equal(result.errors.length,0);console.log('Combined scan continues through all four sources after a 100% match.');
})().catch(error=>{console.error(error);process.exitCode=1;});
