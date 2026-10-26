import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from agent_repair import repair
from release_info import VERSION,BUILD

class AgentRepairTests(unittest.TestCase):
    def test_standalone_repair_replaces_only_agent_and_verifies_version(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder);(home/'agent.json').write_text(json.dumps(dict(pid=81234,created=100.5)))
            client=Mock();client.call.side_effect=[dict(runtime={},jobs=[],service=False),True,dict(version=VERSION,build=BUILD)]
            with patch('agent_repair.sys.frozen',True,create=True),patch('agent_repair.subprocess.Popen') as spawn:
                result=repair(home,client);args=spawn.call_args.args[0];self.assertIn('--agent',args);self.assertIn('--wait-agent',args);self.assertIn('81234',args);self.assertEqual(spawn.call_args.kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'],'1');self.assertIn(VERSION,result)
            self.assertEqual([c.args[0] for c in client.call.call_args_list],['snapshot','shutdown','snapshot'])
    def test_busy_repair_never_shutdowns_or_spawns(self):
        client=Mock();client.call.return_value=dict(runtime={},jobs=[dict(status='queued')])
        with patch('agent_repair.sys.frozen',True,create=True),patch('agent_repair.subprocess.Popen') as spawn:
            with self.assertRaises(ValueError):repair('unused',client)
            spawn.assert_not_called();self.assertEqual(client.call.call_count,1)
    def test_old_agent_cannot_receive_start_from_new_panel(self):
        from agent_client import RemoteManager
        m=RemoteManager.__new__(RemoteManager);m.refresh=Mock();m.raw=dict(version='0.6.0',build=1);m.enqueue=Mock()
        with patch('agent_client.sys.frozen',True,create=True):
            with self.assertRaisesRegex(ValueError,'eldre'):m.start({'id':'test'})
            m.enqueue.assert_not_called();m.raw=dict(version=VERSION,build=BUILD);m.start({'id':'test'});m.enqueue.assert_called_once()
