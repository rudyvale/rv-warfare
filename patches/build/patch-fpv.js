var Files=Java.type('java.nio.file.Files'),Paths=Java.type('java.nio.file.Paths');
var JarFile=Java.type('java.util.jar.JarFile'),CR=Java.type('org.objectweb.asm.ClassReader'),CW=Java.type('org.objectweb.asm.ClassWriter'),CN=Java.type('org.objectweb.asm.tree.ClassNode');
var IL=Java.type('org.objectweb.asm.tree.InsnList'),VI=Java.type('org.objectweb.asm.tree.VarInsnNode'),MI=Java.type('org.objectweb.asm.tree.MethodInsnNode'),JI=Java.type('org.objectweb.asm.tree.JumpInsnNode'),IN=Java.type('org.objectweb.asm.tree.InsnNode'),LN=Java.type('org.objectweb.asm.tree.LabelNode'),FN=Java.type('org.objectweb.asm.tree.FrameNode'),LC=Java.type('org.objectweb.asm.tree.LdcInsnNode'),MN=Java.type('org.objectweb.asm.tree.MethodNode');
var Float=Java.type('java.lang.Float'),jar=new JarFile(arguments[0]),helper='com/norwood/mcheli/uav/WarfareFpv',changes=[];
function intercept(m,target,desc,loads,returnOpcode){
    var code=new IL(),end=new LN();
    for(var j=0;j<loads.length;j++)code.add(new VI(loads[j][0],loads[j][1]));
    code.add(new MI(184,helper,target,desc,false));code.add(new JI(153,end));
    if(returnOpcode===172)code.add(new IN(4));
    code.add(new IN(returnOpcode));code.add(end);code.add(new FN(3,0,null,0,null));
    m.instructions.insert(code);changes.push(m.name+':'+target);
}
function value(m,target,constant){
    var code=new IL(),end=new LN();
    code.add(new VI(25,0));code.add(new MI(184,helper,'enabled','(Ljava/lang/Object;)Z',false));code.add(new JI(153,end));
    if(target){code.add(new VI(25,0));code.add(new MI(184,helper,target,'(Ljava/lang/Object;)F',false));}
    else code.add(new LC(new Float(constant)));
    code.add(new IN(174));code.add(end);code.add(new FN(3,0,null,0,null));m.instructions.insert(code);changes.push(m.name+':value');
}
function rotate(m){
    var code=new IL(),end=new LN();
    code.add(new VI(25,0));code.add(new MI(184,helper,'enabled','(Ljava/lang/Object;)Z',false));code.add(new JI(153,end));
    code.add(new VI(25,0));code.add(new MI(184,helper,'canRotate','(Ljava/lang/Object;)Z',false));code.add(new IN(172));
    code.add(end);code.add(new FN(3,0,null,0,null));m.instructions.insert(code);changes.push(m.name+':rotate');
}
var names=['com/norwood/mcheli/helicopter/MCH_EntityHeli','com/norwood/mcheli/uav/WarfareQuickUav'];
for(var k=0;k<names.length;k++){
    var name=names[k],reader=new CR(jar.getInputStream(jar.getJarEntry(name+'.class'))),node=new CN();reader.accept(node,0);
    for(var i=0;i<node.methods.size();i++){
        var m=node.methods.get(i),n=String(m.name);
        if(k===0){
            if(n==='onUpdate_Control')intercept(m,'control','(Ljava/lang/Object;)Z',[[25,0]],177);
            if(n==='onUpdate_Server')intercept(m,'motion','(Ljava/lang/Object;)Z',[[25,0]],177);
            if(n==='onUpdateAngles')intercept(m,'angles','(Ljava/lang/Object;F)Z',[[25,0],[23,1]],177);
            if(n==='getControlRotYaw')value(m,'yaw',0);
            if(n==='getRollFactor')value(m,null,3.5);
            if(n==='canUpdatePitch'||n==='canUpdateRoll')rotate(m);
        }else if(n==='command')intercept(m,'command','(Ljava/lang/Object;Ljava/lang/Object;[Ljava/lang/String;)Z',[[25,0],[25,1],[25,2]],172);
    }
    if(k===0){
        for(var f=0;f<2;f++){
            var n=f===0?'getPitchFactor':'getYawFactor',m=new MN(1,n,'()F',null,null);
            m.instructions.add(new VI(25,0));m.instructions.add(new MI(183,String(node.superName),n,'()F',false));m.instructions.add(new IN(174));
            value(m,null,f===0?3.5:3.0);node.methods.add(m);
        }
        var m=new MN(1,'canUpdateYaw','(Lnet/minecraft/entity/Entity;)Z',null,null);
        m.instructions.add(new VI(25,0));m.instructions.add(new VI(25,1));
        m.instructions.add(new MI(183,String(node.superName),'canUpdateYaw','(Lnet/minecraft/entity/Entity;)Z',false));m.instructions.add(new IN(172));
        rotate(m);node.methods.add(m);
        var bridges=[['warfareUpdateBlocks','onUpdate_updateBlock',String(node.superName)],['warfareCheckMotion','onUpdate_Server',name],['warfareCheckControl','onUpdate_Control',name]];
        for(var b=0;b<bridges.length;b++){
            var row=bridges[b],bridge=new MN(1,row[0],'()V',null,null);
            bridge.instructions.add(new VI(25,0));bridge.instructions.add(new MI(row[1]==='onUpdate_Server'?183:182,row[2],row[1],'()V',false));bridge.instructions.add(new IN(177));node.methods.add(bridge);
        }
    }
    var writer=new CW(reader,1);node.accept(writer);
    var output=Paths.get(arguments[1],name+'.class');Files.createDirectories(output.getParent());Files.write(output,writer.toByteArray());
}
jar.close();if(changes.length!==11)throw new Error('Unexpected changes: '+JSON.stringify(changes));print(JSON.stringify(changes));
