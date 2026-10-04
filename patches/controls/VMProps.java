package com.norwood.mcheli.vm;

import com.google.common.base.Predicate;
import java.util.*;

public final class VMProps {
    private static final Map<Object, LinkedHashMap<Object, Damage>> damage = new WeakHashMap<Object, LinkedHashMap<Object, Damage>>();
    private static final Map<Predicate<Object>, Predicate<Object>> predicates = new IdentityHashMap<Predicate<Object>, Predicate<Object>>();
    private static final Map<Object, WorldBudget> budgets = new WeakHashMap<Object, WorldBudget>();
    private static final Map<Object, LinkedHashMap<Object, FireRecord>> fires = new WeakHashMap<Object, LinkedHashMap<Object, FireRecord>>();
    private static volatile boolean fireTickHook;

    private static final class Damage { Object state; double amount; long time; }
    private static final class FireRecord { final Object state; final long expiry; FireRecord(Object state, long expiry) { this.state = state; this.expiry = expiry; } }
    private static final class WorldBudget { long tick = Long.MIN_VALUE; int blocks; int flames; int cleanup; }

    public static synchronized Predicate<Object> targets(final Predicate<Object> original) {
        Predicate<Object> result = predicates.get(original);
        if (result == null) {
            result = new Predicate<Object>() { public boolean apply(Object entity) {
                if (original.apply(entity)) return true;
                try { return entity != null && entity.getClass().getName().equals("net.minecraft.entity.item.EntityItem") && !(Boolean) VMReflect.get(entity, "field_70128_L"); }
                catch (Exception e) { return false; }
            }};
            predicates.put(original, result);
        }
        return result;
    }

    public static void fireTickReady() { fireTickHook = true; }

    public static void block(Object bullet, Object hit) {
        try {
            Object world = VMReflect.get(bullet, "field_70170_p");
            if (remote(world)) return;
            Object pos = VMReflect.call(hit, "func_178782_a");
            if (!loaded(world, pos)) return;
            Object state = VMReflect.call(world, "func_180495_p", pos);
            double hardness = VMReflect.num(VMReflect.call(state, "func_185887_b", world, pos));
            double amount = VMReflect.num(VMReflect.call(bullet, "getDamage"));
            if (hardness < 0 || hardness > 20 || !finite(amount) || amount <= 0) return;
            Object shooter = value(bullet, "shooter", "field_85053_h");
            if (!griefing(world, shooter)) return;
            Object material = VMReflect.call(state, "func_185904_a");
            Class<?> materials = Class.forName("net.minecraft.block.material.Material");
            double scale = material == VMReflect.get(materials, "field_151576_e") ? 8 : material == VMReflect.get(materials, "field_151573_f") ? 12 : 1;
            double threshold = Math.max(4, hardness * 16 * scale);
            long now = System.nanoTime();
            synchronized (VMProps.class) {
                LinkedHashMap<Object, Damage> entries = damage.get(world);
                if (entries == null) { entries = new LinkedHashMap<Object, Damage>(); damage.put(world, entries); }
                Damage record = entries.get(pos);
                if (record == null || record.state != state || now - record.time > 30000000000L) { record = new Damage(); record.state = state; entries.put(pos, record); }
                record.amount += Math.min(amount, 1000);
                record.time = now;
                int id = 0x60000000 ^ (pos.hashCode() & 0x1fffffff);
                if (record.amount >= threshold) {
                    if (player(shooter) && !breakAllowed(world, shooter, pos)) { entries.remove(pos); VMReflect.call(world, "func_175715_c", id, pos, -1); return; }
                    if (!reserve(world, true)) return;
                    VMReflect.call(world, "func_175655_b", pos, true);
                    entries.remove(pos);
                    VMReflect.call(world, "func_175715_c", id, pos, -1);
                } else VMReflect.call(world, "func_175715_c", id, pos, Math.min(9, (int) (record.amount / threshold * 10)));
                while (entries.size() > 4096) {
                    Object first = entries.keySet().iterator().next();
                    entries.remove(first);
                    VMReflect.call(world, "func_175715_c", 0x60000000 ^ (first.hashCode() & 0x1fffffff), first, -1);
                }
            }
        } catch (Exception | LinkageError e) { VMReflect.error("projectile block damage", e); }
    }

