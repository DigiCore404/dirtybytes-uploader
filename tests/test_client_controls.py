"""Client controls use exact hashes; cleanup stays opt-in and protects shared payloads."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils.job_history import JobHistory
from utils.qbit_clients import QbitClients,tracker_host
from utils.client_cleanup import eligible,policy_values,shared_payload
from utils.metadata_text import plain_description
from utils.publication_title import post_title
HASH='a'*40

class ClientControlTests(unittest.TestCase):
 def setUp(self):
  (ROOT/'tmp').mkdir(exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp');self.addCleanup(self.temp.cleanup)
  self.history=JobHistory(Path(self.temp.name)/'state.db');self.clients=QbitClients(self.history)
  self.id=self.clients.save({'name':'Disposable fake client','url':'http://127.0.0.1:18999','username':'test','password':'test-only'})
  self.row=dict(hash=HASH,name='Demo',state='stalledUP',progress=1,size=900,amount_left=0,seeding_time=7200,num_complete=8,num_incomplete=3,num_seeds=2,num_leechs=1,tracker='https://tracker.example/secret/announce',content_path='/media/Demo.mkv',save_path='/media',category='demo')
  self.rows=[self.row];self.posts=[];self.version='v5.1.2';self.session=Mock();self.session.__enter__=Mock(return_value=self.session);self.session.__exit__=Mock(return_value=False)
  def get(url,params=None,**kwargs):
   if url.endswith('/trackers'):value=[{'url':self.row['tracker'],'status':2,'num_seeds':8,'num_leeches':3},{'url':'** [DHT] **','status':0}]
   else:value=[copy.deepcopy(r) for r in self.rows if not params or not params.get('hashes') or r['hash']==params['hashes']]
   return Mock(status_code=200,json=Mock(return_value=value))
  def post(url,data,**kwargs):
   self.posts.append((url,data))
   if url.endswith('/delete'):self.rows=[]
   return Mock(status_code=200)
  self.session.get.side_effect=get;self.session.post.side_effect=post
  self.patcher=patch.object(self.clients,'_session',side_effect=lambda client:(self.session,self.version));self.patcher.start();self.addCleanup(self.patcher.stop)
  self.assertTrue(self.clients.sync(self.id)['ok'])
 def action(self,action,**kwargs):return self.clients.action(self.id,HASH,action,**kwargs)
 def test_snapshot_peers_and_tracker_hide_passkeys(self):
  row=self.clients.torrents()['torrents'][0]
  self.assertEqual((row['num_seeds'],row['num_complete'],row['num_leechs'],row['num_incomplete']),(2,8,1,3))
  self.assertEqual(row['tracker'],'tracker.example')
  details=self.clients.details(self.id,HASH);self.assertEqual(details['trackers'][0]['host'],'tracker.example');self.assertNotIn('secret',json.dumps(details))
 def test_all_non_delete_actions_target_one_hash(self):
  for version,pause,resume in [('v5.1.2','stop','start'),('v4.6.9','pause','resume')]:
   self.version=version
   for action,method in [('pause',pause),('resume',resume),('recheck','recheck'),('reannounce','reannounce'),('force_start','setForceStart')]:
    self.action(action);url,data=self.posts[-1];self.assertTrue(url.endswith('/'+method));self.assertEqual(data['hashes'],HASH)
 def test_delete_requires_exact_confirmation_and_keeps_data_by_default(self):
  for bad in ('','b'*40):
   with self.assertRaises(ValueError):self.action('delete',confirm_hash=bad)
  with self.assertRaises(ValueError):self.action('delete',confirm_hash=HASH,delete_data='false')
  self.assertEqual(self.posts,[])
  self.action('delete',confirm_hash=HASH);self.assertEqual(self.posts[-1][1],{'hashes':HASH,'deleteFiles':'false'})
 def test_delete_cancels_pending_delivery_without_readding(self):
  from utils.delivery_queue import DeliveryQueue
  queue=DeliveryQueue(self.history,self.clients)
  with self.history.connect() as db:
   db.execute("INSERT INTO confirmed_deliveries VALUES(?,?,?,?,?,?,?,?,?,?,?)",('test',None,'/media/Demo.mkv','/watch/test.torrent',HASH,self.id,'/media','/media','pending',None,0))
  self.action('delete',confirm_hash=HASH)
  queue.attempt('test')
  with self.history.connect() as db:self.assertEqual(db.execute("SELECT state FROM confirmed_deliveries WHERE id='test'").fetchone()[0],'cancelled')
  self.assertEqual(len(self.posts),1)

 def test_explicit_data_delete(self):
  self.action('delete',confirm_hash=HASH,delete_data=True);self.assertEqual(self.posts[-1][1]['deleteFiles'],'true')
 def test_invalid_bulk_or_stale_torrent_never_posts(self):
  for value in ('all',HASH+'|'+'b'*40):
   with self.assertRaises(ValueError):self.clients.action(self.id,value,'pause')
  self.rows=[]
  with self.assertRaises(ValueError):self.action('recheck')
  self.assertFalse(self.posts)
 def rule(self,**values):return dict(enabled=True,delete_data=False,seed_hours=1,min_seeders=5,match='all',category='',tracker='',confirmed=True,**values)
 def test_default_disabled_confirmation_and_readonly_preview(self):
  self.assertFalse(self.clients.cleanup.get(self.id)['enabled']);self.clients.cleanup.run();self.assertFalse(self.posts)
  rule=self.rule();rule['confirmed']=False
  with self.assertRaises(ValueError):self.clients.cleanup.save(self.id,rule)
  result=self.clients.cleanup.preview(self.id,rule);self.assertEqual(result['count'],1);self.assertFalse(self.posts)
 def test_cleanup_completion_thresholds_scopes_and_unknown_peers(self):
  rule=self.rule();self.assertTrue(eligible(self.row,rule))
  for key,value in [('progress',.99),('progress',float('nan')),('state','checkingUP'),('amount_left',1),('num_complete',-1),('seeding_time',3599)]:
   row={**self.row,key:value};self.assertFalse(eligible(row,rule),(key,value))
  self.assertFalse(eligible(self.row,{**rule,'category':'other'}));self.assertFalse(eligible(self.row,{**rule,'tracker':'other.example'}))
  self.assertTrue(eligible({**self.row,'num_complete':-1},{**rule,'match':'any'}))
  with self.assertRaises(ValueError):policy_values({**rule,'seed_hours':0,'min_seeders':0})
 def test_shared_data_and_uncertain_deletion_do_not_retry(self):
  self.assertTrue(shared_payload(self.row,[self.row,{'hash':'b'*40,'content_path':'/media'}]))
  self.assertTrue(shared_payload(self.row,[{'hash':'b'*40}]))
  self.assertFalse(shared_payload(self.row,[self.row,{'hash':'b'*40,'content_path':'/media/Other.mkv'}]))
  rule=self.clients.cleanup.save(self.id,self.rule());self.session.post.side_effect=RuntimeError('uncertain timeout')
  self.clients.cleanup.run_client({'id':self.id},rule);self.clients.cleanup.run_client({'id':self.id},rule)
  self.assertEqual(self.session.post.call_count,1);self.assertEqual(self.clients.cleanup.events()[0]['state'],'needs_review')
 def test_auto_data_removal_skips_overlap(self):
  self.rows.append({**self.row,'hash':'b'*40,'content_path':'/media'})
  rule=self.clients.cleanup.save(self.id,{**self.rule(),'delete_data':True});self.clients.cleanup.run_client({'id':self.id},rule);self.assertFalse(self.posts)
 def test_successful_cleanup_is_audited(self):
  rule=self.clients.cleanup.save(self.id,self.rule());self.clients.cleanup.run_client({'id':self.id},rule)
  self.assertEqual(self.posts[-1][1]['deleteFiles'],'false');self.assertEqual(self.clients.cleanup.events()[0]['state'],'removed')

 def test_tracker_filter_covers_all_pages_and_combines_with_other_filters(self):
  with self.history.connect() as db:
   original=dict(db.execute('SELECT * FROM qbit_torrents LIMIT 1').fetchone());db.execute('DELETE FROM qbit_torrents')
   for index in range(63):
    row={**original,'hash':format(index,'040x'),'name':'Demo '+str(index),'tracker':'tracker.example' if index<60 else 'other.example','status':'seeding' if index%2==0 else 'paused'}
    db.execute('INSERT INTO qbit_torrents('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))
  result=self.clients.torrents(tracker='tracker.example',limit=10,offset=50)
  self.assertEqual(result['total'],60);self.assertEqual(len(result['torrents']),10);self.assertEqual(result['trackers'],['other.example','tracker.example'])
  self.assertTrue(all(r['tracker']=='tracker.example' for r in result['torrents']))
  self.assertEqual(self.clients.torrents(tracker='other.example',status='seeding',client_id=self.id)['total'],2)
  self.assertEqual(self.clients.torrents(tracker="tracker.example' OR 1=1 --")['total'],0)
  self.assertEqual(self.clients.torrents()['total'],63)

 def test_multiple_rules_keep_scope_edit_delete_and_priority(self):
  first=self.clients.cleanup.save(self.id,{**self.rule(),'new_rule':True,'name':'Keep data','tracker':'tracker.example'})
  second=self.clients.cleanup.save(self.id,{**self.rule(),'new_rule':True,'name':'Other tracker','tracker':'other.example','delete_data':True})
  self.assertEqual(len(self.clients.cleanup.list(self.id)),2)
  self.assertEqual(self.clients.cleanup.first_match(self.id,self.row)['id'],first['id'])
  edited=self.clients.cleanup.save(self.id,{**self.rule(),'rule_id':second['id'],'name':'Later matching rule','tracker':'tracker.example','delete_data':True})
  self.assertEqual(edited['id'],second['id']);self.clients.cleanup.run_client({'id':self.id},edited);self.assertFalse(self.posts)
  self.clients.cleanup.run_client({'id':self.id},first);self.assertEqual(self.posts[-1][1]['deleteFiles'],'false')
  self.clients.cleanup.remove(self.id,second['id']);self.assertEqual(len(self.clients.cleanup.list(self.id)),1)
  self.assertEqual(self.clients.cleanup.events()[0]['rule_name'],'Keep data')
 def test_legacy_rule_migration_preserves_enabled_scope_and_is_not_recreated(self):
  with self.history.connect() as db:
   db.execute("DELETE FROM client_cleanup_meta WHERE key='multiple_rules'")
   db.execute("CREATE TABLE client_cleanup_rules(client_id TEXT PRIMARY KEY,enabled INTEGER,delete_data INTEGER,seed_hours REAL,min_seeders INTEGER,match TEXT,category TEXT,tracker TEXT,updated REAL)")
   db.execute('INSERT INTO client_cleanup_rules VALUES(?,?,?,?,?,?,?,?,?)',(self.id,1,0,48,4,'all','uploads','tracker.example',123))
  from utils.client_cleanup import CleanupRules
  migrated=CleanupRules(self.clients);rule=migrated.get(self.id);self.assertTrue(rule['enabled']);self.assertEqual(rule['category'],'uploads');self.assertEqual(rule['tracker'],'tracker.example');self.assertEqual(rule['seed_hours'],48)
  migrated.remove(self.id,rule['id']);self.assertFalse(CleanupRules(self.clients).list(self.id))
 def test_category_default_persists_and_only_applies_to_confirmed_delivery(self):
  client=self.clients._client(self.id)
  self.clients.save({**client,'default_category':'uploaded-by-test'})
  categories={};posts=[]
  def get(url,params=None,**kwargs):
   value=categories if url.endswith('/categories') else []
   return Mock(status_code=200,json=Mock(return_value=value))
  def post(url,data,**kwargs):
   posts.append((url,data))
   if url.endswith('/createCategory'):categories[data['category']]={'name':data['category']}
   return Mock(status_code=200,content=b'Ok.')
  self.session.get.side_effect=get;self.session.post.side_effect=post
  self.clients.add_torrent(self.id,'b'*40,'/media',raw=b'fixture')
  self.assertNotIn('category',posts[-1][1]);self.assertFalse(categories)
  self.clients.add_torrent(self.id,'c'*40,'/media',raw=b'fixture',use_default_category=True)
  self.assertIn('uploaded-by-test',categories);self.assertEqual(posts[-1][1]['category'],'uploaded-by-test');self.assertEqual(posts[-1][1]['autoTMM'],'false');self.assertEqual(posts[-1][1]['savepath'],'/media')
  self.assertEqual(self.clients._client(self.id)['default_category'],'uploaded-by-test')

class MetadataTextTests(unittest.TestCase):
 def test_provider_html_preserves_paragraphs(self):
  self.assertEqual(plain_description('<p>First <b>paragraph</b>.</p> <p>Second &amp; last.</p>'),'First paragraph.\n\nSecond & last.')
 def test_encoded_html_and_hidden_content(self):
  self.assertEqual(plain_description('&lt;p&gt;One&lt;/p&gt;&lt;p&gt;Two&lt;/p&gt;'),'One\n\nTwo')
  self.assertEqual(plain_description('<p>Visible<br>line</p><script>hidden()</script><style>hidden</style>'),'Visible\nline')
 def test_bbcode_and_plain_text_remain_text(self):
  self.assertEqual(plain_description('[b]Hello[/b]\n\nWorld'),'[b]Hello[/b]\n\nWorld')
 def test_post_title_validation(self):
  self.assertEqual(post_title(' Film (2026) '),'Film (2026)');self.assertEqual(post_title(None),'')
  for value in ('../bad','bad\\path','bad\nheader','x'*201,{}):
   with self.assertRaises(ValueError):post_title(value)

if __name__=='__main__':unittest.main()
