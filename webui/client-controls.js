/* Per-torrent controls and opt-in completed-torrent removal rules. */
let clientTorrentTarget=null,clientTorrentRequest=0,clientTorrentPending=null;
function peerNumber(value){return value==null||!Number.isFinite(Number(value))||Number(value)<0?'—':String(Math.floor(Number(value)));}
function peerText(connected,total){return peerNumber(connected)+' ('+peerNumber(total)+')';}
function clientDuration(seconds){if(seconds==null||!Number.isFinite(Number(seconds))||Number(seconds)<0)return '—';const value=Math.floor(Number(seconds));return value>=86400?Math.floor(value/86400)+'d '+Math.floor(value%86400/3600)+'h':value>=3600?Math.floor(value/3600)+'h '+Math.floor(value%3600/60)+'m':Math.floor(value/60)+'m';}
function clientTorrentMenuActions(torrent,add){
 add('Torrent information',()=>openClientTorrent(torrent));
 for(const [label,action] of [[torrent.status==='paused'?'Resume':'Pause',torrent.status==='paused'?'resume':'pause'],['Force start','force_start'],['Recheck / rehash','recheck'],['Reannounce trackers','reannounce'],['Delete torrent…','delete']])add(label,()=>requestClientTorrentAction(torrent,action),torrent.stale);
}
function openClientTorrentMenu(torrent,event){
 const menu=$('client-torrent-menu');menu.replaceChildren();clientTorrentMenuActions(torrent,(label,callback,disabled)=>{const button=element('button','',label);button.type='button';button.disabled=!!disabled;button.setAttribute('role','menuitem');button.addEventListener('click',()=>{menu.hidden=true;callback();});menu.append(button);});
 menu.hidden=false;const rect=event.currentTarget?.getBoundingClientRect();menu.style.left=Math.max(8,Math.min(event.clientX??rect?.left??8,window.innerWidth-230))+'px';menu.style.top=Math.max(8,Math.min(event.clientY??rect?.bottom??8,window.innerHeight-menu.offsetHeight-8))+'px';
}
document.addEventListener('click',event=>{if(!$('client-torrent-menu').contains(event.target)&&!event.target.closest('.torrent-control'))$('client-torrent-menu').hidden=true;});
document.addEventListener('keydown',event=>{if(event.key==='Escape')$('client-torrent-menu').hidden=true;});
window.addEventListener('resize',()=>$('client-torrent-menu').hidden=true);
function renderClientTorrent(torrent){
 const list=$('client-torrent-info');list.replaceChildren();
 const date=value=>Number(value)>0?new Date(Number(value)*1000).toLocaleString():'—';
 const groups=[['Overview',[['Client',torrent.client_name],['Status',torrent.stale?'Stale snapshot':seedLabels[torrent.status]||torrent.state],['Progress',Number.isFinite(Number(torrent.progress))?(Number(torrent.progress)*100).toFixed(1)+'%':'—'],['Size',prettySize(torrent.size)],['Ratio',torrent.ratio==null?'—':Number(torrent.ratio).toFixed(2)],['Category',torrent.category||'None']]],
  ['Transfers',[['Uploaded',prettySize(torrent.uploaded)],['Downloaded',prettySize(torrent.downloaded)],['Upload speed',prettySize(torrent.upspeed)+'/s'],['Download speed',prettySize(torrent.dlspeed)+'/s']]],
  ['Peers & seeding',[['Seeders',peerText(torrent.num_seeds,torrent.num_complete)],['Leechers',peerText(torrent.num_leechs,torrent.num_incomplete)],['Seed time',clientDuration(torrent.seeding_time)]]],
  ['Dates',[['Added',date(torrent.added_on)],['Completed',date(torrent.completion_on)]]],
  ['Files & identifiers',[['Save path',torrent.save_path],...(torrent.content_path?[['Content path',torrent.content_path]]:[]),['Hash',torrent.hash]]]];
 for(const [title,fields]of groups){const section=element('section','client-info-section'+(title==='Files & identifiers'?' client-info-paths':''));section.append(element('h3','',title));const values=document.createElement('dl');for(const [name,value]of fields){values.append(element('dt','',name),element('dd','',String(value??'—')));}section.append(values);list.append(section);}
 $('client-torrent-buttons').replaceChildren();clientTorrentMenuActions(torrent,(label,callback,disabled)=>{if(label==='Torrent information')return;const button=element('button','button subtle small',label);button.type='button';button.disabled=!!disabled;button.addEventListener('click',callback);$('client-torrent-buttons').append(button);});
}
async function openClientTorrent(torrent){clientTorrentTarget={...torrent};$('client-torrent-name').textContent=torrent.name;renderClientTorrent(torrent);$('client-torrent-trackers').textContent='Loading tracker status…';$('client-torrent-dialog').showModal();await refreshClientTorrent();}
async function refreshClientTorrent(){
 if(!clientTorrentTarget)return;const request=++clientTorrentRequest,target={...clientTorrentTarget};$('client-torrent-live-status').textContent='Reading live information…';$('client-torrent-refresh').disabled=true;
 try{const result=await api('/api/clients/torrent?id='+encodeURIComponent(target.client_id)+'&hash='+encodeURIComponent(target.hash));if(request!==clientTorrentRequest)return;
  clientTorrentTarget={...target,...result.torrent,client_name:result.client_name,stale:false};renderClientTorrent(clientTorrentTarget);$('client-torrent-trackers').replaceChildren();
  if(!result.trackers.length)$('client-torrent-trackers').textContent='No trackers reported.';
  const states={0:'Disabled',1:'Not contacted',2:'Working',3:'Updating',4:'Not working'};
  for(const tracker of result.trackers){const row=element('div','client-tracker-row');const status=element('span','client-tracker-status',states[tracker.status]||'Status unavailable');status.dataset.state=String(tracker.status);row.append(element('strong','client-tracker-host',tracker.host),status,element('span','client-tracker-peers',peerNumber(tracker.seeders)+' seeds · '+peerNumber(tracker.leechers)+' leeches'));$('client-torrent-trackers').append(row);}
  $('client-torrent-live-status').textContent='Live information updated '+new Date().toLocaleTimeString()+'. Counts are connected peers (reported swarm totals).';
 }catch(error){if(request===clientTorrentRequest){$('client-torrent-live-status').textContent=error.message+' Showing the saved snapshot.';$('client-torrent-trackers').textContent='Tracker status unavailable.';clientTorrentTarget={...target,stale:true};renderClientTorrent(clientTorrentTarget);}}
 finally{if(request===clientTorrentRequest)$('client-torrent-refresh').disabled=false;}
}
$('client-torrent-refresh').addEventListener('click',refreshClientTorrent);
$('client-torrent-dialog').addEventListener('close',()=>{++clientTorrentRequest;clientTorrentTarget=null;});
function requestClientTorrentAction(torrent,action){
 if(['delete','recheck'].includes(action)){clientTorrentPending={torrent:{...torrent},action};$('client-torrent-action-title').textContent=action==='delete'?'Remove this torrent?':'Recheck this torrent?';$('client-torrent-action-name').textContent=torrent.name;$('client-torrent-action-help').textContent=action==='delete'?'Remove only this torrent from '+torrent.client_name+'. Downloaded data is kept unless you explicitly select the option below. Deleting data may affect other clients or apps using the same files.':'qBittorrent will read the local files again to verify their piece hashes. Seeding or downloading may pause during this check.';$('client-delete-data-label').hidden=action!=='delete';$('client-delete-data').checked=false;$('client-torrent-action-error').textContent='';$('client-torrent-action-confirm').textContent=action==='delete'?'Remove torrent':'Start recheck';$('client-torrent-action-dialog').showModal();return;}
 executeClientTorrentAction(torrent,action,false).catch(error=>toast(error.message,true));
}
async function executeClientTorrentAction(torrent,action,deleteData){
 const result=await api('/api/clients/action',{id:torrent.client_id,hash:torrent.hash,action,delete_data:deleteData,...(action==='delete'?{confirm_hash:torrent.hash}:{})});if(!result.ok)throw new Error(result.error||'Client refresh failed. Check its state before retrying.');
 if(action==='delete'&&clientTorrentTarget?.hash===torrent.hash&&clientTorrentTarget?.client_id===torrent.client_id)$('client-torrent-dialog').close();
 toast(action==='delete'?(deleteData?'Torrent and client data removal confirmed.':'Torrent removed. Downloaded data kept.'):'Client action accepted.');await refreshClients();if(clientTorrentTarget)await refreshClientTorrent();
}
$('client-torrent-action-form').addEventListener('submit',async event=>{event.preventDefault();if(!clientTorrentPending)return;const pending=clientTorrentPending;const button=$('client-torrent-action-confirm');button.disabled=true;try{await executeClientTorrentAction(pending.torrent,pending.action,$('client-delete-data').checked);$('client-torrent-action-dialog').close();}catch(error){$('client-torrent-action-error').textContent=error.message;}finally{button.disabled=false;}});
$('client-torrent-action-dialog').addEventListener('close',()=>{clientTorrentPending=null;});
let cleanupRulesList=[];
async function refreshCleanupRules(){
 const result=await api('/api/clients/cleanup-rules');cleanupRulesList=result.rules;
 const select=$('cleanup-rule-scope'),selected=select.value;select.replaceChildren(new Option('All clients',''));
 for(const client of clientList)select.append(new Option(client.name,client.id));select.value=clientList.some(c=>c.id===selected)?selected:'';
 $('client-new-rule').disabled=!clientList.length;renderCleanupRules();
}
function renderCleanupRules(){
 const list=$('client-removal-rules');list.replaceChildren();const scope=$('cleanup-rule-scope').value,rules=cleanupRulesList.filter(rule=>!scope||rule.client_id===scope);
 if(!rules.length)list.append(element('p','field-help','No removal rules configured here. Choose + New Rule to add one. Rules start disabled.'));
 for(const rule of rules){
  const row=element('article','cleanup-rule-row'),info=element('div','cleanup-rule-content'),heading=element('div','cleanup-rule-heading');
  heading.append(element('strong','',rule.name),element('span','cleanup-rule-state '+(rule.enabled?'enabled':'disabled'),rule.enabled?'Enabled':'Disabled'));
  const scope=element('div','cleanup-scope-tags');for(const value of [rule.client_name,rule.tracker||'All trackers',rule.category?'Category: '+rule.category:'All client categories'])scope.append(element('span','',value));
  const conditions=[];if(rule.seed_hours)conditions.push(rule.seed_hours+' hours seeding');if(rule.min_seeders)conditions.push(rule.min_seeders+' swarm seeders');
  info.append(heading,scope,element('p','field-help',(conditions.join(rule.match==='all'?' AND ':' OR ')||'No conditions yet')+' · '+(rule.delete_data?'Remove torrent and data':'Remove torrent, keep data')));
  const actions=element('div','draft-actions'),edit=element('button','button subtle small','Edit rule'),remove=element('button','button subtle small','Delete rule');edit.type=remove.type='button';edit.addEventListener('click',()=>openRemovalRule(rule));remove.addEventListener('click',async()=>{remove.disabled=true;try{await api('/api/clients/cleanup-rule-remove',{id:rule.client_id,rule_id:rule.id});toast('Removal rule deleted. Torrents and data are unchanged.');await refreshClients();}catch(error){toast(error.message,true);remove.disabled=false;}});actions.append(edit,remove);row.append(info,actions);list.append(row);
 }
}
function showClientRules(client){$('cleanup-rule-scope').value=client.id;renderCleanupRules();$('client-rules-panel').scrollIntoView({block:'start',behavior:'smooth'});}
function openRemovalRule(rule=null){
 if(!clientList.length){toast('Add a client connection first.',true);return;}
 const client=rule?.client_id||$('cleanup-rule-scope').value||$('torrent-client-filter').value||clientList[0].id;
 $('cleanup-client').replaceChildren(...clientList.map(c=>new Option(c.name,c.id)));$('cleanup-client').value=client;$('cleanup-client').disabled=!!rule?.id;
 $('cleanup-rule-id').value=rule?.id||'';$('cleanup-rule-name').value=rule?.name||'';$('cleanup-rule-title').textContent=rule?.id?'Edit removal rule':'New removal rule';
 for(const key of ['enabled','confirm'])$('cleanup-'+key).checked=key==='enabled'&&!!rule?.enabled;
 $('cleanup-hours').value=rule?.seed_hours||0;$('cleanup-seeders').value=rule?.min_seeders||0;$('cleanup-match').value=rule?.match||'all';$('cleanup-category').value=rule?.category||'';$('cleanup-tracker').value=rule?.tracker||'';$('cleanup-data').value=rule?.delete_data?'delete':'keep';$('cleanup-result').textContent='Preview the matching torrents before enabling this rule. Changes apply only after saving.';
 $('cleanup-rule-dialog').showModal();
}
function cleanupRuleInput(){return {id:$('cleanup-client').value,rule_id:$('cleanup-rule-id').value,new_rule:!$('cleanup-rule-id').value,name:$('cleanup-rule-name').value,enabled:$('cleanup-enabled').checked,seed_hours:$('cleanup-hours').value,min_seeders:$('cleanup-seeders').value,match:$('cleanup-match').value,category:$('cleanup-category').value,tracker:$('cleanup-tracker').value,delete_data:$('cleanup-data').value==='delete',confirmed:$('cleanup-confirm').checked};}
$('client-new-rule').addEventListener('click',()=>openRemovalRule());$('cleanup-rule-scope').addEventListener('change',renderCleanupRules);
$('cleanup-rule-form').addEventListener('submit',event=>{event.preventDefault();$('cleanup-save').click();});
for(const action of ['preview','save'])$('cleanup-'+action).addEventListener('click',async()=>{
 const button=$('cleanup-'+action);button.disabled=true;
 try{
  const rule=cleanupRuleInput();if(action==='save'&&rule.enabled&&!rule.confirmed)throw new Error('Confirm the rule and selected data handling before enabling automatic removal.');
  const result=await api('/api/clients/cleanup-'+(action==='save'?'policy':'preview'),rule);
  if(action==='save'){$('cleanup-rule-dialog').close();toast(result.enabled?'Removal rule saved and enabled.':'Removal rule saved; automatic removal is disabled.');await refreshClients();}
  else $('cleanup-result').textContent=result.count+' completed torrent(s) match. '+(result.shared_data_skips?result.shared_data_skips+' would be skipped because data paths are shared or unknown. ':'')+result.note+(result.examples.length?'\n'+result.examples.join('\n'):'');
 }catch(error){$('cleanup-result').textContent=error.message;}finally{button.disabled=false;}
});
$('client-cleanup-history').addEventListener('toggle',async()=>{if(!$('client-cleanup-history').open)return;try{const result=await api('/api/clients/cleanup-events');$('client-cleanup-events').replaceChildren();if(!result.events.length)$('client-cleanup-events').textContent='No automatic removals requested.';for(const item of result.events){const row=element('div','cleanup-event');row.append(element('strong','',item.name),element('p','field-help',[item.client_name||'Disconnected client',item.rule_name,item.state,new Date(item.created*1000).toLocaleString()].filter(Boolean).join(' · ')),element('p','',item.message));$('client-cleanup-events').append(row);}}catch(error){$('client-cleanup-events').textContent=error.message;}});

