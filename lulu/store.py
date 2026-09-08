"""Local durable memory and task ledger. SQLite only: no vector service, no background model."""
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path


def uid():
    return uuid.uuid4().hex[:16]


CORE_KEYS_LIMIT = 12


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA secure_delete=ON;
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value INTEGER);
        INSERT OR IGNORE INTO meta VALUES('epoch',0);
        CREATE TABLE IF NOT EXISTS memories(
          key TEXT PRIMARY KEY,value TEXT NOT NULL,source TEXT NOT NULL,
          category TEXT NOT NULL,updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,title TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS messages(
          id INTEGER PRIMARY KEY,session TEXT,role TEXT,content TEXT,epoch INTEGER,created REAL);
        CREATE TABLE IF NOT EXISTS tasks(
          id TEXT PRIMARY KEY,session TEXT,goal TEXT,status TEXT,checkpoint TEXT,
          answer TEXT,epoch INTEGER,created REAL,updated REAL);
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY,task TEXT,kind TEXT,detail TEXT,epoch INTEGER,created REAL);
        CREATE TABLE IF NOT EXISTS questions(
          id TEXT PRIMARY KEY,task TEXT NOT NULL,question TEXT NOT NULL,reason TEXT NOT NULL,
          status TEXT NOT NULL,answer TEXT NOT NULL,continuation TEXT NOT NULL,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS reminders(
          id TEXT PRIMARY KEY,text TEXT,due REAL,interval INTEGER,status TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS task_steps(
          id INTEGER PRIMARY KEY,task TEXT NOT NULL,seq INTEGER NOT NULL,kind TEXT NOT NULL,args_hash TEXT NOT NULL,
          status TEXT NOT NULL,result TEXT NOT NULL,artifact TEXT,sha256 TEXT,started REAL,finished REAL);
        CREATE INDEX IF NOT EXISTS task_steps_task ON task_steps(task,args_hash);
        CREATE TABLE IF NOT EXISTS evidence(
          id TEXT PRIMARY KEY,task TEXT NOT NULL,kind TEXT NOT NULL,source TEXT NOT NULL,data_ts TEXT,
          fetched_at TEXT NOT NULL,payload TEXT NOT NULL,digest TEXT,created REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS evidence_task ON evidence(task);
        CREATE TABLE IF NOT EXISTS memory_candidates(
          id TEXT PRIMARY KEY,task TEXT NOT NULL,key TEXT NOT NULL,value TEXT NOT NULL,quote TEXT NOT NULL,
          status TEXT NOT NULL,created REAL NOT NULL);
        """)
        self._migrate()
        self.fts = self._init_fts()
        self.db.execute("UPDATE tasks SET status='interrupted' WHERE status IN ('queued','running')")
        self.db.commit()

    def _migrate(self):
        columns = {row['name'] for row in self.db.execute('PRAGMA table_info(tasks)')}
        for name, ddl in (('phase', "TEXT NOT NULL DEFAULT ''"), ('intent', "TEXT NOT NULL DEFAULT ''"), ('plan', "TEXT NOT NULL DEFAULT ''"),
                          ('answers', "TEXT NOT NULL DEFAULT '[]'"), ('memory_refs', "TEXT NOT NULL DEFAULT '[]'")):
            if name not in columns:
                self.db.execute(f'ALTER TABLE tasks ADD COLUMN {name} {ddl}')
        for table in ('messages', 'events'):
            if 'memory_refs' not in {row['name'] for row in self.db.execute(f'PRAGMA table_info({table})')}:
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN memory_refs TEXT NOT NULL DEFAULT '[]'")
        if 'options' not in {row['name'] for row in self.db.execute('PRAGMA table_info(questions)')}:
            self.db.execute("ALTER TABLE questions ADD COLUMN options TEXT NOT NULL DEFAULT '[]'")
            self.db.execute("ALTER TABLE questions ADD COLUMN phase TEXT NOT NULL DEFAULT ''")
        self.db.commit()

    def _init_fts(self):
        """FTS5 with trigram tokenizer for Chinese. Falls back to substring matching on old SQLite builds."""
        try:
            self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(key,value,tokenize='trigram')")
            count = self.db.execute('SELECT count(*) FROM memories_fts').fetchone()[0]
            if count != self.db.execute('SELECT count(*) FROM memories').fetchone()[0]:
                self.db.execute('DELETE FROM memories_fts')
                self.db.execute('INSERT INTO memories_fts(key,value) SELECT key,value FROM memories')
            self.db.commit()
            return True
        except sqlite3.OperationalError:
            return False

    @property
    def epoch(self):
        return self.db.execute("SELECT value FROM meta WHERE key='epoch'").fetchone()[0]

    def rows(self, sql, args=()):
        return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def session(self, title='新对话'):
        sid = uid()
        with self.db:
            self.db.execute('INSERT INTO sessions VALUES(?,?,?)', (sid, title[:60], time.time()))
        return sid

    # ---------------------------------------------------------------- memory
    def remember(self, key, value, source, category='preference'):
        key, value, source = key.strip(), value.strip(), source.strip()
        if not key or not value or not source or len(key) > 100 or len(value) > 1200:
            raise ValueError('记忆需要名称、内容和来源；名称最多100字，内容最多1200字。')
        if category not in ('preference', 'fact', 'habit', 'core'):
            raise ValueError('无效记忆类别')
        old = self.db.execute('SELECT value FROM memories WHERE key=?', (key,)).fetchone()
        with self.db:
            # A correction invalidates historical prompts, so an obsolete preference cannot win.
            if old and old[0] != value:
                self.db.execute("UPDATE meta SET value=value+1 WHERE key='epoch'")
            self.db.execute('INSERT OR REPLACE INTO memories VALUES(?,?,?,?,?)', (key, value, source[:1200], category, time.time()))
            if self.fts:
                self.db.execute('DELETE FROM memories_fts WHERE key=?', (key,))
                self.db.execute('INSERT INTO memories_fts(key,value) VALUES(?,?)', (key, value))
        return {'key': key, 'value': value, 'saved': True}

    def forget(self, key, keep_task=None):
        """Precise deletion: the memory plus every message/event/task context that was built with it in the prompt.
        keep_task: the task doing the forgetting keeps its own record."""
        with self.db:
            cur = self.db.execute('DELETE FROM memories WHERE key=?', (key,))
            if not cur.rowcount:
                raise ValueError('找不到这条记忆')
            if self.fts:
                self.db.execute('DELETE FROM memories_fts WHERE key=?', (key,))
            self.db.execute("UPDATE meta SET value=value+1 WHERE key='epoch'")
            needle = json.dumps(key, ensure_ascii=False)
            affected_tasks = [r['id'] for r in self.db.execute('SELECT id FROM tasks WHERE instr(memory_refs,?)>0 AND id IS NOT ?', (needle, keep_task))]
            self.db.execute('DELETE FROM messages WHERE instr(memory_refs,?)>0', (needle,))
            self.db.execute('DELETE FROM events WHERE instr(memory_refs,?)>0 AND task IS NOT ?', (needle, keep_task))
            for tid in affected_tasks:
                self.db.execute('DELETE FROM events WHERE task=?', (tid,))
                self.db.execute('DELETE FROM questions WHERE task=?', (tid,))
                self.db.execute('DELETE FROM evidence WHERE task=?', (tid,))
                self.db.execute("UPDATE tasks SET checkpoint='',answer='',plan='',intent='',answers='[]',memory_refs='[]' WHERE id=?", (tid,))
        self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        return {'deleted': key, 'history_cleared': bool(affected_tasks), 'affected_tasks': len(affected_tasks)}

    def _terms(self, query):
        terms = set(re.findall(r'[a-zA-Z0-9]+|[\u4e00-\u9fff]{1,}', query.lower()))
        for term in list(terms):
            if re.search(r'[\u4e00-\u9fff]', term):
                terms.update(term[i:i+2] for i in range(len(term)-1))
        return sorted(terms, key=lambda t: (-len(t), t))[:32]

    def memories(self, query='', limit=12):
        if not query:
            return self.rows('SELECT * FROM memories ORDER BY updated DESC LIMIT ?', (limit,))
        terms = self._terms(query)
        if not terms:
            return []
        rows = []
        if self.fts:
            grams = [t for t in terms if len(t) >= 3] or [t for t in terms if len(t) == 2]
            if grams:
                match = ' OR '.join('"'+g.replace('"', '')+'"' for g in grams[:24])
                try:
                    rows = self.rows('SELECT m.* FROM memories_fts f JOIN memories m ON m.key=f.key WHERE memories_fts MATCH ? ORDER BY bm25(memories_fts) LIMIT 200', (match,))
                except sqlite3.OperationalError:
                    rows = []
        if not rows:
            rows = self.rows('SELECT * FROM memories WHERE '+' OR '.join("instr(lower(key || ' ' || value),?)>0" for _ in terms)+' ORDER BY updated DESC LIMIT 200', terms)

        def score(row):
            text = (row['key']+' '+row['value']).lower()
            return sum(len(t) for t in terms if t in text)
        rows = sorted((r for r in rows if score(r)), key=score, reverse=True)
        return rows[:limit]

    def add_memory_candidate(self, tid, key, value, quote):
        if self.rows("SELECT 1 FROM memories WHERE key=? AND value=?", (key, value)) or self.rows("SELECT 1 FROM memory_candidates WHERE key=? AND value=? AND status='pending'", (key, value)):
            return None
        ident = uid()
        with self.db:
            self.db.execute('INSERT INTO memory_candidates VALUES(?,?,?,?,?,?,?)', (ident, tid, key, value, quote, 'pending', time.time()))
        return ident

    def memory_candidates(self):
        return self.rows("SELECT * FROM memory_candidates WHERE status='pending' ORDER BY created DESC LIMIT 20")

    def resolve_candidate(self, ident, accept):
        rows = self.rows('SELECT * FROM memory_candidates WHERE id=?', (ident,))
        if not rows:
            raise ValueError('候选记忆不存在')
        c = rows[0]
        with self.db:
            self.db.execute('UPDATE memory_candidates SET status=? WHERE id=?', ('accepted' if accept else 'rejected', ident))
        if accept:
            return self.remember(c['key'], c['value'], c['quote'])
        return {'rejected': ident}

    def core_memory(self):
        return self.rows("SELECT * FROM memories WHERE category='core' ORDER BY updated DESC LIMIT ?", (CORE_KEYS_LIMIT,))

    def memory_context(self, query, budget=2200):
        relevant = self.memories(query, 8)
        general = self.rows("SELECT * FROM memories WHERE category='preference' ORDER BY updated DESC LIMIT 12")
        selected, seen, size = [], set(), 0
        for row in self.core_memory()+relevant+general:
            if row['key'] in seen:
                continue
            entry = {'key': row['key'], 'value': row['value'], 'source': row['source'][:500]}
            n = len(json.dumps(entry, ensure_ascii=False))
            if size+n > budget:
                continue
            selected.append(entry); seen.add(row['key']); size += n
        return selected

    # ------------------------------------------------------------- messages
    def message(self, session, role, content, memory_refs=()):
        with self.db:
            self.db.execute('INSERT INTO messages(session,role,content,epoch,created,memory_refs) VALUES(?,?,?,?,?,?)',
                            (session, role, content, self.epoch, time.time(), json.dumps(list(memory_refs), ensure_ascii=False)))

    def history(self, session, budget=3500):
        rows = self.rows('SELECT role,content FROM messages WHERE session=? AND epoch=? ORDER BY id DESC LIMIT 16', (session, self.epoch))
        selected, size = [], 0
        for row in rows:
            if size+len(row['content']) > budget:
                break
            selected.append(row); size += len(row['content'])
        return list(reversed(selected))

    def recent_task_context(self, session, exclude):
        rows = self.rows('SELECT id,goal,checkpoint,status FROM tasks WHERE session=? AND epoch=? AND id!=? ORDER BY updated DESC LIMIT 3', (session, self.epoch, exclude))
        result = []
        for row in rows:
            artifacts = [r['artifact'] for r in self.rows("SELECT artifact FROM task_steps WHERE task=? AND artifact IS NOT NULL AND status='done' ORDER BY id DESC LIMIT 5", (row['id'],))]
            if not artifacts:
                for receipt in self.rows("SELECT detail FROM events WHERE task=? AND epoch=? AND kind='tool_done' ORDER BY id DESC LIMIT 5", (row['id'], self.epoch)):
                    data = json.loads(receipt['detail']).get('result')
                    if isinstance(data, dict) and data.get('path'):
                        artifacts.append(data['path'])
            result.append({'id': row['id'], 'goal': row['goal'][:300], 'checkpoint': row['checkpoint'][:500], 'status': row['status'], 'artifacts': artifacts})
        return result

    # ---------------------------------------------------------------- tasks
    def create_task(self, session, goal):
        tid, now = uid(), time.time()
        with self.db:
            self.db.execute('INSERT INTO tasks(id,session,goal,status,checkpoint,answer,epoch,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',
                            (tid, session, goal, 'queued', '', '', self.epoch, now, now))
        return tid

    def task(self, tid):
        rows = self.rows('SELECT * FROM tasks WHERE id=?', (tid,))
        if not rows:
            raise ValueError('任务不存在')
        return rows[0]

    def update_task(self, tid, **values):
        if not set(values) <= {'status', 'checkpoint', 'answer', 'phase', 'intent', 'plan', 'answers', 'memory_refs'}:
            raise ValueError('无效任务字段')
        for key in ('intent', 'plan', 'answers', 'memory_refs'):
            if key in values and not isinstance(values[key], str):
                values[key] = json.dumps(values[key], ensure_ascii=False)
        values['updated'] = time.time()
        with self.db:
            self.db.execute('UPDATE tasks SET '+','.join(k+'=?' for k in values)+' WHERE id=?', (*values.values(), tid))

    def event(self, tid, kind, detail, memory_refs=()):
        with self.db:
            self.db.execute('INSERT INTO events(task,kind,detail,epoch,created,memory_refs) VALUES(?,?,?,?,?,?)',
                            (tid, kind, json.dumps(detail, ensure_ascii=False, default=str), self.epoch, time.time(), json.dumps(list(memory_refs), ensure_ascii=False)))

    def task_context(self, tid):
        task = self.task(tid)
        if task['epoch'] != self.epoch:
            return {'notice': '记忆已纠正或删除，旧任务上下文不自动加载。请重新给出需要续办的要求。'}
        events = self.rows('SELECT kind,detail FROM events WHERE task=? AND epoch=? ORDER BY id DESC LIMIT 8', (tid, self.epoch))
        steps = self.rows("SELECT kind,artifact,status FROM task_steps WHERE task=? AND status='done' ORDER BY seq", (tid,))
        return {'goal': task['goal'], 'checkpoint': task['checkpoint'], 'status': task['status'], 'phase': task['phase'],
                'answer': task['answer'][:1000], 'recent_events': list(reversed(events)),
                'artifacts': [s['artifact'] for s in steps if s['artifact']], 'answers': json.loads(task['answers'] or '[]')}

    # ---------------------------------------------------------- steps/evidence
    def find_step(self, tid, args_hash):
        rows = self.rows("SELECT * FROM task_steps WHERE task=? AND args_hash=? AND status='done' ORDER BY id DESC LIMIT 1", (tid, args_hash))
        return rows[0] if rows else None

    def start_step(self, tid, kind, args_hash):
        seq = (self.db.execute('SELECT coalesce(max(seq),0) FROM task_steps WHERE task=?', (tid,)).fetchone()[0] or 0)+1
        with self.db:
            cur = self.db.execute('INSERT INTO task_steps(task,seq,kind,args_hash,status,result,started) VALUES(?,?,?,?,?,?,?)',
                                  (tid, seq, kind, args_hash, 'running', '', time.time()))
        return cur.lastrowid

    def finish_step(self, step_id, status, result, artifact=None, sha256=None):
        with self.db:
            self.db.execute('UPDATE task_steps SET status=?,result=?,artifact=?,sha256=?,finished=? WHERE id=?',
                            (status, json.dumps(result, ensure_ascii=False, default=str)[:20000], artifact, sha256, time.time(), step_id))

    def steps(self, tid):
        return self.rows('SELECT * FROM task_steps WHERE task=? ORDER BY seq', (tid,))

    def add_evidence(self, tid, kind, source, payload, data_ts=None, fetched_at=None, digest=None):
        ident = uid()
        with self.db:
            self.db.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?)',
                            (ident, tid, kind, source, data_ts, fetched_at or time.strftime('%Y-%m-%dT%H:%M:%S'),
                             json.dumps(payload, ensure_ascii=False, default=str)[:60000], digest, time.time()))
        return ident

    def evidence(self, tid):
        rows = self.rows('SELECT * FROM evidence WHERE task=? ORDER BY created', (tid,))
        for row in rows:
            try:
                row['payload'] = json.loads(row['payload'])
            except ValueError:
                pass
        return rows

    # ------------------------------------------------------------ questions
    def ask(self, tid, question, reason, options=(), phase=''):
        existing = self.rows("SELECT * FROM questions WHERE task=? AND status='pending'", (tid,))
        if existing:
            return existing[0]
        ident = uid()
        with self.db:
            self.db.execute('INSERT INTO questions(id,task,question,reason,status,answer,continuation,created,options,phase) VALUES(?,?,?,?,?,?,?,?,?,?)',
                            (ident, tid, question, reason, 'pending', '', '', time.time(), json.dumps(list(options), ensure_ascii=False), phase))
        self.event(tid, 'user_input_required', {'question_id': ident, 'question': question, 'reason': reason, 'options': list(options)})
        return self.rows('SELECT * FROM questions WHERE id=?', (ident,))[0]

    def answer_question(self, ident, answer):
        """The same task continues from the phase where it stopped. Returns (task_id, created)."""
        rows = self.rows('SELECT * FROM questions WHERE id=?', (ident,))
        if not rows:
            raise ValueError('待回答问题不存在')
        q = rows[0]
        if q['status'] == 'answered':
            return q['continuation'], False
        if q['status'] != 'pending':
            raise ValueError('该问题已经关闭')
        if not isinstance(answer, str) or not 1 <= len(answer.strip()) <= 4000:
            raise ValueError('请填写1–4000字的答复')
        task = self.task(q['task'])
        answers = json.loads(task['answers'] or '[]')
        answers.append({'question': q['question'], 'answer': answer.strip(), 'at': time.time()})
        now = time.time()
        with self.db:
            self.db.execute("UPDATE questions SET status='answered',answer=?,continuation=? WHERE id=?", (answer.strip(), task['id'], ident))
            self.db.execute("UPDATE tasks SET status='queued',answers=?,updated=? WHERE id=?", (json.dumps(answers, ensure_ascii=False), now, task['id']))
        self.event(task['id'], 'user_input_answered', {'question': q['question'], 'answer': answer.strip()})
        return task['id'], True

    # ------------------------------------------------------------ reminders
    def add_reminder(self, text, due, interval=0):
        if due <= time.time() or interval < 0 or (interval and interval < 60):
            raise ValueError('提醒时间须在未来；重复间隔至少60秒')
        rid = uid()
        with self.db:
            self.db.execute('INSERT INTO reminders VALUES(?,?,?,?,?,?)', (rid, text[:500], due, interval, 'pending', time.time()))
        return {'id': rid, 'text': text, 'due': due, 'interval': interval}

    def acknowledge(self, rid):
        rows = self.rows('SELECT * FROM reminders WHERE id=?', (rid,))
        if not rows:
            raise ValueError('提醒不存在')
        row = rows[0]
        with self.db:
            if row['interval']:
                steps = max(1, int((time.time()-row['due'])//row['interval'])+1)
                self.db.execute('UPDATE reminders SET due=?,status=? WHERE id=?', (row['due']+steps*row['interval'], 'pending', rid))
            else:
                self.db.execute("UPDATE reminders SET status='done' WHERE id=?", (rid,))
