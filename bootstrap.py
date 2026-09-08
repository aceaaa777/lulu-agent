"""Install only into this project. Does not change system Python or install Ollama."""
import os
from pathlib import Path
import subprocess
import sys
import venv

root=Path(__file__).resolve().parent
os.chdir(root)
if sys.version_info<(3,11):
    raise SystemExit('Please install Python 3.12 from python.org, then retry.')
env=root/'.venv'
if not env.exists(): venv.create(env,with_pip=True)
python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
subprocess.run([str(python),'-m','pip','install','-r','requirements.txt','-c','constraints.txt'],check=True)
print('Lulu dependencies installed. Start Ollama and run: ollama pull qwen2.5:7b')
print('Then open the Lulu launcher.')
