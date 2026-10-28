"""Replay saved candidate pools and compare checkpoints without network/API calls."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from run_experiments import validate_dataset, prepare_evaluation_tasks, run_method
from src.code_executor import CodeExecutor
from src.semsynth_controller import SEMSYNTHController, SEMSYNTHConfig
from run_experiments import FixedPoolClient

COMPARE = ['task_id', 'family', 'method', 'passed_all', 'pass_count', 'total_tests',
           'excluded_overlapping_inputs', 'candidate_count', 'chosen_code_sha256',
           'has_candidate', 'questions', 'flipped_answers', 'session_status', 'termination_reason']


def replay(results_root: Path, output: Path):
    dataset_path = ROOT / 'config/ambiguity_benchmark.json'
    dataset_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    raw = validate_dataset(json.loads(dataset_path.read_text(encoding='utf-8')))
    reports, case_studies = [], []
    for manifest_path in sorted(results_root.rglob('manifest.json')):
        folder = manifest_path.parent
        manifest = json.loads(manifest_path.read_text())
        settings = manifest['settings']
        if settings['dataset_sha256'] != dataset_hash:
            raise RuntimeError(f'Dataset hash mismatch: {manifest_path}')
        args = SimpleNamespace(**settings)
        tasks = list(raw)
        if settings['quick']:
            seen = set(); tasks = [t for t in tasks if not (t['family'] in seen or seen.add(t['family']))]
        if settings['max_tasks'] is not None:
            tasks = tasks[:settings['max_tasks']]
        tasks = prepare_evaluation_tasks(tasks, args.max_probes)
        assert len(tasks) == manifest['task_count']
        expected_count = len(tasks) * len(settings['methods'])
        completed = json.loads((folder / 'completeness.json').read_text())
        assert completed['all_complete'] and completed['completed'] == expected_count
        rows = []
        for task in tasks:
            saved_pool = json.loads((folder / 'pools' / f"{task['id']}.json").read_text())
            assert saved_pool['run_id'] == manifest['run_id']
            pool = saved_pool['codes']
            ref = CodeExecutor(timeout=args.timeout)
            outputs = ref.execute_batch(task['reference_code'], task['function_name'], task['evaluation_inputs'])
            assert all(ok for ok, _, _ in outputs)
            gold = [v for _, v, _ in outputs]
            for method in settings['methods']:
                saved = json.loads((folder / 'tasks' / f"{task['id']}__{method}.json").read_text())
                actual = run_method(method, task, pool, args, gold, ref)
                for field in COMPARE:
                    if actual[field] != saved[field]:
                        raise RuntimeError(f"Replay mismatch {folder.name}/{task['id']}/{method}: {field}")
                rows.append(actual)
            if 'real_pilot_qwen' in folder.parts and task['id'] == 'SYN_DEDUP_01':
                def oracle(_text, q):
                    ok, target, _ = ref.execute_function(task['reference_code'], task['function_name'], q.test_input)
                    assert ok
                    return target == q.yes_output
                session = SEMSYNTHController(FixedPoolClient(pool, args.mode, args.model),
                    SEMSYNTHConfig(top_k=args.top_k, max_questions=args.max_questions,
                                   max_probe_inputs=args.max_probes)).run(
                        task['description'], task['function_name'], task['params'],
                        answer_callback=oracle, seed_inputs=task['seed_inputs'])
                case_studies.append({'run_id': manifest['run_id'], 'task_id': task['id'],
                                     'codes': pool, 'selected_code': session.best_code,
                                     'transcript': session.questions_asked,
                                     'termination_reason': session.metadata['termination_reason']})
        with (folder / 'summary.csv').open() as f:
            summaries = list(csv.DictReader(f))
        for summary in summaries:
            group = [r for r in rows if r['method'] == summary['method']]
            assert len(group) == int(summary['completed_tasks'])
            assert sum(r['passed_all'] for r in group) == int(summary['passed_tasks'])
            assert round(sum(r['questions'] for r in group) / len(group), 4) == float(summary['mean_questions'])
        balanced = [r for r in rows if r['method'] == 'balanced']
        reports.append({'path': str(folder.relative_to(ROOT)), 'run_id': manifest['run_id'],
                        'mode_as_recorded': settings['mode'], 'provider_as_recorded': settings['provider'],
                        'model_as_recorded': settings['model'], 'tasks': len(tasks),
                        'verified_task_method_records': len(rows),
                        'balanced_termination': dict(Counter(r['termination_reason'] for r in balanced)),
                        'balanced_questions': sum(r['questions'] for r in balanced),
                        'candidate_counts': dict(Counter(len(json.loads((folder/'pools'/f"{t['id']}.json").read_text())['codes']) for t in tasks))})
    report = {'dataset_sha256': dataset_hash, 'api_calls_made': 0,
              'live_generation_reexecuted': False,
              'scope': 'Re-execution of saved pools, selection, oracle responses and evaluation; excludes original live API provenance and timing.',
              'runs': reports, 'total_verified_records': sum(r['verified_task_method_records'] for r in reports),
              'case_studies': case_studies}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'runs': len(reports), 'verified_records': report['total_verified_records'], 'api_calls': 0}))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-root', type=Path, default=ROOT/'results')
    p.add_argument('--output', type=Path, default=ROOT/'docs/evidence/final/evidence_replay.json')
    a = p.parse_args()
    replay(a.results_root, a.output)
