package com.norwood.mcheli.vm;

import net.minecraft.launchwrapper.IClassTransformer;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

public final class VMLoginTransformer implements IClassTransformer {
    public static String[] append(String[] original){String[] result=java.util.Arrays.copyOf(original,original.length+1);result[original.length]=VMLoginTransformer.class.getName();return result;}
    public byte[] transform(String name,String transformedName,byte[] bytes){
        if(bytes==null||!"net.minecraft.server.network.NetHandlerLoginServer".equals(transformedName))return bytes;
        ClassReader reader=new ClassReader(bytes);ClassNode node=new ClassNode();reader.accept(node,0);int changed=0;
        for(Object value:node.methods){
            MethodNode method=(MethodNode)value;if(!method.desc.equals("()V"))continue;boolean accept=false;
            for(AbstractInsnNode instruction=method.instructions.getFirst();instruction!=null;instruction=instruction.getNext())if(instruction instanceof MethodInsnNode&&((MethodInsnNode)instruction).desc.equals("(Ljava/net/SocketAddress;Lcom/mojang/authlib/GameProfile;)Ljava/lang/String;"))accept=true;
            if(!accept)continue;
            InsnList guard=new InsnList();LabelNode proceed=new LabelNode();guard.add(new VarInsnNode(Opcodes.ALOAD,0));guard.add(new MethodInsnNode(Opcodes.INVOKESTATIC,"com/norwood/mcheli/uav/WarfareOwnerAuth","allowLogin","(Ljava/lang/Object;)Z",false));guard.add(new JumpInsnNode(Opcodes.IFNE,proceed));guard.add(new InsnNode(Opcodes.RETURN));guard.add(proceed);guard.add(new FrameNode(Opcodes.F_SAME,0,null,0,null));method.instructions.insert(guard);changed++;
        }
        if(changed!=1)throw new IllegalStateException("RV login guard requires one native accept method, found "+changed);
        ClassWriter writer=new ClassWriter(reader,ClassWriter.COMPUTE_MAXS);node.accept(writer);return writer.toByteArray();
    }
}
