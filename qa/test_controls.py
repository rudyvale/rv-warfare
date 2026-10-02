import argparse
import os
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--game',type=Path,default=Path(os.environ.get('RV_GAME_ROOT',str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Warfare-1.12.2'))))
parser.add_argument('--compiler',type=Path,default=Path(os.environ.get('RV_ECJ_JAR',str(root/'.local/tools/ecj-4.6.1.jar'))))
parser.add_argument('--work',type=Path,default=root/'.local/controls')
options=parser.parse_args()
game=options.game
java=game/'runtime/bin/java.exe'
build=options.work
libraries=list((game/'libraries').rglob('*.jar')) + list((game/'mods').glob('elegant-networking*.jar'))
cp=os.pathsep.join([str(build/'mcheli-ce-1.5.1-vm-controls1.jar'),*(str(p) for p in libraries)])
compiler=options.compiler
classes=build/'tests'
classes.mkdir(exist_ok=True)
subprocess.run([str(java),'-jar',str(compiler),'-1.8','-encoding','UTF-8','-nowarn','-cp',cp,'-d',str(classes),str(root/'qa/VMControlsTest.java')],check=True)
subprocess.run([str(java),'-Xverify:all',f'-Djava.library.path={game / "natives"}','-cp',os.pathsep.join([str(classes),cp]),'VMControlsTest'],check=True)
