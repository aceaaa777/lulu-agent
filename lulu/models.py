"""Model adapters. Lulu talks to one interface; Ollama, OpenAI-compatible servers and command-line tools plug in behind it.

No agent loop lives here. A provider turns messages (+ optional tools or a JSON schema) into one reply.
`think=True` asks for a deliberate ("thinking") answer: a second model in the two-model Ollama tier, the think flag
on a hybrid model, or the reasoning switch of an API. Thinking text never enters `content`.
"""
import asyncio
import json
import os
import re
import shlex
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field

import httpx

THINK_TOKENS = 1500  # extra generation room reserved for thinking when it is switched on
THINK_TAG = re.compile(r'<think>[\s\S]*?</think>\s*', re.I)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Reply:
    content: str = ''
    tool_calls: list = field(default_factory=list)
    finish_reason: str = 'stop'  # stop | tool_calls | length | error
    usage: dict = field(default_factory=dict)
    thinking: str = ''

    @property
    def failed(self):
        return self.finish_reason == 'error'


def split_thinking(content):
    """Models without native thinking support sometimes inline <think>…</think>; keep it out of the answer."""
    if not content or '<think>' not in content.lower():
        return content or '', ''
    thought = ' '.join(m.group(0) for m in re.finditer(r'<think>([\s\S]*?)</think>', content, re.I))
    return THINK_TAG.sub('', content).strip(), re.sub(r'</?think>', '', thought, flags=re.I).strip()


def extract_json(text):
    """First complete JSON object in free text (command-line backends answer in prose around it)."""
    if not text:
        return None
    text = text.strip()
    fence = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if fence:
        text = fence.group(1).strip()
    start = text.find('{')
    while start >= 0:
        depth, in_string, escape = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        json.loads(text[start:i+1])
                        return text[start:i+1]
                    except ValueError:
                        break
        start = text.find('{', start+1)
    return None


def call(name, **arguments):
    """Scripted tool call, used by tests and fixed workflows."""
    return Reply(tool_calls=[ToolCall('call_'+uuid.uuid4().hex[:8], name, arguments)], finish_reason='tool_calls')


def parse_text_tool_call(raw, tools):
    """Some Qwen/Ollama combinations emit a bare `tool_name {...}` instead of the tool_calls field.
    Accept only an entire, allowlisted JSON call; never execute prose, code fences or partial matches."""
    if not raw or not tools:
        return None
    match = re.fullmatch(r'([A-Za-z_][A-Za-z_0-9]*)\s*(\{[\s\S]*\})', raw.strip())
    allowed = {t['function']['name'] for t in tools}
    if not match or match.group(1) not in allowed:
        return None
    try:
        arguments = json.loads(match.group(2))
    except ValueError:
        return None
    return ToolCall('call_'+uuid.uuid4().hex[:8], match.group(1), arguments) if isinstance(arguments, dict) else None


class ModelProvider:
    """Base adapter. `profile` describes what the backend can do so the loop can degrade gracefully."""
    kind = 'base'
    label = '模型'
    leaves_device = False   # True when prompts (and the material in them) go to another machine

    def __init__(self, model, base, context=8192):
        self.model, self.base, self.context = model, base.rstrip('/'), context
        self.calls = []
        self.num_thread = max(1, min(4, os.cpu_count() or 2))
        self.profile = {'supports_schema': True, 'supports_tools': True, 'context': context, 'supports_think': False}
        self.thinking_model = ''
        self.last_error = ''

    def get_default_model(self):
        return self.model

    def model_for(self, think=False):
        return (self.thinking_model or self.model) if think else self.model

    async def chat(self, messages, tools=None, *, schema=None, max_tokens=1200, temperature=0.0, timeout=120, think=False):
        raise NotImplementedError

    async def models(self):
        """Names of installed/available models, or None when the server is unreachable."""
        return None

    def describe(self):
        return {'backend': self.kind, 'label': self.label, 'model': self.model, 'thinking_model': self.thinking_model or self.model,
                'supports_think': bool(self.profile.get('supports_think')), 'leaves_device': self.leaves_device, 'last_error': self.last_error,
                'calls': len(self.calls), 'last_seconds': self.calls[-1]['seconds'] if self.calls else None}

    def _record(self, start, **extra):
        if extra.get('error'):
            self.last_error = str(extra['error'])[:300]
        self.calls.append({'seconds': round(time.monotonic()-start, 2), **extra})


