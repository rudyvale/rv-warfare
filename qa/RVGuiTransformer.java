import java.util.Arrays;
import net.minecraft.launchwrapper.IClassTransformer;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

public final class RVGuiTransformer implements IClassTransformer {
    public static String[] append(String[] original){String[] values=Arrays.copyOf(original,original.length+1);values[original.length]="RVGuiTransformer";return values;}
    public byte[] transform(String name,String mapped,byte[] bytes){
        if(bytes==null||!Boolean.getBoolean("rv.health.gui"))return bytes;
        boolean hold=name.equals("ichttt.mods.firstaid.client.gui.GuiHoldButton"),screen=name.equals("ichttt.mods.firstaid.client.gui.GuiHealthScreen");if(!hold&&!screen)return bytes;
        ClassReader reader=new ClassReader(bytes);ClassNode node=new ClassNode();reader.accept(node,0);
        for(MethodNode method:node.methods){
            if(screen&&method.name.equals("func_73863_a")){InsnList code=new InsnList();code.add(new VarInsnNode(Opcodes.ALOAD,0));code.add(new VarInsnNode(Opcodes.ILOAD,1));code.add(new MethodInsnNode(Opcodes.INVOKESTATIC,"RVPlayerDamageRuntime","guiX","(Ljava/lang/Object;I)I",false));code.add(new VarInsnNode(Opcodes.ISTORE,1));code.add(new VarInsnNode(Opcodes.ALOAD,0));code.add(new VarInsnNode(Opcodes.ILOAD,2));code.add(new MethodInsnNode(Opcodes.INVOKESTATIC,"RVPlayerDamageRuntime","guiY","(Ljava/lang/Object;I)I",false));code.add(new VarInsnNode(Opcodes.ISTORE,2));method.instructions.insert(code);}
            for(AbstractInsnNode instruction=method.instructions.getFirst();instruction!=null;instruction=instruction.getNext())if(instruction instanceof MethodInsnNode){MethodInsnNode call=(MethodInsnNode)instruction;
                if(hold&&call.owner.equals("org/lwjgl/input/Mouse")&&call.name.equals("isButtonDown")){call.owner="RVPlayerDamageRuntime";call.name="guiMouseDown";}
                if(screen&&call.owner.equals("net/minecraftforge/fml/common/network/simpleimpl/SimpleNetworkWrapper")&&call.name.equals("sendToServer")){call.setOpcode(Opcodes.INVOKESTATIC);call.owner="RVPlayerDamageRuntime";call.name="guiSend";call.desc="(Ljava/lang/Object;Ljava/lang/Object;)V";call.itf=false;}
            }
        }
        ClassWriter writer=new ClassWriter(reader,ClassWriter.COMPUTE_MAXS);node.accept(writer);System.out.println("[RV GUI observer] "+name);return writer.toByteArray();
    }
}
