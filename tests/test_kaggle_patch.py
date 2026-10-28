"""Regression coverage for the Kaggle-first research patch (no API key)."""
import json
from pathlib import Path

import pytest

from src.code_executor import CodeExecutor
from src.candidate_manager import CandidateManager
from src.question_generator import QuestionGenerator
from src.semsynth_controller import SEMSYNTHConfig, SEMSYNTHController
from run_experiments import DEFAULT_DATASET, validate_dataset, main, METHODS


class StaticClient:
    provider = 'fixed'
    model = 'unit'
    def __init__(self, codes):
        self.codes = codes
    def generate_multiple(self, *args, **kwargs):
        return self.codes


@pytest.mark.parametrize('value', [0, 1, -3, 20])
def test_batched_exec_matches_separate_calls(value):
    executor = CodeExecutor()
    code = 'def f(x): return x*x+1'
    got = executor.execute_batch(code, 'f', [{'x': value}])
    assert got == [executor.execute_function(code, 'f', {'x': value})]
    assert executor.stats['hits'] >= 1


def test_executor_batch_preserves_per_probe_namespace():
    code='counter=0\ndef f(x):\n    global counter\n    counter += 1\n    return counter + x'
    exe=CodeExecutor()
    assert exe.execute_batch(code, 'f', [{'x':1},{'x':1}]) == [(True,2,''),(True,2,'')]
    assert exe.stats['subprocess_calls'] == 1


def test_batch_cache_avoids_duplicate_process():
    ex=CodeExecutor()
    code='def f(x): return 2*x'
    args=[{'x':2},{'x':4}]
    assert ex.execute_batch(code,'f',args) == ex.execute_batch(code,'f',args)
    assert ex.stats['subprocess_calls'] == 1
    assert ex.stats['hits'] == 2


def test_executor_invalid_is_never_passed_as_correct():
    ex=CodeExecutor()
    assert not ex.execute_batch('def f(:', 'f', [{'x':1}])[0][0]


def test_probe_round_robin_mutates_later_coordinate():
    q=QuestionGenerator(max_probe_inputs=9)
    probes=q.build_probe_inputs([{'x':3,'y':4}])
    assert {'x':3,'y':0} in probes
    assert {'x':0,'y':4} in probes


def test_semantic_grounding_for_dedup():
    assert QuestionGenerator._semantic_question('Remove duplicates', {'xs':[3,1,3]}, [3,1])
    assert QuestionGenerator._semantic_question('Remove duplicates', {'xs':[3,1,3]}, [1,3]) is None


def test_weighted_info_prefers_balanced_probability_not_count():
    cm=CandidateManager()
    candidates=cm.add_candidates(['def f(x): return 1','def f(x): return 2','def f(x): return 3'])
    for c,w in zip(candidates,[0.8,0.1,0.1]): c.score=w
    score1=QuestionGenerator._weighted_score(candidates,[0],0.10)
    score2=QuestionGenerator._weighted_score(candidates,[1],0.10)
    assert score1>score2>0


def test_invalid_only_candidate_no_false_success():
    ctl=SEMSYNTHController(StaticClient(['def f(x): return x +']),SEMSYNTHConfig())
    result=ctl.run('identity', 'f','x', lambda *a: True,[{'x':1}])
    assert not result.success
    assert result.metadata['selection_status']=='empty'
    assert result.metadata['rejected_candidates']


def test_soft_beliefs_keep_candidates_and_normalize():
    codes=['def f(x): return x','def f(x): return x+1','def f(x): return x+2']
    ctl=SEMSYNTHController(StaticClient(codes),SEMSYNTHConfig(
        top_k=3,max_questions=2,max_probe_inputs=3,belief_mode='soft',
        answer_error_rate=0.15,posterior_threshold=0.99))
    result=ctl.run('return x', 'f','x',lambda text,q: q.yes_output==3,[{'x':3}])
    assert result.total_candidates==3
    assert result.remaining_candidates==3
    assert abs(sum(result.metadata['posterior'].values())-1)<1e-6
    assert result.metadata['belief_mode']=='soft'
    assert not result.metadata['converged'] or max(result.metadata['posterior'].values()) >= 0.99


def test_entire_new_dataset_has_32_cases_8_families():
    tasks=validate_dataset(json.loads(DEFAULT_DATASET.read_text()))
    assert len(tasks)==32
    assert len({t['family'] for t in tasks})==8
    assert all(len(t['evaluation_inputs'])>=5 for t in tasks)
    assert all(t['reference_code'] in t['candidate_codes'] for t in tasks)


@pytest.mark.parametrize('family', ['dedup','sorting','intersection','parity','case','trim','threshold','palindrome'])
def test_reference_works_on_held_out_inputs_for_family(family):
    tasks=json.loads(DEFAULT_DATASET.read_text())
    task=next(t for t in tasks if t['family']==family)
    ex=CodeExecutor()
    outputs=ex.execute_batch(task['reference_code'],task['function_name'],task['evaluation_inputs'])
    assert len(outputs)==len(task['evaluation_inputs'])
    assert all(ok for ok,_,_ in outputs)


def test_quick_runner_resume_no_extra_execution(tmp_path):
    base=['--quick','--max-tasks','1','--methods','direct1','--output-dir',str(tmp_path)]
    status=main(base)
    assert status['all_complete'] and status['completed']==1
    case_files=list(tmp_path.rglob('tasks/*.json'))
    assert len(case_files)==1
    old=case_files[0].stat().st_mtime_ns
    status=main(base)
    assert status['all_complete'] and case_files[0].stat().st_mtime_ns==old
    assert list(tmp_path.rglob('SEMSYNTH_RESULTS.zip'))


def test_two_shards_do_not_overlap(tmp_path):
    args=['--quick','--max-tasks','2','--methods','direct1','--output-dir',str(tmp_path),
          '--num-shards','2']
    first=main(args+['--shard-index','0'])
    assert first['shard_complete'] and not first['all_complete']
    second=main(args+['--shard-index','1'])
    assert second['all_complete'] and second['completed']==2
