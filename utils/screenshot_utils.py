"""Screenshot generation shared by browser uploads and CLI workers."""
import json
import subprocess
from pathlib import Path
from utils.config_loader import ConfigLoader
from utils.screenshot_batch import generate_batch


def generate_screenshots(directory, category_id):
    config = ConfigLoader().get_config()
    return generate_batch(directory, config, generate_candidate)


def generate_candidate(source,target,config):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                            '-of', 'json', str(source)], capture_output=True, text=True,
                           check=True, timeout=60)
    duration = float(json.loads(probe.stdout)['format']['duration'])
    if duration <= 0:
        raise ValueError('Video duration is not valid.')
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    engine=config.get('MediaTools','SCREENSHOT_ENGINE',fallback='ffmpeg').strip().lower()
    if engine=='mtn':
        from utils.mtn_screenshots import generate
        try:return generate(source,target,duration,config)
        except (OSError,ValueError,RuntimeError,subprocess.SubprocessError):
            if not config.get('MediaTools','MTNBIN',fallback='').strip():raise
            import copy
            fallback=copy.deepcopy(config);fallback.set('MediaTools','MTNBIN','')
            for image in target.glob('*.jpg'):image.unlink()
            print('Configured MTN failed; trying the bundled/system MTN.',flush=True)
            return generate(source,target,duration,fallback)
    if engine!='ffmpeg':raise ValueError('Choose ffmpeg or mtn as the screenshot engine.')
    count = min(12, max(1, config.getint('MediaTools', 'SCREENSHOT_SINGLES', fallback=5)))
    for i in range(1, count + 1):
        output = target / f'screenshot-{i:02d}.jpg'
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                        '-ss', str(duration * i / (count + 1)), '-i', str(source),
                        '-frames:v', '1', '-vf', 'scale=min(1280\\,iw):-2',
                        '-q:v', '3', str(output)], check=True, timeout=90)
        if not output.exists() or not output.stat().st_size:
            raise RuntimeError(f'Screenshot {i} could not be generated.')
        print(f'Screenshots: {i}/{count}', flush=True)
