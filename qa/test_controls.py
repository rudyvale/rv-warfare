import os
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
game=Path(os.environ['LOCALAPPDATA'])/'Warfare-1.12.2'
java=game/'runtime/bin/java.exe'
build=root/'.local/controls'
libraries=list((game/'libraries').rglob('*.jar')) + list((game/'mods').glob('elegant-networking*.jar'))
cp=os.pathsep.join([str(build/'mcheli-ce-1.5.1-vm-controls1.jar'),*(str(p) for p in libraries)])
compiler=Path.home()/'Documents/Codex/2026-10-01/new-chat-2/work/ecj-4.6.1.jar'
classes=build/'tests'
classes.mkdir(exist_ok=True)
subprocess.run([str(java),'-jar',str(compiler),'-1.8','-encoding','UTF-8','-nowarn','-cp',cp,'-d',str(classes),str(root/'qa/VMControlsTest.java')],check=True)
subprocess.run([str(java),'-Xverify:all',f'-Djava.library.path={game / "natives"}','-cp',os.pathsep.join([str(classes),cp]),'VMControlsTest'],check=True)