class OllamaProvider(ModelProvider):
    """Local Ollama. Two shapes: a pair of models (instruct + thinking) or one hybrid model with the think flag."""
    kind = 'ollama'
    label = '本地模型'

    def __init__(self, model='qwen3:4b-instruct-2507-q4_K_M', base='http://127.0.0.1:11434', context=8192, thinking_model='', hybrid=False):
        super().__init__(model, os.environ.get('LULU_OLLAMA_BASE', base), context)
        self.api_base = self.base  # kept for the state endpoint
        self.thinking_model = thinking_model or ''
        self.hybrid = bool(hybrid)  # one model that thinks only when asked (qwen3:8b)
        self.profile['supports_think'] = bool(self.thinking_model or self.hybrid)

    async def models(self):
        try:
            async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
                resp = await client.get(self.base+'/api/tags')
                resp.raise_for_status()
                return [m['name'] for m in resp.json().get('models', [])]
        except (httpx.HTTPError, ValueError, KeyError):
            return None

    def build_payload(self, messages, tools=None, schema=None, max_tokens=1200, temperature=0.0, think=False):
        converted = []
        for original in messages:
            item = {'role': original['role'], 'content': original.get('content') or ''}
            if original.get('tool_calls'):
                item['tool_calls'] = [{'function': {'name': c['name'], 'arguments': c['arguments']}} for c in original['tool_calls']]
            if original.get('name'):
                item['tool_name'] = original['name']
            converted.append(item)
        think = bool(think and self.profile.get('supports_think'))
        payload = {'model': self.model_for(think), 'messages': converted, 'stream': False, 'keep_alive': '5m',
                   'options': {'num_ctx': self.context, 'num_thread': self.num_thread,
                               'num_predict': int(max_tokens)+(THINK_TOKENS if think else 0), 'temperature': temperature}}
        if self.hybrid:
            payload['think'] = think          # hybrid models must be told explicitly, both ways
        elif think and self.thinking_model:
            payload['think'] = True           # a dedicated thinking model; the instruct model gets no flag at all
        if tools:
            payload['tools'] = tools
        if schema:
            payload['format'] = schema
        return payload

    async def chat(self, messages, tools=None, *, schema=None, max_tokens=1200, temperature=0.0, timeout=120, think=False):
        payload = self.build_payload(messages, tools, schema, max_tokens, temperature, think)
        if payload.get('think'):
            timeout = int(timeout)+THINK_TOKENS//2
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=5), trust_env=False) as client:
                response = await client.post(self.base+'/api/chat', json=payload)
                response.raise_for_status()
                data = response.json()
            message = data['message']
            calls = [ToolCall('call_'+uuid.uuid4().hex[:8], c['function']['name'], c['function'].get('arguments') or {})
                     for c in message.get('tool_calls', [])]
            content, inline_thought = split_thinking(message.get('content', '') or '')
            thinking = (message.get('thinking') or '') or inline_thought
            if not calls and tools:
                parsed = parse_text_tool_call(content, tools)
                if parsed:
                    calls, content = [parsed], ''
            usage = {'input_tokens': data.get('prompt_eval_count'), 'output_tokens': data.get('eval_count'),
                     'eval_seconds': round((data.get('eval_duration') or 0)/1e9, 2),
                     'prompt_seconds': round((data.get('prompt_eval_duration') or 0)/1e9, 2), 'load_seconds': round((data.get('load_duration') or 0)/1e9, 2),
                     'total_seconds': round((data.get('total_duration') or 0)/1e9, 2), 'thinking_chars': len(message.get('thinking') or ''),
                     'model': payload['model'], 'think': bool(payload.get('think'))}
            self._record(start, **usage)
            finish = 'tool_calls' if calls else ('length' if data.get('done_reason') == 'length' else 'stop')
            return Reply(content=content, tool_calls=calls, finish_reason=finish, usage=usage, thinking=thinking)
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            detail = str(exc)
            if isinstance(exc, httpx.HTTPStatusError):
                detail = exc.response.text[:400]
                if exc.response.status_code == 404 and 'not found' in detail:
                    detail = f'模型 {payload["model"]} 尚未安装，请先运行安装脚本或在“模型”页体检。'
            if isinstance(exc, httpx.TimeoutException):
                detail = f'模型在{int(timeout)}秒内未答复，请缩短任务或关闭占用内存的程序后重试。'
            if isinstance(exc, httpx.ConnectError):
                detail = '本机模型服务未运行或无法连接。'
            self._record(start, error=detail)
            return Reply(content='本机模型调用失败：'+detail, finish_reason='error')


