import tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from client_launch import client_mods,command,find_game,launch

class ClientLaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.game=self.root/'Steam Library/steamapps/common/DayZ';self.game.mkdir(parents=True)
        for name in ('DayZ_x64.exe','DayZ_BE.exe'):(self.game/name).touch()
        self.p=dict(name='Test',port=2310,root=str(self.root/'server'),mods=[])
    def mod(self,name,**kwargs):
        m=dict(folder='@'+name,title=name,enabled=True,load_mode='client',**kwargs);self.p['mods'].append(m);return m
    def test_profile_order_modes_and_absolute_paths(self):
        for name,mode in [('One','client'),('Two','server'),('Three','both')]:
            m=self.mod(name);m['load_mode']=mode;(Path(self.p['root'])/m['folder']/'Addons').mkdir(parents=True)
        m=self.mod('Disabled');m['enabled']=False
        mods=client_mods(self.p,self.game,[]);self.assertEqual([m['title'] for m in mods],['One','Three'])
        args=command(self.game,self.p,mods);self.assertEqual(args[:6],[str(self.game/'DayZ_BE.exe'),'0','1','1','-exe','DayZ_x64.exe']);self.assertIn('-connect=127.0.0.1',args);self.assertIn('-port=2310',args);self.assertEqual(len([a for a in args if a.startswith('-mod=')]),1);self.assertNotIn('-servermod=',str(args));self.assertIn(str(Path(self.p['root'])/'@Three'),args[-1])
    def test_local_developer_mod_and_workshop_fallback(self):
        local=self.root/'development/@My mod';(local/'Addons').mkdir(parents=True);self.mod('Developer',source='local',path=str(local));self.mod('Workshop',id='123')
        workshop=self.root/'Steam Library/steamapps/workshop/content/221100/123';(workshop/'addons').mkdir(parents=True)
        mods=client_mods(self.p,self.game,[self.root/'Steam Library']);self.assertEqual([m['path'] for m in mods],[str(local),str(workshop)])
    def test_missing_and_explicit_override_do_not_silently_omit_mods(self):
        self.mod('Required',id='123');mods=client_mods(self.p,self.game,[])
        with self.assertRaisesRegex(ValueError,'Mangler klientmod'):command(self.game,self.p,mods)
        explicit=self.root/'mod';(explicit/'addons').mkdir(parents=True);mods=client_mods(self.p,self.game,[],{'123':str(explicit)});self.assertIn(str(explicit),command(self.game,self.p,mods)[-1])
        explicit.rename(self.root/'gone')
        with self.assertRaises(ValueError):command(self.game,self.p,mods)
    def test_find_client_and_launch_in_desktop_with_game_id(self):
        self.assertEqual(find_game([self.root/'Steam Library']),str(self.game));args=command(self.game,self.p,[])
        with patch('client_launch.subprocess.Popen',return_value=Mock(pid=123)) as spawn:launch(args)
        self.assertEqual(spawn.call_args.args[0],args);self.assertEqual(spawn.call_args.kwargs['env']['SteamAppId'],'221100');self.assertEqual(spawn.call_args.kwargs['cwd'],str(self.game))
    def test_reject_server_folder_and_missing_battleye(self):
        with self.assertRaises(ValueError):command(self.root,self.p,[])
        (self.game/'DayZ_BE.exe').unlink()
        with self.assertRaises(ValueError):command(self.game,self.p,[])
    def test_dialog_displays_selected_profile_mods(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication,QWidget
        from client_launch_ui import ClientDialog
        app=QApplication.instance() or QApplication([]);studio=QWidget();studio.p=self.p;studio.manager=Mock(home=self.root);studio.guard=lambda fn:fn()
        self.mod('Missing')
        with patch('client_launch_ui.steam_roots',return_value=[self.root/'Steam Library']):
            dialog=ClientDialog(studio);self.assertIn('Test',dialog.windowTitle());self.assertEqual(dialog.table.rowCount(),1);self.assertIn('MANGLER',dialog.table.item(0,1).text());dialog.close();dialog.deleteLater()
