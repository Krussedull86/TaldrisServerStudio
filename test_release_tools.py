import importlib.util,json,hashlib,tempfile,types,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('release_tools',Path(__file__).parent/'scripts'/'release.py'); release=importlib.util.module_from_spec(spec); spec.loader.exec_module(release)
class ReleaseTests(unittest.TestCase):
    def test_package_excludes_server_data_and_promotion_reuses_exact_package(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'dist').mkdir(); (root/'dist'/'TaldrisServerStudio.exe').write_bytes(b'MZtest'); (root/'LES_MEG.md').write_text('Readme'); (root/'DRIFT_DISCORD_EDITORER.md').write_text('Guide'); (root/'settings.json').write_text('private')
            metadata=types.SimpleNamespace(VERSION='0.5.0',BUILD=12,REPOSITORY='owner/studio')
            with patch.object(release,'ROOT',root),patch.dict('sys.modules',{'release_info':metadata}):release.package()
            out=root/'release_output'; binary=out/'TaldrisServerStudio-Windows.zip'; before=binary.read_bytes()
            with zipfile.ZipFile(binary) as z:self.assertEqual(set(z.namelist()),{'TaldrisServerStudio.exe','LES_MEG.md','DRIFT_DISCORD_EDITORER.md'})
            calls=[]
            def fake(*args):
                calls.append(args)
                if args[:2]==('api','repos/owner/studio/releases/tags/dev-v0.5.0.b12'):return json.dumps(dict(prerelease=True,draft=False))
                if args[0]=='api':return 'a'*40
                return ''
            with patch.object(release,'ROOT',root),patch.object(release,'gh',side_effect=fake),patch.dict('os.environ',{'DEV_TAG':'dev-v0.5.0.b12','GH_REPO':'owner/studio'}):release.promote()
            create=next(c for c in calls if c[:2]==('release','create')); self.assertEqual(create[2],'v0.5.0.b12'); self.assertIn('--latest',create); self.assertEqual(create[create.index('--target')+1],'a'*40); self.assertEqual(binary.read_bytes(),before)
if __name__=='__main__':unittest.main()
