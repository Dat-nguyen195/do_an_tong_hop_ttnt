"""Regressions found while integrating the team branches; no API calls."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.candidate_manager import CandidateManager
from src.llm_client import LLMClient
from src.question_generator import QuestionGenerator
from run_experiments import DEFAULT_DATASET, main, prepare_evaluation_tasks
from scripts.merge_shards import merge

ROOT = Path(__file__).resolve().parents[1]


def test_executor_unicode_with_legacy_parent_encoding():
    # Explicitly disable UTF-8 mode in the parent. Both execution paths must
    # still transport non-ASCII code, inputs and outputs without corruption.
    program = '''
from src.code_executor import CodeExecutor
e = CodeExecutor()
text = "Ti\\u1ebfng Vi\\u1ec7t \\U0001f600"
code = "def f(s): return s + '\\u0111'"
assert e.execute_function(code, 'f', {'s': text}) == (True, text + '\\u0111', '')
assert e.execute_batch(code, 'f', [{'s': text + '!'}]) == [(True, text + '!\\u0111', '')]
'''
    result = subprocess.run([sys.executable, '-X', 'utf8=0', '-c', program],
                            cwd=ROOT, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')


def test_sampling_preserves_semantically_different_string_whitespace():
    class Client(LLMClient):
        def __init__(self):
            super().__init__(api_key='unused')
            self.calls = 0

        def generate_code(self, *_args, **_kwargs):
            self.calls += 1
            return "def f(): return 'a b'" if self.calls == 1 else "def f(): return 'a  b'"

    client = Client()
    assert len(client.generate_multiple('return text', 'f', k=2)) == 2
    assert client.calls == 2


def test_shared_admission_excludes_invalid_or_wrong_function():
    manager = CandidateManager()
    rejected = manager.add_valid_candidates([
        'def f(:', 'def g(x): return x', 'import os\ndef f(x): return x',
        'def f(x): return x', 'def f(x): return x',
    ], 'f')
    assert len(rejected) == 3
    assert manager.total_count == 1


def test_every_evaluation_input_is_disjoint_from_clarification_probes():
    original = json.loads(DEFAULT_DATASET.read_text(encoding='utf-8'))
    for max_probes in (8, 12):
        prepared = prepare_evaluation_tasks(original, max_probes)
        for task in prepared:
            probes = QuestionGenerator(max_probe_inputs=max_probes).build_probe_inputs(
                task['seed_inputs'], task['params'])
            assert task['evaluation_inputs']
            assert all(inp not in probes for inp in task['evaluation_inputs'])
        assert sum(t['excluded_overlapping_inputs'] for t in prepared) > 0
    assert all(len(t['evaluation_inputs']) == 5 for t in original)


def test_no_heldout_inputs_fails_before_measurement():
    with pytest.raises(ValueError, match='No held-out'):
        prepare_evaluation_tasks([{
            'id': 'empty', 'seed_inputs': [{'x': 1}], 'params': 'x',
            'evaluation_inputs': [{'x': 1}],
        }], 8)


def test_method_selection_has_separate_resumable_run_identity(tmp_path):
    common = ['--max-tasks', '1', '--output-dir', str(tmp_path)]
    one = main(common + ['--methods', 'direct1'])
    two = main(common + ['--methods', 'first_valid'])
    assert one['run_id'] != two['run_id']
    assert one['all_complete'] and two['all_complete']
    assert main(common + ['--methods', 'direct1'])['run_id'] == one['run_id']


def test_shards_infer_methods_and_reject_changed_dataset(tmp_path):
    common = ['--quick', '--max-tasks', '2', '--methods', 'direct1', '--num-shards', '2']
    sources = []
    for index in (0, 1):
        out = tmp_path / str(index)
        main(common + ['--shard-index', str(index), '--output-dir', str(out)])
        sources.append(next(out.rglob('SEMSYNTH_RESULTS.zip')))
    status = merge(sources, tmp_path / 'merged', DEFAULT_DATASET)
    assert status['all_complete'] and status['completed'] == 2
    changed = tmp_path / 'changed.json'
    changed.write_text(DEFAULT_DATASET.read_text(encoding='utf-8') + '\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Dataset differs'):
        merge(sources, tmp_path / 'rejected', changed)
    assert not (tmp_path / 'rejected').exists()


def test_merge_script_can_be_run_directly():
    result = subprocess.run([sys.executable, 'scripts/merge_shards.py', '--help'],
                            cwd=ROOT, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('codes,expected_error', [
    ([], 'No valid candidate'),
    (['def other(xs): return xs'], 'No valid candidate'),
    (['def remove_duplicates(xs): return xs',
      'def remove_duplicates(xs): return list(xs)'], None),
])
def test_demo_rejects_empty_candidates_and_labels_unresolved(monkeypatch, codes, expected_error):
    pytest.importorskip('streamlit')
    from streamlit.testing.v1 import AppTest
    from src.llm_client import MockLLMClient
    monkeypatch.setattr(MockLLMClient, 'generate_multiple', lambda *_a, **_k: codes)
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    if expected_error:
        assert any(expected_error in item.value for item in app.error)
    else:
        assert any('tentative' in item.value for item in app.warning)
        assert not app.success