    public static void flamethrower(Object world, Object hit, double chance, Object projectile) {
        try {
            if (remote(world)) return;
            if (fireTickHook && finite(chance) && chance >= 0 && Math.random() < Math.min(chance, 1)) {
                Object support = VMReflect.call(hit, "func_178782_a");
                Object side = VMReflect.get(hit, "field_178784_b");
                Object pos = VMReflect.call(support, "func_177972_a", side);
                Object shooter = value(projectile, "shooter", "field_85053_h");
                placeFire(world, pos, support, side, shooter);
            }
            block(projectile, hit);
        } catch (Exception | LinkageError e) { VMReflect.error("flamethrower", e); }
    }

    public static int explosionBlockId(Object world, int x, int y, int z, Object explosion) {
        try {
            if (remote(world)) return 0;
            Object pos = blockPos(x, y, z);
            if (!loaded(world, pos)) return 0;
            Object block = Class.forName("com.norwood.mcheli.wrapper.W_WorldFunc");
            int id = ((Number) VMReflect.call(block, "getBlockId", world, x, y, z)).intValue();
            if (id == 0) return 0;
            Object source = value(explosion, "explodedPlayer", "exploder");
            if (source == null) source = value(explosion, "field_77283_e");
            if (!griefing(world, source)) return 0;
            if (player(source) && !breakAllowed(world, source, pos)) return 0;
            return reserve(world, true) ? id : 0;
        } catch (Exception | LinkageError e) { VMReflect.error("native explosion block", e); return 0; }
    }

    public static boolean explosionFire(Object world, Object pos, Object state, Object explosion) {
        try {
            if (remote(world) || !fireTickHook || !isFire(state)) return false;
            double x = VMReflect.num(VMReflect.get(explosion, "field_77284_b"));
            double y = VMReflect.num(VMReflect.get(explosion, "field_77285_c"));
            double z = VMReflect.num(VMReflect.get(explosion, "field_77282_d"));
            if (Math.abs(coord(pos, "func_177958_n") - Math.floor(x)) > 1 || Math.abs(coord(pos, "func_177956_o") - Math.floor(y)) > 1 || Math.abs(coord(pos, "func_177952_p") - Math.floor(z)) > 1) return false;
            Object support = VMReflect.call(pos, "func_177977_b");
            Object source = value(explosion, "explodedPlayer", "exploder");
            if (source == null) source = value(explosion, "field_77283_e");
            return placeFire(world, pos, support, enumFacing("UP"), source);
        } catch (Exception | LinkageError e) { VMReflect.error("explosion fire", e); return false; }
    }

    public static boolean fireTick(Object world, Object pos, Object state) {
        try {
            FireRecord record;
            synchronized (VMProps.class) {
                LinkedHashMap<Object, FireRecord> entries = fires.get(world);
                if (entries == null || (record = entries.get(pos)) == null) return false;
            }
            if (state != record.state) { forget(world, pos); return false; }
            long now = worldTick(world);
            if (now >= record.expiry) {
                if (!loaded(world, pos)) { forget(world, pos); return true; }
                WorldBudget budget = budget(world);
                synchronized (VMProps.class) {
                    rollover(budget, now);
                    if (budget.cleanup >= 16) { schedule(world, pos, 1); return true; }
                    budget.cleanup++;
                }
                if (state == record.state) VMReflect.call(world, "func_175698_g", pos);
                forget(world, pos);
                return true;
            }
            schedule(world, pos, (int) Math.max(1, Math.min(100, record.expiry - now)));
            return true;
        } catch (Exception | LinkageError e) {
            boolean managed;
            synchronized (VMProps.class) { LinkedHashMap<Object, FireRecord> entries = fires.get(world); managed = entries != null && entries.containsKey(pos); }
            VMReflect.error("managed fire tick", e);
            return managed;
        }
    }

