import argparse
import os
import sys
from pathlib import Path


def main():
    if sys.version_info<(3,11):
        raise SystemExit('需要 Python 3.11 或更新版本。Windows 请先双击 安装并启动 Lulu.cmd。')
    from aiohttp import web
    from filelock import FileLock, Timeout
    from lulu.server import create_app
    parser=argparse.ArgumentParser(description='Lulu 独立 Agent 试用版')
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--data-dir',type=Path)
    args=parser.parse_args()
    assets=Path(os.environ.get('LULU_AGENT_ROOT',str(Path(__file__).resolve().parent)))
    home=args.data_dir or assets
    (home/'data').mkdir(parents=True,exist_ok=True)
    lock=FileLock(home/'data'/'server.lock')
    try: lock.acquire(timeout=0)
    except Timeout: raise SystemExit('Lulu 已在运行。')
    app=create_app(home,args.port,assets=assets)
    async def connection(app):
        import json, os
        path=home/'data'/'connection.json'
        temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps({'port':args.port,'token':app['token'],'pid':os.getpid()}))
        temp.chmod(0o600)
        temp.replace(path)
    app.on_startup.append(connection)
    try: web.run_app(app,host='127.0.0.1',port=args.port,print=lambda text:print('Lulu: '+text))
    finally: lock.release()


if __name__=='__main__': main()
