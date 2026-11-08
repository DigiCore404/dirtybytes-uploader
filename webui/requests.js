/* Tracker requests stay read-only until the reviewed torrent is published. */
let requestOffset=0,requestSort='added',requestOrder='desc',requestLoad=0,requestTotal=null,requestRows=0;
function setTrackerRequest(row){
 $('request-id').value=row?.id||'';$('request-selection').textContent=row?'#'+row.id+' · '+row.title:'';
 $('request-requirements').textContent=row?.description||'';$('request-requirements').hidden=!row?.description;
 review=null;
}
async function chooseTrackerRequest(id){
 const row=await api('/api/requests/'+id);setTrackerRequest(row);
 if([...$('category').options].some(o=>o.value===String(row.category)))$('category').value=String(row.category);
 page('upload');step(source?2:1);toast('Request selected. Choose the matching release and review its requirements.');
}
async function loadTrackerRequests(reset=false){
 if(reset)requestOffset=0;const serial=++requestLoad;
 const params=new URLSearchParams({search:$('requests-search').value,category:$('requests-category').value||0,offset:requestOffset,sort:requestSort,order:requestOrder});
 $('requests-message').textContent='Loading open requests…';
 try{
  const result=await api('/api/requests?'+params);if(serial!==requestLoad)return;
  requestTotal=result.total;requestRows=result.requests.length;const tbody=$('requests-rows');tbody.replaceChildren();
  for(const row of result.requests){
   const tr=document.createElement('tr');
   for(const value of ['#'+row.id+' · '+row.title,state.categories.find(c=>String(c.id)===String(row.category))?.name||row.category,Number(row.reward||0).toLocaleString(),Number(row.votes||0).toLocaleString(),row.added]){const td=document.createElement('td');td.textContent=value;tr.append(td);}
   const actions=document.createElement('td'),view=document.createElement('a'),fill=document.createElement('button');
   view.textContent='View request';view.href=row.url;view.target='_blank';view.rel='noopener noreferrer';view.className='button subtle small';
   fill.type='button';fill.className='button primary small';fill.textContent='Fill request';fill.addEventListener('click',()=>chooseTrackerRequest(row.id).catch(e=>toast(e.message,true)));
   actions.append(view,fill);tr.append(actions);tbody.append(tr);
  }
  $('requests-message').textContent=requestRows?'Showing '+(requestOffset+1)+'–'+(requestOffset+requestRows)+(requestTotal===null?'':' of '+requestTotal)+' open requests':'No open requests match these filters.';
  $('requests-previous').disabled=requestOffset===0;$('requests-next').disabled=requestTotal===null?requestRows<25:requestOffset+25>=requestTotal;
  document.querySelectorAll('[data-request-sort]').forEach(b=>{b.textContent=b.dataset.label+(requestSort===b.dataset.requestSort?(requestOrder==='asc'?' ↑':' ↓'):' ↕');b.parentElement.setAttribute('aria-sort',requestSort===b.dataset.requestSort?(requestOrder==='asc'?'ascending':'descending'):'none');});
 }catch(e){if(serial!==requestLoad)return;$('requests-message').textContent=e.message;$('requests-rows').replaceChildren();$('requests-next').disabled=true;}
}
$('requests-form').addEventListener('submit',e=>{e.preventDefault();loadTrackerRequests(true);});
$('requests-refresh').addEventListener('click',()=>loadTrackerRequests());
$('requests-previous').addEventListener('click',()=>{requestOffset=Math.max(0,requestOffset-25);loadTrackerRequests();});
$('requests-next').addEventListener('click',()=>{requestOffset+=25;loadTrackerRequests();});
document.querySelectorAll('[data-request-sort]').forEach(b=>b.addEventListener('click',()=>{requestOrder=requestSort===b.dataset.requestSort&&requestOrder==='desc'?'asc':'desc';requestSort=b.dataset.requestSort;loadTrackerRequests(true);}));
$('browse-requests').addEventListener('click',()=>page('requests'));
$('clear-request').addEventListener('click',()=>setTrackerRequest(null));
$('request-id').addEventListener('input',()=>{$('request-selection').textContent='';$('request-requirements').hidden=true;review=null;});
