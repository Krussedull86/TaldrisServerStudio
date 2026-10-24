import hashlib,io,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from program_updates import check,download,repository,asset_url,ASSET
from release_info import VERSION,BUILD
class UpdateTests(unittest.TestCase):
    def fixture(self,channel='dev'):
        tag=('dev-' if channel=='dev' else '')+f'v{VERSION}.b{BUILD+10}'; repo='owner/studio'; data=dict(version=VERSION,build=BUILD+10,asset=ASSET,size=123,sha256='a'*64)
        release=dict(tag_name=tag,draft=False,prerelease=channel=='dev',assets=[dict(name=n,browser_download_url=asset_url(repo,tag,n)) for n in [ASSET,'build.json']])
        def fetch(url):
            if url.endswith('build.json'):return data
            return [release] if channel=='dev' else release
        return repo,tag,data,release,fetch
    def test_channel_and_checksum_metadata(self):
        for channel in ['dev','stable']:
            repo,tag,_,_,fetch=self.fixture(channel); info=check(repo,channel,fetch); self.assertEqual(info['tag'],tag); self.assertTrue(info['newer'])
    def test_stable_never_accepts_prerelease(self):
        repo,_,_,release,fetch=self.fixture('stable'); release['prerelease']=True
        with self.assertRaises(ValueError):check(repo,'stable',fetch)
    def test_foreign_assets_and_mismatched_build_rejected(self):
        repo,_,data,release,fetch=self.fixture(); release['assets'][0]['browser_download_url']='https://evil.example/file'
        with self.assertRaises(ValueError):check(repo,'dev',fetch)
        repo,_,data,release,fetch=self.fixture(); data['build']=BUILD+11
        with self.assertRaises(ValueError):check(repo,'dev',fetch)
    def test_download_verified_and_bad_checksum_removed(self):
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as z:z.writestr('TaldrisServerStudio.exe',b'MZtest')
        blob=raw.getvalue(); repo,tag,data,release,fetch=self.fixture(); data.update(size=len(blob),sha256=hashlib.sha256(blob).hexdigest()); info=check(repo,'dev',fetch)
        with tempfile.TemporaryDirectory() as d:
            with patch('program_updates.urlopen',return_value=io.BytesIO(blob)):path=download(info,d)
            self.assertEqual(Path(path).read_bytes(),blob)
            info['sha256']='b'*64
            with patch('program_updates.urlopen',return_value=io.BytesIO(blob)):
                with self.assertRaises(ValueError):download(info,d)
            self.assertFalse(list(Path(d).glob('*.partial')))
    def test_repository_validation(self):
        self.assertEqual(repository('https://github.com/owner/studio'),'owner/studio')
        for value in ['https://bad.example/repo','owner/../repo','../repo','owner/name;run']:
            with self.assertRaises(ValueError):repository(value)
if __name__=='__main__':unittest.main()
