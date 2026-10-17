from pathlib import Path
import subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils.web_settings import defaults
from utils.runtime_tools import find_tool
from utils.mtn_screenshots import generate
class MtnTests(unittest.TestCase):
 def test_real_contact_sheet_and_five_frames(self):
  config=defaults()
  if not find_tool('mtn',config):self.skipTest('Bundled Linux MTN required')
  with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
   root=Path(temp);video=root/'video.mp4';target=root/'screens';target.mkdir()
   subprocess.run(['ffmpeg','-loglevel','error','-f','lavfi','-i','testsrc2=size=640x360:rate=5:duration=24','-c:v','mpeg4',str(video)],check=True)
   generate(video,target,24,config)
   files=list(target.glob('*.jpg'));self.assertEqual(len(files),6)
   self.assertTrue((target/'video-sheet.jpg').is_file())
   self.assertTrue(all(f.read_bytes().startswith(b'\xff\xd8') for f in files))
