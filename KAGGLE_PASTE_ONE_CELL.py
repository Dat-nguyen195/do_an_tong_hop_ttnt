# SEMSYNTH — one-cell Kaggle runner. Run with Internet ON; CPU is enough.
# Choose ONE source: set REPO_URL to your GitHub repository, OR upload the
# original project ZIP plus SEMSYNTH_KAGGLE_EXPLAIN_PATCH.zip as Kaggle Inputs.
# Enter your Gemini key manually below, or leave blank for a hidden prompt.
GEMINI_API_KEY = ""  # Paste your Gemini API key here, or leave blank for getpass().
REPO_URL = ""  # Optional: "https://github.com/<user>/<your-repo>.git"
BRANCH = "main"
MODEL = "gemini-3.8-flash"
PROFILE = "pilot"  # "smoke"=1 task, "pilot"=8 task families, "full"=32 synthetic cases
TOP_K, MAX_QUESTIONS, SEED = 3, 3, 3101
MAX_MINUTES = 540
RUN_TESTS = False  # Optional: tests run locally before distribution; enable to repeat in Kaggle

import os, sys, subprocess, zipfile, shutil, json
from pathlib import Path
from getpass import getpass

assert PROFILE in {"smoke", "pilot", "full"}
WORK = Path('/kaggle/working') if Path('/kaggle/working').is_dir() else Path.cwd()
INPUT = Path('/kaggle/input')
PROJECT_DEST = WORK / 'semsynth_repo'
OUTPUT = WORK / 'semsynth_results'
KEY = GEMINI_API_KEY.strip() or os.environ.get('GEMINI_API_KEY', '').strip()
if not KEY:
    KEY = getpass('Enter Gemini API key (input hidden): ').strip()
if not KEY:
    raise ValueError('Gemini API key is required for a real Gemini run.')
os.environ['GEMINI_API_KEY'] = KEY
GEMINI_API_KEY, KEY = '', ''  # Do not put the key in logged output or result archives.


def checked_zip(archive):
    with zipfile.ZipFile(archive) as z:
        for m in z.infolist():
            p = Path(m.filename)
            if p.is_absolute() or '..' in p.parts or (p.parts and ':' in p.parts[0]):
                raise ValueError('Unsafe archive member in ' + str(archive))
            # Refuse archived symbolic links.
            if ((m.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('ZIP contains symbolic link: ' + m.filename)
        return [m.filename for m in z.infolist()]


def extract_safe(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    checked_zip(archive)
    with zipfile.ZipFile(archive) as z:
        z.extractall(destination)


archives = sorted(INPUT.rglob('*.zip')) if INPUT.exists() else []
patches = [p for p in archives if 'SEMSYNTH_PATCH_MARKER.txt' in checked_zip(p)]
if len(patches) > 1:
    raise RuntimeError('Attach just one SEMSYNTH patch ZIP, not multiple versions.')
if REPO_URL.strip():
    if (PROJECT_DEST / '.git').is_dir():
        subprocess.run(['git', '-C', str(PROJECT_DEST), 'fetch', '--depth', '1', 'origin', BRANCH], check=True)
        subprocess.run(['git', '-C', str(PROJECT_DEST), 'reset', '--hard', 'FETCH_HEAD'], check=True)
    else:
        if PROJECT_DEST.exists():
            shutil.rmtree(PROJECT_DEST)
        subprocess.run(['git', 'clone', '--depth', '1', '--branch', BRANCH,
                        REPO_URL.strip(), str(PROJECT_DEST)], check=True)
    PROJECT = PROJECT_DEST
else:
    sources = [p for p in archives if p not in patches and any(
        s.endswith('/run_experiments.py') or s == 'run_experiments.py' for s in checked_zip(p))]
    if len(sources) != 1:
        raise RuntimeError('Upload exactly one original SEMSYNTH source ZIP plus the patch ZIP, '
                           'or set REPO_URL to your GitHub repository.')
    if PROJECT_DEST.exists():
        shutil.rmtree(PROJECT_DEST)
    extract_safe(sources[0], PROJECT_DEST)
    candidates = list(PROJECT_DEST.rglob('run_experiments.py'))
    if len(candidates) != 1:
        raise RuntimeError('Original ZIP must have exactly one run_experiments.py')
    PROJECT = candidates[0].parent
if patches:
    extract_safe(patches[0], PROJECT)
if 'proposed_explain' not in (PROJECT/'run_experiments.py').read_text(encoding='utf-8'):
    raise RuntimeError('The explainability patch was not applied. Attach its ZIP '
                       'as a Kaggle input or push the patched files to GitHub.')
print('SEMSYNTH project:', PROJECT)
print('Profile:', PROFILE, '| Gemini model:', MODEL, '| source patch:', bool(patches))

subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                '-r', str(PROJECT / 'requirements-gemini-kaggle.txt')], check=True)
if RUN_TESTS:
    subprocess.run([sys.executable, '-m', 'pytest', '-q'], cwd=PROJECT, check=True)
subprocess.run([sys.executable, 'scripts/preflight.py', '--mode', 'real',
                '--provider', 'gemini', '--output-dir', str(OUTPUT)], cwd=PROJECT, check=True)

cmd = [sys.executable, 'run_experiments.py', '--mode', 'real', '--provider', 'gemini',
       '--model', MODEL, '--top-k', str(TOP_K), '--max-questions', str(MAX_QUESTIONS),
       '--seed', str(SEED), '--max-minutes', str(MAX_MINUTES),
       '--output-dir', str(OUTPUT)]
if PROFILE in {'smoke', 'pilot'}:
    cmd.append('--quick')
if PROFILE == 'smoke':
    cmd += ['--max-tasks', '1']
if PROFILE == 'full':
    cmd.append('--require-complete')
try:
    subprocess.run(cmd, cwd=PROJECT, check=True)
finally:
    result_zips = sorted(OUTPUT.glob('*/SEMSYNTH_RESULTS.zip'), key=lambda p: p.stat().st_mtime)
    if result_zips:
        final = WORK / 'SEMSYNTH_RESULTS.zip'
        shutil.copy2(result_zips[-1], final)
        print('Results ZIP:', final)
        with zipfile.ZipFile(final) as z:
            if 'completeness.json' in z.namelist():
                complete = json.loads(z.read('completeness.json'))
                print('Completed:', complete['completed'], '/', complete['expected'],
                      '| complete:', complete['all_complete'])
        try:
            from IPython.display import display, FileLink
            display(FileLink(str(final)))
        except ImportError:
            pass
    else:
        print('No results ZIP yet; check the preceding Kaggle error.')
