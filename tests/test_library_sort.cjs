const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const ctx={window:{}};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../webui/library-sort.js'),'utf8'),ctx);const sort=ctx.window.LibrarySort.rows;
const listing={folders:[{name:'Folder',size:null,modified:30,type:'folder'}],files:[{name:'File10',size:10,modified:10,type:'mkv'},{name:'File2',size:20,modified:20,type:'avi'}]};
const names=rows=>Array.from(rows,r=>r.name);
assert.deepEqual(names(sort(listing,'name','asc',true)),['Folder','File2','File10']);
assert.deepEqual(names(sort(listing,'name','desc',false)),['Folder','File10','File2']);
assert.deepEqual(names(sort(listing,'size','desc',false)),['File2','File10','Folder']);
assert.deepEqual(names(sort(listing,'modified','desc',false)),['Folder','File2','File10']);
assert.deepEqual(names(sort(listing,'type','asc',false)),['File2','Folder','File10']);
assert.equal(listing.files[0].name,'File10');console.log('Library sorting: natural names, size, dates, type, folders-first and unknown sizes passed.');

assert.equal(ctx.window.LibrarySort.next('name','asc','name').direction,'desc');
assert.equal(ctx.window.LibrarySort.next('name','desc','size').direction,'desc');
assert.equal(ctx.window.LibrarySort.next('size','desc','name').direction,'asc');
assert.equal(ctx.window.LibrarySort.next('size','desc','modified').direction,'desc');
console.log('Header sort toggles and sensible initial directions passed.');
