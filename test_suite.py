import copy,json,os,socket,tempfile,threading,time,unittest,zipfile
from pathlib import Path
from unittest.mock import Mock,patch
from config_documents import Document,parse_xml,xml_text,cfg_fields,cfg_set,validate_text,type_rows,edit_type,merge_types,digest
from discord_host import authorized
from host_engine import HostEngine
from host_api import AgentAPI,AgentClient
from rcon_client import packet,unpack,command

TYPES='''<?xml version="1.0"?><types><!--keep--><type name="Apple" custom="yes"><nominal>10</nominal><min>3</min><lifetime>100</lifetime><flags count_in_map="1" count_in_player="0"/><usage name="Town"/><unknown preserve="yes"/></type></types>'''

class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.p=dict(root=str(self.root),id='p');(self.root/'types.xml').write_text(TYPES)
    def test_types_preserve_unknown_fields_and_comments(self):
        edited=edit_type(TYPES,0,'nominal','20');self.assertIn('<!--keep-->',edited);self.assertIn('custom="yes"',edited);self.assertIn('<unknown preserve="yes"',edited);self.assertEqual(type_rows(edited)[0]['nominal'],'20')
        edited=edit_type(edited,0,'usage','Town; Village');self.assertEqual(type_rows(edited)[0]['usage'],'Town; Village')
        with self.assertRaises(ValueError):edit_type(edited,0,'nominal','-2')
    def test_import_duplicate_behavior(self):
        other='<types><type name="Apple"><nominal>40</nominal></type><type name="Pear"/></types>'
        text,added,skipped=merge_types(TYPES,other);self.assertEqual((added,skipped),(1,1));self.assertEqual(type_rows(text)[0]['nominal'],'10')
        text,added,skipped=merge_types(TYPES,other,True);self.assertEqual(next(r['nominal'] for r in type_rows(text) if r['name']=='Apple'),'40')
    def test_backup_conflict_and_restore_to_editor(self):
        doc=Document(self.p,'types.xml',self.root/'data');doc.text=edit_type(doc.text,0,'nominal','22');old=doc.save();self.assertEqual(Path(old).read_text(),TYPES)
        doc.restore(old);self.assertEqual(doc.text,TYPES);self.assertNotEqual((self.root/'types.xml').read_text(),TYPES)
        (self.root/'types.xml').write_text('<types/>')
        with self.assertRaises(ValueError):doc.save()
    def test_path_escape_and_entities_rejected(self):
        with self.assertRaises(ValueError):Document(self.p,'../outside.xml',self.root)
        with self.assertRaises(ValueError):parse_xml('<!DOCTYPE a [<!ENTITY x "hello">]><a>&x;</a>')
    def test_cfg_scanner_strings_comments_and_unknowns(self):
        text='// ignored = 2;\nhostname="URL https://example/;ok"; /* comment */ maxPlayers=60; class Missions {class DayZ {template="dayzOffline.test";};}; unknown[]={1,2};'
        fields=cfg_fields(text);self.assertEqual([f['key'] for f in fields],['hostname','maxPlayers','template','unknown[]']);edited=cfg_set(text,1,'120');self.assertIn('maxPlayers= 120;',edited);self.assertIn('/* comment */',edited);validate_text(edited,'.cfg')
        with self.assertRaises(ValueError):validate_text('maxPlayers=nope;','.cfg')
        with self.assertRaises(ValueError):validate_text('hostname="unterminated;','.cfg')
    def test_battleye_fields_are_line_based(self):
        text='RConPort 2406\nRConPassword secret\n';fields=cfg_fields(text);self.assertEqual(len(fields),2);self.assertEqual(fields[1]['style'],'line');validate_text(cfg_set(text,0,'3306'),'.cfg')

class RConTests(unittest.TestCase):
    def test_packet_crc_validation(self):
        self.assertEqual(unpack(packet(b'\x00secret')),b'\x00secret')
        bad=bytearray(packet(b'\x01\x00players'));bad[-1]^=1
        with self.assertRaises(ValueError):unpack(bytes(bad))
    def test_login_ack_and_multipart_out_of_order(self):
        server=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);server.bind(('127.0.0.1',0));server.settimeout(3);self.addCleanup(server.close);errors=[]
        def serve():
            try:
                data,peer=server.recvfrom(4096);self.assertEqual(unpack(data),b'\x00secret');server.sendto(packet(b'\x00\x01'),peer)
                data,peer=server.recvfrom(4096);self.assertEqual(unpack(data),b'\x01\x00players');server.sendto(packet(b'\x02\x01message'),peer);data,_=server.recvfrom(4096);self.assertEqual(unpack(data),b'\x02\x01')
                server.sendto(packet(b'\x01\x00\x00\x02\x01world'),peer);server.sendto(packet(b'\x01\x00\x00\x02\x00hello '),peer)
            except Exception as error:errors.append(error)
        thread=threading.Thread(target=serve);thread.start();self.assertEqual(command('127.0.0.1',server.getsockname()[1],'secret','players'),'hello world');thread.join();self.assertFalse(errors)

