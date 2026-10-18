'use strict';
function renderConfigSettings(settings,categories=[]){
 const target=document.getElementById('config-settings');if(!target)return;
 const hostFields=document.getElementById('image-host-advanced');hostFields.replaceChildren();
 const open=new Set(Array.from(target.querySelectorAll('details[open]')).map(x=>x.dataset.section));const first=!target.children.length;target.replaceChildren();
 const intro=element('div','config-intro');intro.append(element('h2','','Uploader configuration'),element('p','','These controls save directly to '+settings.config_file+'. Both the web service and CLI use this file. Client connections and workspace access have their own controls.'));target.append(intro);
 for(const section of settings.config_schema||[]){
  const details=element('details','card config-section');details.dataset.section=section.section;details.open=open.has(section.section)||(first&&section.section==='MediaTools');
  const summary=element('summary','',section.title);details.append(summary);const grid=element('div','config-grid');
  for(const field of section.fields){
   const wrapper=element('div','config-field'),id='cfg-'+section.section+'-'+field.key;const label=element('label','',field.label);label.htmlFor=id;
   const input=element(field.type==='select'?'select':'input');if(field.type==='select'){for(const option of field.options)input.append(new Option(option.label,option.value));}input.id=id;input.dataset.configSection=section.section;input.dataset.configKey=field.key;input.dataset.configType=field.type;
   if(field.type!=='select')input.type={boolean:'checkbox',number:'number',secret:'password'}[field.type]||'text';input.disabled=field.locked;
   if(field.type==='boolean')input.checked=String(field.value).toLowerCase()==='true';else input.value=field.value;
   input.dataset.original=field.type==='boolean'?String(input.checked):input.value;
   if(field.type==='secret'){input.autocomplete='new-password';input.placeholder=field.saved?'Saved — leave blank to keep':'Not configured';}
   if(field.range){input.min=field.range[0];input.max=field.range[1];input.step=field.key==='ratio_target'?'0.1':'1';}
   const help=element('small','field-help',field.help+(field.locked?' Managed by Docker; change the container mount.':''));
   if(field.type==='boolean'){const toggle=element('div','config-toggle');toggle.append(label,input);wrapper.append(toggle,help);}else wrapper.append(label,input,help);
   if(field.key.endsWith('_categories')||field.key==='categories'){input.type='hidden';wrapper.append(categoryPicker(input,field.label,categories));help.textContent=(field.help||'Choose the categories where this feature applies.').replace(/Comma-separated (?:DirtyBytes |DigitalCore )?category IDs/g,'Categories').replace('Comma-separated categories','Categories')+' Choose names here; web and CLI use the saved category IDs.';}
   const mapping=element('code','config-key',section.section+'.'+field.key.toUpperCase());wrapper.append(mapping);
   if(field.key==='mtnsetting'){
    const controls=element('div','mtn-grid-controls');
    for(const [flag,name,fallback] of [['c','Columns',2],['r','Rows',8]]){
     const box=element('div'),gridLabel=element('label','',name),number=element('input');number.type='number';number.min=1;number.max=20;number.id=id+'-'+flag;gridLabel.htmlFor=number.id;
     const match=input.value.match(new RegExp('-'+flag+'\\s+(\\d+)'));number.value=match?match[1]:fallback;
     number.addEventListener('input',()=>{const expression=new RegExp('-'+flag+'\\s+\\d+');input.value=expression.test(input.value)?input.value.replace(expression,'-'+flag+' '+number.value):input.value+' -'+flag+' '+number.value;});
     box.append(gridLabel,number);controls.append(box);
    }
    wrapper.insertBefore(controls,label);input.setAttribute('aria-label','Advanced MTN layout flags');label.textContent='Advanced MTN layout flags';
   }
   grid.append(wrapper);
  }
  if(section.section==='ImageHost')hostFields.append(...grid.children);else{details.append(grid);target.append(details);}
 }
 const save=element('div','settings-savebar'),button=element('button','button primary','Save uploader settings');button.type='submit';save.append(element('span','','One configuration for WebUI and CLI.'),button);target.append(save);
}
function collectConfigSettings(scope=document.getElementById('settings-form')){
 const changes={};for(const input of scope.querySelectorAll('[data-config-key]')){
  if(input.disabled)continue;const value=input.type==='checkbox'?String(input.checked):input.value;
  if(value===input.dataset.original||input.dataset.configType==='secret'&&!value)continue;
  const section=input.dataset.configSection;(changes[section]||={})[input.dataset.configKey]=value;
 }return changes;
}

function updateImageHostFields(){
 const host=document.getElementById('image-host').value;
 document.getElementById('image-host-key-fields').hidden=!['imgbb','imghost'].includes(host);
 document.querySelector('label[for="image-host-key"]').firstChild.textContent=(host==='imgbb'?'ImgBB':'imghost.dev')+' API key ';
 document.getElementById('image-host-help').textContent={
  dirtybytes:'Uses your DirtyBytes API key from Connect DirtyBytes. No separate image-host key is needed.',
  digitalcore:'DigitalCore’s image host is ready to use. No separate image-host key is needed.',
  imgbb:'Enter your ImgBB API key. Covers, screenshots and contact sheets will use ImgBB.',
  imghost:'Enter your imghost.dev API key.',
  custom:'Enter your upload API URL and, if required, its Authorization value below.'
 }[host]||'';
 for(const input of document.querySelectorAll('#image-host-advanced [data-config-key]')){
  const visible=input.dataset.configKey==='nsfw'?host==='imghost':host==='custom';
  input.closest('.config-field').hidden=!visible;
 }
}
document.getElementById('image-host').addEventListener('change',updateImageHostFields);

function categoryPicker(input,label,categories){
 const picker=element('div','category-picker'),chips=element('div','category-chips'),controls=element('div','category-controls');
 const select=element('select'),add=element('button','button subtle','+ Add');add.type='button';select.setAttribute('aria-label','Add category to '+label);add.setAttribute('aria-label','Add selected category to '+label);
 const selected=new Set(input.value.split(',').map(x=>x.trim()).filter(Boolean));
 const names=new Map(categories.map(row=>[String(row.id),row.name]));
 function draw(){
  chips.replaceChildren();for(const id of selected){const name=names.get(id)||'Unknown category (#'+id+')',chip=element('span','category-chip'),remove=element('button','','−');remove.type='button';remove.setAttribute('aria-label','Remove '+name+' from '+label);remove.addEventListener('click',()=>{selected.delete(id);draw();});chip.append(element('span','',name),remove);chips.append(chip);}
  if(!selected.size)chips.append(element('small','field-help','No categories selected. See the description for default behaviour.'));
  select.replaceChildren(new Option('Choose a category…',''));for(const row of categories)if(!selected.has(String(row.id)))select.append(new Option(row.name,String(row.id)));
  add.disabled=!select.value;input.value=[...selected].join(', ');
 }
 select.addEventListener('change',()=>{add.disabled=!select.value;});
 add.addEventListener('click',()=>{if(select.value){selected.add(select.value);draw();}});
 controls.append(select,add);picker.append(chips,controls);draw();return picker;
}
