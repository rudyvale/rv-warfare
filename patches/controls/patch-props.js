var Files=Java.type('java.nio.file.Files'),Paths=Java.type('java.nio.file.Paths'),Jar=Java.type('java.util.jar.JarFile');
var CR=Java.type('org.objectweb.asm.ClassReader'),CW=Java.type('org.objectweb.asm.ClassWriter'),CN=Java.type('org.objectweb.asm.tree.ClassNode');
var IL=Java.type('org.objectweb.asm.tree.InsnList'),VI=Java.type('org.objectweb.asm.tree.VarInsnNode'),MI=Java.type('org.objectweb.asm.tree.MethodInsnNode');
var jar=new Jar(arguments[0]),name='techguns/entities/projectiles/GenericProjectile',node=new CN(),reader=new CR(jar.getInputStream(jar.getJarEntry(name+'.class')));reader.accept(node,0);
var count=0,owner='com/norwood/mcheli/vm/VMProps';
for(var i=0;i<node.methods.size();i++){
    var m=node.methods.get(i);
    if(String(m.name)==='findEntityOnPath')for(var x=m.instructions.getFirst();x!==null;x=x.getNext())if(x.getOpcode()===178&&String(x.name)==='BULLET_TARGETS'){
        m.instructions.insert(x,new MI(184,owner,'targets','(Lcom/google/common/base/Predicate;)Lcom/google/common/base/Predicate;',false));count++;
    }
    if(String(m.name)==='hitBlock')for(var x=m.instructions.getFirst();x!==null;x=x.getNext())if(x.getOpcode()===177){
        var code=new IL();code.add(new VI(25,0));code.add(new VI(25,1));code.add(new MI(184,owner,'block','(Ljava/lang/Object;Ljava/lang/Object;)V',false));m.instructions.insertBefore(x,code);count++;
    }
}
if(count!==2)throw new Error('Techguns props hook mismatch '+count);
var writer=new CW(reader,1);node.accept(writer);var path=Paths.get(arguments[1],name+'.class');Files.createDirectories(path.getParent());Files.write(path,writer.toByteArray());jar.close();print(JSON.stringify(['nativeDroppedItemCollision','nativeBlockDamage']));