class PermissionTests(unittest.TestCase):
    def test_fail_closed_guild_server_and_owner_boundaries(self):
        settings=dict(guild_id='1',owners=['2'],roles={'read':['3'],'control':['4']},server_roles={'private':{'read':['5']}})
        self.assertTrue(authorized(settings,1,2,[],'private','restore'));self.assertFalse(authorized(settings,9,2,[],'private','restore'))
        self.assertTrue(authorized(settings,1,10,[3],'public','status'));self.assertFalse(authorized(settings,1,10,[3],'private','status'))
        self.assertFalse(authorized(settings,1,10,[4],'public','restore'));self.assertFalse(authorized(settings,1,10,[4],'public','arbitrary_shell'))

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.home=Path(self.tmp.name);self.e=HostEngine(self.home/'data');self.p=self.e.manager.state['servers'][0];self.root=self.home/'server';self.root.mkdir();self.p['root']=str(self.root);(self.root/'serverDZ.cfg').write_text('hostname="Test";steamQueryPort=2305;');self.e.manager.save()
    def test_document_save_optimistic_and_live_server_block(self):
        doc=Document(self.p,'serverDZ.cfg',self.e.home);params=dict(file='serverDZ.cfg',base=digest(doc.original),text='hostname="Changed";steamQueryPort=2305;')
        self.e.execute('document_save',self.p['id'],params);self.assertIn('Changed',(self.root/'serverDZ.cfg').read_text())
        with self.assertRaises(ValueError):self.e.execute('document_save',self.p['id'],params)
        with patch.object(self.e.manager,'running',return_value=True):
            with self.assertRaises(ValueError):self.e.execute('backup',self.p['id'],{})
    def test_restart_countdown_is_cancellable_and_manual_stop_no_recovery(self):
        with patch.object(self.e.manager,'running',return_value=True),patch.object(self.e,'rcon',return_value='OK') as rcon:
            self.e.execute('restart',self.p['id'],{'minutes':5});self.assertEqual(self.p['shutdown_request']['phase'],'countdown');self.e.execute('cancel_restart',self.p['id'],{});self.assertNotIn('shutdown_request',self.p);self.assertEqual(rcon.call_count,2)
    def test_failed_rcon_does_not_schedule_shutdown(self):
        with patch.object(self.e.manager,'running',return_value=True),patch.object(self.e,'rcon',side_effect=TimeoutError('offline')):
            with self.assertRaises(TimeoutError):self.e.execute('restart',self.p['id'],{})
        self.assertNotIn('shutdown_request',self.p)
    def test_restore_swaps_world_and_removes_added_persistence(self):
        world=self.root/'mpmissions';world.mkdir();(world/'saved.txt').write_text('old');self.e.backup(self.p);archive=next((self.e.home/'backups'/self.p['id']).glob('*.zip')).name
        (world/'saved.txt').write_text('new');(world/'extra.txt').write_text('must disappear');self.e.restore(self.p,archive);self.assertEqual((world/'saved.txt').read_text(),'old');self.assertFalse((world/'extra.txt').exists())
    def test_restore_rejects_archive_escape(self):
        folder=self.e.home/'backups'/self.p['id'];folder.mkdir(parents=True)
        with zipfile.ZipFile(folder/'bad.zip','w') as z:z.writestr('../outside.txt','no')
        with self.assertRaises(ValueError):self.e.restore(self.p,'bad.zip')
        self.assertFalse((self.home/'outside.txt').exists())
    def test_mod_rollback_keeps_local_sources(self):
        mod=self.root/'@A';old=self.root/'@A.previous';mod.mkdir();old.mkdir();(mod/'version').write_text('new');(old/'version').write_text('old');self.p['mods']=[dict(id='123',folder='@A',enabled=True),dict(id='',folder='@Dev',source='local',path=str(self.home/'@Dev'),enabled=False)]
        self.e.rollback_mods(self.p);self.assertEqual((mod/'version').read_text(),'old');self.assertEqual((old/'version').read_text(),'new')
    def test_conflicting_profile_save_rejected(self):
        with self.assertRaises(ValueError):self.e.patch_state([dict(id=self.p['id'],fields={'name':{'before':'wrong','after':'changed'}})])
        self.assertNotEqual(self.p['name'],'changed')
    def test_api_authorization_and_real_round_trip(self):
        api=AgentAPI(self.e);api.start();self.addCleanup(api.stop);client=AgentClient(self.e.home);snap=client.call('snapshot');self.assertEqual(snap['state']['servers'][0]['id'],self.p['id'])
        from urllib.request import Request,urlopen
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError):urlopen(Request('http://127.0.0.1:'+str(api.server.server_port),data=b'{"method":"snapshot"}',headers={'Authorization':'Bearer wrong'}))
        self.e.start();self.addCleanup(self.e.stop);job=client.call('enqueue',{'action':'document_save','server':self.p['id'],'data':dict(file='serverDZ.cfg',base=digest((self.root/'serverDZ.cfg').read_text()),text='hostname="API";steamQueryPort=2305;')})
        until=time.monotonic()+5
        while self.e.jobs[job['id']]['status'] not in ('completed','failed') and time.monotonic()<until:time.sleep(.02)
        self.assertEqual(self.e.jobs[job['id']]['status'],'completed')

class EditorUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    def test_tree_numeric_and_boolean_edits_and_map_coordinates(self):
        from editors_ui import ConfigCenter
        from map_workbench import MapWorkbench,coordinates
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'serverDZ.cfg').write_text('maxPlayers=60;enableWhitelist=0;');(root/'types.xml').write_text(TYPES)
            studio=Mock();studio.p=dict(root=folder,id='p',name='Test',config='serverDZ.cfg',map_size=10000,map_image='');studio.manager.home=root/'data';studio.guard=lambda fn:fn()
            center=ConfigCenter(studio);center.open_path('serverDZ.cfg');first=center.tree.topLevelItem(0);first.setText(1,'120');self.assertIn('120',center.doc.text)
            from PySide6.QtCore import Qt
            second=center.tree.topLevelItem(1);second.setCheckState(1,Qt.Checked);self.assertIn('enableWhitelist= 1;',center.doc.text)
            workbench=MapWorkbench(studio);self.assertEqual(workbench.scene_to_world(250,750),(2500,2500));self.assertEqual(workbench.world_to_scene(2500,2500),(250,750))
            xml=parse_xml('<eventposdef><event name="Car"><pos x="100" z="200" y="5" a="90"/></event></eventposdef>');points=coordinates(xml);self.assertEqual(points[0]['x'],100);self.assertEqual(points[0]['node'].get('y'),'5')
            center.deleteLater();workbench.deleteLater()

class DiscordRegistrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_register_commands_and_views_without_discord_network(self):
        import discord
        from unittest.mock import AsyncMock
        from discord_host import DiscordHost
        with tempfile.TemporaryDirectory() as folder:
            engine=HostEngine(Path(folder));engine.manager.state['discord']={'enabled':True,'guild_id':'123','owners':['456'],'channel_id':'789'};host=DiscordHost(engine);registered=[]
            async def fake_start(client,token):
                await client._async_setup_hook();await client.setup_hook();registered.extend(client.tree.get_commands(guild=discord.Object(id=123)));await client.close()
            with patch.object(discord.Client,'start',fake_start),patch('discord.app_commands.CommandTree.sync',AsyncMock(return_value=[])):
                await host.main('test-token-not-a-real-account')
            commands=registered[0].commands;self.assertIn('fillagre',[c.name for c in commands]);self.assertIn('restart',[c.name for c in commands]);self.assertIn('panel',[c.name for c in commands])

class SafetyTests(unittest.TestCase):
    setUp=EngineTests.setUp
    def test_offline_job_blocks_start_for_whole_backup(self):
        entered=threading.Event();release=threading.Event();errors=[]
        def backup(p):entered.set();release.wait(3)
        def run():
            try:self.e.backup(self.p)
            except Exception as error:errors.append(error)
        with patch.object(self.e.manager,'backup',side_effect=backup):
            thread=threading.Thread(target=run);thread.start();self.assertTrue(entered.wait(2))
            with self.assertRaisesRegex(ValueError,'jobb'):self.e.manager.start(self.p)
            release.set();thread.join()
        self.assertFalse(errors);self.assertNotIn(self.p['id'],self.e.manager.busy)
    def test_query_response_parse_and_truncation(self):
        from server_health import parse_info
        data=b'\xff\xff\xff\xffI\x11Name\x00Map\x00dayz\x00DayZ\x00\x00\x00\x05\x3c\x00'
        parsed=parse_info(data);self.assertEqual(parsed['players'],5);self.assertEqual(parsed['max_players'],60)
        with self.assertRaises(ValueError):parse_info(data[:12])
    def test_machine_secret_round_trip_does_not_enter_snapshot(self):
        from host_security import store_secrets,load_secrets
        store_secrets(self.e.home,{'discord_token':'not-a-real-token'});self.assertEqual(load_secrets(self.e.home)['discord_token'],'not-a-real-token');self.assertNotIn('not-a-real-token',json.dumps(self.e.snapshot()))

