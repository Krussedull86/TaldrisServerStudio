import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import self_install
from core import reserved_ports
from server_health import query
from windows_firewall import server_ports

class InstallationTests(unittest.TestCase):
    def test_install_is_repeatable_and_launcher_tracks_updates(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);home=root/'data';home.mkdir();source=root/'download.exe';source.write_bytes(b'MZ-program')
            def atomic(path,value):Path(path).write_text(json.dumps(value))
            with patch('self_install.sys.platform','win32'),patch('self_install.sys.frozen',True,create=True),patch('self_install.sys.executable',str(source)),patch.dict(os.environ,{'LOCALAPPDATA':str(root)}),patch('self_install.register_windows') as register,patch('host_security.atomic_private',atomic):
                target=Path(self_install.install(home));self.assertEqual(target.read_bytes(),source.read_bytes());self.assertEqual(self_install.install(home),str(target));self.assertEqual(register.call_count,2)
                info=self_install.read_install(home);launcher=Path(info['launcher']);self.assertTrue(launcher.is_file())
                newer=home/'program_versions'/'dev-v99.0.0.b100'/'TaldrisServerStudio.exe';newer.parent.mkdir();newer.write_bytes(b'MZ-newer');atomic(home/'active_program.json',{'exe':str(newer)})
                self.assertEqual(self_install.install(home),str(newer))
                with patch('self_install.sys.executable',str(launcher)):self.assertEqual(self_install.launcher_target(home),newer.resolve())
                atomic(home/'active_program.json',{'exe':str(source)})
                with patch('self_install.sys.executable',str(launcher)):
                    with self.assertRaises(ValueError):self_install.launcher_target(home)
    def test_source_mode_cannot_install(self):
        with patch('self_install.sys.platform','linux'):
            with self.assertRaises(ValueError):self_install.install('unused')
    def test_conflicting_version_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);home=root/'data';home.mkdir();source=root/'download.exe';source.write_bytes(b'MZ-original')
            def atomic(path,value):Path(path).write_text(json.dumps(value))
            with patch('self_install.sys.platform','win32'),patch('self_install.sys.frozen',True,create=True),patch('self_install.sys.executable',str(source)),patch.dict(os.environ,{'LOCALAPPDATA':str(root)}),patch('self_install.register_windows'),patch('host_security.atomic_private',atomic):
                target=Path(self_install.install(home));source.write_bytes(b'MZ-changed')
                with self.assertRaises(ValueError):self_install.install(home)
                self.assertEqual(target.read_bytes(),b'MZ-original')

class LocalQueryTests(unittest.TestCase):
    def test_optional_query_never_reads_config_or_opens_socket(self):
        p=dict(root='/missing',config='missing.cfg',port=3302,query_enabled=False)
        self.assertEqual(server_ports(p),[3302,3303,3304])
        with patch('server_health.socket.socket',side_effect=AssertionError('Query must stay off')):self.assertTrue(query(p)['disabled'])
    def test_port_conflicts_remain_checked_without_query_monitoring(self):
        with tempfile.TemporaryDirectory() as folder:
            p=dict(root=folder,config='serverDZ.cfg',port=3302,query_enabled=False);path=Path(folder)/p['config']
            path.write_text('hostname="test";');self.assertEqual(reserved_ports(p),{3302,3303,3304,3305})
            path.write_text('steamQueryPort=27016;');self.assertIn(27016,reserved_ports(p));self.assertNotIn(27016,server_ports(p))
            p['query_enabled']=True;self.assertIn(27016,server_ports(p))

    def test_local_start_reaches_exe_without_query_config(self):
        from core import Manager
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manager=Manager(root/'data');p=manager.state['servers'][0];server=root/'server';server.mkdir();p.update(root=str(server),query_enabled=False)
            (server/'DayZServer_x64.exe').touch();(server/'serverDZ.cfg').write_text('hostname="Local";')
            proc=Mock(pid=812100);proc.poll.return_value=None
            with patch('core.subprocess.Popen',return_value=proc) as spawn,patch('core.directx_issue',return_value=None),patch('core.ensure_firewall') as firewall:
                manager.start(p);spawn.assert_called_once();firewall.assert_called_once();self.assertTrue(manager.running(p))