class OpenAICompatibleProvider(ModelProvider):
    """Any /v1/chat/completions server (DashScope, DeepSeek, OpenRouter, LM Studio, llama-server, vLLM)."""
    kind = 'api'
    label = 'API 接口'
    leaves_device = True

    def __init__(self, model, base='http://127.0.0.1:1234/v1', api_key='', context=8192, think_param='enable_thinking', thinking_model=''):
        super().__init__(model, base, context)
        self.api_key = api_key
        self.api_base = self.base
        self.think_param = think_param   # '' = the endpoint has no reasoning switch
        self.thinking_model = thinking_model or ''
        self.profile['supports_think'] = bool(think_param or thinking_model)
        if self.base.startswith('http://127.0.0.1') or self.base.startswith('http://localhost'):
            self.leaves_device = False

    def _headers(self):
        return {'Authorization': 'Bearer '+self.api_key} if self.api_key else {}

    async def models(self):
        try:
            async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
                resp = await client.get(self.base+'/models', headers=self._headers())
                resp.raise_for_status()
                return [m['id'] for m in resp.json().get('data', [])]
        except (httpx.HTTPError, ValueError, KeyError):
            return None

    def build_payload(self, messages, tools=None, schema=None, max_tokens=1200, temperature=0.0, think=False):
        converted = []
        for original in messages:
            item = {'role': original['role'], 'content': original.get('content') or ''}
            if original.get('tool_calls'):
                item['tool_calls'] = [{'id': c['id'], 'type': 'function', 'function': {'name': c['name'], 'arguments': json.dumps(c['arguments'], ensure_ascii=False)}} for c in original['tool_calls']]
            if original['role'] == 'tool':
                item['tool_call_id'] = original.get('tool_call_id', 'call_0')
            converted.append(item)
        think = bool(think and self.profile.get('supports_think'))
        payload = {'model': self.model_for(think), 'messages': converted, 'max_tokens': int(max_tokens)+(THINK_TOKENS if think else 0), 'temperature': temperature}
        if think and self.think_param and not self.thinking_model:
            payload[self.think_param] = True
        if tools and self.profile.get('supports_tools', True):
            payload['tools'] = tools
        if schema and self.profile.get('supports_schema', True):
            payload['response_format'] = {'type': 'json_schema', 'json_schema': {'name': schema.get('title', 'reply'), 'schema': schema, 'strict': False}}
        return payload

    async def chat(self, messages, tools=None, *, schema=None, max_tokens=1200, temperature=0.0, timeout=120, think=False):
        payload = self.build_payload(messages, tools, schema, max_tokens, temperature, think)
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=5), trust_env=False) as client:
                response = await client.post(self.base+'/chat/completions', json=payload, headers=self._headers())
                response.raise_for_status()
                data = response.json()
            choice = data['choices'][0]
            message = choice['message']
            calls = []
            for c in message.get('tool_calls') or []:
                try:
                    arguments = json.loads(c['function'].get('arguments') or '{}')
                except ValueError:
                    arguments = {}
                calls.append(ToolCall(c.get('id') or 'call_'+uuid.uuid4().hex[:8], c['function']['name'], arguments))
            content, inline_thought = split_thinking(message.get('content') or '')
            thinking = message.get('reasoning_content') or message.get('reasoning') or inline_thought or ''
            if schema and content and extract_json(content) and not content.lstrip().startswith('{'):
                content = extract_json(content)
            if not calls and tools:
                parsed = parse_text_tool_call(content, tools)
                if parsed:
                    calls, content = [parsed], ''
            usage = data.get('usage') or {}
            self._record(start, input_tokens=usage.get('prompt_tokens'), output_tokens=usage.get('completion_tokens'), model=payload['model'])
            finish = 'tool_calls' if calls else ('length' if choice.get('finish_reason') == 'length' else 'stop')
            return Reply(content=content, tool_calls=calls, finish_reason=finish, usage=usage, thinking=thinking)
        except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
            detail = exc.response.text[:400] if isinstance(exc, httpx.HTTPStatusError) else str(exc)
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (401, 403):
                detail = '接口拒绝了钥匙（HTTP %d）。请在“模型”页重新填写 API 钥匙。' % exc.response.status_code
            if isinstance(exc, httpx.TimeoutException):
                detail = f'模型在{int(timeout)}秒内未答复。'
            if isinstance(exc, httpx.ConnectError):
                detail = '连不上接口地址 '+self.base+'，请检查网络或地址。'
            self._record(start, error=detail)
            return Reply(content='模型调用失败：'+detail, finish_reason='error')