/* Column widths are local to this browser and uploader origin. */
const torrentColumnStorageKey='uploader.client-column-widths.v1';
const torrentColumnDefaults={name:320,client:150,size:100,progress:130,status:110,dlspeed:110,upspeed:110,ratio:85,seeders:90,leechers:90,seeding_time:110,tracker:180,added_on:160,actions:85};
function validTorrentColumnWidth(key,value){return Number.isFinite(value)&&value>=(key==='name'?120:60)&&value<=1600;}
function readTorrentColumnWidths(){try{const saved=JSON.parse(localStorage.getItem(torrentColumnStorageKey)||'{}');return Object.fromEntries(Object.entries(torrentColumnDefaults).map(([key,width])=>[key,validTorrentColumnWidth(key,saved?.[key])?saved[key]:width]));}catch{return {...torrentColumnDefaults};}}
function fitTorrentColumns(keys,widths,available){
 const minimums=keys.map(key=>key==='name'?120:60),minimum=minimums.reduce((a,b)=>a+b,0);
 const extra=keys.map((key,index)=>Math.max(0,widths[key]-minimums[index])),weight=extra.reduce((a,b)=>a+b,0);
 const space=Math.max(0,available-minimum);
 return keys.map((key,index)=>minimums[index]+space*(weight?extra[index]/weight:1/keys.length));
}
let torrentColumnWidths=readTorrentColumnWidths(),stopTorrentColumnResize=null,torrentColumnObserver=null;
function saveTorrentColumnWidths(){try{localStorage.setItem(torrentColumnStorageKey,JSON.stringify(torrentColumnWidths));}catch{/* Resizing still works when browser storage is unavailable. */}}
function installTorrentColumns(table){
 if(stopTorrentColumnResize)stopTorrentColumnResize();if(torrentColumnObserver)torrentColumnObserver.disconnect();
 const group=document.createElement('colgroup'),headers=[...table.querySelectorAll('thead th')],columns=[];
 function apply(){const keys=columns.map(c=>c.key),fallback=keys.reduce((total,key)=>total+torrentColumnWidths[key],0),minimum=keys.reduce((sum,key)=>sum+(key==='name'?120:60),0),available=table.parentElement?.clientWidth||fallback,values=fitTorrentColumns(keys,torrentColumnWidths,available);for(let i=0;i<columns.length;i++){const item=columns[i];item.width=values[i];item.col.style.width=values[i]+'px';item.handle.setAttribute('aria-valuenow',String(Math.round(values[i])));}table.style.width='100%';table.style.minWidth=minimum+'px';}
 for(const header of headers){
  const key=header.dataset.columnKey;if(!(key in torrentColumnDefaults))continue;
  const col=document.createElement('col'),handle=document.createElement('span');group.append(col);handle.className='torrent-column-resize';handle.tabIndex=0;handle.setAttribute('role','separator');handle.setAttribute('aria-orientation','vertical');handle.setAttribute('aria-label','Resize '+header.textContent.replace(/[↑↓↕]/g,'').trim()+' column');handle.setAttribute('aria-valuemin',String(key==='name'?120:60));handle.setAttribute('aria-valuemax','1600');handle.title='Drag to resize. Double-click to reset. Arrow keys resize; Home resets.';
  const item={key,col,handle,width:0};
  const setWidth=value=>{const index=columns.indexOf(item),other=columns[index+1]||columns[index-1];if(!other)return;const minimum=key==='name'?120:60,otherMin=other.key==='name'?120:60,delta=Math.max(minimum-item.width,Math.min(1600-item.width,other.width-otherMin,value-item.width));for(const c of columns)torrentColumnWidths[c.key]=c.width;torrentColumnWidths[key]+=delta;torrentColumnWidths[other.key]-=delta;apply();};
  handle.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();});
  handle.addEventListener('dblclick',event=>{event.preventDefault();event.stopPropagation();setWidth(torrentColumnDefaults[key]);saveTorrentColumnWidths();});
  handle.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home'].includes(event.key))return;event.preventDefault();event.stopPropagation();setWidth(event.key==='Home'?torrentColumnDefaults[key]:item.width+(event.key==='ArrowRight'?1:-1)*(event.shiftKey?40:10));saveTorrentColumnWidths();});
  handle.addEventListener('pointerdown',event=>{
   if(event.button!==0)return;event.preventDefault();event.stopPropagation();if(stopTorrentColumnResize)stopTorrentColumnResize();
   const start=event.clientX,width=item.width,pointer=event.pointerId;handle.setPointerCapture(pointer);document.body.classList.add('resizing-torrent-column');
   const move=event=>{if(event.pointerId===pointer)setWidth(width+event.clientX-start);};
   const end=()=>{handle.removeEventListener('pointermove',move);handle.removeEventListener('pointerup',end);handle.removeEventListener('pointercancel',end);handle.removeEventListener('lostpointercapture',end);if(handle.hasPointerCapture(pointer))handle.releasePointerCapture(pointer);document.body.classList.remove('resizing-torrent-column');stopTorrentColumnResize=null;saveTorrentColumnWidths();};
   stopTorrentColumnResize=end;handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',end);handle.addEventListener('pointercancel',end);handle.addEventListener('lostpointercapture',end);
  });
  header.append(handle);columns.push(item);
 }
 table.prepend(group);apply();if(typeof ResizeObserver!=='undefined'&&table.parentElement){torrentColumnObserver=new ResizeObserver(apply);torrentColumnObserver.observe(table.parentElement);}
}
$('reset-torrent-columns').addEventListener('click',()=>{if(stopTorrentColumnResize)stopTorrentColumnResize();torrentColumnWidths={...torrentColumnDefaults};saveTorrentColumnWidths();const table=$('client-torrents').querySelector('table');if(table){table.querySelector('colgroup')?.remove();table.querySelectorAll('.torrent-column-resize').forEach(handle=>handle.remove());installTorrentColumns(table);}});

function updateTorrentTrackerFilter(trackers){
 const select=$('torrent-tracker-filter'),selected=select.value;
 select.replaceChildren(new Option('All trackers',''));
 for(const host of trackers)select.append(new Option(host,host));const options=$('cleanup-tracker-options');if(options)options.replaceChildren(...trackers.map(host=>new Option(host,host)));
 if(selected&&!trackers.includes(selected))select.append(new Option(selected+' (not found)',selected));
 select.value=selected;
}