    private static boolean placeFire(Object world, Object pos, Object support, Object side, Object source) throws Exception {
        if (!fireTickHook || !loaded(world, pos) || !loaded(world, support) || !griefing(world, source)) return false;
        if (!(Boolean) VMReflect.call(world, "func_175623_d", pos)) return false;
        Object fire = VMReflect.get(Class.forName("net.minecraft.init.Blocks"), "field_150480_ab");
        Object supportState = VMReflect.call(world, "func_180495_p", support);
        Object supportBlock = VMReflect.call(supportState, "func_177230_c");
        if (((Number) VMReflect.call(supportBlock, "getFlammability", world, support, side)).intValue() <= 0) return false;
        synchronized (VMProps.class) {
            WorldBudget budget = budget(world);
            long now = worldTick(world);
            rollover(budget, now);
            LinkedHashMap<Object, FireRecord> entries = fires.get(world);
            if (entries == null) { entries = new LinkedHashMap<Object, FireRecord>(); fires.put(world, entries); }
            if (budget.flames >= 2 || entries.size() >= 64 || entries.containsKey(pos)) return false;
            budget.flames++;
        }
        Object prior = VMReflect.call(world, "func_180495_p", pos);
        Object snapshot = VMReflect.call(Class.forName("net.minecraftforge.common.util.BlockSnapshot"), "getBlockSnapshot", world, pos);
        Object state = VMReflect.call(fire, "func_176223_P");
        try { state = VMReflect.call(state, "func_177226_a", VMReflect.get(fire, "field_176543_a"), Integer.valueOf(15)); }
        catch (Exception ignored) { }
        long expiry = worldTick(world) + 100;
        try {
            if (!(Boolean) VMReflect.call(world, "func_175656_a", pos, state)) {
                rollbackFire(world, pos, state, prior, expiry);
                return false;
            }
            synchronized (VMProps.class) { fires.get(world).put(pos, new FireRecord(state, expiry)); }
            Object actor = placementActor(source);
            Object event = invokeForgeStatic(blockPlaceEvent(), actor, snapshot, side);
            if ((Boolean) VMReflect.call(event, "isCanceled")) {
                rollbackFire(world, pos, state, prior, expiry);
                return false;
            }
            if (VMReflect.call(world, "func_180495_p", pos) != state) { forget(world, pos); return false; }
            schedule(world, pos, 100);
            return true;
        } catch (Exception | LinkageError e) {
            rollbackFire(world, pos, state, prior, expiry);
            VMReflect.error("managed fire placement", e);
            return false;
        }
    }

    private static Object placementActor(Object source) throws Exception {
        if (source == null) return null;
        return Class.forName("net.minecraft.entity.player.EntityPlayer").isInstance(source) ? source : null;
    }

    private static void rollbackFire(Object world, Object pos, Object placed, Object prior, long expiry) {
        try {
            Object current = VMReflect.call(world, "func_180495_p", pos);
            if (current != placed) { forget(world, pos); return; }
            VMReflect.call(world, "func_175656_a", pos, prior);
            current = VMReflect.call(world, "func_180495_p", pos);
            if (current != placed) { forget(world, pos); return; }
            synchronized (VMProps.class) {
                LinkedHashMap<Object, FireRecord> entries = fires.get(world);
                if (entries == null) { entries = new LinkedHashMap<Object, FireRecord>(); fires.put(world, entries); }
                if (!entries.containsKey(pos)) entries.put(pos, new FireRecord(placed, expiry));
            }
            try { schedule(world, pos, 1); }
            catch (Exception | LinkageError e) { VMReflect.error("managed fire rollback schedule", e); }
            VMReflect.error("managed fire rollback", new IllegalStateException("Placed fire could not be restored"));
        } catch (Exception | LinkageError e) {
            try {
                if (VMReflect.call(world, "func_180495_p", pos) != placed) { forget(world, pos); return; }
            } catch (Exception | LinkageError ignored) { }
            synchronized (VMProps.class) {
                LinkedHashMap<Object, FireRecord> entries = fires.get(world);
                if (entries == null) { entries = new LinkedHashMap<Object, FireRecord>(); fires.put(world, entries); }
                if (!entries.containsKey(pos)) entries.put(pos, new FireRecord(placed, expiry));
            }
            try { schedule(world, pos, 1); }
            catch (Exception | LinkageError scheduleError) { VMReflect.error("managed fire rollback schedule", scheduleError); }
            VMReflect.error("managed fire rollback", e);
        }
    }

