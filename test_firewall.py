import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from windows_firewall import server_ports, set_query_port, ensure_firewall, rule_script

class FirewallTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.p=dict(root=self.tmp.name,config='serverDZ.cfg',port=3302,id='test',name="Test ' server")
        self.config=Path(self.tmp.name)/'serverDZ.cfg'
        self.config.write_text('hostname="https://example/steamQueryPort = 12;";\n// steamQueryPort = 8;\nsteamQueryPort = 3305;')
    def test_effective_ports_ignore_comments_and_strings(self):
        self.assertEqual(server_ports(self.p),[3302,3303,3304,3305])
    def test_missing_query_requires_explicit_setting(self):
        self.config.write_text('hostname="test";')
        with self.assertRaises(ValueError):server_ports(self.p)
    def test_edit_keeps_other_config_and_rejects_duplicates(self):
        text=self.config.read_text(); changed=set_query_port(text,27016)
        self.assertTrue(changed.startswith(text[:text.rfind('steamQueryPort')]))
        self.assertIn('steamQueryPort = 27016;',changed)
        with self.assertRaises(ValueError):set_query_port('steamQueryPort=1; steamQueryPort=2;',3)
    def test_existing_rule_does_not_elevate(self):
        with patch('windows_firewall.sys.platform','win32'),patch('windows_firewall.subprocess.run',return_value=Mock(returncode=0)) as run:
            ensure_firewall(self.p,lambda s:None); self.assertEqual(run.call_count,1)
    def test_elevation_rejection_is_not_success(self):
        with patch('windows_firewall.sys.platform','win32'),patch('windows_firewall.subprocess.run',side_effect=[Mock(returncode=5),Mock(returncode=1)]) as run:
            with self.assertRaises(ValueError):ensure_firewall(self.p,lambda s:None)
            self.assertEqual(run.call_count,2)
    def test_opt_out_and_scoped_script(self):
        self.p['auto_firewall']=False
        with patch('windows_firewall.subprocess.run') as run:
            ensure_firewall(self.p,lambda s:None); run.assert_not_called()
        script=rule_script(self.p,[3302,3305])
        self.assertIn('-Program $exe -Protocol UDP -LocalPort $ports',script)
        self.assertIn("Test '' server",script)
        self.assertNotIn('Set-NetFirewallProfile',script)
