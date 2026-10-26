import copy,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from batch_import import parse_batch,read_batch,tokenize,apply_profile,fingerprint
from core import Manager,command

class ParserTests(unittest.TestCase):
    def test_common_windows_script_variables_quotes_modes_and_extra(self):
        text=r'''@echo off
set "server=D:\Program Files (x86)\Steam\steamapps\common\DayZServer"
set PORT=2302
cd /d "%server%"
start "taldris test" DayZServer_x64.exe ^
 -config=serverDZ_taldris.cfg -port=%port% -profiles=SC ^
 "-mod=@CF;@My Mod;@Weather" -servermods=@Weather -name=Developer -cpuCount=4 -dologs -adminlog -freezecheck
 timeout /t 60
goto loop
'''
        report=parse_batch(text,r'C:\scripts\start.bat');p=report['candidates'][0]['profile']
        self.assertEqual(p['root'],r'D:\Program Files (x86)\Steam\steamapps\common\DayZServer');self.assertEqual(p['config'],'serverDZ_taldris.cfg');self.assertEqual(p['port'],2302);self.assertEqual(p['profiles'],'SC');self.assertEqual(len(p['mods']),3)
        self.assertEqual(p['mods'][2]['load_mode'],'both');self.assertTrue(all(m['source']=='local' and m['id']=='' for m in p['mods']));self.assertIn('-cpuCount=4',p['extra_args']);self.assertTrue(report['warnings'])
    def test_dp0_start_directory_title_and_multiple_starts(self):
        text=r'''set "dir=%~dp0server"
start /D "%dir%" "One" DayZServer_x64.exe -port=2302 -config=serverDZ.cfg
cd /d "%dir%"
"%dir%\DayZServer_x64.exe" -port=2402 -config=other.cfg
'''
        report=parse_batch(text,r'C:\setup\start.cmd');self.assertEqual(len(report['candidates']),2)
        self.assertEqual(report['candidates'][0]['profile']['root'],r'C:\setup\server');self.assertEqual(report['candidates'][1]['profile']['port'],2402)
    def test_unsafe_dynamic_lines_are_not_evaluated(self):
        report=parse_batch(r'''powershell -Command "Remove-Item anything"
if exist something (
set ROOT=C:\wrong
start "hidden" DayZServer_x64.exe
)
cd /d C:\server
start "real" DayZServer_x64.exe -config=serverDZ.cfg -foo=ignored -name=%UNKNOWN%
''',r'C:\setup\start.bat')
        self.assertEqual(len(report['candidates']),1);self.assertTrue(report['warnings']);self.assertIn('Uløste',str(report['candidates'][0]['warnings']));self.assertIn('Ikke importert',str(report['candidates'][0]['warnings']))
    def test_external_config_and_unknown_start_switch_are_reported(self):
        report=parse_batch(r'''cd /d C:\server
start "a" DayZServer_x64.exe -config=D:\config\serverDZ.cfg
start /affinity FF "b" DayZServer_x64.exe
''',r'C:\start.bat')
        self.assertIn('utenfor',str(report['candidates'][0]['warnings']));self.assertTrue(report['warnings'])
    def test_argv_roundtrip_with_spaces_backslashes_and_empty_title(self):
        args=['',r'C:\Program Files\Server\DayZServer_x64.exe','-mod=@My Mod;@CF',r'-BEpath=C:\Server\BattlEye','-name=Developer']
        self.assertEqual([t[0] for t in tokenize(subprocess.list2cmdline(args))],args)
    def test_encodings_and_size_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'start.bat';p.write_bytes('start "Norsk æøå" DayZServer_x64.exe'.encode('utf-16'));self.assertEqual(read_batch(p)['candidates'][0]['profile']['name'],'Norsk æøå')
            p.write_bytes(b'x'*(1024*1024+1))
            with self.assertRaises(ValueError):read_batch(p)

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.manager=Manager(self.root/'data');self.server=self.root/'server';self.server.mkdir();(self.server/'DayZServer_x64.exe').write_bytes(b'MZ-test');(self.server/'serverDZ.cfg').write_text('hostname="Existing";maxPlayers=80;');(self.server/'world.keep').write_text('unchanged')
        self.data=dict(name='Imported',root=str(self.server),config='serverDZ.cfg',profiles='SC',port=2302,mods=[],extra_args=['-name=Test','-filePatching'],query_enabled=False,auto_firewall=False)
    def test_import_creates_only_profile_and_retains_exact_server_files(self):
        before={str(p.relative_to(self.server)):p.read_bytes() for p in self.server.rglob('*') if p.is_file()}
        with patch('subprocess.Popen',side_effect=AssertionError('No process allowed')):
            p=apply_profile(self.manager,self.data)
        self.assertEqual(len(self.manager.state['servers']),2);self.assertEqual(p['max_players'],80);self.assertIn('-filePatching',command(p));self.assertEqual(before,{str(p.relative_to(self.server)):p.read_bytes() for p in self.server.rglob('*') if p.is_file()});self.assertFalse((self.server/'SC').exists())
    def test_replace_preserves_identity_and_unrelated_settings(self):
        old=self.manager.state['servers'][0];old['backup_keep']=17;old['steam_user']='ExistingSteam'
        p=apply_profile(self.manager,self.data,old['id'],fingerprint(old));self.assertEqual(p['id'],old['id']);self.assertEqual(p['backup_keep'],17);self.assertEqual(p['steam_user'],'ExistingSteam');self.assertEqual(len(self.manager.state['servers']),1)
    def test_stale_active_and_invalid_imports_are_atomic(self):
        old=self.manager.state['servers'][0];before=copy.deepcopy(self.manager.state)
        with self.assertRaises(ValueError):apply_profile(self.manager,self.data,old['id'],'stale')
        with patch.object(self.manager,'running',return_value=True):
            with self.assertRaises(ValueError):apply_profile(self.manager,self.data,old['id'],fingerprint(old))
        for updates in [{'extra_args':['-config=elsewhere']},{'config':'../escape.cfg'},{'root':str(self.root/'missing')},{'extra_args':['-cpuCount=bad']}]:
            with self.assertRaises(ValueError):apply_profile(self.manager,{**self.data,**updates})
        self.assertEqual(before,self.manager.state)
    def test_persistence_failure_restores_existing_profile(self):
        old=self.manager.state['servers'][0];before=copy.deepcopy(old)
        with patch.object(self.manager,'save',side_effect=OSError('disk error')):
            with self.assertRaises(OSError):apply_profile(self.manager,self.data,old['id'],fingerprint(old))
        self.assertEqual(old,before)
    def test_import_through_authenticated_loopback_api(self):
        from host_engine import HostEngine
        from host_api import AgentAPI,AgentClient
        engine=HostEngine(self.root/'agent');api=AgentAPI(engine);api.start();self.addCleanup(api.stop)
        client=AgentClient(engine.home);p=client.call('import_batch',{'profile':self.data});self.assertEqual(p['name'],'Imported');self.assertEqual(len(client.call('snapshot')['state']['servers']),2)

