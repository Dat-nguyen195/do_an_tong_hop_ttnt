"""Dependency-light Kaggle setup validation (no remote network calls)."""
import argparse
import importlib.util
import json
import os
import platform
import tempfile
from pathlib import Path

from run_experiments import DEFAULT_DATASET, validate_dataset


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mode', choices=['offline','real'], default='offline')
    p.add_argument('--provider', choices=['gemini','openai','openrouter'], default='gemini')
    p.add_argument('--dataset', type=Path, default=DEFAULT_DATASET)
    p.add_argument('--output-dir', type=Path, default=Path('/kaggle/working') if Path('/kaggle/working').exists() else Path('results'))
    args=p.parse_args()
    problems=validate_dataset(json.loads(args.dataset.read_text(encoding='utf-8')))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=args.output_dir) as temp:
        temp.write(b'preflight');temp.flush()
    if args.mode == 'real':
        env={'gemini':'GEMINI_API_KEY','openai':'OPENAI_API_KEY','openrouter':'OPENROUTER_API_KEY'}[args.provider]
        if not os.environ.get(env):
            p.error(f'{env} is missing; add it using Kaggle Secrets. Never print its value.')
        package = 'google.genai' if args.provider == 'gemini' else 'openai'
        if importlib.util.find_spec(package) is None:
            p.error(f'Missing {package}; install requirements-llm.txt')
    print(json.dumps({'preflight':'PASS', 'python':platform.python_version(),
                      'tasks':len(problems), 'families':len({p['family'] for p in problems}),
                      'mode':args.mode, 'writeable_output':str(args.output_dir)},indent=2))

if __name__=='__main__':
    main()
