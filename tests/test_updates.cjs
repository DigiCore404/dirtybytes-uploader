const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(),copied=[],calls=[];
function makeNode(tag='div'){const value={tag,children:[],hidden:false,value:'',href:'',disabled:false,open:false,events:{},_text:'',addEventListener(name,fn){this.events[name]=fn;},showModal(){this.open=true;},close(){this.open=false;},append(...items){this.children.push(...items);},replaceChildren(...items){this._text='';this.children=items;}};Object.defineProperty(value,'textContent',{get(){return this._text+this.children.map(c=>c.textContent).join('');},set(text){this._text=String(text);this.children=[];}});return value;}
function node(id){if(!nodes.has(id))nodes.set(id,makeNode());return nodes.get(id);}
const result={status:'available',current_version:'1.0.0',latest_version:'2.0.0',available:true,notes:'<script>not executed</script>',checked_at:'2026-01-01T00:00:00Z',installation:'docker',release_url:'https://github.com/example/uploader/releases/tag/v2.0.0',instructions:{image:'ghcr.io/example/uploader:latest',docker_commands:'docker compose pull\ndocker compose up -d',git_commands:'git fetch --tags origin',package_commands:'verified package steps'}};
const context=vm.createContext({document:{getElementById:node,createElement:makeNode,createTextNode:text=>({textContent:text})},window:{},navigator:{clipboard:{writeText:async value=>copied.push(value)}},state:{},api:async(path,body)=>{calls.push([path,body]);return result;},setTimeout:()=>1,clearTimeout:()=>{},Date});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../webui/updates.js'),'utf8'),context);
(async()=>{
 await context.window.refreshUpdates();assert.equal(node('update-banner').hidden,false);assert.equal(node('update-installed').textContent,'1.0.0');
 node('update-banner-open').events.click();assert.equal(node('update-dialog').open,true);assert.equal(node('update-notes').textContent,result.notes);
 assert.equal(node('update-commands').textContent,result.instructions.docker_commands);await node('update-copy').events.click();assert(copied[0].includes('ghcr.io/example/uploader:latest'));
 node('update-method').value='package';node('update-method').events.change();assert.equal(node('update-commands').textContent,'verified package steps');assert.equal(node('update-docker-help').hidden,true);
 node('update-close').events.click();assert.equal(node('update-dialog').open,false);
 await context.window.refreshUpdates(true);assert.equal(calls.at(-1)[0],'/api/updates/check');assert.deepEqual(JSON.parse(JSON.stringify(calls.at(-1)[1])),{});
 result.status='current';result.available=false;await context.window.refreshUpdates();assert.equal(node('update-banner').hidden,true);
 const rendered=makeNode();context.window.renderUploaderChangelog(rendered,'# History\n\n## 1.2.3\n\n- First item\n\n- Second `code` item\n\n<script>literal</script>');assert.deepEqual(rendered.children.map(c=>c.tag),['h2','h3','ul','p']);assert.equal(rendered.children[2].children.length,2);assert(rendered.textContent.includes('<script>literal</script>'));assert.equal(rendered.children[2].children[1].children[1].tag,'code');
 console.log('PASS: banner, plain-text release notes, installation-specific instructions, copying and authenticated check requests.');
})().catch(error=>{console.error(error);process.exitCode=1;});