class ProvisionAndRecoveryTests(unittest.TestCase):
    setUp=EngineTests.setUp
    def test_provision_argument_order_and_independent_query_port(self):
        (self.root/'serverDZ.cfg').unlink();mission=self.root/'mpmissions'/'dayzOffline.chernarusplus';mission.mkdir(parents=True)
        self.p['max_players']=80;self.e.execute('create_config',self.p['id'],{});text=(self.root/'serverDZ.cfg').read_text();self.assertIn('maxPlayers = 80;',text);self.assertIn('steamQueryPort = 2305;',text)
    def test_clone_uses_new_game_query_and_rcon_ports_and_omits_world(self):
        be=self.root/'profiles'/'BattlEye';be.mkdir(parents=True);(be/'BEServer_x64.cfg').write_text('RConPort 2306\nRConPassword old-password\n');storage=self.root/'mpmissions'/'dayzOffline.test'/'storage_1';storage.mkdir(parents=True);(storage/'players.db').write_text('old')
        target=self.home/'test-server';result=self.e.clone(self.p,{'root':str(target),'name':'Test'});self.assertEqual(result['port'],2402);self.assertIn('2405',(target/'serverDZ.cfg').read_text());self.assertIn('2406',(target/'profiles'/'BattlEye'/'BEServer_x64.cfg').read_text());self.assertNotIn('old-password',(target/'profiles'/'BattlEye'/'BEServer_x64.cfg').read_text());self.assertFalse((target/'mpmissions'/'dayzOffline.test'/'storage_1').exists())
    def test_restore_journal_recovers_interrupted_directory_swap(self):
        from restore_transaction import write_journal,recover
        world=self.root/'mpmissions';world.mkdir();(world/'value').write_text('old');old=self.root/'mpmissions.restore-123';world.rename(old);world.mkdir();(world/'value').write_text('partial');stage=self.root/'.taldris-restore-123';stage.mkdir()
        write_journal(self.root,{'stage':stage.name,'committed':False,'entries':[{'file':'mpmissions','old':old.name,'existed':True,'done':True}]});recover(self.root);self.assertEqual((world/'value').read_text(),'old');self.assertFalse(old.exists())
    def test_state_patch_is_atomic_across_profiles(self):
        other=self.e.manager.add();before=self.p['name']
        with self.assertRaises(ValueError):self.e.patch_state([{'id':self.p['id'],'fields':{'name':{'before':before,'after':'Changed'}}},{'id':other['id'],'fields':{'name':{'before':'WRONG','after':'Oops'}}}])
        self.assertEqual(self.p['name'],before)

class UpdateIsolationTests(unittest.TestCase):
    setUp=EngineTests.setUp
    def test_agent_upgrade_waits_for_jobs_and_never_stops_dayz(self):
        self.e.api=Mock();self.e.pending_upgrade_exe='new.exe';self.e.jobs['active']={'status':'running'}
        with patch.object(self.e.manager,'force_stop') as stop:
            self.e.tick();self.e.api.call.assert_not_called();self.e.jobs['active']['status']='completed';self.e.tick();self.e.api.call.assert_called_once_with('upgrade',{'exe':'new.exe'});stop.assert_not_called()
    def test_panel_spawn_gets_independent_pyinstaller_environment(self):
        from panel_handoff import launch_handoff
        with patch('panel_handoff.sys.frozen',True,create=True),patch('panel_handoff.psutil.Process',return_value=Mock(pid=123,create_time=lambda:10)),patch('panel_handoff.subprocess.Popen') as spawn:
            launch_handoff('new.exe',self.e.home);self.assertEqual(spawn.call_args.kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'],'1')
    def test_old_active_version_does_not_redirect_a_newer_manual_exe(self):
        from panel_handoff import active_exe
        path=self.e.home/'program_versions'/'dev-v0.0.1.b1'/'TaldrisServerStudio.exe';path.parent.mkdir(parents=True);path.write_bytes(b'MZ')
        (self.e.home/'active_program.json').write_text(json.dumps({'exe':str(path)}));self.assertIsNone(active_exe(self.e.home))