def flatten_messages(messages, schema=None):
    """One prompt string for tools that take a single text (claude -p, codex exec)."""
    parts = []
    for m in messages:
        role = m.get('role')
        content = m.get('content') or ''
        if role == 'system':
            parts.append('【要求】\n'+content)
        elif role == 'user':
            parts.append('【用户】\n'+content)
        elif role == 'assistant':
            parts.append('【助理】\n'+content)
        elif role == 'tool':
            parts.append('【工具返回】\n'+content)
    if schema:
        parts.append('【输出格式】只输出一个符合下面 JSON Schema 的 JSON 对象，不要解释，不要 Markdown 围栏：\n'+json.dumps(schema, ensure_ascii=False))
    return '\n\n'.join(parts)


class CommandProvider(ModelProvider):
    """A command-line tool answers each call: `{prompt}` in the command is replaced by the prompt (or it is piped to
    stdin when absent); `{output_file}` names a file the tool writes its final message to. No tool calling."""
    kind = 'cli'
    label = '命令行工具'
    leaves_device = True

    def __init__(self, command, model='', prompt_via='arg', output='stdout', context=8192, workdir=''):
        name = model or (command.split()[0] if command.strip() else 'cli')
        super().__init__(name, 'cmd://', context)
        self.command = command
        self.prompt_via = prompt_via        # arg | stdin
        self.output = output                # stdout | json:<field> | file
        self.workdir = workdir
        self.profile.update(supports_tools=False, supports_schema=True, supports_think=False)

    @property
    def executable(self):
        try:
            return shlex.split(self.command)[0] if self.command else ''
        except ValueError:
            return ''

    def available(self):
        exe = self.executable
        return bool(exe) and (os.path.isabs(exe) and os.path.exists(exe) or shutil.which(exe) is not None)

    async def models(self):
        return [self.model] if self.available() else None

    def build_command(self, prompt, output_file):
        try:
            parts = shlex.split(self.command)
        except ValueError:
            raise ValueError('命令格式无效')
        if self.model and '{model}' in self.command:
            parts = [p.replace('{model}', self.model) for p in parts]
        parts = [p.replace('{output_file}', output_file) for p in parts]
        if '{prompt}' in self.command:
            parts = [p.replace('{prompt}', prompt) for p in parts]
            stdin = None
        elif self.prompt_via == 'arg':
            parts.append(prompt); stdin = None
        else:
            stdin = prompt
        return parts, stdin

    def parse_output(self, stdout, output_file):
        if self.output == 'file' or '{output_file}' in self.command:
            try:
                text = open(output_file, encoding='utf-8').read()
            except OSError:
                text = stdout
            return text.strip()
        if self.output.startswith('json:'):
            try:
                data = json.loads(stdout)
            except ValueError:
                data = None
            if data is None:
                fragment = extract_json(stdout)
                data = json.loads(fragment) if fragment else {}
            if isinstance(data, dict) and data.get('is_error'):
                raise ValueError(str(data.get('result') or data.get('error') or '命令报告错误')[:300])
            value = data.get(self.output[5:], '') if isinstance(data, dict) else ''
            return str(value).strip()
        return stdout.strip()

    async def chat(self, messages, tools=None, *, schema=None, max_tokens=1200, temperature=0.0, timeout=120, think=False):
        prompt = flatten_messages(messages, schema)
        start = time.monotonic()
        folder = tempfile.mkdtemp(prefix='lulu-cli-')
        output_file = os.path.join(folder, 'reply.txt')
        try:
            if not self.available():
                raise FileNotFoundError('找不到命令 '+(self.executable or self.command)+'，请确认已安装并登录。')
            parts, stdin = self.build_command(prompt, output_file)
            env = dict(os.environ)
            env.pop('CLAUDECODE', None)
            process = await asyncio.create_subprocess_exec(*parts, stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
                                                           stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                           cwd=self.workdir or folder, env=env)
            try:
                out, err = await asyncio.wait_for(process.communicate(stdin.encode('utf-8') if stdin is not None else None), timeout=max(timeout, 60))
            except asyncio.TimeoutError:
                process.kill()
                await asyncio.gather(process.wait(), return_exceptions=True)
                raise TimeoutError(f'命令在{int(max(timeout, 60))}秒内没有返回。')
            stdout = out.decode('utf-8', 'replace')
            if process.returncode != 0 and not stdout.strip():
                raise RuntimeError((err.decode('utf-8', 'replace').strip() or f'退出码 {process.returncode}')[:300])
            text = self.parse_output(stdout, output_file)
            content, thinking = split_thinking(text)
            if schema:
                fragment = extract_json(content)
                if not fragment:
                    raise ValueError('命令没有返回 JSON：'+content[:160])
                content = fragment
            self._record(start, output_chars=len(content), model=self.model)
            return Reply(content=content, finish_reason='stop', usage={'output_chars': len(content)}, thinking=thinking)
        except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
            detail = str(exc)[:400]
            self._record(start, error=detail)
            return Reply(content=self.label+'调用失败：'+detail, finish_reason='error')
        finally:
            shutil.rmtree(folder, ignore_errors=True)


