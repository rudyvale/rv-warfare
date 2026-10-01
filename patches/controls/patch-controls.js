var Files=Java.type('java.nio.file.Files'),Paths=Java.type('java.nio.file.Paths');
var JarFile=Java.type('java.util.jar.JarFile'),CR=Java.type('org.objectweb.asm.ClassReader'),CW=Java.type('org.objectweb.asm.ClassWriter'),CN=Java.type('org.objectweb.asm.tree.ClassNode');
var IL=Java.type('org.objectweb.asm.tree.InsnList'),VI=Java.type('org.objectweb.asm.tree.VarInsnNode'),MI=Java.type('org.objectweb.asm.tree.MethodInsnNode'),JI=Java.type('org.objectweb.asm.tree.JumpInsnNode'),IN=Java.type('org.objectweb.asm.tree.InsnNode'),LN=Java.type('org.objectweb.asm.tree.LabelNode'),FN=Java.type('org.objectweb.asm.tree.FrameNode'),LC=Java.type('org.objectweb.asm.tree.LdcInsnNode'),FI=Java.type('org.objectweb.asm.tree.FieldInsnNode'),FieldNode=Java.type('org.objectweb.asm.tree.FieldNode');
var jar=new JarFile(arguments[0]),prefix='com/norwood/mcheli/',vm=prefix+'vm/',changes=[];
function loads(code,items){for(var i=0;i<items.length;i++)code.add(new VI(items[i][0],items[i][1]));}
function invoke(code,cls,name,desc){code.add(new MI(184,vm+cls,name,desc,false));}
function hook(m,cls,name,desc,args){var code=new IL();loads(code,args);invoke(code,cls,name,desc);m.instructions.insert(code);changes.push(m.name+':'+name);}
function returns(m,opcode,cls,name,desc,args){var count=0;for(var node=m.instructions.getFirst();node!==null;node=node.getNext()){if(node.getOpcode()===opcode){var code=new IL();loads(code,args);invoke(code,cls,name,desc);m.instructions.insertBefore(node,code);count++;}}if(count===0)throw new Error('No return '+m.name);changes.push(m.name+':'+name);}
function intercept(m,cls,name,desc,args){var code=new IL(),end=new LN();loads(code,args);invoke(code,cls,name,desc);code.add(new JI(153,end));code.add(new IN(177));code.add(end);code.add(new FN(3,0,null,0,null));m.instructions.insert(code);changes.push(m.name+':'+name);}
function find(node,name,desc){for(var i=0;i<node.methods.size();i++){var m=node.methods.get(i);if(String(m.name)===name&&(!desc||String(m.desc)===desc))return m;}throw new Error('Missing '+node.name+'.'+name+' '+desc);}
function patch(path,edit){var name=prefix+path,entry=jar.getJarEntry(name+'.class');if(entry===null)throw new Error('Missing '+name);var reader=new CR(jar.getInputStream(entry)),node=new CN();reader.accept(node,0);edit(node);var writer=new CW(reader,1);node.accept(writer);var output=Paths.get(argumentsOutput,name+'.class');Files.createDirectories(output.getParent());Files.write(output,writer.toByteArray());}
var argumentsOutput=String(arguments[1]);
patch('event/MouseInputHandler',function(n){
    hook(find(n,'handleRenderTickPre'),'VMPilot','frame','()V',[]);
    returns(find(n,'updateMouseDelta'),177,'VMPilot','mouse','(Ljava/lang/Object;)V',[[25,0]]);
    var m=find(n,'updateCameraRoll'),count=0;
    for(var x=m.instructions.getFirst();x!==null;x=x.getNext())if(x.getOpcode()===184&&String(x.name)==='setCameraRoll'){
        var code=new IL();code.add(new VI(25,1));invoke(code,'VMPilot','cameraRoll','(FLjava/lang/Object;)F');m.instructions.insertBefore(x,code);count++;
    }
    if(count!==1)throw new Error('Camera roll hook mismatch');changes.push('cameraRoll');
});
patch('aircraft/MCH_EntityAircraft',function(n){
    intercept(find(n,'setAngles'),'VMPilot','angles','(Ljava/lang/Object;Ljava/lang/Object;ZFFFFFFF)Z',[[25,0],[25,1],[21,2],[23,3],[23,4],[23,5],[23,6],[23,7],[23,8],[23,9]]);
    intercept(find(n,'updateRecoil'),'VMCombat','suppressRecoil','(Ljava/lang/Object;)Z',[[25,0]]);
    hook(find(n,'spawnParticleMuzzleFlash'),'VMCombat','muzzle','(Ljava/lang/Object;Ljava/lang/Object;DDD)V',[[25,0],[25,2],[24,3],[24,5],[24,7]]);
});
patch('aircraft/MCH_AircraftClientTickHandler',function(n){
    var m=find(n,'commonPlayerControl');
    hook(m,'VMPilot','keys','(Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;Z)V',[[25,0],[25,1],[25,2],[21,3]]);
    returns(m,172,'VMPilot','packet','(ZLjava/lang/Object;Ljava/lang/Object;Z)Z',[[25,2],[25,4],[21,3]]);
});
patch('networking/data/DataPlayerControlAircraft',function(n){
    n.fields.add(new FieldNode(1,'vmThrottle','F',null,null));
    var m=find(n,'<init>','()V');
    for(var x=m.instructions.getFirst();x!==null;x=x.getNext())if(x.getOpcode()===177){var code=new IL();code.add(new VI(25,0));code.add(new LC(new java.lang.Float(-1)));code.add(new FI(181,String(n.name),'vmThrottle','F'));m.instructions.insertBefore(x,code);}
    returns(find(n,'<init>','(Lio/netty/buffer/ByteBuf;)V'),177,'VMFlight','read','(Ljava/lang/Object;Ljava/lang/Object;)V',[[25,0],[25,1]]);
    returns(find(n,'serialize'),177,'VMFlight','write','(Ljava/lang/Object;Ljava/lang/Object;)V',[[25,0],[25,1]]);
});
patch('networking/packet/control/PacketPlayerControlBase',function(n){returns(find(n,'handlePilotControls'),177,'VMFlight','receive','(Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;)V',[[25,1],[25,2],[25,3]]);});
patch('uav/WarfareFpv',function(n){returns(find(n,'control'),172,'VMFlight','afterControl','(ZLjava/lang/Object;)Z',[[25,0]]);returns(find(n,'resetControl'),177,'VMFlight','reset','(Ljava/lang/Object;)V',[[25,0]]);});
patch('sound/MCH_SoundEvents',function(n){intercept(find(n,'playSound','(Lnet/minecraft/world/World;DDDLnet/minecraft/util/ResourceLocation;FF)V'),'VMCombat','soundAt','(Ljava/lang/Object;DDDLjava/lang/Object;FF)Z',[[25,0],[24,1],[24,3],[24,5],[25,7],[23,8],[23,9]]);});
patch('weapon/MCH_WeaponBase',function(n){intercept(find(n,'playSound','(Lnet/minecraft/entity/Entity;Lnet/minecraft/util/ResourceLocation;)V'),'VMCombat','weaponSound','(Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;)Z',[[25,0],[25,1],[25,2]]);});
patch('weapon/MCH_WeaponInfo',function(n){returns(find(n,'onPostReload'),177,'VMCombat','tune','(Ljava/lang/Object;)V',[[25,0]]);});
patch('weapon/MCH_EntityBaseBullet',function(n){returns(find(n,'func_70071_h_'),177,'VMCombat','trail','(Ljava/lang/Object;)V',[[25,0]]);hook(find(n,'onImpact'),'VMCombat','impact','(Ljava/lang/Object;Ljava/lang/Object;)V',[[25,0],[25,1]]);});
patch('helper/client/MCH_CameraManager',function(n){returns(find(n,'onCameraSetupEvent'),177,'VMCombat','camera','(Ljava/lang/Object;)V',[[25,0]]);});
jar.close();if(changes.length!==19)throw new Error('Unexpected hook count '+changes.length+' '+JSON.stringify(changes));print(JSON.stringify(changes));
