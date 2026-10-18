'use strict';
let librarySelected=null,libraryRequest=0;
let libraryPath='',libraryListing=null,libraryOverrides=new Map(),libraryBusy=false;
async function loadLibrary(path=libraryPath){
 const request=++libraryRequest;
 const table=$('library-rows');table.replaceChildren(element('p','field-help','Reading folders and filters.json…'));
 try{
  const listing=await api('/api/library'+(path?'?path='+encodeURIComponent(path):''));if(request!==libraryRequest)return;libraryListing=listing;libraryPath=listing.path;
  $('library-path').textContent=listing.path;$('library-up').disabled=!listing.parent;
  const bookmarks=$('library-folders');bookmarks.replaceChildren(new Option('Content library',listing.root));
  for(const saved of listing.saved_folders)if(saved!==listing.root)bookmarks.append(new Option(saved,saved));
  bookmarks.value=listing.saved_folders.includes(listing.path)||listing.path===listing.root?listing.path:listing.root;
  table.replaceChildren();
  for(const [kind,rows] of [['folder',listing.folders],['file',listing.files]])for(const row of rows){
   if(request!==libraryRequest)return;
   const item=element('div','library-row'),open=element('button','library-name');open.type='button';open.append(icon(kind==='folder'?'folder':'grid'),element('span','',row.name));
   if(kind==='folder'){open.addEventListener('click',()=>loadLibrary(row.path));open.title='Open folder';}else{open.title=row.name;}
   const info=element('small','field-help',kind==='file'?prettySize(row.size):'Folder');
   const category=element('select');category.setAttribute('aria-label','Category for '+row.name);category.append(new Option(row.category?'Automatic: '+row.category.name:'No matching filter',''));
   if(libraryOverrides.has(row.path)){const saved=libraryOverrides.get(row.path),cat=state.categories.find(c=>c.id===saved);if(cat)category.append(new Option(cat.name,String(saved)));}
   category.value=libraryOverrides.has(row.path)?String(libraryOverrides.get(row.path)):'';
   const fillCategories=()=>{if(category.dataset.full)return;const selected=category.value;for(const cat of state.categories)if(![...category.options].some(o=>o.value===String(cat.id)))category.append(new Option(cat.name,String(cat.id)));category.dataset.full='1';category.value=selected;};category.addEventListener('focus',fillCategories);category.addEventListener('pointerdown',fillCategories);
   const upload=element('button','button subtle','Upload Direct');upload.type='button';upload.disabled=!row.category&&!category.value;
   category.addEventListener('change',()=>{if(category.value)libraryOverrides.set(row.path,Number(category.value));else libraryOverrides.delete(row.path);upload.disabled=!row.category&&!category.value;});
   upload.addEventListener('click',()=>uploadFromLibrary(row));
   item.addEventListener('contextmenu',event=>{event.preventDefault();openLibraryMenu(row,kind,event);});
   const more=element('button','button subtle','⋯');more.type='button';more.setAttribute('aria-label','Actions for '+row.name);more.addEventListener('click',event=>{event.stopPropagation();openLibraryMenu(row,kind,{clientX:event.currentTarget.getBoundingClientRect().left,clientY:event.currentTarget.getBoundingClientRect().bottom});});
   item.append(open,info,category,upload,more);table.append(item);if(table.children.length%100===0)await new Promise(requestAnimationFrame);
  }
  if(!listing.folders.length&&!listing.files.length)table.append(element('p','field-help','This folder is empty.'));
 }catch(error){table.replaceChildren(element('p','field-help',error.message));}
}
async function uploadFromLibrary(row,details={}){
 if(libraryBusy)return;libraryBusy=true;$('library-context').hidden=true;
 try{const payload={source:row.path,...details};if(!('category' in details)&&libraryOverrides.has(row.path))payload.category=libraryOverrides.get(row.path);if(!('category' in payload)&&row.category)payload.expected_category=row.category.id;const result=await api('/api/library/upload',payload);toast('Upload started. Automatic processing is running.');$('library-metadata-dialog').close();page('activity');openJob(result.id);}
 catch(error){toast(error.message,true);}finally{libraryBusy=false;}
}
$('library-up').addEventListener('click',()=>{if(libraryListing?.parent)loadLibrary(libraryListing.parent);});
$('library-refresh').addEventListener('click',()=>loadLibrary());
$('library-folders').addEventListener('change',()=>loadLibrary($('library-folders').value));
$('library-add').addEventListener('click',()=>{$('library-add-path').value=libraryPath||state.settings.content;$('library-add-dialog').showModal();});
$('library-add-close').addEventListener('click',()=>$('library-add-dialog').close());
$('library-add-form').addEventListener('submit',async event=>{event.preventDefault();const button=event.submitter;button.disabled=true;try{const path=$('library-add-path').value;await api('/api/library/folders',{path});$('library-add-dialog').close();await loadLibrary(path);}catch(error){toast(error.message,true);}finally{button.disabled=false;}});
$('library-remove').addEventListener('click',async()=>{try{await api('/api/library/folders',{action:'remove',path:libraryPath});await loadLibrary(libraryListing.root);toast('Folder shortcut removed. Files were kept.');}catch(error){toast(error.message,true);}});
document.addEventListener('click',event=>{if(!$('library-context').contains(event.target))$('library-context').hidden=true;});
document.addEventListener('keydown',event=>{if(event.key==='Escape')$('library-context').hidden=true;});
async function loadCategoryFilters(){
 if($('filters-json').dataset.loaded)return;
 try{const result=await api('/api/category-filters');$('filters-json').value=result.text;$('filters-json').dataset.loaded='1';$('filters-location').textContent=result.path;
  $('filters-categories').textContent=state.categories.map(row=>row.id+' = '+row.name).join(' · ');
 }catch(error){$('filters-result').textContent=error.message;}
}
$('category-filters-panel').addEventListener('toggle',()=>{if($('category-filters-panel').open)loadCategoryFilters();});
$('filters-test').addEventListener('click',async()=>{const button=$('filters-test');button.disabled=true;try{const result=await api('/api/category-filters/test',{name:$('filters-test-name').value,text:$('filters-json').value});$('filters-result').textContent=result.category?'Expected category: '+result.category.name:'No rule matched. Automatic upload will not start for this name.';}catch(error){$('filters-result').textContent=error.message;}finally{button.disabled=false;}});
$('filters-save').addEventListener('click',async()=>{const button=$('filters-save');button.disabled=true;try{const result=await api('/api/category-filters',{text:$('filters-json').value});$('filters-result').textContent=result.message;libraryOverrides.clear();review=null;await boot();}catch(error){$('filters-result').textContent=error.message;}finally{button.disabled=false;}});

