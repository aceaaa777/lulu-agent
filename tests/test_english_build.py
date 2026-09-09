"""The English tree: produced by packaging/localize.py from this checkout, it must compile, import, keep the tag row and
serve English answers end to end through the demo model — the same path the English package's users take."""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r'[一-鿿]')


@pytest.fixture(scope='module')
def english_tree(tmp_path_factory):
    out = tmp_path_factory.mktemp('src-en')
    result = subprocess.run([sys.executable, str(ROOT / 'packaging/localize.py'), '--lang', 'en', '--out', str(out)], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout+result.stderr
    assert 'renamed' in result.stdout
    return out


def test_tree_compiles_and_reads_english(english_tree):
    assert subprocess.run([sys.executable, '-m', 'compileall', '-q', str(english_tree / 'lulu'), str(english_tree / 'packaging')]).returncode == 0
    assert (english_tree / 'lulu/lang.py').read_text(encoding='utf-8').strip().endswith("LANG = 'en'")
    probe = subprocess.run([sys.executable, '-c', 'import sys,json; sys.path.insert(0, sys.argv[1]); from lulu import skills, server; '
                            'print(json.dumps([skills.LABELS, skills.TIME_OPTIONS, skills.OPTIONS["scope"], server.VERSION]))', str(english_tree)],
                           capture_output=True, text=True)
    assert probe.returncode == 0, probe.stderr
    labels, time_options, scope, version = json.loads(probe.stdout)
    assert labels['translate'] == 'Translate' and labels['remind'] == 'Remind me' and not any(CJK.search(v) for v in labels.values())
    assert time_options == ['In 10 minutes', 'In 30 minutes', 'In 1 hour', 'Tomorrow at 9 AM']
    assert not any(CJK.search(v) for v in scope)
    assert 'var english := true' in (english_tree / 'desktop/src/animation_state.gd').read_text(encoding='utf-8')   # done board by default
    gd = (english_tree / 'desktop/src/pet.gd').read_text(encoding='utf-8')
    assert "'label':'Translate'" in gd and 'Interface size' in gd
    assert subprocess.run([sys.executable, str(ROOT / 'packaging/check_gdscript_strings.py'), str(english_tree / 'desktop/src')]).returncode == 0
    for name in ['packaging/installer/Install and start Lulu.command', 'packaging/installer/Install and start Lulu.cmd', 'packaging/installer/tools/Install and start.ps1',
                 'packaging/installer/Start here.md', 'Install local models.command', 'Check backend.command']:
        assert (english_tree / name).exists(), name
    readme = (english_tree / 'packaging/installer/Start here.md').read_text(encoding='utf-8')
    assert not CJK.search(readme) and '{installer}' in readme and '{data_dir}' in readme and '{log_path}' in readme
    for script in ['packaging/installer/Install and start Lulu.command', 'Install local models.command', 'Check backend.command']:
        text = (english_tree / script).read_text(encoding='utf-8')
        assert not CJK.search(text), script
        assert '安装' not in text
    build = (english_tree / 'packaging/build_release.py').read_text(encoding='utf-8')
    assert 'Install local models.command' in build and 'Start here.md' in build and "'Install and start Lulu.command'" in build


def wait_for(path, seconds=40):
    for _ in range(int(seconds*4)):
        if path.exists():
            return True
        time.sleep(.25)
    return False


@pytest.fixture(scope='module')
def english_server(english_tree, tmp_path_factory):
    home = tmp_path_factory.mktemp('home')
    (home / 'workspace').mkdir()
    (home / 'workspace/minutes.md').write_text('Meeting minutes\nDate: 2026-09-01\nDecision: project code name Pine 731, owner Lu Yao, budget 18650, deadline 2026-11-23.\nNext: Zhou Wen collects requirements.\n', encoding='utf-8')
    env = dict(os.environ, LULU_FAKE_MODEL='1', LULU_NO_LOCATE='1', PYTHONPATH=str(english_tree))
    port = 8794
    # the same server run.py starts, without run.py's Python-version gate (the test machine may be older than the package's runtime)
    boot = ('import json,os,sys; from pathlib import Path; from aiohttp import web; from lulu.server import create_app\n'
            f'home=Path({str(home)!r}); (home/"data").mkdir(exist_ok=True); app=create_app(home,{port},assets=Path({str(english_tree)!r}))\n'
            'async def conn(app): (home/"data"/"connection.json").write_text(json.dumps({"port":%d,"token":app["token"],"pid":os.getpid()}))\n'
            'app.on_startup.append(conn); web.run_app(app,host="127.0.0.1",port=%d)' % (port, port))
    proc = subprocess.Popen([sys.executable, '-c', boot], cwd=english_tree, env=env, stdout=open(home / 'server.log', 'w'), stderr=subprocess.STDOUT)
    try:
        assert wait_for(home / 'data/connection.json'), (home / 'server.log').read_text(encoding='utf-8', errors='replace')
        conn = json.loads((home / 'data/connection.json').read_text())
        yield {'base': f'http://127.0.0.1:{conn["port"]}', 'token': conn['token'], 'home': home}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def call(server, method, path, body=None):
    req = urllib.request.Request(server['base']+path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={'X-Lulu-Token': server['token'], 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        raise AssertionError(f'{method} {path} -> {exc.code}: {exc.read().decode("utf-8", "replace")[:400]}')


def run_task(server, sid, text, skill=None, files=(), options=None):
    payload = {'session': sid, 'text': text}
    if skill:
        payload.update(skill=skill, files=list(files), options=options or {})
    tid = call(server, 'POST', '/api/chat', payload)['task']
    for _ in range(400):
        task = call(server, 'GET', '/api/tasks/'+tid)['task']
        if task['status'] not in ('queued', 'running'):
            return task
        time.sleep(.05)
    raise AssertionError('task did not finish: '+json.dumps(task, ensure_ascii=False)[:300])


def test_english_tags_end_to_end(english_server):
    sid = call(english_server, 'POST', '/api/sessions', {})['id']
    desktop = call(english_server, 'GET', '/api/desktop')
    assert desktop['backend']['label'] and not CJK.search(desktop['backend']['label'])
    assert desktop['lang'] == 'en'   # the pet holds up the English "done" board on completion
    answers = {}
    answers['remind'] = run_task(english_server, sid, 'call Sam tomorrow at 8am', skill='remind')
    assert answers['remind']['status'] == 'completed' and '08:00' in answers['remind']['answer'] and 'call Sam' in answers['remind']['answer']
    pending = call(english_server, 'GET', '/api/desktop')['reminders']
    assert pending and pending[0]['text'] == 'call Sam'
    answers['remind_list'] = run_task(english_server, sid, 'what reminders do I have?', skill='remind')
    assert answers['remind_list']['status'] == 'completed' and 'call Sam' in answers['remind_list']['answer']
    answers['remind_cancel'] = run_task(english_server, sid, 'cancel the reminder', skill='remind')
    assert answers['remind_cancel']['status'] == 'completed' and 'call Sam' in answers['remind_cancel']['answer']
    assert not call(english_server, 'GET', '/api/desktop')['reminders']
    answers['translate'] = run_task(english_server, sid, 'Good morning, everyone.', skill='translate', options={'lang': 'French'})
    assert answers['translate']['status'] == 'completed'
    answers['summarize'] = run_task(english_server, sid, 'Summarize: minutes.md', skill='summarize', files=['minutes.md'], options={'length': 'A few key points'})
    assert answers['summarize']['status'] == 'completed'
    answers['ask_file'] = run_task(english_server, sid, 'who is the owner?', skill='ask_file', files=['minutes.md'])
    assert answers['ask_file']['status'] == 'completed'
    answers['record'] = run_task(english_server, sid, 'the printer code is 4471', skill='record')
    assert answers['record']['status'] == 'completed'
    answers['chat'] = run_task(english_server, sid, 'hello!', skill='chat')
    assert answers['chat']['status'] == 'completed'
    for name, task in answers.items():
        assert not CJK.search(task['answer'] or ''), (name, task['answer'])
        if os.environ.get('PRINT_ANSWERS'):
            print(f'\n[{name}] {task["answer"]}')
    events = call(english_server, 'GET', '/api/tasks/'+answers['translate']['id'])
    for event in events.get('events', []):
        assert not CJK.search(json.dumps(event, ensure_ascii=False)), event


def test_english_package_layout(english_tree, tmp_path):
    """build_release.py run from the English tree names the package -en- and ships English scripts and readme."""
    sys.path.insert(0, str(ROOT / 'tests'))
    from test_packaging import fake_pet
    pet, frames = fake_pet(tmp_path, 'macos')
    out = tmp_path / 'dist'
    result = subprocess.run([sys.executable, str(english_tree / 'packaging/build_release.py'), '--platform', 'macos', '--pet', str(pet), '--frames', str(frames),
                             '--out', str(out), '--no-zip'], capture_output=True, text=True, cwd=english_tree)
    assert result.returncode == 0, result.stdout+result.stderr
    folder = next(out.glob('Lulu-*'))
    assert re.fullmatch(r'Lulu-[\d.]+-en-macos', folder.name), folder.name
    assert (folder / 'Install and start Lulu.command').exists() and (folder / 'Start here.md').exists()
    assert (folder / 'agent/Install local models.command').exists() and (folder / 'agent/Check backend.command').exists()
    assert not any(CJK.search(p.name) for p in folder.rglob('*')), [p.name for p in folder.rglob('*') if CJK.search(p.name)]
    release = json.loads((folder / 'release.json').read_text(encoding='utf-8'))
    assert release['lang'] == 'en' and release['platform'] == 'macos'
    readme = (folder / 'Start here.md').read_text(encoding='utf-8')
    assert not CJK.search(readme) and 'Install and start Lulu.command' in readme and '{' not in readme
    assert (folder / 'agent/lulu/lang.py').read_text(encoding='utf-8').strip().endswith("LANG = 'en'")
    script = (folder / 'Install and start Lulu.command').read_text(encoding='utf-8')
    assert 'Install local models.command' in script and not CJK.search(script)
