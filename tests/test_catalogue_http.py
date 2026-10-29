import os, tempfile, unittest
from pathlib import Path
from unittest.mock import Mock, patch
from utils import catalogue_http, catalogue_sessions, public_download

class CatalogueHttpTests(unittest.TestCase):
    def test_blvckout_parser_supplies_detail_fields_without_browser(self):
        html='''<h1>Fixture Movie</h1><a id="front-cover" href="https://images.example/cover.jpg"></a><ul><li><small>Studio:</small>Fixture Studio</li><li><small>Length:</small>1 hrs. 59 mins.</li><li><small>Released:</small>Dec 16 2014</li></ul>'''
        with patch.object(catalogue_http,'catalogue_page',return_value={'html':html,'url':'https://www.adultdvdempire.com/123/fixture.html'}):
            row=catalogue_http.fetch('https://www.adultdvdempire.com/123/fixture.html')
        self.assertEqual(row['transport'],'http')
        self.assertEqual(row['metadata']['runtime_minutes'],119)
        self.assertEqual(row['metadata']['studio'],'Fixture Studio')
        self.assertEqual(row['metadata']['release_year'],2014)

    def test_gates_stop_without_automated_acceptance(self):
        with patch.object(catalogue_http,'catalogue_page',return_value={'html':'<form id="challenge-form"></form>','url':'https://www.jeedoo.com/'}):
            with self.assertRaisesRegex(ValueError,'manual'): catalogue_http.fetch('https://www.jeedoo.com/')

    def test_session_storage_validation_replacement_and_deletion(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(catalogue_sessions,'path',return_value=Path(folder)/'cookies.json'):
            catalogue_sessions.save('adultdvdempire.com','consent=yes; session=private')
            self.assertEqual(catalogue_sessions.cookie_for('www.adultdvdempire.com'),'consent=yes; session=private')
            self.assertEqual(catalogue_sessions.cookie_for('www.jeedoo.com'),'')
            self.assertEqual(catalogue_sessions.cookie_for('evil.adultdvdempire.com'),'')
            for bad in ['Cookie: session=private','session=x\r\nAuthorization: x','invalid','']:
                with self.assertRaises(ValueError): catalogue_sessions.save('adultdvdempire.com',bad)
            with self.assertRaises(ValueError): catalogue_sessions.save('evil.invalid','session=x')
            if os.name!='nt': self.assertEqual(catalogue_sessions.path().stat().st_mode&0o777,0o600)
            catalogue_sessions.save('adultdvdempire.com','',clear=True)
            self.assertEqual(catalogue_sessions.cookie_for('www.adultdvdempire.com'),'')

    def test_cookies_only_for_catalogue_reads_and_no_cross_host_redirects(self):
        connection=Mock();response=connection.getresponse.return_value
        response.status=200;response.read.return_value=b'<h1>Fixture</h1>'
        response.getheader.side_effect=lambda name: {'Content-Type':'text/html','Content-Length':'16'}.get(name)
        with patch.object(public_download.socket,'getaddrinfo',return_value=[(0,0,0,'',('93.184.216.34',443))]),patch.object(public_download,'PinnedHTTPS',return_value=connection),patch.object(catalogue_sessions,'cookie_for',return_value='session=private'):
            public_download.catalogue_page('https://www.jeedoo.com/')
            self.assertEqual(connection.request.call_args.kwargs['headers']['Cookie'],'session=private')
            public_download.download('https://www.jeedoo.com/image.jpg')
            self.assertNotIn('Cookie',connection.request.call_args.kwargs['headers'])
            response.status=302
            response.getheader.side_effect=lambda name:'https://www.adultdvdempire.com/' if name=='Location' else ''
            before=connection.request.call_count
            with self.assertRaisesRegex(ValueError,'another host'): public_download.catalogue_page('https://www.jeedoo.com/')
            self.assertEqual(connection.request.call_count,before+1)
