var Files=Java.type('java.nio.file.Files'),Paths=Java.type('java.nio.file.Paths');
var JarFile=Java.type('java.util.jar.JarFile'),CR=Java.type('org.objectweb.asm.ClassReader'),CW=Java.type('org.objectweb.asm.ClassWriter'),CN=Java.type('org.objectweb.asm.tree.ClassNode');
var InsnList=Java.type('org.objectweb.asm.tree.InsnList'),VarInsn=Java.type('org.objectweb.asm.tree.VarInsnNode'),MethodInsn=Java.type('org.objectweb.asm.tree.MethodInsnNode'),JumpInsn=Java.type('org.objectweb.asm.tree.JumpInsnNode'),Insn=Java.type('org.objectweb.asm.tree.InsnNode'),Label=Java.type('org.objectweb.asm.tree.LabelNode'),Frame=Java.type('org.objectweb.asm.tree.FrameNode');
var jar=new JarFile(arguments[0]),helper='com/norwood/mcheli/uav/WarfareQuickUav',changes=[];
function inject(method,loads,target,descriptor){
    var code=new InsnList(),end=new Label();
    for(var j=0;j<loads.length;j++)code.add(new VarInsn(25,loads[j]));
    code.add(new MethodInsn(184,helper,target,descriptor,false));
    code.add(new JumpInsn(153,end));code.add(new Insn(177));code.add(end);code.add(new Frame(3,0,null,0,null));
    method.instructions.insert(code);changes.push(method.name+':'+target);
}
var names=['com/norwood/mcheli/MCH_EventHook','com/norwood/mcheli/uav/MCH_ItemUavTablet','com/norwood/mcheli/uav/MCH_EntityUavStation','com/norwood/mcheli/command/MCH_Command'];
for(var k=0;k<names.length;k++){
    var name=names[k],reader=new CR(jar.getInputStream(jar.getJarEntry(name+'.class'))),node=new CN();reader.accept(node,0);
    for(var i=0;i<node.methods.size();i++){
        var m=node.methods.get(i);
        if(name===names[0]&&String(m.name)==='onUavTabletInteract')inject(m,[1],'interact','(Ljava/lang/Object;)Z');
        if(name===names[3]&&String(m.name)==='func_184881_a')inject(m,[1,2,3],'command','(Ljava/lang/Object;Ljava/lang/Object;[Ljava/lang/String;)Z');
        for(var p=m.instructions.getFirst();p!==null;p=p.getNext()){
            if(p instanceof MethodInsn&&String(p.owner)==='com/norwood/mcheli/factories/UavStationGuiFactory'&&String(p.name)==='openGui'&&(name===names[1]||name===names[2])){
                m.instructions.set(p,new MethodInsn(184,helper,'open','(Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;)V',false));changes.push(name+':quickOpen');break;
            }
        }
    }
    var writer=new CW(reader,1);node.accept(writer);
    var output=Paths.get(arguments[1],name+'.class');Files.createDirectories(output.getParent());Files.write(output,writer.toByteArray());
}
if(changes.length!==4)throw new Error('Unexpected changes: '+JSON.stringify(changes));
print(JSON.stringify(changes));jar.close();
