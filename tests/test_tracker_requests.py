import configparser,json,unittest
from unittest.mock import MagicMock,patch
from utils.tracker_requests import TrackerRequests,request_id

class RequestClientTests(unittest.TestCase):
 def setUp(self):
  self.config=configparser.ConfigParser(interpolation=None)
  self.config.read_dict({'Website':{'SITEURL':'https://tracker.example','API_KEY':'private-fixture-key'},'Network':{'VERIFY_SSL':'true','Timeout':'12'}})
  self.client=TrackerRequests(self.config)
 def response(self,data,status=200,total='2'):
  response=MagicMock(status_code=status,headers={'X-Total-Count':total})
  response.__enter__.return_value=response;response.iter_content.return_value=[json.dumps(data).encode()]
  return response
 def test_list_uses_authenticated_bounded_pagination_without_forwarding_credentials(self):
  rows=[{'id':1,'request':'<img onerror=evil()>','filled':0,'type':25},{'id':2,'filled':1}]
  with patch('utils.tracker_requests.requests.get',return_value=self.response(rows)) as get:
   result=self.client.listing('wanted',25,50,'reward','desc')
  self.assertEqual([r['id'] for r in result['requests']],[1]);self.assertEqual(result['total'],2)
  args=get.call_args;self.assertEqual(args.args[0],'https://tracker.example/api/v1/requests/search')
  self.assertEqual(args.kwargs['params']['index'],50);self.assertEqual(args.kwargs['params']['limit'],25)
  self.assertFalse(args.kwargs['allow_redirects']);self.assertEqual(args.kwargs['headers']['X-API-KEY'],'private-fixture-key')
  self.assertEqual(result['requests'][0]['url'],'https://tracker.example/requests/1')
 def test_filled_changed_and_missing_requests_are_rejected(self):
  for row in [{'id':17,'filled':1},{'id':18,'filled':0},None]:
   with patch('utils.tracker_requests.requests.get',return_value=self.response({'request':row})):
    with self.assertRaises(ValueError):self.client.selected(17)
  with patch('utils.tracker_requests.requests.get',return_value=self.response({'request':{'id':17,'filled':0}})):
   self.assertEqual(self.client.selected(17)['id'],17)
 def test_http_errors_and_redirects_are_not_silently_treated_as_empty_lists(self):
  for code in [301,401,403,404,429,500]:
   with patch('utils.tracker_requests.requests.get',return_value=self.response([],code)):
    with self.assertRaises(ValueError) as error:self.client.listing()
    self.assertNotIn('private-fixture-key',str(error.exception))
 def test_size_limits_and_non_json_responses_stop_cleanly(self):
  for chunks in [[b'x'*(2*1024*1024+1)],[b'<html>Login</html>']]:
   response=self.response([]);response.iter_content.return_value=chunks
   with patch('utils.tracker_requests.requests.get',return_value=response):
    with self.assertRaises(ValueError):self.client.listing()
 def test_request_ids_and_sorting_are_strict(self):
  self.assertEqual(request_id('17'),17);self.assertEqual(request_id(''),0)
  for value in [-1,True,False,'1.5','12/3',2147483648,{},[]]:
   with self.assertRaises(ValueError):request_id(value)
  with self.assertRaises(ValueError):self.client.listing(sort='injected')

if __name__=='__main__':unittest.main()
