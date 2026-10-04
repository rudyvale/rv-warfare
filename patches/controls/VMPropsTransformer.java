package com.norwood.mcheli.vm;

import net.minecraft.launchwrapper.IClassTransformer;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.tree.AbstractInsnNode;
import org.objectweb.asm.tree.ClassNode;
import org.objectweb.asm.tree.FrameNode;
import org.objectweb.asm.tree.InsnList;
import org.objectweb.asm.tree.InsnNode;
import org.objectweb.asm.tree.JumpInsnNode;
import org.objectweb.asm.tree.LabelNode;
import org.objectweb.asm.tree.MethodInsnNode;
import org.objectweb.asm.tree.MethodNode;
import org.objectweb.asm.tree.VarInsnNode;

public final class VMPropsTransformer implements IClassTransformer {
    private static final String props = "com/norwood/mcheli/vm/VMProps";

    public byte[] transform(String name, String transformedName, byte[] bytes) {
        if (bytes == null) return null;
        if ("techguns.entities.projectiles.FlamethrowerProjectile".equals(transformedName)) return flamethrower(bytes);
        if ("com.norwood.mcheli.helper.world.MCH_ExplosionV2".equals(transformedName)) return explosion(bytes);
        if ("net.minecraft.block.BlockFire".equals(transformedName)) return fire(bytes);
        return bytes;
    }

    private static byte[] flamethrower(byte[] bytes) {
        ClassReader reader = new ClassReader(bytes);
        ClassNode node = new ClassNode();
        reader.accept(node, 0);
        int found = 0;
        for (Object value : node.methods) {
            MethodNode method = (MethodNode) value;
            if (!"hitBlock".equals(method.name) || !"(Lnet/minecraft/util/math/RayTraceResult;)V".equals(method.desc)) continue;
            for (AbstractInsnNode instruction = method.instructions.getFirst(); instruction != null; instruction = instruction.getNext()) {
                if (!(instruction instanceof MethodInsnNode)) continue;
                MethodInsnNode call = (MethodInsnNode) instruction;
                if (call.getOpcode() != Opcodes.INVOKESTATIC || !"techguns/entities/projectiles/FlamethrowerProjectile".equals(call.owner) || !"burnBlocks".equals(call.name) || !"(Lnet/minecraft/world/World;Lnet/minecraft/util/math/RayTraceResult;D)V".equals(call.desc)) continue;
                method.instructions.insertBefore(call, new VarInsnNode(Opcodes.ALOAD, 0));
                call.owner = props;
                call.name = "flamethrower";
                call.desc = "(Lnet/minecraft/world/World;Lnet/minecraft/util/math/RayTraceResult;DLjava/lang/Object;)V";
                found++;
            }
        }
        if (found != 1) throw new IllegalStateException("VM props requires one supported Techguns flame hook, found " + found);
        return write(reader, node);
    }

    private static byte[] explosion(byte[] bytes) {
        ClassReader reader = new ClassReader(bytes);
        ClassNode node = new ClassNode();
        reader.accept(node, 0);
        int blockIds = 0;
        int firePlacements = 0;
        for (Object value : node.methods) {
            MethodNode method = (MethodNode) value;
            if (!"doExplosionB".equals(method.name) || !"(ZZ)V".equals(method.desc)) continue;
            for (AbstractInsnNode instruction = method.instructions.getFirst(); instruction != null; instruction = instruction.getNext()) {
                if (!(instruction instanceof MethodInsnNode)) continue;
                MethodInsnNode call = (MethodInsnNode) instruction;
                if (call.getOpcode() == Opcodes.INVOKESTATIC && call.owner.endsWith("/W_WorldFunc") && "getBlockId".equals(call.name) && "(Lnet/minecraft/world/World;III)I".equals(call.desc)) {
                    blockIds++;
                    if (blockIds == 1) {
                        method.instructions.insertBefore(call, new VarInsnNode(Opcodes.ALOAD, 0));
                        call.owner = props;
                        call.name = "explosionBlockId";
                        call.desc = "(Lnet/minecraft/world/World;IIILjava/lang/Object;)I";
                    }
                }
                if (call.getOpcode() == Opcodes.INVOKEVIRTUAL && "net/minecraft/world/World".equals(call.owner) && "func_175656_a".equals(call.name) && "(Lnet/minecraft/util/math/BlockPos;Lnet/minecraft/block/state/IBlockState;)Z".equals(call.desc)) {
                    method.instructions.insertBefore(call, new VarInsnNode(Opcodes.ALOAD, 0));
                    call.setOpcode(Opcodes.INVOKESTATIC);
                    call.owner = props;
                    call.name = "explosionFire";
                    call.desc = "(Lnet/minecraft/world/World;Lnet/minecraft/util/math/BlockPos;Lnet/minecraft/block/state/IBlockState;Ljava/lang/Object;)Z";
                    call.itf = false;
                    firePlacements++;
                }
            }
        }
        if (blockIds != 2 || firePlacements != 1) throw new IllegalStateException("VM props requires supported MCH explosion hooks; block lookups=" + blockIds + ", fire placements=" + firePlacements);
        return write(reader, node);
    }

    private static byte[] fire(byte[] bytes) {
        ClassReader reader = new ClassReader(bytes);
        ClassNode node = new ClassNode();
        reader.accept(node, 0);
        int found = 0;
        for (Object value : node.methods) {
            MethodNode method = (MethodNode) value;
            if (!("func_180650_b".equals(method.name) || "updateTick".equals(method.name)) || !"(Lnet/minecraft/world/World;Lnet/minecraft/util/math/BlockPos;Lnet/minecraft/block/state/IBlockState;Ljava/util/Random;)V".equals(method.desc)) continue;
            InsnList hook = new InsnList();
            LabelNode proceed = new LabelNode();
            hook.add(new VarInsnNode(Opcodes.ALOAD, 1));
            hook.add(new VarInsnNode(Opcodes.ALOAD, 2));
            hook.add(new VarInsnNode(Opcodes.ALOAD, 3));
            hook.add(new MethodInsnNode(Opcodes.INVOKESTATIC, props, "fireTick", "(Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;)Z", false));
            hook.add(new JumpInsnNode(Opcodes.IFEQ, proceed));
            hook.add(new InsnNode(Opcodes.RETURN));
            hook.add(proceed);
            hook.add(new FrameNode(Opcodes.F_SAME, 0, null, 0, null));
            method.instructions.insert(hook);
            found++;
        }
        if (found != 1) throw new IllegalStateException("VM props requires one supported BlockFire update hook, found " + found);
        VMProps.fireTickReady();
        return write(reader, node);
    }

    private static byte[] write(ClassReader reader, ClassNode node) {
        ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
        node.accept(writer);
        return writer.toByteArray();
    }
}
