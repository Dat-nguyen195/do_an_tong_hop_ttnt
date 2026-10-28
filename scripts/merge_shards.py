"""Merge independently generated SEMSYNTH_RESULTS.zip archives safely."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from run_experiments import aggregate, archive, validate_dataset, prepare_evaluation_tasks, DEFAULT_DATASET


def merge(sources: list[Path], destination: Path, dataset: Path, methods: list[str] | None = None):
    if len(sources)<2:
        raise ValueError('Specify at least two shard ZIPs')
    manifest=None
    # Validate all manifests and dataset provenance before writing anything.
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    for source in sources:
        with zipfile.ZipFile(source) as z:
            current = json.loads(z.read('manifest.json'))
            if manifest is not None and current != manifest:
                raise ValueError('Incompatible configurations; cannot merge shards')
            if current['settings']['dataset_sha256'] != digest:
                raise ValueError('Dataset differs from the shard dataset')
            manifest = current
    declared_methods = manifest['settings'].get('methods')
    if not declared_methods:
        raise ValueError('Legacy archives lack the method manifest; rerun with the integrated runner')
    if methods is not None and set(methods) != set(declared_methods):
        raise ValueError('Requested methods differ from shard methods')
    methods = declared_methods
    destination.mkdir(parents=True, exist_ok=True)
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
    tasks = prepare_evaluation_tasks(tasks, settings['max_probes'])
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
    p.add_argument('--methods',default=None,help='Optional check; defaults to methods stored in the shards')
    a=p.parse_args()
    merge(a.archives,a.output_dir,a.dataset,a.methods.split(',') if a.methods else None)

if __name__=='__main__':
    main()
