"""Kaggle/CPU-first, resumable SEMSYNTH benchmark.

Offline tasks are *controlled synthetic regression cases*, never published as
real LLM accuracy. All selection methods reuse one candidate pool per task.
The target program acts only as a simulated user and held-out evaluator;
SEMSYNTH and non-oracle baselines never inspect evaluation outputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import shutil
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

from src.code_executor import CodeExecutor
from src.llm_client import LLMClient
from src.semsynth_controller import SEMSYNTHConfig, SEMSYNTHController

ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / 'config' / 'ambiguity_benchmark.json'
METHODS = ('direct1', 'first_valid', 'random', 'balanced', 'proposed', 'oracle_upper_bound')
REVISION = 'semsynth-kaggle-v1'


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def sha(value: Any) -> str:
    return hashlib.sha256(json_text(value).encode('utf-8')).hexdigest()[:16]


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + '.part')
    pending.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')
    os.replace(pending, path)


def validate_dataset(dataset: Any) -> list[dict[str, Any]]:
    if not isinstance(dataset, list) or not dataset:
        raise ValueError('Dataset must be a nonempty array')
    ids = set()
    for task in dataset:
        for key in ('id', 'family', 'description', 'function_name', 'params',
                    'seed_inputs', 'candidate_codes', 'reference_code', 'evaluation_inputs'):
            if key not in task:
                raise ValueError(f'Task {task.get("id", "?")} missing {key}')
        if task['id'] in ids or not isinstance(task['id'], str) or '/' in task['id']:
            raise ValueError(f'Duplicate or invalid task id: {task["id"]}')
        ids.add(task['id'])
        if not task['seed_inputs'] or not task['evaluation_inputs'] or not task['candidate_codes']:
            raise ValueError(f'Empty seeds/evaluation/candidate bank: {task["id"]}')
        if not all(isinstance(p, dict) for p in task['seed_inputs'] + task['evaluation_inputs']):
            raise ValueError(f'Inputs must be JSON dicts: {task["id"]}')
        if task['reference_code'] not in task['candidate_codes']:
            raise ValueError(f'Reference must be represented in offline bank: {task["id"]}')
    return dataset


def evaluate(code: str | None, task: dict, executor: CodeExecutor,
             expected: list[Any]) -> dict[str, Any]:
    if code is None:
        return {'passed_all': False, 'pass_count': 0, 'total_tests': len(expected), 'failures': ['no_candidate']}
    failures = []
    passed = 0
    observations = executor.execute_batch(code, task['function_name'], task['evaluation_inputs'])
    for i, (gold, (ok, actual, error)) in enumerate(zip(expected, observations)):
        if ok and actual == gold:
            passed += 1
        else:
            failures.append({'index': i, 'error': error if not ok else 'wrong_output',
                             'expected': gold, 'actual': actual})
    return {'passed_all': passed == len(expected) and len(expected) > 0,
            'pass_count': passed, 'total_tests': len(expected), 'failures': failures}


def task_pool(task: dict, args, root: Path) -> list[str]:
    path = root / 'pools' / f'{task["id"]}.json'
    if path.exists() and args.resume:
        saved = json.loads(path.read_text(encoding='utf-8'))
        if saved.get('task_id') == task['id'] and saved.get('run_id') == root.name:
            return saved['codes']
        raise RuntimeError(f'Candidate pool cache mismatch: {path}')
    if args.mode == 'offline':
        codes = list(task['candidate_codes'])
        random.Random(f'{args.seed}:{task["id"]}').shuffle(codes)
        codes = codes[:args.top_k]
    else:
        llm = LLMClient(provider=args.provider, model=args.model)
        if not llm.is_configured:
            raise ValueError(f'Missing API key for {args.provider}; add it to Kaggle Secrets')
        codes = llm.generate_multiple(task['description'], task['function_name'], task['params'], k=args.top_k)
    codes = list(dict.fromkeys(c.strip() for c in codes if c and c.strip()))
    atomic_json(path, {'run_id': root.name, 'task_id': task['id'], 'codes': codes,
                       'provider': args.provider if args.mode == 'real' else 'offline-bank',
                       'model': args.model if args.mode == 'real' else 'synthetic-fixed'})
    return codes


class FixedPoolClient:
    def __init__(self, codes: list[str], mode: str, model: str):
        self.codes = list(codes)
        self.provider = 'frozen-' + mode
        self.model = model

    def generate_multiple(self, *_args, **_kwargs) -> list[str]:
        return list(self.codes)


def run_method(method: str, task: dict, pool: list[str], args,
               gold: list[Any], reference_executor: CodeExecutor) -> dict:
    started = time.monotonic()
    chosen: str | None = None
    session = None
    evaluator = CodeExecutor(timeout=args.timeout, enable_cache=args.cache)
    noisy_answers = 0
    questions = 0
    if method in {'direct1', 'first_valid', 'oracle_upper_bound'}:
        if method == 'direct1':
            chosen = pool[0] if pool else None
        elif method == 'first_valid':
            for code in pool:
                try:
                    evaluator.validate_code(code)
                    chosen = code
                    break
                except (ValueError, SyntaxError):
                    continue
        else:
            # Evaluation-only oracle upper bound; NEVER a deployable baseline.
            scores = [evaluate(c, task, evaluator, gold)['pass_count'] for c in pool]
            chosen = pool[max(range(len(scores)), key=lambda i: scores[i])] if scores else None
    else:
        config = SEMSYNTHConfig(
            top_k=args.top_k, max_questions=args.max_questions,
            execution_timeout=args.timeout, max_probe_inputs=args.max_probes,
            belief_mode='soft' if method == 'proposed' else 'hard',
            answer_error_rate=args.answer_error_rate,
            posterior_threshold=args.posterior_threshold,
            semantic_questions=(method == 'proposed'),
            enable_execution_cache=args.cache,
            selection_strategy='random' if method == 'random' else 'balanced',
            selection_seed=int(sha([args.seed, task['id'], method])[:8], 16),
        )
        controller = SEMSYNTHController(
            FixedPoolClient(pool, args.mode, args.model or 'default'), config)
        noise_rng = random.Random(f'{args.seed}:{task["id"]}:{method}:noise')

        def oracle(_text, question):
            nonlocal noisy_answers
            ok, target, error = reference_executor.execute_function(
                task['reference_code'], task['function_name'], question.test_input)
            if not ok:
                raise RuntimeError(f'Simulated target failed for {task["id"]}: {error}')
            answer = target == question.yes_output
            if noise_rng.random() < args.simulated_flip_rate:
                answer = not answer
                noisy_answers += 1
            return answer

        session = controller.run(
            task['description'], task['function_name'], task['params'],
            answer_callback=oracle, seed_inputs=task['seed_inputs'])
        chosen = session.best_code
        questions = len(session.questions_asked)
    verdict = evaluate(chosen, task, evaluator, gold)
    return {
        'task_id': task['id'], 'family': task['family'], 'method': method,
        'passed_all': verdict['passed_all'], 'pass_count': verdict['pass_count'],
        'total_tests': verdict['total_tests'], 'failures': verdict['failures'],
        'candidate_count': len(pool), 'chosen_code_sha256': hashlib.sha256((chosen or '').encode()).hexdigest(),
        'has_candidate': chosen is not None, 'questions': questions,
        'flipped_answers': noisy_answers, 'elapsed_s': round(time.monotonic()-started, 5),
        'executor_stats': (session.metadata['executor_stats'] if session else evaluator.stats),
        'session_status': session.metadata['selection_status'] if session else 'baseline',
        'termination_reason': session.metadata['termination_reason'] if session else 'baseline',
        'semantic_question_count': sum(not q['question'].startswith('For input') for q in session.questions_asked)
                                   if session else 0,
    }


def aggregate(output: Path, tasks: list[dict], methods: list[str], selected: list[dict], run_id: str) -> dict:
    records: list[dict] = []
    invalid = []
    for path in sorted((output / 'tasks').glob('*.json')):
        try:
            item = json.loads(path.read_text(encoding='utf-8'))
            if item.get('run_id') != run_id:
                invalid.append(str(path))
            else:
                records.append(item)
        except Exception:
            invalid.append(str(path))
    expected_all = {(t['id'], m) for t in tasks for m in methods}
    expected_selected = {(t['id'], m) for t in selected for m in methods}
    actual = {(item['task_id'], item['method']) for item in records}
    unexpected = sorted(actual - expected_all)
    missing = sorted(expected_all - actual)
    missing_shard = sorted(expected_selected - actual)
    if invalid or unexpected:
        raise RuntimeError(f'Corrupt/unexpected records: {invalid}, {unexpected}')
    status = {'run_id': run_id, 'expected': len(expected_all), 'completed': len(actual),
              'missing': [{'task_id': t, 'method': m} for t, m in missing],
              'shard_expected': len(expected_selected),
              'shard_completed': len(expected_selected & actual),
              'shard_missing': [{'task_id': t, 'method': m} for t, m in missing_shard],
              'all_complete': not missing, 'shard_complete': not missing_shard}
    atomic_json(output / 'completeness.json', status)

    fields = ['task_id','family','method','passed_all','pass_count','total_tests','candidate_count',
              'has_candidate','questions','flipped_answers','elapsed_s','session_status',
              'termination_reason','semantic_question_count']
    with (output / 'per_task.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); w.writeheader(); w.writerows(records)
    runtime_fields=['task_id','method','elapsed_s','subprocess_calls','cache_hits','cache_misses']
    with (output / 'runtime.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=runtime_fields);w.writeheader()
        for r in records:
            stats=r['executor_stats']
            w.writerow({'task_id':r['task_id'],'method':r['method'],'elapsed_s':r['elapsed_s'],
                        'subprocess_calls':stats.get('subprocess_calls',0),
                        'cache_hits':stats.get('hits',0), 'cache_misses':stats.get('misses',0)})
    with (output / 'runs.jsonl').open('w', encoding='utf-8') as f:
        for row in records:
            f.write(json_text(row)+'\n')
    groups = []
    for method in methods:
        subset = [r for r in records if r['method'] == method]
        groups.append({'method':method, 'completed_tasks':len(subset),
                       'passed_tasks':sum(int(r['passed_all']) for r in subset),
                       'pass_rate_on_completed':round(sum(int(r['passed_all']) for r in subset)/len(subset),6) if subset else None,
                       'mean_questions':round(sum(r['questions'] for r in subset)/len(subset),4) if subset else None,
                       'mean_elapsed_s':round(sum(r['elapsed_s'] for r in subset)/len(subset),4) if subset else None,
                       'reported_as_full_benchmark': not missing})
    with (output / 'summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(groups[0].keys()));w.writeheader();w.writerows(groups)
    with (output / 'failures.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['task_id','method','pass_count','total_tests','termination_reason'],
                         extrasaction='ignore');w.writeheader()
        w.writerows(r for r in records if not r['passed_all'])
    return status


def archive(output: Path):
    final = output / 'SEMSYNTH_RESULTS.zip'
    with zipfile.ZipFile(final, 'w', zipfile.ZIP_DEFLATED) as z:
        for item in sorted(output.rglob('*')):
            if item.is_file() and item != final and not item.name.endswith('.part'):
                z.write(item, item.relative_to(output))
    return final


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=['offline','real'], default='offline')
    p.add_argument('--dataset',type=Path,default=DEFAULT_DATASET)
    p.add_argument('--provider',choices=['gemini','openai','openrouter'],default='gemini')
    p.add_argument('--model',default=None)
    p.add_argument('--methods',default=','.join(METHODS))
    p.add_argument('--quick',action='store_true',help='One case per family (8 tasks)')
    p.add_argument('--max-tasks',type=int,default=None)
    p.add_argument('--seed',type=int,default=3101)
    p.add_argument('--top-k',type=int,default=3)
    p.add_argument('--max-questions',type=int,default=3)
    p.add_argument('--max-probes',type=int,default=8)
    p.add_argument('--timeout',type=int,default=5)
    p.add_argument('--answer-error-rate',type=float,default=0.10)
    p.add_argument('--posterior-threshold',type=float,default=0.90)
    p.add_argument('--simulated-flip-rate',type=float,default=0.0)
    p.add_argument('--num-shards',type=int,default=1)
    p.add_argument('--shard-index',type=int,default=0)
    p.add_argument('--max-minutes',type=float,default=0,help='Stop safely before Kaggle timeout; 0=no limit')
    p.add_argument('--output-dir',type=Path,default=ROOT/'results'/'semsynth_benchmark')
    p.add_argument('--no-resume',action='store_false',dest='resume')
    p.add_argument('--no-cache',action='store_false',dest='cache')
    p.add_argument('--require-complete',action='store_true')
    p.add_argument('--aggregate-only',action='store_true')
    args=p.parse_args(argv)
    methods=[m.strip() for m in args.methods.split(',') if m.strip()]
    if not methods or len(set(methods))!=len(methods) or any(m not in METHODS for m in methods):
        p.error(f'--methods must be unique names from {METHODS}')
    if args.num_shards<1 or not 0<=args.shard_index<args.num_shards or args.top_k<1 or args.max_questions<0 or args.max_probes<1 or args.timeout<1:
        p.error('Invalid shards, top-k or max-questions')
    if not 0<=args.simulated_flip_rate<=1:
        p.error('--simulated-flip-rate must be in [0,1]')
    if args.mode == 'real' and not args.aggregate_only:
        key={'gemini':'GEMINI_API_KEY','openai':'OPENAI_API_KEY','openrouter':'OPENROUTER_API_KEY'}[args.provider]
        if not os.environ.get(key):
            p.error(f'Missing {key}: enable Internet and add the Kaggle Secret (not required for offline)')
    tasks = validate_dataset(json.loads(args.dataset.read_text(encoding='utf-8')))
    if args.quick:
        seen=set(); reduced=[]
        for t in tasks:
            if t['family'] not in seen:
                seen.add(t['family']);reduced.append(t)
        tasks=reduced
    if args.max_tasks is not None:
        if args.max_tasks < 1: p.error('--max-tasks must be positive')
        tasks=tasks[:args.max_tasks]
    dataset_digest = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    settings={'revision':REVISION,'dataset_sha256':dataset_digest,'quick':args.quick,
              'max_tasks':args.max_tasks,'mode':args.mode,'provider':args.provider if args.mode=='real' else 'offline',
              'model':args.model if args.mode=='real' else 'fixed', 'seed':args.seed,
              'top_k':args.top_k,'max_questions':args.max_questions,'max_probes':args.max_probes,
              'timeout':args.timeout,'answer_error_rate':args.answer_error_rate,
              'posterior_threshold':args.posterior_threshold,
              'simulated_flip_rate':args.simulated_flip_rate,'cache':args.cache}
    run_id=sha(settings)
    output=args.output_dir/run_id;output.mkdir(parents=True,exist_ok=True)
    manifest=output/'manifest.json'
    if manifest.exists():
        prior=json.loads(manifest.read_text(encoding='utf-8'))
        if prior['settings']!=settings:
            raise RuntimeError('Manifest mismatch; choose a different output directory')
    else:
        atomic_json(manifest,{'run_id':run_id,'settings':settings,
                              'evaluation_kind':'controlled synthetic regression' if args.mode=='offline'
                                 else 'real candidate generation on synthetic tasks; simulated user',
                              'warning':'32 cases are generated from 8 template families; not independent research tasks',
                              'python':sys.version.split()[0], 'task_count':len(tasks)})
    shard=[t for idx,t in enumerate(tasks) if idx % args.num_shards==args.shard_index]
    print(f'RUN {run_id} | mode={args.mode} | tasks={len(shard)}/{len(tasks)} | methods={methods}',flush=True)
    started=time.monotonic(); completed=0
    if not args.aggregate_only:
        for task in shard:
            missing_methods=[m for m in methods if not ((output/'tasks'/f'{task["id"]}__{m}.json').exists() and args.resume)]
            if not missing_methods:
                print(f'SKIP {task["id"]}: checkpoint complete',flush=True)
                continue
            if args.max_minutes>0 and time.monotonic()-started>=args.max_minutes*60:
                print('TIME BUDGET reached: saved completed task checkpoints',flush=True)
                break
            pool=task_pool(task,args,output)
            ref_executor=CodeExecutor(timeout=args.timeout)
            expected=[]
            for ok,value,error in ref_executor.execute_batch(task['reference_code'],task['function_name'],task['evaluation_inputs']):
                if not ok:
                    raise RuntimeError(f'Broken reference for {task["id"]}: {error}')
                expected.append(value)
            for method in missing_methods:
                result=run_method(method,task,pool,args,expected,ref_executor)
                result['run_id']=run_id
                atomic_json(output/'tasks'/f'{task["id"]}__{method}.json',result)
                completed+=1
                print(f'{task["id"]} {method}: {result["pass_count"]}/{result["total_tests"]} '
                      f'questions={result["questions"]} sec={result["elapsed_s"]:.2f}',flush=True)
    status=aggregate(output,tasks,methods,shard,run_id)
    z=archive(output)
    print(json.dumps({k:v for k,v in status.items() if k not in ('missing','shard_missing')},indent=2))
    print(f'Archive: {z}\nNew task-method checkpoints: {completed}',flush=True)
    if args.require_complete and not status['all_complete']:
        raise SystemExit(2)
    return status

if __name__=='__main__':
    main()
