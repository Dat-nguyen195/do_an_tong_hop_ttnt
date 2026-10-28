"""Build LaTeX tables directly from the saved evidence selected for the report."""
from pathlib import Path
from collections import Counter
import csv
import json
ROOT=Path(__file__).resolve().parent.parent
RUNS={'offline':'integration_review/e6a84cf2098af752',
      'gemini':'real_pilot_gemini/8be202264a584167',
      'qwen':'real_pilot_qwen/b6c988199ed7b1d5'}


def esc(s):
    return str(s).replace('\\',r'\textbackslash{}').replace('&',r'\&').replace('%',r'\%').replace('_',r'\_').replace('#',r'\#')


def table(name,caption,label,columns,header,rows,wide=False,note=''):
    env='table*' if wide else 'table'
    width=r'\textwidth' if wide else r'\columnwidth'
    text='\\begin{'+env+'}[t]\n\\centering\n\\caption{'+caption+'}\n\\label{'+label+'}\n\\footnotesize\n'
    text+='\\begin{tabularx}{'+width+'}{@{}'+columns+'@{}}\n\\toprule\n'+header+r' \\ \midrule'+'\n'
    text+='\n'.join(' & '.join(row)+r' \\' for row in rows)
    text+='\n\\bottomrule\n\\end{tabularx}\n'
    if note:text+='\\par\\smallskip '+note+'\n'
    text+='\\end{'+env+'}\n'
    (ROOT/'report/tables'/name).write_text(text,encoding='utf-8')