    private static boolean isFire(Object state) throws Exception { return VMReflect.call(state, "func_177230_c") == VMReflect.get(Class.forName("net.minecraft.init.Blocks"), "field_150480_ab"); }
    private static Object value(Object target, String... names) {
        if (target == null) return null;
        for (String name : names) try { Object result = VMReflect.get(target, name); if (result != null) return result; } catch (Exception ignored) { }
        return null;
    }
    private static boolean remote(Object world) throws Exception { return (Boolean) VMReflect.get(world, "field_72995_K"); }
    private static boolean loaded(Object world, Object pos) throws Exception { return (Boolean) VMReflect.call(world, "func_175668_a", pos, Boolean.FALSE); }
    private static boolean player(Object entity) { try { return entity != null && Class.forName("net.minecraft.entity.player.EntityPlayerMP").isInstance(entity); } catch (Exception e) { return false; } }
    private static boolean griefing(Object world, Object entity) throws Exception {
        Object rules = VMReflect.call(world, "func_82736_K");
        if (!(Boolean) VMReflect.call(rules, "func_82766_b", "mobGriefing")) return false;
        return entity == null || !player(entity) || !remote(world);
    }
    private static boolean breakAllowed(Object world, Object player, Object pos) throws Exception {
        Object mode = VMReflect.call(VMReflect.get(player, "field_71134_c"), "func_73081_b");
        return ((Number) invokeForgeStatic(blockBreakEvent(), world, mode, player, pos)).intValue() >= 0;
    }
    private static java.lang.invoke.MethodHandle blockPlaceEvent() throws Exception {
        java.lang.invoke.MethodHandle value = blockPlaceEvent;
        if (value != null) return value;
        synchronized (VMProps.class) {
            value = blockPlaceEvent;
            if (value == null) {
                Class<?>[] parameters = {Class.forName("net.minecraft.entity.Entity"), Class.forName("net.minecraftforge.common.util.BlockSnapshot"), Class.forName("net.minecraft.util.EnumFacing")};
                Class<?> result = Class.forName("net.minecraftforge.event.world.BlockEvent$EntityPlaceEvent");
                value = java.lang.invoke.MethodHandles.publicLookup().findStatic(Class.forName("net.minecraftforge.event.ForgeEventFactory"), "onBlockPlace", java.lang.invoke.MethodType.methodType(result, parameters));
                blockPlaceEvent = value;
            }
        }
        return value;
    }
    private static java.lang.invoke.MethodHandle blockBreakEvent() throws Exception {
        java.lang.invoke.MethodHandle value = blockBreakEvent;
        if (value != null) return value;
        synchronized (VMProps.class) {
            value = blockBreakEvent;
            if (value == null) {
                Class<?>[] parameters = {Class.forName("net.minecraft.world.World"), Class.forName("net.minecraft.world.GameType"), Class.forName("net.minecraft.entity.player.EntityPlayerMP"), Class.forName("net.minecraft.util.math.BlockPos")};
                value = java.lang.invoke.MethodHandles.publicLookup().findStatic(Class.forName("net.minecraftforge.common.ForgeHooks"), "onBlockBreakEvent", java.lang.invoke.MethodType.methodType(int.class, parameters));
                blockBreakEvent = value;
            }
        }
        return value;
    }
    private static Object invokeForgeStatic(java.lang.invoke.MethodHandle method, Object... args) throws Exception {
        try { return method.invokeWithArguments(args); }
        catch (Throwable error) {
            if (error instanceof Exception) throw (Exception) error;
            if (error instanceof LinkageError) throw (LinkageError) error;
            throw new RuntimeException(error);
        }
    }
    private static boolean reserve(Object world, boolean block) throws Exception {
        WorldBudget budget = budget(world);
        synchronized (VMProps.class) {
            rollover(budget, worldTick(world));
            if (block) { if (budget.blocks >= 4) return false; budget.blocks++; }
            else { if (budget.flames >= 2) return false; budget.flames++; }
            return true;
        }
    }
    private static WorldBudget budget(Object world) { synchronized (VMProps.class) { WorldBudget value = budgets.get(world); if (value == null) { value = new WorldBudget(); budgets.put(world, value); } return value; } }
    private static void rollover(WorldBudget value, long tick) { if (value.tick != tick) { value.tick = tick; value.blocks = 0; value.flames = 0; value.cleanup = 0; } }
    private static long worldTick(Object world) throws Exception { return ((Number) VMReflect.call(world, "func_82737_E")).longValue(); }
    private static void schedule(Object world, Object pos, int delay) throws Exception { Object fire = VMReflect.get(Class.forName("net.minecraft.init.Blocks"), "field_150480_ab"); VMReflect.call(world, "func_175684_a", pos, fire, Integer.valueOf(delay)); }
    private static Object blockPos(int x, int y, int z) throws Exception { return Class.forName("net.minecraft.util.math.BlockPos").getConstructor(int.class, int.class, int.class).newInstance(Integer.valueOf(x), Integer.valueOf(y), Integer.valueOf(z)); }
    private static double coord(Object pos, String name) throws Exception { return ((Number) VMReflect.call(pos, name)).doubleValue(); }
    private static Object enumFacing(String name) throws Exception { return Enum.valueOf((Class) Class.forName("net.minecraft.util.EnumFacing"), name); }
    private static void forget(Object world, Object pos) { synchronized (VMProps.class) { LinkedHashMap<Object, FireRecord> entries = fires.get(world); if (entries != null) entries.remove(pos); } }
    private static boolean finite(double value) { return !Double.isNaN(value) && !Double.isInfinite(value); }
    private static volatile java.lang.invoke.MethodHandle blockPlaceEvent;
    private static volatile java.lang.invoke.MethodHandle blockBreakEvent;
}
