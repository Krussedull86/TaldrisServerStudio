import os,ssl,struct,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from urllib.error import URLError
from network_tls import tls_context,network_message
import windows_runtime as runtime
class NetworkRuntimeTests(unittest.TestCase):
    def test_ca_bundle_is_loaded_without_disabling_verification(self):
        ctx=tls_context(); self.assertTrue(ctx.check_hostname); self.assertEqual(ctx.verify_mode,ssl.CERT_REQUIRED); self.assertGreater(ctx.cert_store_stats()['x509_ca'],0)
        with patch('network_tls.ssl.create_default_context') as factory:
            mock=factory.return_value; result=tls_context(); mock.load_verify_locations.assert_called_once(); self.assertIs(result,mock)
    def test_certificate_error_has_actionable_message(self):
        error=URLError(ssl.SSLCertVerificationError(1,'CERTIFICATE_VERIFY_FAILED'))
        self.assertIn('dato/klokkeslett',network_message(error)); self.assertIn('fortsatt aktiv',network_message(error))
    def pe(self,path,machine):
        header=bytearray(128); header[:2]=b'MZ'; struct.pack_into('<I',header,0x3c,64); header[64:68]=b'PE\x00\x00'; struct.pack_into('<H',header,68,machine); path.write_bytes(header); return path
    def test_wrong_architecture_local_dll_is_identified_without_loading(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.pe(root/'DayZServer_x64.exe',0x8664); dll=self.pe(root/runtime.DIRECTX_DLL,0x014c); before=dll.read_bytes()
            with patch.object(runtime,'sys',types.SimpleNamespace(platform='win32')):message=runtime.directx_issue(root)
            self.assertIn('32-bit',message); self.assertIn('64-bit',message); self.assertIn('0xc000007b',message); self.assertEqual(dll.read_bytes(),before)
    def test_missing_dll_directs_to_dxsetup(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.pe(root/'DayZServer_x64.exe',0x8664)
            with patch.object(runtime,'sys',types.SimpleNamespace(platform='win32')),patch.dict(os.environ,{'SystemRoot':str(root/'windows')}):message=runtime.directx_issue(root)
            self.assertIn('DXSETUP.exe',message)
    def test_valid_system_dll_and_matching_local_dll(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.pe(root/'DayZServer_x64.exe',0x8664); system=root/'windows'/'System32'; system.mkdir(parents=True); self.pe(system/runtime.DIRECTX_DLL,0x8664)
            with patch.object(runtime,'sys',types.SimpleNamespace(platform='win32')),patch.dict(os.environ,{'SystemRoot':str(root/'windows')}):self.assertEqual(runtime.directx_issue(root),'')
            self.pe(root/runtime.DIRECTX_DLL,0x8664)
            with patch.object(runtime,'sys',types.SimpleNamespace(platform='win32')):self.assertEqual(runtime.directx_issue(root),'')
    def test_corrupt_pe_header_not_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.dll'; p.write_bytes(b'MZbad'); self.assertIsNone(runtime.pe_machine(p))
if __name__=='__main__':unittest.main()
