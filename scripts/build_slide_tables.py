"""Generate presentation tables from the report's fixed saved runs (no API calls)."""
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def write_table(path, columns, header, rows):
    lines = [r'\renewcommand{\arraystretch}{1.12}',
             r'\begin{tabular}{@{}' + columns + r'@{}}',
             r'\toprule', header + r' \\ \midrule']
    lines.extend(' & '.join(row) + r' \\' for row in rows)
    lines.extend([r'\bottomrule', r'\end{tabular}'])
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    runs = json.loads((ROOT/'docs/evidence/final/report_runs.json').read_text())
    records = {label: [json.loads(p.read_text()) for p in sorted(
        (ROOT/'results'/folder/'tasks').glob('*.json'))]
        for label, folder in runs.items()}
    out = ROOT/'report/slides/tables'
    out.mkdir(parents=True, exist_ok=True)
    methods = ['direct1', 'first_valid', 'balanced']
    offline = records['offline']
    rows = []
    families = sorted({r['family'] for r in offline})
    for family in families + [None]:
        group = [r for r in offline if family is None or r['family'] == family]
        per_method = [[r for r in group if r['method'] == m] for m in methods]
        fractions = [f"{sum(r['passed_all'] for r in rs)}/{len(rs)}" for rs in per_method]
        mean = sum(r['questions'] for r in per_method[2])/len(per_method[2])
        rows.append([family.capitalize() if family else r'\textbf{Overall}',
                     *fractions, f'{mean:.4f}' if family is None else f'{mean:.2f}'])
    write_table(out/'offline_by_family.tex', 'lrrrr',
                'Family & Direct-1 & First-valid & Balanced & Mean Qs', rows)
    rows = []
    for label in ['gemini', 'qwen']:
        model = json.loads((ROOT/'results'/runs[label]/'manifest.json').read_text())['settings']['model']
        for method, title in zip(methods, ['Direct-1', 'First-valid', 'Balanced']):
            group = [r for r in records[label] if r['method'] == method]
            passed = sum(r['passed_all'] for r in group)
            rows.append([r'\texttt{' + model + '}', title,
                         f'{passed}/{len(group)}', f'{100*passed/len(group):.1f}'+r'\%',
                         f"{sum(r['questions'] for r in group)/len(group):.2f}"])
    write_table(out/'pilot_results.tex', 'llrrr',
                'Recorded identifier & Selector & Passed & Rate & Mean Qs', rows)
    rows = []
    for label, title in [('offline', 'Offline'), ('gemini', 'Gemini'), ('qwen', 'Qwen')]:
        counts = Counter(r['termination_reason'] for r in records[label] if r['method'] == 'balanced')
        rows.append([title, str(counts['single_candidate']), str(counts['no_distinguishing_question'])])
    write_table(out/'stopping.tex', 'lrr', 'Run & Single & Unresolved', rows)
    print('Generated three slide tables from saved checkpoints; no API calls.')


if __name__ == '__main__':
    main()
