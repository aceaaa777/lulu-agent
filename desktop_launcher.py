"""One local supervisor for the model, agent service and two native windows."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import signal
import subprocess
import sys
import time
import urllib.request
from filelock import FileLock, Timeout


# urllib obeys the system proxy by default; with a VPN/proxy switched on, a loopback health check would be sent to the
# proxy and time out, and the launcher would keep "restarting" a perfectly healthy agent. Always go direct.
_direct=urllib.request.build_opener(urllib.request.ProxyHandler({}))
# child processes of a windowed (no console) runtime on Windows must not pop up console windows of their own
_quiet={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}


def healthy(port, token=None, heartbeat=None):
    """Agent liveness: a fresh heartbeat file (written by the server's event loop every second) counts as healthy;
    the HTTP probe is the fallback. A blocked event loop stops both; a proxy or port hiccup stops neither."""
    if heartbeat is not None:
        try:
            if time.time()-heartbeat.stat().st_mtime<6: return {'ok':True,'via':'heartbeat'}
        except OSError: pass
    try:
        req=urllib.request.Request(f'http://127.0.0.1:{port}/'+('api/health' if token else 'api/tags'),headers={'X-Lulu-Token':token} if token else {})
        with _direct.open(req,timeout=2) as r: return json.load(r)
    except (OSError,ValueError): return None


def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try: process.wait(timeout=12)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)


def package_root(start):
    """The folder that holds this Lulu: walks up from `start` to the first folder with a pet/ or desktop/ inside, so a
    frozen runtime placed in runtime/LuluRuntime/ still finds the package it belongs to."""
    start=Path(start).resolve()
    for folder in [start,*start.parents]:
        if (folder/'pet').is_dir() or (folder/'desktop').is_dir(): return folder
    return start


def find_pet(root):
    """The pet program: an exported build under pet/ (release packages) before the Godot editor running the source tree
    (development). Returns (command list, description) or (None, reason)."""
    exported=[root/'pet/Lulu.exe',root/'pet/Lulu.app/Contents/MacOS/Lulu',root/'pet/Lulu.x86_64',root/'build/pet/windows/Lulu.exe',root/'build/pet/macos/Lulu.app/Contents/MacOS/Lulu',root/'build/pet/linux/Lulu.x86_64']
    wanted={'nt':'.exe','darwin':'Lulu.app'}.get(os.name if os.name=='nt' else sys.platform,'.x86_64')
    for candidate in exported:
        if candidate.exists() and wanted in str(candidate): return [str(candidate)],'exported '+str(candidate)
    if not (root/'desktop/project.godot').exists(): return None,'安装包缺少桌宠程序（pet/ 目录）。'
    runtime=root/'runtime'
    editors=[runtime/'godot.exe',runtime/'Godot.app/Contents/MacOS/Godot',runtime/'godot',Path(os.environ.get('LULU_GODOT_BIN','')),
             Path.home()/'Downloads/Godot.app/Contents/MacOS/Godot',Path('/Applications/Godot.app/Contents/MacOS/Godot'),Path('/tmp/Godot_v4.4.1-stable_linux.x86_64')]
    for name in ['godot4','godot','Godot']:
        found=shutil.which(name)
        if found: editors.append(Path(found))
    for editor in editors:
        if str(editor) and editor.exists(): return [str(editor),'--path',str(root/'desktop')],'editor '+str(editor)
    return None,'没有桌宠程序：既没有 pet/ 里的导出版，也找不到 Godot 4.4。'


def available_port(preferred):
    with socket.socket() as sock:
        try: sock.bind(('127.0.0.1',preferred))
        except OSError: sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=package_root(Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent))
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--headless',action='store_true')
    args=parser.parse_args()
    root=args.root.resolve()
    agent_root=root/'agent' if (root/'agent').is_dir() else root
    runtime=root/'runtime'
    data=args.data_dir or Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'Library/Application Support' if sys.platform=='darwin' else Path.home()/'.local/share')))/'Lulu'
    data=data.resolve()
    def interrupted(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,interrupted)
    data.mkdir(parents=True,exist_ok=True); (data/'data').mkdir(exist_ok=True)
    lock=FileLock(data/'desktop.lock')
    try: lock.acquire(timeout=0)
    except Timeout:
        (data/'show-panel').touch()
        return 0
    logs=data/'logs'; logs.mkdir(exist_ok=True)
    logfile=logs/'desktop.log'
    if logfile.exists() and logfile.stat().st_size>5*1024*1024: logfile.replace(logs/'desktop.previous.log')
    log=logfile.open('a',buffering=1)
    def report(message): print(time.strftime('%Y-%m-%d %H:%M:%S'),message,file=log,flush=True)
    env=os.environ.copy()
    env['LULU_AGENT_ROOT']=str(agent_root)
    env['LULU_CONNECTION']=str(data/'data/connection.json')
    env['LULU_SHOW_PANEL']=str(data/'show-panel')
    env['PATH']=str(runtime)+os.pathsep+env.get('PATH','')
    model_process=server=pet=None
    try:
        # The model is a setting, not a prerequisite: with an API / command-line backend Ollama is not needed, and a
        # missing Ollama is reported in the 模型 page instead of stopping the shell from opening.
        try:
            sys.path.insert(0,str(agent_root))
            from lulu import backends
            backend=backends.load_config(data).get('backend','ollama')
        except Exception as exc:
            report('config unreadable, assuming local model: '+str(exc)); backend='ollama'
        model_port=available_port(11435) if (root/'models').exists() else 11434
        if backend=='ollama' and not healthy(model_port):
            binary=runtime/('ollama.exe' if os.name=='nt' else 'ollama')
            binary=str(binary) if binary.exists() else shutil.which('ollama')
            if not binary and sys.platform=='darwin' and Path('/Applications/Ollama.app/Contents/Resources/ollama').exists(): binary='/Applications/Ollama.app/Contents/Resources/ollama'
            if not binary and os.name=='nt' and (Path(os.environ.get('LOCALAPPDATA',''))/'Programs/Ollama/ollama.exe').exists(): binary=str(Path(os.environ['LOCALAPPDATA'])/'Programs/Ollama/ollama.exe')
            if not binary:
                report('Ollama not found; opening without a local model (see the 模型 page)')
            else:
                model_env=env.copy(); model_env.update(OLLAMA_HOST=f'127.0.0.1:{model_port}',OLLAMA_NUM_PARALLEL='1',OLLAMA_MAX_LOADED_MODELS='1',OLLAMA_NO_CLOUD='1')
                if (root/'models').exists(): model_env['OLLAMA_MODELS']=str(root/'models')
                model_process=subprocess.Popen([binary,'serve'],env=model_env,stdout=log,stderr=log,**_quiet)
                for _ in range(40):
                    if healthy(model_port): break
                    if model_process.poll() is not None: report('local model service exited; continuing without it'); break
                    time.sleep(.25)
        elif backend!='ollama': report('backend '+backend+': local model service not started')
        env['LULU_OLLAMA_BASE']=f'http://127.0.0.1:{model_port}'
        port=available_port(8766)
        command=([sys.executable,'--server'] if getattr(sys,'frozen',False) else [sys.executable,str((agent_root if (agent_root/'entry.py').exists() else root)/'entry.py'),'--server'])+['--no-browser','--port',str(port),'--data-dir',str(data)]
        def start_server():
            process=subprocess.Popen(command,env=env,stdout=log,stderr=log,**_quiet)
            for _ in range(80):
                if process.poll() is not None: raise RuntimeError('Agent 启动失败，请查看日志。')
                try:
                    connection=json.loads((data/'data/connection.json').read_text())
                    if connection['pid']==process.pid and healthy(port,connection['token']): return process
                except (OSError,ValueError,KeyError): pass
                time.sleep(.25)
            stop(process); raise RuntimeError('Agent 启动超时。')
        server=start_server(); report('Agent ready')
        if args.headless:
            while server.poll() is None: time.sleep(1)
            return server.returncode
        pet_command,how=find_pet(root)
        if not pet_command: raise RuntimeError(how)
        frames=next((p for p in [root/'pet/frames.pck',root/'build/pet/frames.pck'] if p.exists()),None)
        if frames: env['LULU_FRAMES']=str(frames)
        report('pet: '+how+('; frames '+str(frames) if frames else '; frames from source tree'))
        pet=subprocess.Popen(pet_command,env=env,stdout=log,stderr=log)
        restarts=0; health_failures=0; tick=0
        while pet.poll() is None:
            time.sleep(1)
            tick+=1
            if tick%5==0:
                try: local_token=json.loads((data/'data/connection.json').read_text())['token']
                except (OSError,ValueError,KeyError): local_token=''
                if healthy(port,local_token,data/'data/heartbeat'): health_failures=0
                else:
                    health_failures+=1; report(f'health check failed ({health_failures}); a long stall shows up as [lulu-watchdog] lines above')
            if server.poll() is not None or health_failures>=9:
                stop(server); health_failures=0
                restarts+=1
                if restarts>3: raise RuntimeError('Agent 连续退出三次，请查看日志后重新启动。')
                report('Restarting agent; interrupted tasks remain saved')
                time.sleep(min(restarts,3)); server=start_server()
        if pet.returncode: raise RuntimeError(f'桌宠窗口异常退出（{pet.returncode}），请查看日志。')
        report('Desktop closed')
        return pet.returncode
    except KeyboardInterrupt:
        report('Stopped'); return 0
    except Exception as exc:
        report(str(exc))
        error=data/'启动问题.txt'; error.write_text(str(exc)+'\n日志：'+str(logfile),encoding='utf-8')
        if os.name=='nt': os.startfile(str(error))
        elif sys.platform=='darwin': subprocess.Popen(['open','-t',str(error)])
        return 1
    finally:
        stop(pet); stop(server); stop(model_process); log.close(); lock.release()

if __name__=='__main__': raise SystemExit(main())
