import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from core import Manager,reserved_ports

class MultiServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.home=Path(self.tmp.name);self.m=Manager(self.home/'data')
    def profile(self,p,folder,query):
        root=self.home/folder;root.mkdir();p.update(root=str(root),auto_firewall=False)
        (root/'DayZServer_x64.exe').touch();(root/'serverDZ.cfg').write_text(f'steamQueryPort={query};')
    def test_new_profiles_get_non_overlapping_ports(self):
        a=self.m.state['servers'][0];b=self.m.add();c=self.m.add()
        self.assertEqual([a['port'],b['port'],c['port']],[2302,2402,2502]);self.assertFalse(reserved_ports(a)&reserved_ports(b))
    def test_two_servers_start_and_stopping_one_keeps_other(self):
        a=self.m.state['servers'][0];b=self.m.add();self.profile(a,'a',2305);self.profile(b,'b',2405)
        one=Mock(pid=812001);two=Mock(pid=812002);one.poll.return_value=None;two.poll.return_value=None
        with patch('core.subprocess.Popen',side_effect=[one,two]):self.m.start(a);self.m.start(b)
        self.assertTrue(self.m.running(a));self.assertTrue(self.m.running(b));self.m.force_stop(a);two.terminate.assert_not_called();self.assertTrue(self.m.running(b))
    def test_query_port_conflict_blocks_second_process(self):
        a=self.m.state['servers'][0];b=self.m.add();self.profile(a,'a',27016);self.profile(b,'b',27016)
        one=Mock(pid=812001);one.poll.return_value=None
        with patch('core.subprocess.Popen',return_value=one):self.m.start(a)
        with patch('core.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(ValueError,'27016'):self.m.start(b)
            spawn.assert_not_called()