class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    def test_preview_corrects_fields_and_commits_only_after_review(self):
        from PySide6.QtWidgets import QWidget,QMessageBox
        from batch_import_ui import BatchImportDialog
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();server=root/'server';server.mkdir();(server/'DayZServer_x64.exe').touch();cfg=server/'serverDZ.cfg';cfg.write_text('hostname="Existing";');mod=server/'@Dev';(mod/'addons').mkdir(parents=True);(mod/'addons'/'dev.pbo').touch()
            path=root/'start.bat';path.write_text('cd /d "'+str(server)+'"\nstart "Test" DayZServer_x64.exe -config=serverDZ.cfg -mod=@Dev -serverMod=@Dev -name=Test')
            studio=QWidget();studio.manager=Manager(root/'data');dialog=BatchImportDialog(studio,path)
            self.assertEqual(dialog.mods.rowCount(),1);self.assertEqual(dialog.mods.cellWidget(0,2).currentData(),'both');self.assertEqual(dialog.mods.item(0,3).text(),'Finnes');self.assertTrue(dialog.local.isChecked());self.assertEqual(len(studio.manager.state['servers']),1)
            dialog.fields['name'].setText('Reviewed')
            with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):dialog.commit()
            self.assertEqual(dialog.result_profile['name'],'Reviewed');self.assertEqual(len(studio.manager.state['servers']),2);self.assertEqual(cfg.read_text(),'hostname="Existing";');self.assertTrue(mod.is_dir());dialog.deleteLater();studio.deleteLater()
