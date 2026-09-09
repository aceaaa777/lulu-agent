"""Speed-derived budgets. Timeouts and context sizes come from a measurement, not from constants tuned on one Mac."""
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path

CHARS_PER_TOKEN = 1.6   # conservative for mixed Chinese/JSON prompts on Qwen tokenizers


def physical_memory_gb():
    try:
        if hasattr(os, 'sysconf') and os.sysconf_names.get('SC_PHYS_PAGES'):
            return os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')/2**30
    except (ValueError, OSError):
        pass
    try:
        import ctypes
        class Status(ctypes.Structure):
            _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong),
                        ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
        status = Status(); status.dwLength = ctypes.sizeof(Status)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return status.ullTotalPhys/2**30
    except (AttributeError, OSError):
        return 0.0


@dataclass
class Budget:
    tier: str = 'B'                 # A: 8GB-class, B: 16GB-class, C: external endpoint
    context: int = 8192
    prompt_chars: int = 7000        # hard cap on assembled prompt characters
    max_output_tokens: int = 1600
    generate_tps: float = 0.0       # measured tokens/second, 0 = unknown
    prefill_tps: float = 0.0
    num_thread: int = 4
    memory_gb: float = 0.0
    measured_at: float = 0.0
    model: str = ''

    def step_timeout(self, prompt_chars, expected_output_tokens):
        """Seconds allowed for one model call. Unknown speed falls back to a low-spec assumption (3 tok/s, 40 tok/s prefill)."""
        gen = self.generate_tps or 3.0
        pre = self.prefill_tps or 40.0
        seconds = prompt_chars/CHARS_PER_TOKEN/pre + expected_output_tokens/gen
        return int(min(900, max(45, seconds*1.5+10)))

    def task_timeout(self, steps):
        return int(min(3600, max(120, steps*self.step_timeout(self.prompt_chars, 400)+self.step_timeout(self.prompt_chars, self.max_output_tokens))))

    def to_json(self):
        return asdict(self)


def default_budget(model=''):
    memory = physical_memory_gb()
    cores = os.cpu_count() or 2
    budget = Budget(model=model, memory_gb=round(memory, 1), num_thread=max(2, min(8, cores-1)))
    if 0 < memory < 12:
        budget.tier, budget.context, budget.prompt_chars, budget.max_output_tokens = 'A', 4096, 3600, 1200
    return budget


def load(path, model=''):
    path = Path(path)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            budget = Budget(**{k: v for k, v in data.items() if k in Budget.__dataclass_fields__})
            if budget.model == model or not model:
                return budget
        except (ValueError, TypeError):
            pass
    return default_budget(model)


def save(path, budget):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(budget.to_json(), ensure_ascii=False, indent=2), encoding='utf-8')


async def measure(provider, path=None):
    """One short generation and one long prompt. Writes the result when a path is given."""
    budget = default_budget(provider.model)
    provider.num_thread = budget.num_thread
    start = time.monotonic()
    short = await provider.chat([{'role': 'user', 'content': '请用中文数数，从一数到二十，每个数字用顿号分隔。'}], max_tokens=64, temperature=0, timeout=300)
    if short.failed:
        return budget, short.content
    usage = short.usage or {}
    if usage.get('eval_seconds') and usage.get('output_tokens'):
        budget.generate_tps = round(usage['output_tokens']/max(usage['eval_seconds'], 0.01), 1)
    else:
        budget.generate_tps = round((usage.get('output_tokens') or 32)/max(time.monotonic()-start, 0.01), 1)
    filler = '这是用于测量提示词处理速度的中文段落，内容本身没有意义，只用来占据上下文。'*40
    start = time.monotonic()
    long = await provider.chat([{'role': 'user', 'content': filler+'\n只回答“好”。'}], max_tokens=4, temperature=0, timeout=600)
    usage = long.usage or {}
    if not long.failed:
        if usage.get('prompt_seconds') and usage.get('input_tokens'):
            budget.prefill_tps = round(usage['input_tokens']/max(usage['prompt_seconds'], 0.01), 1)
        else:
            budget.prefill_tps = round((usage.get('input_tokens') or len(filler)/CHARS_PER_TOKEN)/max(time.monotonic()-start, 0.01), 1)
    budget.measured_at = time.time()
    if budget.generate_tps and budget.generate_tps < 2.5 and budget.tier != 'A':
        budget.tier, budget.context, budget.prompt_chars, budget.max_output_tokens = 'A', 4096, 3600, 1200
    provider.context = budget.context
    if path:
        save(path, budget)
    return budget, None