def main():
    out=ROOT/'report/tables';out.mkdir(exist_ok=True)
    records={}
    for label,path in RUNS.items():
        records[label]=[json.loads(p.read_text()) for p in sorted((ROOT/'results'/path/'tasks').glob('*.json'))]
    offline=records['offline']
    rows=[]
    for method,label in [('direct1','Direct-1'),('first_valid','First-valid'),('balanced','Balanced')]:
        r=[x for x in offline if x['method']==method];passed=sum(x['passed_all'] for x in r)
        rows.append([label,f'{passed}/{len(r)}',f'{100*passed/len(r):.3f}'+r'\%',f"{sum(x['questions'] for x in r)/len(r):.4f}"])
    table('offline_results.tex','Controlled offline results on 32 cases. Rate is finite-suite case success.','tab:offline_results','Xrrr',
          'Method & Passed & Rate & Mean Qs',rows)
    rows=[]
    for label in ['gemini','qwen']:
        model=json.loads((ROOT/'results'/RUNS[label]/'manifest.json').read_text())['settings']['model']
        for method,method_label in [('direct1','Direct-1'),('first_valid','First-valid'),('balanced','Balanced')]:
            r=[x for x in records[label] if x['method']==method];passed=sum(x['passed_all'] for x in r)
            rows.append([r'\texttt{'+esc(model)+'}',method_label,f'{passed}/{len(r)}',f'{100*passed/len(r):.1f}'+r'\%',f"{sum(x['questions'] for x in r)/len(r):.2f}"])
    table('real_llm_results.tex','Saved LLM-labeled pilot pools: eight synthetic cases per recorded backend, requested top-$K=3$.','tab:real_llm_results','Xlrrr',
          'Recorded model identifier & Selector & Passed & Rate & Mean Qs',rows,True,
          'Same ordered pool per task; actual saved pools contain two or three programs. Reference-program feedback is noiseless.')
    rows=[]
    for label,title in [('offline','Offline (32)'),('gemini','Gemini (8)'),('qwen','Qwen (8)')]:
        r=[x for x in records[label] if x['method']=='balanced'];counts=Counter(x['termination_reason'] for x in r)
        rows.append([title,str(counts['single_candidate']),str(counts['no_distinguishing_question'])])
    table('stopping_reasons.tex','Balanced stopping states. All listed selections pass retained tests; unresolved remains tentative.','tab:stopping_reasons','Xrr',
          'Run (cases) & One remains & Unresolved',rows)
    summaries=[
      ('Specification parsing','Partial','Description, function name and parameters; no full constraint parser.'),
      ('47 features / XGBoost','Not integrated','Retained design; execution observations supply deterministic output partitions.'),
      ('Candidate initialization','Partial','LLM adapters or fixed banks; strategy--code AGA is not implemented.'),
      ('Information gain','Special case','Uniform priors and binary output partitions yield $H_b(p)$.'),
      ('Semantic templates','Partial','Dedup/sort wording in UI; I/O fallback. Wording disabled in measured Balanced runs.'),
      ('Atomic decomposition','Not integrated','Binary question form does not implement an NLP compound-question decomposer.'),
      ('Diversity penalty','Not integrated','Exact repeated-question suppression only, without the Jaccard penalty.'),
      ('Belief update','Partial','Hard filtering measured; optional soft weights unit-tested without noise evaluation.'),
      ('Contradiction recovery','Not integrated','No full consistency/recovery pipeline in the evaluated loop.'),
      ('Beam / length buckets','Not integrated','Small pools only; no large-space performance claim.'),
      ('AGA / regeneration','Not integrated','No strategy stage or feedback-conditioned re-synthesis.'),
      ('Oracle / termination','Implemented','Reference feedback in experiments; empty, single, budget or unresolved outcomes.'),
      ('UI / evidence runner','Implemented','Streamlit, shared pools, probe separation, checkpoint/CSV and replay.')]
    table('implementation_scope.tex','Alignment with the original SEMSYNTH design. Implementation status is distinct from empirical validation.','tab:implementation_scope','p{0.23\\textwidth}p{0.17\\textwidth}X',
          'Design component & Prototype status & Implementation/evaluation boundary',[[a,b,c] for a,b,c in summaries],True)
    family_notes={
      'dedup':('remove_duplicates(xs)','Stable first occurrences or sorted unique values'),
      'sorting':('sort_numbers(xs)','Ascending or descending order'),
      'intersection':('common_elements(a, b)','Sorted unique intersection or original-order multiplicity'),
      'parity':('select_numbers(xs)','Even or odd values'),
      'case':('normalize_text(s)','Lowercase or uppercase'),
      'trim':('clean_text(s)','Both-side or left-only trimming'),
      'threshold':('is_large(x, threshold)','Strict or inclusive lower bound'),
      'palindrome':('is_palindrome(s)','Case-sensitive or case-insensitive symmetry')}
    rows=[]
    for family,(signature,notes) in family_notes.items():
        rows.append([esc(family),'4',r'\texttt{'+esc(signature)+'}',notes])
    table('synthetic_families.tex','Eight related template families. Reference intent varies across the four cases in each family.','tab:synthetic_families','llp{0.33\\textwidth}X',
          'Family & Cases & Interface & Target interpretations across variants',rows,True,
          'Every offline bank has three candidate implementations and includes its reference; each case starts with five evaluation inputs.')
    catalog=list(csv.DictReader((ROOT/'docs/dataset_catalog.csv').open(encoding='utf-8')))
    rows=[]
    for r in catalog:
        status='Source contract checked; local tests reduced/adapted.'
        if r['task_id']=='MB_001':status='ID corrected; tuples represented as JSON lists.'
        elif r['task_id']=='MB_003':status='Removes first and last occurrences.'
        elif r['task_id']=='MB_004':status='ID corrected; local parameter name differs.'
        elif r['task_id']=='MB_006':status='Local ASCII-uppercase task; no source verified.'
        elif r['task_id']=='MB_007':status='MBPP/534 adaptation: integer index instead of span.'
        verified=r['verified_source_id'].replace('ADAPTED_FROM_','').replace('NONE_VERIFIED','Local only')
        rows.append([esc(r['task_id']),esc(r['claimed_id']),esc(verified),status])
    table('dataset_catalog.tex','Pilot provenance audit (15 tasks). These tasks are not the measured 32-case benchmark.','tab:dataset_catalog','lllX',
          'Local ID & Legacy ID & Audited source & Contract/adaptation boundary',rows,True,
          'Thirteen upstream contracts are checked against local tests; two local/adapted contracts are kept separate. URLs, licenses, hashes and 46 local-test checks are included in the CSV and audit evidence.')
    (ROOT/'docs/evidence/final/report_runs.json').write_text(json.dumps(RUNS,indent=2)+'\n')
    print('Generated six report tables from evidence and audited catalog.')

if __name__=='__main__': main()
