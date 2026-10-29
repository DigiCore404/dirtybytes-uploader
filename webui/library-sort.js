/* File/folder ordering never mutates the server listing. Unknown sizes stay last. */
window.LibrarySort={rows(listing,key='name',direction='asc',foldersFirst=true){
 const sign=direction==='desc'?-1:1;
 const rows=[...listing.folders.map(row=>({...row,kind:'folder'})),...listing.files.map(row=>({...row,kind:'file'}))];
 return rows.sort((a,b)=>{if(foldersFirst&&a.kind!==b.kind)return a.kind==='folder'?-1:1;const av=a[key],bv=b[key];if(av==null||bv==null){if(av!==bv)return av==null?1:-1;}const order=['size','modified'].includes(key)?Number(av)-Number(bv):String(av||'').localeCompare(String(bv||''),undefined,{numeric:true,sensitivity:'base'});return sign*order||a.name.localeCompare(b.name);});
}};
