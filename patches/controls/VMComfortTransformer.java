package com.norwood.mcheli.vm;

import net.minecraft.launchwrapper.IClassTransformer;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

public final class VMComfortTransformer implements IClassTransformer {
    public static String[] append(String[] original){String[] result=java.util.Arrays.copyOf(original,original.length+2);result[original.length]=VMComfortTransformer.class.getName();result[original.length+1]=VMPropsTransformer.class.getName();return result;}
    public byte[] transform(String name,String transformedName,byte[] bytes){
        boolean medical="ichttt.mods.firstaid.common.EventHandler".equals(transformedName),visual="team.creative.enhancedvisuals.client.render.EVRenderer".equals(transformedName);
        if(bytes==null||!medical&&!visual)return bytes;
        ClassReader reader=new ClassReader(bytes);ClassNode node=new ClassNode();reader.accept(node,0);int changed=0;
        for(Object value:node.methods){MethodNode method=(MethodNode)value;
            if(medical&&method.name.equals("onWorldLoad")&&method.desc.equals("(Lnet/minecraftforge/event/world/WorldEvent$Load;)V")){
                boolean rule=false;for(AbstractInsnNode i=method.instructions.getFirst();i!=null;i=i.getNext())if(i instanceof LdcInsnNode&&"naturalRegeneration".equals(((LdcInsnNode)i).cst))rule=true;
                if(!rule)continue;method.instructions.clear();method.instructions.add(new InsnNode(Opcodes.RETURN));method.tryCatchBlocks.clear();if(method.localVariables!=null)method.localVariables.clear();changed++;
            }
            if(visual&&method.name.equals("render")&&method.desc.equals("(Lnet/minecraftforge/fml/common/gameevent/TickEvent$RenderTickEvent;)V")){
                InsnList code=new InsnList();LabelNode proceed=new LabelNode();code.add(new MethodInsnNode(Opcodes.INVOKESTATIC,"com/norwood/mcheli/vm/VMComfort","clearView","()Z",false));code.add(new JumpInsnNode(Opcodes.IFEQ,proceed));code.add(new InsnNode(Opcodes.RETURN));code.add(proceed);code.add(new FrameNode(Opcodes.F_SAME,0,null,0,null));method.instructions.insert(code);changed++;
            }
        }
        if(changed!=1)throw new IllegalStateException("RV comfort requires one supported native method in "+transformedName+", found "+changed);
        ClassWriter writer=new ClassWriter(reader,ClassWriter.COMPUTE_MAXS);node.accept(writer);System.out.println("[RV comfort] "+(medical?"FirstAid preserves world regeneration":"EnhancedVisuals clear vehicle view"));return writer.toByteArray();
    }
}
