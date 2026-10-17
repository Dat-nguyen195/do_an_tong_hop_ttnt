"""Merge independently generated SEMSYNTH_RESULTS.zip archives safely."""
import argparse
import json
import tempfile
import zipfile
from pathlib import Path

from run_experiments import aggregate, archive, validate_dataset, DEFAULT_DATASET


def merge(sources: list[Path], destination: Path, dataset: Path, methods: list[str]):
    if len(sources)<2:
        raise ValueError('Specify at least two shard ZIPs')
    destination.mkdir(parents=True, exist_ok=True)
    manifest=None
    for source in sources:
        with zipfile.ZipFile(source) as z:
            for name in z.namelist():
                entry=Path(name)
                if entry.is_absolute() or '..' in entry.parts:
                    raise ValueError(f'Unsafe ZIP member: {name}')
                if name=='manifest.json':
                    current=json.loads(z.read(name))
                    if manifest is not None and current != manifest:
                        raise ValueError('Incompatible configurations; cannot merge shards')
                    manifest=current
                if not (name=='manifest.json' or name.startswith('tasks/') or name.startswith('pools/')):
                    continue
                if name.endswith('/'):
                    continue
                target=destination/entry;target.parent.mkdir(parents=True,exist_ok=True)
                data=z.read(name)
                if target.exists() and target.read_bytes()!=data:
                    raise ValueError(f'Conflicting checkpoint {name}')
                target.write_bytes(data)
    if manifest is None:
        raise ValueError('Missing manifest')
    tasks=validate_dataset(json.loads(dataset.read_text(encoding='utf-8')))
    settings=manifest['settings']
    if settings['quick']:
        seen=set();tasks=[t for t in tasks if not (t['family'] in seen or seen.add(t['family']))]
    if settings['max_tasks'] is not None:
        tasks=tasks[:settings['max_tasks']]
    status=aggregate(destination,tasks,methods,tasks,manifest['run_id'])
    final=archive(destination)
    print(json.dumps({'all_complete':status['all_complete'], 'expected':status['expected'],
                      'completed':status['completed'], 'archive':str(final)},indent=2))
    return status


def main():
    p=argparse.ArgumentParser()
    p.add_argument('archives',nargs='+',type=Path)
    p.add_argument('--output-dir',type=Path,default=Path('results/merged'))
    p.add_argument('--dataset',type=Path,default=DEFAULT_DATASET)
    p.add_argument('--methods',default='direct1,first_valid,random,balanced,proposed,oracle_upper_bound')
    a=p.parse_args()
    merge(a.archives,a.output_dir,a.dataset,a.methods.split(','))

if __name__=='__main__':
    main()
