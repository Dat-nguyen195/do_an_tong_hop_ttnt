"""Regression: explanation is transparent and does not perturb SEMSYNTH decisions."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from run_experiments import main
from src.semsynth_controller import SEMSYNTHConfig, SEMSYNTHController


class FrozenClient:
    provider = "frozen"
    model = "test"

    def generate_multiple(self, *args, **kwargs):
        return [
            "def f(xs): return list(dict.fromkeys(xs))",
            "def f(xs): return sorted(set(xs))",
            "def f(xs): return xs",
        ]


def _session(explain):
    cfg = SEMSYNTHConfig(top_k=3, max_questions=3, belief_mode="soft",
                         posterior_threshold=0.98, semantic_questions=True,
                         explain_questions=explain)
    return SEMSYNTHController(FrozenClient(), cfg).run(
        "Remove duplicates from a list", "f", "xs",
        answer_callback=lambda _text, q: q.yes_output == list(dict.fromkeys(q.test_input["xs"])),
        seed_inputs=[{"xs": [3, 1, 3, 2]}],
    )


def test_explain_flag_is_observational_only():
    base = _session(False)
    explained = _session(True)
    assert base.best_code == explained.best_code
    assert [q["answer"] for q in base.questions_asked] == [q["answer"] for q in explained.questions_asked]
    assert [q["yes_candidate_ids"] for q in base.questions_asked] == [
        q["yes_candidate_ids"] for q in explained.questions_asked]
    assert all('explanation' not in q for q in base.questions_asked)
    assert explained.questions_asked
    for q in explained.questions_asked:
        assert q['explanation']['input'] == q['test_input']
        assert q['explanation']['yes_candidate_ids'] == q['yes_candidate_ids']
        assert q['explanation']['grounding'].startswith('Observed execution')
        assert abs(sum(q['belief_after'].values()) - 1) < 1e-5


def test_explain_export_and_baseline_parity(tmp_path: Path):
    out = tmp_path / 'semsynth'
    status = main([
        '--mode', 'offline', '--max-tasks', '1', '--top-k', '3', '--max-questions', '2',
        '--methods', 'proposed,proposed_explain', '--output-dir', str(out),
    ])
    assert status['all_complete']
    artifact = list(out.rglob('SEMSYNTH_RESULTS.zip'))
    assert len(artifact) == 1
    summaries = list(out.rglob('per_task.csv'))
    with summaries[0].open(newline='', encoding='utf-8') as f:
        records = {r['method']: r for r in csv.DictReader(f)}
    for key in ('passed_all', 'pass_count', 'questions', 'termination_reason'):
        assert records['proposed'][key] == records['proposed_explain'][key]
    records_raw = list(out.rglob('runs.jsonl'))
    records_json = [json.loads(x) for x in records_raw[0].read_text().splitlines()]
    base = next(r for r in records_json if r['method'] == 'proposed')
    explain = next(r for r in records_json if r['method'] == 'proposed_explain')
    assert base['chosen_code_sha256'] == explain['chosen_code_sha256']
    explanation_files = list(out.rglob('explanations.jsonl'))
    assert explanation_files and explanation_files[0].is_file()
    assert len(explanation_files[0].read_text().splitlines()) == explain['explanation_count']


def test_partial_run_is_archived_on_failure(tmp_path, monkeypatch):
    import run_experiments as runner
    import pytest

    def failed_pool(*_args, **_kwargs):
        raise ConnectionError('simulated external service failure')

    monkeypatch.setattr(runner, 'task_pool', failed_pool)
    with pytest.raises(RuntimeError, match='partial results have been archived'):
        main(['--max-tasks', '1', '--methods', 'direct1', '--output-dir', str(tmp_path)])
    zips = list(tmp_path.rglob('SEMSYNTH_RESULTS.zip'))
    assert len(zips) == 1
    import zipfile
    with zipfile.ZipFile(zips[0]) as z:
        assert 'run_error.json' in z.namelist()
        status = json.loads(z.read('completeness.json'))
    assert not status['all_complete']
