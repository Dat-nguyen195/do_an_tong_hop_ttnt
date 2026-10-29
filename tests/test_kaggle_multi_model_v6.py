"""V6 regression tests: no Gemini API or model downloads required."""
from __future__ import annotations
import json
from types import SimpleNamespace
from pathlib import Path

from src import semsynth_kaggle_provider as provider
from src.llm_client import LLMClient, SUPPORTED_PROVIDERS
from run_experiments import task_pool, sha


def test_local_provider_installed():
    assert 'local' in SUPPORTED_PROVIDERS
    client = LLMClient(provider='local', model='Qwen/test')
    assert client.is_configured
    assert client.model == 'Qwen/test'


def test_8_shared_prompts_generate_once_per_family(monkeypatch, tmp_path):
    tasks = json.loads((Path(__file__).parent.parent/'config/ambiguity_benchmark.json').read_text())
    calls=[]
    monkeypatch.setattr(LLMClient, 'generate_multiple',lambda self,d,f,p,k: calls.append((d,f,p,k)) or ['def x(): return 1', 'def x(): return 2'])
    opts=SimpleNamespace(mode='real',provider='local',model='fake',top_k=2,seed=3101,
                         resume=True,share_identical_prompts=True)
    root=tmp_path/'runid123'
    for task in tasks:
        assert len(task_pool(task,opts,root))==2
    assert len(calls)==8
    assert len(list((root/'pools').glob('*.json')))==32
    assert len(list((root/'shared_prompt_pools').glob('*.json')))==8
    # Resume: zero new generation calls.
    for task in tasks:
        task_pool(task,opts,root)
    assert len(calls)==8


def test_gemini_429_backoff_and_cache(monkeypatch, tmp_path):
    monkeypatch.setenv('SEMSYNTH_API_LEDGER',str(tmp_path/'ledger.json'))
    monkeypatch.setenv('SEMSYNTH_GEMINI_RETRIES','1')
    monkeypatch.setenv('SEMSYNTH_GEMINI_MIN_SPACING','0')
    monkeypatch.setenv('SEMSYNTH_GEMINI_THINKING_BUDGET','512')
    monkeypatch.setenv('SEMSYNTH_RESPONSE_CACHE',str(tmp_path/'cache'))
    class Obj:
        def __init__(self,**kw): self.__dict__.update(kw)
    class Config:
        def __init__(self,**kw): pass
    class FakeGenaiTypes:
        GenerateContentConfig=Config
        ThinkingConfig=Config
    import sys,types
    google=types.ModuleType('google')
    genai=types.ModuleType('google.genai')
    genai.types=FakeGenaiTypes
    monkeypatch.setitem(sys.modules,'google',google)
    monkeypatch.setitem(sys.modules,'google.genai',genai)
    import google
    google.genai=genai
    calls=[]
    class Model:
        def generate_content(self,**kwargs):
            calls.append(kwargs)
            if len(calls)==1:raise RuntimeError('429 RESOURCE_EXHAUSTED Please retry in 0.01s')
            return Obj(text='```python\ndef f(): return 1\n```')
    class API:
        models=Model()
    c=LLMClient(provider='gemini',model='gemini-2.5-flash',api_key='fake')
    c._client=API()
    monkeypatch.setattr(provider.time,'sleep',lambda seconds:None)
    assert 'def f()' in c.chat('x','system')
    assert len(calls)==2
    assert 'def f()' in c.chat('x','system')
    assert len(calls)==2


def test_quota_rate_limit_detection():
    assert provider._is_daily_quota('GenerateRequestsPerDayPerProjectPerModel-FreeTier')
    assert not provider._is_daily_quota('GenerateRequestsPerMinutePerProjectPerModel-FreeTier')
    assert provider._time_delay('Please retry in 46.947s')==46.947