class ClaudeCliProvider(CommandProvider):
    """Claude Code in headless mode (`claude -p`), on the user's own subscription login."""
    kind = 'claude_cli'
    label = 'Claude 命令行'

    def __init__(self, command='claude', model='', context=8192, workdir=''):
        base = command.strip() or 'claude'
        full = base+' -p --output-format json'+(' --model {model}' if model else '')
        super().__init__(full, model or 'claude', prompt_via='stdin', output='json:result', context=context, workdir=workdir)
        self.claude_command = base
        self.profile['supports_think'] = False


def provider_from_config(config):
    """Legacy shape: {"model": "...", "provider": "ollama"|"openai", "base": "...", "api_key": "...", "context": 8192}.
    New installs use backends.build_provider; this stays for older config files and tests."""
    kind = config.get('provider', 'ollama')
    context = int(config.get('context', 8192))
    if kind == 'openai':
        return OpenAICompatibleProvider(config.get('model', 'local'), config.get('base', 'http://127.0.0.1:1234/v1'),
                                        config.get('api_key', ''), context)
    return OllamaProvider(config.get('model', 'qwen3:4b-instruct-2507-q4_K_M'), config.get('base', 'http://127.0.0.1:11434'), context,
                          thinking_model=config.get('thinking_model', ''), hybrid=bool(config.get('hybrid')))
