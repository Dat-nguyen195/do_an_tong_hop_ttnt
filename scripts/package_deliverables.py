#!/usr/bin/env python3
"""Build and verify source/evidence archives in a fresh Python environment.

Slides are included; video artifacts and credentials are excluded. Historical generations
are replayed from saved pools; this command never requests new LLM generations.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parent.parent
TOP_FILES={'.env.example','.gitignore','README.md','requirements.txt','requirements.lock.txt',
           'requirements-kaggle.txt','requirements-llm.txt','pytest.ini','app.py',
           'run_experiments.py','kaggle_run.py'}
TOP_DIRS={'src','tests','scripts','config','notebooks','report','docs','image','results'}
EXCLUDE_PARTS={'.git','.venv','venv','env','__pycache__','.pytest_cache','build','dist','tmp','scratch'}
EXCLUDE_SUFFIXES={'.pyc','.pyo','.aux','.bbl','.blg','.fls','.log','.out','.toc','.nav','.snm',
                  '.webp','.mp4','.webm','.avi','.mov','.xlsx','.docx'}
RUN_FOLDERS={'integration_review','real_pilot_gemini','real_pilot_qwen','real_smoke_gemini','real_smoke_qwen'}
REPORT_PDFS={'report/SEMSYNTH_Report_CO3101.pdf','report/SEMSYNTH_Slides_CO3101.pdf'}


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files():
    result=[]
    for p in ROOT.rglob('*'):
        if not p.is_file(): continue
        rel=p.relative_to(ROOT)
        if any(part in EXCLUDE_PARTS for part in rel.parts): continue
        if p.name.startswith('.env') and rel.as_posix()!='.env.example': continue
        if p.suffix.lower() in EXCLUDE_SUFFIXES or p.name.endswith(('.fdb_latexmk','.synctex.gz')): continue
        if p.name=='DELIVERABLES_PROVENANCE.json' or p.suffix=='.zip':continue
        if len(rel.parts)==1:
            if rel.name not in TOP_FILES:continue
        elif rel.parts[0] not in TOP_DIRS:continue
        if rel.parts[0]=='report' and p.suffix=='.pdf' and rel.as_posix() not in REPORT_PDFS:continue
        if rel.parts[0]=='image' and p.name!='01.png':continue
        if rel.parts[0]=='results' and (len(rel.parts)<3 or rel.parts[1] not in RUN_FOLDERS):continue
        result.append(p)
    return sorted(result)


def evidence_files():
    return [p for p in source_files() if p.relative_to(ROOT).parts[0]=='results'
            or p.relative_to(ROOT).parts[:2]==('docs','evidence')
            or p.relative_to(ROOT).as_posix()=='docs/dataset_catalog.csv']


def write_zip(destination: Path, files):
    members={str(p.relative_to(ROOT).as_posix()):{'sha256':sha(p),'bytes':p.stat().st_size} for p in files}
    manifest={'schema':1,'checked_on':'2026-10-28','files':members,
              'scope':'Course deliverables including editable LaTeX slides; videos excluded.'}
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.relative_to(ROOT))
        z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    verify_zip(destination)
    return manifest


def verify_zip(path):
    with zipfile.ZipFile(path) as z:
        m=json.loads(z.read('MANIFEST.json'))
        assert set(z.namelist())==set(m['files'])|{'MANIFEST.json'}
        for name,record in m['files'].items():
            p=Path(name)
            assert not p.is_absolute() and '..' not in p.parts
            data=z.read(name)
            assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256'],name


def clean_environment():
    env=dict(os.environ)
    for k in list(env):
        if k in {'DEFAULT_MODEL','LLM_MODEL','LLM_PROVIDER','LLM_BASE_URL','VIRTUAL_ENV','PYTHONPATH','PYTHONHOME'} or k.startswith(('OPENAI_','GEMINI_','OPENROUTER_')):
            env.pop(k,None)
    env.update(PYTHONDONTWRITEBYTECODE='1',PIP_DISABLE_PIP_VERSION_CHECK='1')
    return env


def checked(command, cwd, env, log_path):
    started=time.monotonic()
    r=subprocess.run([str(x) for x in command],cwd=cwd,env=env,capture_output=True,text=True,timeout=600)
    log_path.write_text(r.stdout+r.stderr,encoding='utf-8')
    if r.returncode:raise RuntimeError(f'{log_path.name} failed (exit {r.returncode}); inspect the saved log.')
    return {'exit_code':r.returncode,'elapsed_s':round(time.monotonic()-started,3),'log':log_path.name}


def verify_clean_archive(archive: Path, log_dir: Path):
    env=clean_environment(); steps={}
    with tempfile.TemporaryDirectory(prefix='semsynth-release-') as temp:
        temp=Path(temp);project=temp/'source';project.mkdir()
        with zipfile.ZipFile(archive) as z:z.extractall(project)
        pyenv=temp/'venv'
        steps['create_venv']=checked([sys.executable,'-m','venv',pyenv],temp,env,log_dir/'create_venv.txt')
        py=pyenv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        steps['install']=checked([py,'-m','pip','install','--quiet','-r',project/'requirements.lock.txt'],project,env,log_dir/'install.txt')
        steps['pip_check']=checked([py,'-m','pip','check'],project,env,log_dir/'pip_check.txt')
        junit=log_dir/'pytest.xml'
        steps['pytest']=checked([py,'-m','pytest','-q','-p','no:cacheprovider','--junitxml',junit],project,env,log_dir/'pytest.txt')
        xml=ET.parse(junit).getroot();suites=[xml] if xml.tag=='testsuite' else list(xml.iter('testsuite'))
        counts={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ['tests','errors','failures','skipped']}
        assert counts['tests']>0 and counts['errors']==counts['failures']==counts['skipped']==0,counts
        steps['preflight']=checked([py,'scripts/preflight.py','--mode','offline'],project,env,log_dir/'preflight.txt')
        steps['demo']=checked([py,'kaggle_run.py','--offline-suite'],project,env,log_dir/'demo.txt')
        steps['offline_run']=checked([py,'run_experiments.py','--mode','offline','--methods','direct1,first_valid,balanced',
                      '--require-complete','--output-dir',temp/'new_results'],project,env,log_dir/'offline_run.txt')
        import csv
        baseline=list(csv.DictReader((project/'results/integration_review/e6a84cf2098af752/summary.csv').open()))
        generated=list(csv.DictReader(next((temp/'new_results').rglob('summary.csv')).open()))
        fields=['method','completed_tasks','passed_tasks','pass_rate_on_completed','mean_questions']
        assert [{k:r[k] for k in fields} for r in baseline]==[{k:r[k] for k in fields} for r in generated]
        steps['evidence_replay']=checked([py,'scripts/verify_evidence.py','--output',log_dir/'replayed_evidence.json'],project,env,log_dir/'evidence_replay.txt')
        steps['latex_build']=checked(['latexmk','-pdf','-interaction=nonstopmode','-halt-on-error','-outdir=build','main.tex'],project/'report',env,log_dir/'latex_build.txt')
        steps['slide_tables']=checked([py,'scripts/build_slide_tables.py'],project,env,log_dir/'slide_tables.txt')
        steps['slides_build']=checked(['latexmk','-pdf','-interaction=nonstopmode','-halt-on-error','-outdir=build','slides.tex'],project/'report/slides',env,log_dir/'slides_build.txt')
        for logfile in ['report/build/main.log','report/slides/build/slides.log']:
            texlog=(project/logfile).read_text(errors='replace')
            if any(s in texlog for s in ['Overfull \\hbox','Overfull \\vbox','There were undefined references','There were undefined citations']):
                raise RuntimeError(f'Unpacked LaTeX build has unresolved references or overflow: {logfile}')
        steps['environment']=checked([py,'-m','pip','freeze'],project,env,log_dir/'installed_packages.txt')
        return {'fresh_virtualenv':True,'dependencies_installed_from':'requirements.lock.txt','tests':counts,
                'offline_summary_matches':True,'api_calls_made':0,'live_generation_reexecuted':False,'steps':steps}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,default=ROOT/'dist');args=p.parse_args()
    dest=args.output_dir.resolve();dest.mkdir(parents=True,exist_ok=True)
    report=ROOT/'report/SEMSYNTH_Report_CO3101.pdf'
    slides=ROOT/'report/SEMSYNTH_Slides_CO3101.pdf'
    if not report.exists() or not slides.exists():raise RuntimeError('Build and visually verify report and slide PDFs before packaging.')
    logs=ROOT/'docs/evidence/final/reproduction';logs.mkdir(parents=True,exist_ok=True)
    snapshot=dest/'source_verification_snapshot.zip'
    write_zip(snapshot,source_files())
    verification=verify_clean_archive(snapshot,logs)
    verification['source_verification_snapshot_sha256']=sha(snapshot)
    (ROOT/'docs/evidence/final/FINAL_VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n')
    source=dest/'semsynth_source.zip';evidence=dest/'semsynth_evidence.zip'
    source_manifest=write_zip(source,source_files());write_zip(evidence,evidence_files())
    snapshot.unlink()
    pdf=dest/report.name;shutil.copy2(report,pdf)
    slide_pdf=dest/slides.name;shutil.copy2(slides,slide_pdf)
    pages=subprocess.run(['pdfinfo',pdf],capture_output=True,text=True,check=True).stdout
    pages=int(next(line.split(':',1)[1] for line in pages.splitlines() if line.startswith('Pages:')))
    slide_info=subprocess.run(['pdfinfo',slide_pdf],capture_output=True,text=True,check=True).stdout
    slide_count=int(next(line.split(':',1)[1] for line in slide_info.splitlines() if line.startswith('Pages:')))
    replay=json.loads((logs/'replayed_evidence.json').read_text())
    git_head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True).stdout.strip()
    provenance={'checked_on':'2026-10-28','project':'SEMSYNTH CO3101 partial implementation',
                'scope_excludes':['video'],'git_head':git_head,
                'source_manifest_sha256':hashlib.sha256(json.dumps(source_manifest['files'],sort_keys=True).encode()).hexdigest(),
                'working_tree_note':'Archive member hashes identify the actual local snapshot; Git HEAD alone does not.',
                'artifacts':{x.name:{'sha256':sha(x),'bytes':x.stat().st_size} for x in [source,evidence,pdf,slide_pdf]},
                'report_pages':pages,'slide_count':slide_count,'verification':{'fresh_virtualenv':True,'tests':verification['tests'],
                 'saved_records_replayed':replay['total_verified_records'],'offline_summary_matches':True,
                 'latex_build':'PASS','slides_build':'PASS','api_calls_made':0},
                'historical_live_generation_limit':'Saved model identifiers/pools are retained; original provider requests and pinned model weight digests are unavailable.'}
    for target in [dest/'DELIVERABLES_PROVENANCE.json',ROOT/'docs/evidence/DELIVERABLES_PROVENANCE.json']:
        target.write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'source':str(source),'evidence':str(evidence),'report':str(pdf),'slides':str(slide_pdf),'tests':verification['tests'],'pages':pages,'slide_count':slide_count},indent=2))


if __name__=='__main__':main()
