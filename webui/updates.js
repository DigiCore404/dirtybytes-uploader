/* Public release notices; no installation commands run in the browser. */
(() => {
 const node = id => document.getElementById(id);
 let release, timer, checks = 0;
 function show(result) {
  release = result;
  node('update-installed').textContent = result.current_version;
  const labels = {checking:'Checking for updates…',current:'No newer stable release is available.',available:'Version '+result.latest_version+' is available.',unavailable:'Could not check for updates. Your uploader keeps working; try again later.',disabled:'Update checks are disabled. Enable Check updates under Upload behaviour to receive notifications.',no_release:'No stable release has been published yet.',not_checked:'Not checked yet.'};
  node('update-status').textContent = labels[result.status] || 'Update status unavailable.';
  if(result.checked_at && result.status!=='checking') node('update-status').textContent += ' Last checked: '+new Date(result.checked_at).toLocaleString();
  node('update-banner').hidden = !result.available;
  node('update-banner-title').textContent = 'Version '+result.latest_version+' is available';
  node('update-banner-detail').textContent = 'You are running '+result.current_version+'. View the changes and update instructions.';
  node('update-check').disabled = result.status==='checking';
  if(node('app-version')) node('app-version').textContent = result.current_version;
 }
 async function refresh(force=false) {
  clearTimeout(timer);
  try {
   const result=await api(force?'/api/updates/check':'/api/updates',force?{}:undefined);
   show(result);
   if(result.status==='checking' && checks++<12) timer=setTimeout(()=>refresh(),1000);
   else {checks=0;timer=setTimeout(()=>refresh(),6*60*60*1000);}
  } catch(error) {
   node('update-check').disabled=false;
   node('update-status').textContent='Could not check for updates. Your uploader keeps working; try again later.';
   if(state) timer=setTimeout(()=>refresh(),30*60*1000);
  }
 }
 window.refreshUpdates=refresh;
 function method() {
  if(!release)return;
  const selected=node('update-method').value, guide=release.instructions;
  for(const name of ['docker','git','package']) node('update-'+name+'-help').hidden=name!==selected;
  node('update-commands').textContent=guide[selected+'_commands'];
  node('update-image').textContent=guide.image;
  node('update-copy-status').textContent='';
 }
 function open() {
  if(!release){refresh();return;}
  node('update-dialog-title').textContent=release.available?'Update to version '+release.latest_version:'Update instructions';
  node('update-versions').textContent='Installed: '+release.current_version+(release.latest_version?' · Latest release: '+release.latest_version:'');
  node('update-notes').textContent=release.notes||'Open the release page for changes and available downloads.';
  node('update-release-link').href=release.release_url;
  node('update-method').value=release.installation==='docker'?'docker':release.source_type==='git'?'git':'package';
  method();node('update-dialog').showModal();
  node('update-changelog').textContent='Loading full changelog…';
  api('/api/changelog?latest=1').then(result=>{node('update-changelog').textContent=(result.notice?result.notice+'\n\n':'')+(result.text||'No changelog was included in this installation.');}).catch(()=>{node('update-changelog').textContent='Could not load the changelog. Open Changelog in the menu or view the GitHub release.';});
 }
 node('update-check').addEventListener('click',()=>{checks=0;refresh(true);});
 node('update-open').addEventListener('click',open);
 node('update-banner-open').addEventListener('click',open);
 node('update-close').addEventListener('click',()=>node('update-dialog').close());
 node('update-method').addEventListener('change',method);
 node('update-copy').addEventListener('click',async()=>{
  const mode=node('update-method').value;
  const text=(mode==='docker'?'# Set IMAGE in .env (or image: in compose.yaml) to:\n# '+release.instructions.image+'\n':'')+node('update-commands').textContent;
  try{await navigator.clipboard.writeText(text);node('update-copy-status').textContent='Commands copied. Follow the steps above before running them.';}
  catch(error){const range=document.createRange();range.selectNodeContents(node('update-commands'));const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);node('update-copy-status').textContent='Commands selected. Press Ctrl+C (or ⌘C) to copy.';}
 });
})();
