"""A canned model for UI work and demos: answers every schema plausibly without any model server.

Enabled with the environment variable LULU_FAKE_MODEL=1 (or backend "fake" in config). Nothing it says is real; the
work window shows it as 演示模型 so nobody mistakes a rehearsal for the product.
"""
import json
import re

from . import intent as intents
from .models import ModelProvider, Reply


class FakeProvider(ModelProvider):
    kind = 'fake'
    label = '演示模型'

    def __init__(self):
        super().__init__('演示模型（不是真的模型）', 'fake://')
        self.profile.update(supports_schema=True, supports_tools=False, supports_think=True)

    async def models(self):
        return [self.model]

    async def chat(self, messages, tools=None, *, schema=None, max_tokens=1200, temperature=0.0, timeout=120, think=False):
        user = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), '')
        title = schema.get('title') if schema else ''
        try:
            data = json.loads(user)
        except ValueError:
            data = {}
        content = self.answer(title, user, data if isinstance(data, dict) else {})
        self._record(0, model=self.model, think=think, thinking_chars=42 if think else 0)
        return Reply(content=content, thinking='（演示：这里本来是思考过程）' if think else '')

    def answer(self, title, user, data):
        if title == 'intent':
            return json.dumps(intents.heuristic(data.get('用户请求', user)), ensure_ascii=False)
        if title == 'summary':
            text = data.get('原文', '')
            first = re.split(r'[。\n]', text.strip())[0][:80]
            return json.dumps({'summary': (first+'。') if first else '（演示摘要）', 'points': [p.strip()[:40] for p in re.split(r'[。\n]', text) if p.strip()][:3]}, ensure_ascii=False)
        if title == 'extract':
            return json.dumps({'fields': []}, ensure_ascii=False)
        if title == 'translation':
            src = data.get('原文', '')
            return json.dumps({'translation': '[演示译文 → '+data.get('目标语言', '')+'] '+src}, ensure_ascii=False)
        if title == 'rewrite':
            return json.dumps({'text': '（演示改写）'+data.get('原文', '')}, ensure_ascii=False)
        if title == 'ask_file':
            text = data.get('文件内容', '')
            quote = re.split(r'[。\n]', text.strip())[0][:60]
            return json.dumps({'answer': '（演示回答）'+quote, 'quote': quote, 'found': bool(quote)}, ensure_ascii=False)
        if title == 'extract_rows':
            cols = data.get('表格列', [])
            words = re.findall(r'[一-鿿A-Za-z0-9]{2,}', data.get('原文', ''))
            rows = [{c: (words[i*len(cols)+j] if i*len(cols)+j < len(words) else '') for j, c in enumerate(cols)} for i in range(min(3, max(1, len(words)//max(1, len(cols)))))]
            return json.dumps({'rows': rows}, ensure_ascii=False)
        if title == 'draft':
            return json.dumps({'status': 'deliverable', 'title': '演示文档', 'body_markdown': '# 演示文档\n\n这是演示模型写的正文，只用来看界面。\n\n'+data.get('请求', '')[:200], 'assumptions': [], 'questions': [], 'reason': ''}, ensure_ascii=False)
        if title == 'judge':
            return json.dumps({'verdict': 'finished'})
        if title == 'queries':
            return json.dumps({'queries': []})
        if title == 'facts':
            return json.dumps({'facts': []})
        if title == 'memory':
            return json.dumps({'key': '演示记忆', 'value': user[:60]}, ensure_ascii=False)
        if title == 'candidates':
            return json.dumps({'candidates': []})
        if title == 'answer':
            return json.dumps({'answer': '（演示回答）资料里没有可核对的内容。'}, ensure_ascii=False)
        text = user.split('用户：')[-1][:80]
        return '（演示模型）我在，你说的是：'+text
