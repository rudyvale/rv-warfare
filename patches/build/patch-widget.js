var Files = Java.type('java.nio.file.Files');
var Paths = Java.type('java.nio.file.Paths');
var ClassReader = Java.type('org.objectweb.asm.ClassReader');
var ClassWriter = Java.type('org.objectweb.asm.ClassWriter');
var ClassNode = Java.type('org.objectweb.asm.tree.ClassNode');
var AnnotationNode = Java.type('org.objectweb.asm.tree.AnnotationNode');
var ArrayList = Java.type('java.util.ArrayList');
var source = Files.readAllBytes(Paths.get(arguments[0]));
var reader = new ClassReader(source);
var node = new ClassNode();
reader.accept(node, 0);
var patched = [];
function clientOnly(member) {
    if (member.visibleAnnotations === null) member.visibleAnnotations = new ArrayList();
    var annotation = new AnnotationNode('Lnet/minecraftforge/fml/relauncher/SideOnly;');
    annotation.values = new ArrayList();
    annotation.values.add('value');
    annotation.values.add(Java.to(['Lnet/minecraftforge/fml/relauncher/Side;', 'CLIENT'], 'java.lang.String[]'));
    member.visibleAnnotations.add(annotation);
    patched.push(member.name);
}
for (var i = 0; i < node.methods.size(); i++) {
    var method = node.methods.get(i);
    if (['draw', 'renderFeed', 'resolve', 'drawStatus'].indexOf(String(method.name)) !== -1) clientOnly(method);
}
for (var i = 0; i < node.fields.size(); i++) {
    var field = node.fields.get(i);
    if (String(field.name) === 'feedBuffer') clientOnly(field);
}
if (patched.length !== 5) throw new Error('Unexpected WidgetUavCameraFeed structure: ' + JSON.stringify(patched));
var writer = new ClassWriter(reader, 0);
node.accept(writer);
Files.write(Paths.get(arguments[1]), writer.toByteArray());
print(JSON.stringify({clientOnlyMembers: patched}));