function openLibraryMenu(row,kind,event){
 const menu=$('library-context');menu.replaceChildren();
 function action(label,handler,disabled=false){const button=element('button','',label);button.type='button';button.disabled=disabled;button.addEventListener('click',()=>{menu.hidden=true;handler();});menu.append(button);}
 if(kind==='folder')action('Open folder',()=>loadLibrary(row.path));
 action('Upload Direct',()=>uploadFromLibrary(row),!row.category&&!libraryOverrides.has(row.path));
 action('Upload with metadata',()=>openLibraryMetadata(row));
 action('Test category rules',async()=>{page('settings');$('category-filters-panel').open=true;await loadCategoryFilters();$('filters-test-name').value=row.name;$('filters-test').click();$('category-filters-panel').scrollIntoView({block:'start'});});
 action('Copy path',async()=>{try{if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(row.path);else{const input=element('textarea');input.value=row.path;document.body.append(input);input.select();const copied=document.execCommand('copy');input.remove();if(!copied)throw new Error('Copy unavailable');}toast('Path copied.');}catch(error){toast('Could not copy the path: '+row.path,true);}});
 action('Refresh',()=>loadLibrary());
 menu.hidden=false;menu.style.left=Math.max(8,Math.min(event.clientX,window.innerWidth-210))+'px';menu.style.top=Math.max(8,Math.min(event.clientY,window.innerHeight-menu.offsetHeight-8))+'px';
}
function openLibraryMetadata(row){
 librarySelected=row;$('library-metadata-name').textContent=row.name;
 const category=$('library-category');category.replaceChildren(new Option(row.category?'Automatic: '+row.category.name:'Choose a category (no matching filter)',''));for(const cat of state.categories)category.append(new Option(cat.name,String(cat.id)));category.value=libraryOverrides.has(row.path)?String(libraryOverrides.get(row.path)):'';
 for(const id of ['studio','performers','genre','year','runtime','language','imdb','game-url','description','images'])if($('library-'+id))$('library-'+id).value='';
 $('library-metadata-dialog').showModal();
}
$('library-metadata-close').addEventListener('click',()=>$('library-metadata-dialog').close());
$('library-lookup').addEventListener('click',()=>openMetadata('library'));
$('library-metadata-form').addEventListener('submit',async event=>{event.preventDefault();if(!librarySelected)return;const button=event.submitter;button.disabled=true;try{const details={description:$('library-description').value,images:$('library-images').value.split('\n').map(x=>x.trim()).filter(Boolean),metadata:{}};for(const [id,key] of [['studio','studio'],['performers','performers'],['genre','content_tags'],['year','release_year'],['runtime','runtime_minutes'],['language','language'],['imdb','imdbId'],['game-url','gameUrl']])if($('library-'+id)?.value.trim())details.metadata[key]=$('library-'+id).value.trim();if($('library-category').value)details.category=Number($('library-category').value);await uploadFromLibrary(librarySelected,details);}finally{button.disabled=false;}});
window.addEventListener('resize',()=>$('library-context').hidden=true);
