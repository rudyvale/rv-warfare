import os
import json
import pathlib
import re
import shutil
import sys

root = pathlib.Path(__file__).parent
sys.path.insert(0, str(root / 'python-libs'))
import nbtlib as n

stage = root / 'warfare-stage'
world = stage / 'Battlefield'
state = json.loads((stage/'server-state.json').read_text())
if state['state'] != 'stopped':
    raise SystemExit('Stop the stage server first')
region = world/'region'
if region.exists():
    region.rename(world/'region-before-arena')
shutil.copytree(root/'battlefield-region', region)
level = n.load(world/'level.dat')
data = level['Data']
for key,value in {'SpawnX':0,'SpawnY':65,'SpawnZ':-210,'GameType':0}.items():
    data[key]=n.Int(value)
data['LevelName']=n.String('Crossfire Valley | Warfare 1.12.2')
data['DayTime']=n.Long(1000)
data['raining']=n.Byte(0)
data['thundering']=n.Byte(0)
rules={'doMobSpawning':'false','doDaylightCycle':'false','doWeatherCycle':'false','keepInventory':'true','commandBlockOutput':'false','logAdminCommands':'false','sendCommandFeedback':'false','announceAdvancements':'false','spawnRadius':'0','gameLoopFunction':'warfare:tick'}
for key,value in rules.items():
    data['GameRules'][key]=n.String(value)
data['BorderCenterX']=n.Double(0)
data['BorderCenterZ']=n.Double(0)
data['BorderSize']=n.Double(630)
data['BorderSizeLerpTarget']=n.Double(630)
level.save(world/'level.dat')
config=stage/'config'/'techguns.cfg'
text=config.read_text(encoding='utf-8')
text=text.replace('B:machinesNeedNoPower=false','B:machinesNeedNoPower=true')
text=re.sub(r'(I:SpawnWeight\w+=)\d+',r'\g<1>0',text)
text=re.sub(r'(I:"Techguns Spawnweight [^"]+"=)\d+',r'\g<1>0',text)
text=text.replace('B:SpawnStructures=true','B:SpawnStructures=false')
text=text.replace('B:SpawnOreClusters=true','B:SpawnOreClusters=false')
config.write_text(text,encoding='utf-8')
properties=stage/'server.properties'
text=properties.read_text().replace('gamemode=1','gamemode=0')
properties.write_text(text,encoding='utf-8')
functions=world/'data'/'functions'/'warfare'
functions.mkdir(parents=True,exist_ok=True)
def function(name,lines):
    (functions/(name+'.mcfunction')).write_text('\n'.join(lines)+'\n',encoding='utf-8')

menu=[{'text':'\nWARFARE 1.12.2\n','color':'gold','bold':True},{'text':'[BLUE BASE] ','color':'aqua','clickEvent':{'action':'run_command','value':'/trigger blue set 1'}},{'text':'[RED BASE]\n','color':'red','clickEvent':{'action':'run_command','value':'/trigger red set 1'}},{'text':'[GET KIT] ','color':'green','clickEvent':{'action':'run_command','value':'/trigger kit set 1'}},{'text':'[LOBBY]\n','color':'yellow','clickEvent':{'action':'run_command','value':'/trigger lobby set 1'}},{'text':'Tab: players | J: map | Right click: UAV controller\n','color':'gray'},{'text':'Drone: RC Goblin with Bomb + Portable UAV Controller. Weapons and vehicles: open E, search in JEI.\n','color':'white'}]
function('help',['tellraw @s '+json.dumps(menu,ensure_ascii=False),'scoreboard players set @s menu 0','scoreboard players enable @s menu'])
function('welcome',['title @s times 10 60 20','title @s subtitle {"text":"Guns | Vehicles | UAV camera","color":"aqua"}','title @s title {"text":"WELCOME TO WARFARE","color":"gold"}','function warfare:help','scoreboard players tag @s add w_seen','scoreboard players enable @s blue','scoreboard players enable @s red','scoreboard players enable @s kit','scoreboard players enable @s lobby','function warfare:kit'])
function('kit',['clear @s techguns:m4','give @s techguns:m4 1','give @s minecraft:cooked_beef 32','replaceitem entity @s slot.armor.head minecraft:iron_helmet','replaceitem entity @s slot.armor.chest minecraft:iron_chestplate','replaceitem entity @s slot.armor.legs minecraft:iron_leggings','replaceitem entity @s slot.armor.feet minecraft:iron_boots','give @s mcheli:rc-goblin-bomb 1','give @s mcheli:uav_station2 1','give @s mcheli:fuel 8','scoreboard players set @s kit 0','scoreboard players enable @s kit','tellraw @s {"text":"Kit received. /trigger help is /trigger menu set 1. More ammo and equipment are in base chests.","color":"green"}'])
for team,x in [('blue',-185),('red',255)]:
    function(team,['scoreboard teams join '+team+' @s','tp @s '+str(x)+' 65 -29','spawnpoint @s '+str(x)+' 65 -29','scoreboard players set @s '+team+' 0','scoreboard players enable @s '+team,'function warfare:help'])
function('lobby',['tp @s 0 65 -210','scoreboard players set @s lobby 0','scoreboard players enable @s lobby','function warfare:help'])
function('tick',['execute @a[tag=!w_seen] ~ ~ ~ function warfare:welcome']+['execute @a[score_'+key+'_min=1] ~ ~ ~ function warfare:'+name for key,name in [('menu','help'),('kit','kit'),('blue','blue'),('red','red'),('lobby','lobby')]])
setup=['scoreboard objectives add menu trigger','scoreboard objectives add kit trigger','scoreboard objectives add blue trigger','scoreboard objectives add red trigger','scoreboard objectives add lobby trigger','scoreboard objectives add kills playerKillCount','scoreboard objectives setdisplay list kills','scoreboard teams add blue Blue','scoreboard teams option blue color aqua','scoreboard teams option blue friendlyfire false','scoreboard teams add red Red','scoreboard teams option red color red','scoreboard teams option red friendlyfire false','setworldspawn 0 65 -210','worldborder center 0 0','worldborder set 630','gamerule gameLoopFunction warfare:tick','gamerule sendCommandFeedback true']
(root/'warfare-setup-commands.txt').write_text('\n'.join(setup)+'\n',encoding='utf-8')
client=pathlib.Path(os.environ['VM_CLIENT_ROOT'])
shutil.copytree(stage/'config',client/'config',dirs_exist_ok=True)
options=client/'options.txt'
text=options.read_text(encoding='utf-8-sig')
text=re.sub(r'^lang:.*$', 'lang:ru_ru',text,flags=re.M)
text=re.sub(r'^renderDistance:.*$','renderDistance:12',text,flags=re.M)
text=re.sub(r'^maxFps:.*$','maxFps:144',text,flags=re.M)
options.write_text(text,encoding='utf-8')
print(json.dumps({'arena_ready':True,'functions':len(list(functions.glob('*.mcfunction'))),'spawn':[0,65,-210]}))
