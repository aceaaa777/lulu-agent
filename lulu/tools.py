"""Local capabilities: files, documents, memory, reminders, search. Plain async functions, no agent framework."""
import asyncio
import json
import re
from datetime import datetime

from . import websearch

S = {'type': 'string'}


class ToolError(ValueError):
    pass


class Tools:
    def __init__(self, store, files):
        self.store, self.files = store, files

    async def execute(self, tid, user_text, name, args):
        """Run one capability with event logging. Returns a JSON-serialisable result or raises ToolError."""
        self.store.event(tid, 'tool_started', {'tool': name, 'arguments': args})
        work = asyncio.create_task(self._dispatch(user_text, name, args))
        try:
            result = await asyncio.shield(work)
            self.store.event(tid, 'tool_done', {'tool': name, 'action': args.get('action'), 'result': result})
            return result
        except asyncio.CancelledError:
            # Complete an admitted file write before releasing the single-task lock, so cancellation never reports idle
            # while a worker still mutates files.
            try:
                result = await work
                self.store.event(tid, 'tool_done', {'tool': name, 'result': result, 'cancel_requested': True})
            except Exception as exc:
                self.store.event(tid, 'tool_failed', {'tool': name, 'error': str(exc)})
            raise
        except Exception as exc:
            self.store.event(tid, 'tool_failed', {'tool': name, 'error': str(exc)[:500]})
            raise ToolError(str(exc)[:500])

    async def _dispatch(self, user_text, name, args):
        handler = getattr(self, 'do_'+name, None)
        if handler is None:
            raise ValueError('未知工具 '+name)
        return await handler(user_text, **args)

    # ------------------------------------------------------------------ memory
    async def do_memory(self, user_text, action, key='', value='', quote='', query=''):
        if action == 'save':
            if not quote or quote not in user_text:
                raise ValueError('只能从本轮用户原话保存记忆；quote必须是原话的连续摘录。')
            return self.store.remember(key, value, quote)
        if action == 'recall':
            return self.store.memories(query, 20)
        raise ValueError('无效记忆操作')

    # ------------------------------------------------------------------- files
    async def do_file(self, user_text, action, path='', content='', old='', new='', offset=0, limit=3000, overwrite=False, replace_all=False):
        if action == 'list':
            return self.files.listing(path)
        if action == 'read':
            text = await asyncio.to_thread(self.files.read, path)
            return {'path': path, 'total_chars': len(text), 'offset': offset, 'text': text[offset:offset+limit],
                    'next_offset': offset+limit if offset+limit < len(text) else None}
        if action == 'write':
            # Literal user requirements are deterministic constraints, not paraphrasing hints.
            for literal in re.findall(r'(?:明确写出|包含原文|原样写入)[“"](.+?)[”"]', user_text):
                if literal not in content:
                    raise ValueError('用户要求文档原样包含“'+literal+'”，当前内容缺失。请把原句正确写入正文，不要改写这句话。尚未写入文件。')
            return await asyncio.to_thread(self.files.write, path, content, overwrite=overwrite)
        if action == 'edit':
            return await asyncio.to_thread(self.files.edit, path, old, new, replace_all)
        raise ValueError('无效文件操作')

    async def do_document(self, user_text, action, path, destination='', rows=None, cell='', value=''):
        if action == 'convert':
            return await asyncio.to_thread(self.files.convert, path, destination)
        if action == 'analyze':
            return await asyncio.to_thread(self.files.analyze, path)
        if action == 'table':
            return await asyncio.to_thread(self.files.write, path, rows=rows or [])
        if action == 'cell':
            return await asyncio.to_thread(self.files.cell, path, cell, value)
        raise ValueError('无效文档操作')

    # -------------------------------------------------------------------- tasks
    async def do_task(self, user_text, action, tid='', checkpoint='', task_id='', query=''):
        if action == 'checkpoint':
            self.store.update_task(tid, checkpoint=checkpoint[:2200])
            return {'saved': True}
        if action == 'recall':
            return self.store.task_context(task_id)
        if action == 'search':
            return self.store.rows('SELECT id,goal,status,checkpoint FROM tasks WHERE epoch=? AND goal LIKE ? ORDER BY updated DESC LIMIT 8',
                                   (self.store.epoch, '%'+query+'%'))
        raise ValueError('无效任务操作')

    # ---------------------------------------------------------------- reminders
    async def do_reminder(self, user_text, action, text='', at='', interval=0, reminder_id=''):
        if action == 'add':
            when = datetime.fromisoformat(at).astimezone().timestamp()
            return self.store.add_reminder(text, when, int(interval or 0))
        if action == 'list':
            return self.store.rows("SELECT * FROM reminders WHERE status='pending' ORDER BY due")
        if action == 'cancel':
            with self.store.db:
                cur = self.store.db.execute("UPDATE reminders SET status='cancelled' WHERE id=?", (reminder_id,))
            if not cur.rowcount:
                raise ValueError('提醒不存在')
            return {'cancelled': reminder_id}
        raise ValueError('无效提醒操作')

    # ------------------------------------------------------------------- search
    async def do_search(self, user_text, action, query):
        if action == 'local':
            matches = self.files.listing(query)
            if matches:
                return matches
            result = []
            for item in self.files.listing()[:80]:
                if item['bytes'] > 1_000_000:
                    continue
                try:
                    text = await asyncio.to_thread(self.files.read, item['path'])
                    idx = text.lower().find(query.lower())
                    if idx >= 0:
                        result.append({'path': item['path'], 'excerpt': text[max(0, idx-100):idx+400]})
                except (ValueError, UnicodeError):
                    pass
                if len(result) >= 10:
                    break
            return result
        if action == 'web':
            try:
                results, engine, failures = await websearch.search(query, count=6)
            except websearch.SearchError as exc:
                raise ValueError(exc.detail or exc.reason)
            return {'engine': engine, 'results': results}
        if action == 'url':
            return await websearch.fetch(query, max_chars=3500)
        raise ValueError('无效搜索操作')
