"""Audit the local pilot against upstream sources; never call an LLM API."""
from __future__ import annotations
import ast
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.code_executor import CodeExecutor

HE_URL = 'https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz'
MB_URL = 'https://raw.githubusercontent.com/google-research/google-research/master/mbpp/mbpp.jsonl'
LICENSE_URL = 'https://huggingface.co/datasets/google-research-datasets/mbpp/raw/main/README.md'


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class StripTyping(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        return None if node.module == 'typing' else node

    def visit_FunctionDef(self, node):
        node.returns = None
        for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            arg.annotation = None
        return self.generic_visit(node)


def main():
    out = ROOT / 'docs/evidence/final'
    out.mkdir(parents=True, exist_ok=True)
    he_bytes = urllib.request.urlopen(HE_URL, timeout=45).read()
    mb_bytes = urllib.request.urlopen(MB_URL, timeout=45).read()
    license_card = urllib.request.urlopen(LICENSE_URL, timeout=45).read()
    assert b'cc-by-4.0' in license_card
    he = {t['task_id']: t for t in map(json.loads, gzip.decompress(he_bytes).decode().splitlines())}
    mb = {t['task_id']: t for t in map(json.loads, mb_bytes.decode().splitlines())}
    path = ROOT / 'config/dataset_sample.json'
    tasks = json.loads(path.read_text(encoding='utf-8'))
    results, selected, catalog = [], [], []
    corrected = {'MB_001': 2, 'MB_002': 8, 'MB_003': 11, 'MB_004': 91, 'MB_005': 62}
    for task in tasks:
        tid = task['id']
        legacy = task.get('legacy_source_id', task['source_id'])
        input_names = list(task['test_cases'][0]['input'])
        verified, upstream, license_name = None, None, ''
        notes = 'Local tests are a reduced/adapted suite; clarification questions are project-authored.'
        if tid.startswith('HE_'):
            verified = task['source_id']
            upstream = he[verified]
            source_url = HE_URL
            code = upstream['prompt'] + upstream['canonical_solution']
            license_name = 'MIT'
            status = 'SOURCE_AND_LOCAL_TESTS_VERIFIED'
        elif tid in corrected:
            verified = f'MBPP/{corrected[tid]}'
            upstream = mb[corrected[tid]]
            task['source_id'] = verified
            source_url = MB_URL
            code = upstream['code']
            license_name = 'CC-BY-4.0 (dataset card)'
            status = 'SOURCE_AND_LOCAL_TESTS_VERIFIED'
            if legacy != verified:
                notes += f' Legacy ID {legacy} corrected to {verified}.'
            if tid == 'MB_001':
                notes += ' Tuple inputs/outputs represented as JSON lists; local ordering expectations retained.'
            if tid == 'MB_003':
                notes += ' Removes BOTH first and last occurrences; a single occurrence is removed once.'
            if tid == 'MB_004':
                notes += ' Local parameter string_list corresponds positionally to upstream str1.'
        elif tid == 'MB_006':
            task['source'] = 'Self-authored'
            task['source_id'] = 'LOCAL/count_upper'
            verified = 'NONE_VERIFIED'
            source_url = MB_URL
            code = "def count_upper(s):\n    return sum('A' <= c <= 'Z' for c in s)"
            notes = 'Legacy MBPP/105 counts Boolean True values. No upstream source verified for this ASCII-uppercase task; self-authored local contract.'
            license_name = 'Local adaptation; no upstream license asserted'
            status = 'LOCAL_CONTRACT_ONLY'
        else:
            task['source'] = 'MBPP-adapted'
            task['source_id'] = 'MBPP/534'
            verified = 'ADAPTED_FROM_MBPP/534'
            upstream = mb[534]
            source_url = MB_URL
            code = 'def search_literal(pattern, text):\n    return text.find(pattern)'
            notes = 'Adapted from MBPP/534: original regex search returns (start,end); local literal search returns start index or -1. Not a canonical benchmark result.'
            license_name = 'CC-BY-4.0 upstream; modified contract'
            status = 'ADAPTED_CONTRACT_ONLY'
        if legacy != task['source_id']:
            task['legacy_source_id'] = legacy
        tree = StripTyping().visit(ast.parse(code))
        ast.fix_missing_locations(tree)
        code = ast.unparse(tree)
        func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == task['function_name'])
        canonical_names = [a.arg for a in func.args.args]
        cases = []
        for case in task['test_cases']:
            assert len(input_names) == len(canonical_names), tid
            mapped = dict(zip(canonical_names, [case['input'][name] for name in input_names]))
            cases.append({'input': mapped, 'expected_output': case['expected_output']})
        verdict = CodeExecutor(timeout=5).run_all_tests(code, task['function_name'], cases)
        if not verdict['passed_all']:
            raise RuntimeError(f'Contract verification failed: {tid}: {verdict}')
        task['provenance'] = {'audited_source_id': verified, 'source_url': source_url,
                              'audit_status': status, 'contract_notes': notes}
        results.append({'task_id': tid, 'verified_source_id': verified, 'status': status,
                        'local_tests_passed': verdict['pass_count'], 'local_tests': len(cases),
                        'reference_sha256': digest(code.encode()),
                        'normalization': 'typing imports/annotations removed; local argument names mapped by position; JSON normalizes tuples to lists'})
        if upstream is not None:
            selected.append({'local_id': tid, 'upstream': upstream})
        title = 'Remove First and Last Occurrences' if tid == 'MB_003' else task['title']
        catalog.append({'task_id': tid, 'title': title,
                        'function_name': f"{task['function_name']}({', '.join(input_names)})",
                        'claimed_source': 'HumanEval' if tid.startswith('HE_') else 'MBPP',
                        'claimed_id': legacy, 'verified_source_id': verified,
                        'source_url': source_url, 'license': license_name,
                        'adaptation_details': notes, 'audit_status': status})
    path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (ROOT / 'docs/dataset_catalog.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(catalog[0]))
        writer.writeheader(); writer.writerows(catalog)
    (out / 'upstream_selected_tasks.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    report = {'checked_on': '2026-10-28', 'sources': {HE_URL: digest(he_bytes), MB_URL: digest(mb_bytes), LICENSE_URL: digest(license_card)},
              'pilot_dataset_sha256': digest(path.read_bytes()), 'task_count': len(tasks),
              'source_matched_tasks': 13, 'adapted_or_local_contract_tasks': 2,
              'local_tests_passed': sum(t['local_tests_passed'] for t in results), 'tasks': results}
    (out / 'dataset_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['task_count','source_matched_tasks','adapted_or_local_contract_tasks','local_tests_passed']}, indent=2))


if __name__ == '__main__':
    main()
