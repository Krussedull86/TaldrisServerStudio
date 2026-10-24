import io,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import steam_services as svc
from core import Manager
class SteamTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.home=Path(self.temp.name); self.m=Manager(self.home/'data'); self.p=self.m.state['servers'][0]; self.p['root']=str(self.home/'server files'); self.p['steamcmd']=str(self.home/'steamcmd.exe')
    def test_anonymous_and_account_arguments(self):
        args=svc.steam_arguments(self.p,'all',['1559212036']); self.assertEqual(args[args.index('+login')+1],'anonymous'); self.assertIn('223350',args); self.assertIn('221100',args)
        self.p.update(login_mode='account',steam_user='kjell_test'); args=svc.steam_arguments(self.p,'server'); self.assertEqual(args[args.index('+login')+1],'kjell_test'); self.assertNotIn('password',args)
        self.p['steam_user']='+quit'
        with self.assertRaises(ValueError):svc.steam_arguments(self.p,'server')
    def test_ids(self):
        self.assertEqual(svc.workshop_id('https://steamcommunity.com/sharedfiles/filedetails/?id=1559212036'),'1559212036')
        for value in ['0','123;quit','https://bad.example/?id=123','../123']:
            with self.assertRaises(ValueError):svc.workshop_id(value)
    def test_success_is_not_exit_code_only(self):
        self.assertFalse(svc.result_summary('', 'server',[],0)[0]); self.assertFalse(svc.result_summary("Success! App '223350' fully installed.",'server',[],0,False)[0])
        self.assertTrue(svc.result_summary("Success! App '223350' fully installed.",'server',[],0)[0])
        self.assertFalse(svc.result_summary("Success! App '223350' fully installed. ERROR! No subscription",'server',[],0)[0])
        output="Success! App '223350' fully installed.\nSuccess. Downloaded item 123 to \"C:/mods/123\" (10 bytes)"
        self.assertTrue(svc.result_summary(output,'all',['123'],0)[0]); self.assertFalse(svc.result_summary(output,'all',['123','456'],0)[0])
    def test_bootstrap_and_traversal(self):
        def archive(name):
            data=io.BytesIO()
            with zipfile.ZipFile(data,'w') as z:z.writestr(name,b'MZfake exe')
            return data.getvalue()
        target=self.home/'steam'; exe=svc.install_steamcmd(target,fetch=lambda *a,**kw:archive('steamcmd.exe')); self.assertEqual(Path(exe).read_bytes(),b'MZfake exe')
        self.assertEqual(svc.install_steamcmd(target,fetch=lambda *a,**kw:(_ for _ in ()).throw(AssertionError('must reuse'))),exe)
        with self.assertRaises(ValueError):svc.install_steamcmd(self.home/'bad',fetch=lambda *a,**kw:archive('../steamcmd.exe'))
        self.assertFalse((self.home/'steamcmd.exe').exists())
    def test_provision_never_overwrites(self):
        (Path(self.p['root'])/'mpmissions'/'dayzOffline.chernarusplus').mkdir(parents=True)
        path=svc.provision(self.p,'New DayZ',40,'dayzOffline.chernarusplus'); self.assertIn('New DayZ',Path(path).read_text())
        with self.assertRaises(ValueError):svc.provision(self.p,'Other',10,'dayzOffline.chernarusplus')
        self.assertIn('New DayZ',Path(path).read_text())
    def test_config_injection_and_missing_mission(self):
        with self.assertRaises(ValueError):svc.provision(self.p,'New',40,'../bad')
        with self.assertRaises(ValueError):svc.cfg_string('evil"; password="oops')
        with self.assertRaises(ValueError):svc.provision(self.p,'New',40,'does_not_exist')
    def test_browse_parser(self):
        parser=svc.BrowseParser(); parser.feed('<div class="workshopItem"><a href="https://steamcommunity.com/sharedfiles/filedetails/?id=123"><img src="preview"></a><a href="https://steamcommunity.com/sharedfiles/filedetails/?id=123"><div class="workshopItemTitle">Test &amp; Mod</div></a></div>'); self.assertEqual(parser.items,[{'id':'123','title':'Test & Mod'}])
    def test_current_valve_ssr_search(self):
        state={'queries':[{'state':{'data':dict(current_page=1,total_count=2,results=[dict(publishedfileid='123',consumer_appid=221100,file_type=0),dict(publishedfileid='456',consumer_appid=730,file_type=0)])}}]}
        raw='<script type="application/json" id="valve-ssr-data">'+json.dumps({'renderContext':{'queryData':json.dumps(state)}})+'</script>'
        self.assertEqual(svc.browse_ids(raw),['123'])
        state['queries'][0]['state']['data'].update(results=[],total_count=0)
        raw='<script id="valve-ssr-data">'+json.dumps({'renderContext':{'queryData':json.dumps(state)}})+'</script>'
        self.assertEqual(svc.browse_ids(raw),[])
    def test_wrong_game_and_private_items_rejected(self):
        for item in [dict(publishedfileid='123',result=1,consumer_app_id=730),dict(publishedfileid='123',result=9)]:
            with patch.object(svc,'api',return_value={'publishedfiledetails':[item]}):
                with self.assertRaises(ValueError):svc.details(['123'])
    def test_collection_order_preserved(self):
        calls=[]
        def response(method,params):
            if method=='GetCollectionDetails':return {'collectiondetails':[dict(result=1,children=[dict(publishedfileid='12'),dict(publishedfileid='11')])]}
            ids=[str(v) for k,v in params.items() if k.startswith('publishedfileids')]
            return {'publishedfiledetails':[dict(publishedfileid=w,result=1,consumer_app_id=221100,title=w,file_type=2 if w=='100' else 0) for w in ids]}
        with patch.object(svc,'api',side_effect=response):self.assertEqual([x['id'] for x in svc.collection('100')],['12','11'])
if __name__=='__main__':unittest.main()
