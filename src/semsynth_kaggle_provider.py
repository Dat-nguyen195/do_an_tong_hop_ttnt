"""Kaggle V6 local HF + one rate-limited Gemini adapter for SEMSYNTH.

Uses the repository's prompts, evaluator, methods, and task dataset unchanged.
Does not substitute offline/synthetic candidates for failed API calls.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from pathlib import Path

_MODEL_CACHE = {}
_LAST_GEMINI_REQUEST = 0.0


def _cache_path(provider, model, mode, system, user, temperature, maxout):
    # Compatible with V4 Gemini cache hashes when mode=budget512.
    payload = [provider, model, mode, system, user, temperature, maxout]
    key = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return Path(os.getenv('SEMSYNTH_RESPONSE_CACHE', './.semsynth_response_cache')) / (key + '.txt')


def _save_text(path, content):
    if not content.strip():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.part')
    temporary.write_text(content, encoding='utf-8')
    os.replace(temporary, path)


def _time_delay(message):
    patterns = [r'[Pp]lease retry in\s+(\d+(?:\.\d+)?)\s*s',
                r"retryDelay['\"]?\s*:\s*['\"](\d+(?:\.\d+)?)s"]
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return float(match.group(1))
    return None


def _is_daily_quota(message):
    text = message.lower()
    return any(t in text for t in ('requests per day', 'daily quota', 'per-day',
                                  'per_day', 'perday', 'requests_per_day', 'rpd limit'))


def _ledger_attempt():
    fn = os.getenv('SEMSYNTH_API_LEDGER')
    if not fn:
        return
    p = Path(fn)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(p.read_text(encoding='utf-8')) if p.is_file() else {}
    except (ValueError, OSError):
        data = {}
    tag = os.getenv('SEMSYNTH_CONDITION', 'one_gemini')
    calls = data.setdefault('calls', {})
    calls[tag] = calls.get(tag, 0) + 1
    data['last_unix'] = time.time()
    tmp = p.with_suffix('.part')
    tmp.write_text(json.dumps(data, indent=2), encoding='utf-8')
    os.replace(tmp, p)


def _pace_gemini(spacing: float):
    """Enforce spacing across requests and across restarted Kaggle subprocesses."""
    global _LAST_GEMINI_REQUEST
    elapsed_monotonic = time.monotonic() - _LAST_GEMINI_REQUEST
    elapsed_wall = float('inf')
    ledger_path = os.getenv('SEMSYNTH_API_LEDGER')
    if ledger_path and Path(ledger_path).is_file():
        try:
            last_unix = json.loads(Path(ledger_path).read_text(encoding='utf-8')).get('last_unix', 0)
            elapsed_wall = max(0.0, time.time() - float(last_unix))
        except (ValueError, OSError, TypeError):
            pass
    remaining = spacing - min(elapsed_monotonic, elapsed_wall)
    if remaining > 0:
        time.sleep(remaining)
    _LAST_GEMINI_REQUEST = time.monotonic()


def _gemini_call(client, user, system, temperature, maxout):
    """Rate limits are per project/model; retry server-directed minute caps only.

    Daily exhaustion fails cleanly so runner archives completed tasks for next day.
    """
    global _LAST_GEMINI_REQUEST
    from google.genai import types
    model = client.model
    budget = int(os.getenv('SEMSYNTH_GEMINI_THINKING_BUDGET', '512'))
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        max_output_tokens=maxout,
        thinking_config=types.ThinkingConfig(thinking_budget=budget),
    )
    spacing = float(os.getenv('SEMSYNTH_GEMINI_MIN_SPACING', '16'))
    max_retries = max(0, int(os.getenv('SEMSYNTH_GEMINI_RETRIES', '5')))
    for attempt in range(max_retries + 1):
        _pace_gemini(spacing)
        _ledger_attempt()
        try:
            response = client._get_client().models.generate_content(
                model=model, contents=user, config=config)
            return getattr(response, 'text', '') or ''
        except Exception as error:
            status = getattr(error, 'code', None) or getattr(error, 'status_code', None)
            msg = str(error)
            is_429 = status == 429 or '429' in msg or 'RESOURCE_EXHAUSTED' in msg
            transient = is_429 or status in (408, 500, 502, 503, 504)
            if is_429 and _is_daily_quota(msg):
                raise RuntimeError('Gemini DAILY quota exhausted. Checkpoint saved; resume after quota reset.') from error
            if not transient or attempt == max_retries:
                raise
            suggested = _time_delay(msg)
            delay = max((suggested + 3) if suggested else 0,
                        min(90, 10 * (2 ** attempt)))
            delay += random.uniform(0.2, 1.2)
            print(f'  Gemini temporary {status or "API"} error; retry {attempt + 1}/{max_retries} after {delay:.1f}s', flush=True)
            time.sleep(delay)
    raise AssertionError('Unreachable')


def _local_client(client):
    if client.model not in _MODEL_CACHE:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        torch.set_num_threads(min(4, max(1, os.cpu_count() or 2)))
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        dtype = torch.float16 if device == 'cuda' else torch.float32
        print(f'  Loading local model {client.model} on {device} ({dtype})', flush=True)
        tok = AutoTokenizer.from_pretrained(client.model, trust_remote_code=False)
        try:
            model = AutoModelForCausalLM.from_pretrained(
                client.model, dtype=dtype, trust_remote_code=False)
        except TypeError:  # Older supported transformers versions
            model = AutoModelForCausalLM.from_pretrained(
                client.model, torch_dtype=dtype, trust_remote_code=False)
        model.to(device).eval()
        _MODEL_CACHE[client.model] = (tok, model, device)
    return _MODEL_CACHE[client.model]


def _local_chat(client, user, system, temperature, maxout):
    import torch
    tokenizer, model, device = client._get_client()
    messages = [{'role': 'system', 'content': system},
                {'role': 'user', 'content': user}]
    data = tokenizer.apply_chat_template(messages, add_generation_prompt=True,
                                         tokenize=True, return_dict=True,
                                         return_tensors='pt')
    if isinstance(data, torch.Tensor):
        data = {'input_ids': data}
    else:
        try:
            data = dict(data)  # BatchEncoding is a Mapping, not necessarily dict.
        except (ValueError, TypeError) as exc:
            raise RuntimeError('Unsupported tokenizer.apply_chat_template result') from exc
    data = {key: value.to(device) for key, value in data.items()}
    if 'attention_mask' not in data:
        data['attention_mask'] = torch.ones_like(data['input_ids'])
    prompt_len = data['input_ids'].shape[-1]
    prompt_key = hashlib.sha256(json.dumps([client.model, system, user, temperature, maxout],
                             ensure_ascii=False).encode('utf-8')).hexdigest()
    seed = int(prompt_key[:12], 16) % (2**31 - 1)
    torch.manual_seed(seed)
    if device == 'cuda':
        torch.cuda.manual_seed_all(seed)
    pad_token_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    with torch.inference_mode():
        output = model.generate(**data, do_sample=True,
                                temperature=max(float(temperature), 0.05),
                                top_p=0.95, max_new_tokens=maxout,
                                pad_token_id=pad_token_id)
    return tokenizer.decode(output[0][prompt_len:], skip_special_tokens=True)


def install(LLMClient, PROVIDER_CONFIG, SUPPORTED_PROVIDERS):
    if getattr(LLMClient, '_kaggle_v6_installed', False):
        return SUPPORTED_PROVIDERS
    PROVIDER_CONFIG['local'] = {'env_key': 'SEMSYNTH_LOCAL_ENABLED',
                                'base_url': None, 'default_model': 'Qwen/Qwen2.5-Coder-0.5B-Instruct'}
    original_init = LLMClient.__init__
    original_get = LLMClient._get_client
    original_chat = LLMClient.chat
    original_multi = LLMClient.generate_multiple

    def init(self, *args, **kwargs):
        provider = kwargs.get('provider') or (args[0] if args else None)
        if provider == 'local':
            # The constructor accepts local only after the global list is patched below.
            pass
        original_init(self, *args, **kwargs)
        if self.provider == 'local':
            self.api_key = 'LOCAL_MODEL_NO_API_KEY'
        # Gemini V4 compatibility: 3072-token output cap by default.
        if self.provider == 'gemini' and self.max_tokens == 4096:
            self.max_tokens = int(os.getenv('SEMSYNTH_GEMINI_MAX_OUTPUT', '3072'))

    def get(self):
        if self.provider == 'local':
            return _local_client(self)
        if self.provider == 'gemini':
            if self._client is None:
                from google import genai
                from google.genai import types
                http_options = {'timeout': 120000}
                if (hasattr(types, 'HttpRetryOptions') and
                    'retry_options' in getattr(types.HttpOptions, 'model_fields', {}) and
                    'attempts' in getattr(types.HttpRetryOptions, 'model_fields', {})):
                    http_options['retry_options'] = types.HttpRetryOptions(attempts=1)
                self._client = genai.Client(api_key=self.api_key,
                                             http_options=types.HttpOptions(**http_options))
            return self._client
        return original_get(self)

    def chat(self, user_message, system_message='You are a helpful assistant.', **kwargs):
        if self.provider not in ('gemini', 'local'):
            return original_chat(self, user_message, system_message, **kwargs)
        temperature = kwargs.get('temperature', self.temperature)
        maxout = (int(os.getenv('SEMSYNTH_LOCAL_MAX_TOKENS', '512')) if self.provider == 'local'
                  else kwargs.get('max_tokens', self.max_tokens))
        mode = ('budget' + os.getenv('SEMSYNTH_GEMINI_THINKING_BUDGET', '512')
                if self.provider == 'gemini' else 'local-v6-mask')
        path = _cache_path(self.provider, self.model, mode, system_message,
                           user_message, temperature, maxout)
        if path.is_file():
            return path.read_text(encoding='utf-8')
        if self.provider == 'gemini':
            content = _gemini_call(self, user_message, system_message, temperature, maxout)
        else:
            content = _local_chat(self, user_message, system_message, temperature, maxout)
        _save_text(path, content)
        return content

    def multi(self, description, function_name, params='', k=5):
        if self.provider not in ('gemini', 'local'):
            return original_multi(self, description, function_name, params, k)
        if k < 1:
            return []
        hints = ['prefer the most literal interpretation',
                 'consider a reasonable edge-case interpretation',
                 'consider an alternative interpretation of ambiguous wording',
                 'prefer a concise Pythonic implementation',
                 'prefer explicit careful boundary handling']
        candidates, seen = [], set()
        for i in range(k):
            try:
                code = self.generate_code(description, function_name, params,
                          temperature=min(.25 + .15 * i, 1.0),
                          variant_hint=hints[i % len(hints)]).strip()
            except RuntimeError as e:
                # A genuinely empty/local truncated answer becomes an explicit
                # missing candidate; never substitute a synthetic answer.
                if 'Empty model response' in str(e):
                    print(f'  Empty generation for candidate {i + 1}/{k}', flush=True)
                    continue
                raise
            norm = re.sub(r'\s+', ' ', code).strip()
            if norm and norm not in seen:
                seen.add(norm)
                candidates.append(code)
        return candidates

    LLMClient.__init__ = init
    LLMClient._get_client = get
    LLMClient.chat = chat
    LLMClient.generate_multiple = multi
    LLMClient._kaggle_v6_installed = True
    return tuple(dict.fromkeys((*SUPPORTED_PROVIDERS, 'local')))
