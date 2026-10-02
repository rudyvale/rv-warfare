var Jar=Java.type('java.util.jar.JarFile'),CR=Java.type('org.objectweb.asm.ClassReader'),CN=Java.type('org.objectweb.asm.tree.ClassNode');
var jar=new Jar(arguments[0]);
for(var a=1;a<arguments.length;a++){var node=new CN();new CR(jar.getInputStream(jar.getJarEntry(arguments[a]+'.class'))).accept(node,7);print('CLASS '+node.name);for(var i=0;i<node.fields.size();i++){var field=node.fields.get(i);print('FIELD '+field.access+' '+field.name+' '+field.desc);}for(var i=0;i<node.methods.size();i++){var method=node.methods.get(i);print('METHOD '+method.access+' '+method.name+' '+method.desc);}}
jar.close();
