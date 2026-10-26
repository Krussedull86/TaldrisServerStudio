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
    def shared_profiles(self):
        a=self.m.state['servers'][0];b=self.m.add();root=self.home/'shared';root.mkdir();(root/'DayZServer_x64.exe').touch()
        for p,cfg,profiles,query,instance in [(a,'a.cfg','profiles/a',2305,1),(b,'b.cfg','profiles/b',2405,2)]:
            p.update(root=str(root),config=cfg,profiles=profiles,auto_firewall=False)
            (root/cfg).write_text(f'steamQueryPort={query};instanceId={instance};class Missions {{class DayZ {{template="dayzOffline.test";}};}};')
        one=Mock(pid=812001);two=Mock(pid=812002);one.poll.return_value=None;two.poll.return_value=None
        return a,b,root,one,two
    def test_shared_exe_starts_two_independent_instances(self):
        a,b,root,one,two=self.shared_profiles()
        with patch('core.subprocess.Popen',side_effect=[one,two]):self.m.start(a);self.m.start(b)
        self.assertTrue(self.m.running(a));self.assertTrue(self.m.running(b));self.m.force_stop(b);one.terminate.assert_not_called()
    def test_shared_world_and_profiles_conflicts_have_specific_errors(self):
        a,b,root,one,two=self.shared_profiles()
        with patch('core.subprocess.Popen',return_value=one):self.m.start(a)
        text=(root/'b.cfg').read_text();(root/'b.cfg').write_text(text.replace('instanceId=2','instanceId=1'))
        with patch('core.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(ValueError,'Verdensdata-konflikt'):self.m.start(b)
            spawn.assert_not_called()
        (root/'b.cfg').write_text(text);b['profiles']=a['profiles']
        with self.assertRaisesRegex(ValueError,'Profiles-konflikt'):self.m.start(b)
    def test_shared_mission_start_never_rewrites_running_messages(self):
        a,b,root,one,two=self.shared_profiles();db=root/'mpmissions/dayzOffline.test/db';db.mkdir(parents=True);messages=db/'messages.xml';messages.write_text('<messages><!--keep--></messages>')
        with patch('core.subprocess.Popen',side_effect=[one,two]):self.m.start(a);self.m.start(b)
        self.assertEqual(messages.read_text(),'<messages><!--keep--></messages>')
    def test_shared_mission_plan_and_file_maintenance_still_block(self):
        a,b,root,one,two=self.shared_profiles()
        with patch('core.subprocess.Popen',return_value=one):self.m.start(a)
        b['scheduled_restart']=True
        with self.assertRaisesRegex(ValueError,'Restartplanen'):self.m.start(b)
        b['scheduled_restart']=False;self.m.busy.add(a['id'])
        with self.assertRaisesRegex(ValueError,'filvedlikehold'):self.m.start(b)
