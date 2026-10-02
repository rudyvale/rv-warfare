var Jar=Java.type('java.util.jar.JarFile'),CR=Java.type('org.objectweb.asm.ClassReader'),CN=Java.type('org.objectweb.asm.tree.ClassNode'),T=Java.type('org.objectweb.asm.util.Textifier'),V=Java.type('org.objectweb.asm.util.TraceMethodVisitor'),PW=Java.type('java.io.PrintWriter');
var jar=new Jar(arguments[0]),node=new CN(),methodName=''+arguments[2];
new CR(jar.getInputStream(jar.getJarEntry(arguments[1]+'.class'))).accept(node,0);
for(var i=0;i<node.methods.size();i++){var method=node.methods.get(i);if((''+method.name)===methodName){print('METHOD '+method.name+' '+method.desc);var trace=new T();method.accept(new V(trace));var output=new PW(java.lang.System.out,true);trace.print(output);output.flush();}}
jar.close();
