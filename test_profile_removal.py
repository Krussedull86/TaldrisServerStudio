import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from host_engine import HostEngine
from batch_import import fingerprint

class ProfileRemovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.engine=HostEngine(self.root/'data');self.p=self.engine.manager.state['servers'][0];self.p['root']=str(self.root/'server');Path(self.p['root']).mkdir();(Path(self.p['root'])/'world.keep').write_text('keep');self.engine.manager.save()
    def test_delete_keeps_disk_and_other_running_server(self):
        e=self.engine;q=e.manager.add();proc=Mock(pid=12345);proc.poll.return_value=None;e.manager.procs[q['id']]=proc;e.retries[self.p['id']]=1
        result=e.remove_profile(self.p['id'],fingerprint(self.p));self.assertEqual(result['selected'],q['id']);self.assertEqual((Path(self.p['root'])/'world.keep').read_text(),'keep');self.assertIs(e.manager.state['servers'][0],q);self.assertTrue(e.manager.running(q));proc.terminate.assert_not_called();self.assertNotIn(self.p['id'],e.retries)
    def test_last_delete_creates_only_blank_profile_and_persists(self):
        e=self.engine;identity=self.p['id'];e.remove_profile(identity,fingerprint(self.p));q=e.manager.state['servers'][0];self.assertNotEqual(q['id'],identity);self.assertEqual(q['root'],'');self.assertFalse(e.manager.running(q));fresh=HostEngine(e.home);self.assertEqual(fresh.manager.state['servers'][0]['id'],q['id'])
    def test_active_pending_and_stale_removal_rejected(self):
        e=self.engine;before=copy.deepcopy(e.manager.state)
        with patch.object(e.manager,'running',return_value=True):
            with self.assertRaises(ValueError):e.remove_profile(self.p['id'],fingerprint(self.p))
        e.jobs['job']={'server':self.p['id'],'status':'queued'}
        with self.assertRaises(ValueError):e.remove_profile(self.p['id'],fingerprint(self.p))
        e.jobs.clear()
        with self.assertRaises(ValueError):e.remove_profile(self.p['id'],'old')
        self.assertEqual(e.manager.state,before)
    def test_failed_save_does_not_remove_profile(self):
        e=self.engine;before=copy.deepcopy(e.manager.state)
        with patch.object(e.manager,'save',side_effect=OSError('disk')):
            with self.assertRaises(OSError):e.remove_profile(self.p['id'],fingerprint(self.p))
        self.assertEqual(e.manager.state,before)
    def test_api_deletion_cannot_enqueue_deleted_profile(self):
        from host_api import AgentAPI,AgentClient
        api=AgentAPI(self.engine);api.start();self.addCleanup(api.stop);client=AgentClient(self.engine.home);client.call('remove_profile',{'server':self.p['id'],'expected':fingerprint(self.p)})
        with self.assertRaises(ValueError):self.engine.enqueue('start',self.p['id'])
        self.assertEqual(len(client.call('snapshot')['state']['servers']),1)
