package com.norwood.mcheli.uav;

import java.lang.reflect.*;
import java.util.*;

public final class WarfareQuickUav {
    private static final String BASE = "com.norwood.mcheli.";

    private static Object call(Object receiver, String name, Object... args) throws Exception {
        Class<?> type = receiver instanceof Class ? (Class<?>) receiver : receiver.getClass();
        for (Method m : type.getMethods()) {
            if (!m.getName().equals(name) || m.getParameterTypes().length != args.length) continue;
            Class<?>[] types = m.getParameterTypes();
            boolean match = true;
            for (int i = 0; i < types.length; i++) {
                if (args[i] == null) continue;
                if (types[i].isPrimitive()) {
                    if (types[i] == boolean.class && !(args[i] instanceof Boolean)) match = false;
                    else if (types[i] != boolean.class && !(args[i] instanceof Number)) match = false;
                } else if (!types[i].isInstance(args[i])) match = false;
            }
            if (match) return m.invoke(receiver instanceof Class ? null : receiver, args);
        }
        throw new NoSuchMethodException(type.getName() + "." + name);
    }

    private static Object field(Object value, String name) throws Exception {
        return value.getClass().getField(name).get(value);
    }

    private static Class<?> type(String name) throws Exception {
        return Class.forName(name);
    }

    private static Object success() throws Exception {
        return type("net.minecraft.util.EnumActionResult").getField("SUCCESS").get(null);
    }

    private static boolean ru(Object player) {
        try {
            Object board = call(field(player, "field_70170_p"), "func_96441_U");
            Object objective = call(board, "func_96518_b", "wlang");
            Object score = call(board, "func_96529_a", call(player, "func_70005_c_"), objective);
            return ((Number) call(score, "func_96652_c")).intValue() != 2;
        } catch (Exception ignored) { return true; }
    }

    private static void message(Object player, String russian, String english) throws Exception {
        Object component = type("net.minecraft.util.text.TextComponentString").getConstructor(String.class)
                .newInstance(ru(player) ? russian : english);
        call(player, "func_145747_a", component);
    }

    private static boolean usable(Object uav, Object player) throws Exception {
        if (!type(BASE + "aircraft.MCH_EntityAircraft").isInstance(uav)) return false;
        if (!(Boolean) call(uav, "isUAV") || (Boolean) call(uav, "isTargetDrone")) return false;
        if ((Boolean) field(uav, "field_70128_L") || (Boolean) call(uav, "isDestroyed")) return false;
        Object otherStation = call(uav, "getUavStation");
        Object other = otherStation == null ? null : call(otherStation, "getOperator");
        return other == null || other == player;
    }

    private static Object nearest(Object player, Object station) throws Exception {
        Object world = field(player, "field_70170_p");
        double best = 32.0 * 32.0;
        Object found = null;
        for (Object entity : new ArrayList<Object>((List<?>) field(world, "field_72996_f"))) {
            if (!usable(entity, player)) continue;
            double distance = ((Number) call(entity, "func_70068_e", station)).doubleValue();
            if (distance < best) { best = distance; found = entity; }
        }
        return found;
    }

    private static void connect(Object player, Object station, Object uav) throws Exception {
        call(station, "pairUav", call(uav, "func_110124_au"));
        call(uav, "setFuel", call(uav, "getMaxFuel"));
        Object result = call(type(BASE + "uav.MCH_UavControl"), "connect", player, station, uav);
        if (!"OK".equals(result.toString())) throw new IllegalStateException("UAV: " + result);
        call(player, "func_71053_j");
        message(player, "§aДрон подключён и заправлен. §fW — взлёт, S — газ вниз, мышь — поворот, Shift — выход.",
                "§aUAV connected and fueled. §fW: take off, S: throttle down, mouse: steer, Shift: exit.");
        System.out.println("[WarfareQuickUav] CONNECT operator=" + call(player, "func_70005_c_")
                + " uav=" + call(uav, "func_110124_au") + " fuel=" + call(uav, "getFuel"));
    }

    public static boolean interact(Object event) {
        Object station = null;
        Object player = null;
        try {
            if (!"MAIN_HAND".equals(call(event, "getHand").toString())) return false;
            Object stack = call(event, "getItemStack");
            Object item = call(stack, "func_77973_b");
            boolean tablet = type(BASE + "uav.MCH_ItemUavTablet").isInstance(item);
            if (!tablet && !type(BASE + "uav.MCH_ItemUavStation").isInstance(item)) return false;
            Object uav = call(event, "getTarget");
            if (!type(BASE + "aircraft.MCH_EntityAircraft").isInstance(uav) || !(Boolean) call(uav, "isUAV")) return false;
            call(event, "setCanceled", true);
            call(event, "setCancellationResult", success());
            Object world = call(event, "getWorld");
            if ((Boolean) field(world, "field_72995_K")) return true;
            player = call(event, "getEntityPlayer");
            if (!usable(uav, player)) {
                message(player, "§cДрон занят другим игроком или уничтожен.", "§cThis UAV is occupied or destroyed.");
                return true;
            }
            if (((Number) call(player, "func_70068_e", uav)).doubleValue() > 64.0) return true;
            if (call(player, "func_184187_bx") != null) {
                message(player, "§eСначала нажми Shift, чтобы выйти из текущего управления.", "§ePress Shift to leave your current vehicle first.");
                return true;
            }
            if (tablet) call(type(BASE + "uav.MCH_ItemUavTablet"), "addPairedUav", stack, call(uav, "func_110124_au"));
            station = call(type(BASE + "uav.MCH_EntityUavStation"), "createHandheld", world, player,
                    call(event, "getHand"), Collections.singletonList(call(uav, "func_110124_au")), false);
            if (!(Boolean) call(world, "func_72838_d", station)) throw new IllegalStateException("Station spawn rejected");
            connect(player, station, uav);
            return true;
        } catch (Exception error) {
            error.printStackTrace();
            try {
                if (station != null) {
                    call(type(BASE + "uav.MCH_UavControl"), "disconnect", station);
                    call(station, "func_70106_y");
                }
                if (player != null) message(player, "§cНе удалось подключить дрон. Ошибка сохранена в журнале сервера.",
                        "§cUAV connection failed. See the server log.");
            } catch (Exception ignored) { }
            return player != null;
        }
    }

    public static void open(Object factory, Object player, Object station) {
        try {
            Object uav = nearest(player, station);
            if (uav != null) { connect(player, station, uav); return; }
            message(player, "§eРядом нет дрона. Поставь дрон, возьми контроллер и нажми ПКМ по дрону.",
                    "§eNo UAV nearby. Place one, hold a controller and right-click the UAV.");
            call(player, "func_184210_p");
            if ((Boolean) call(station, "isHandheld")) call(station, "func_70106_y");
        } catch (Exception error) {
            error.printStackTrace();
            try { call(factory, "openGui", player, station); } catch (Exception fallback) { fallback.printStackTrace(); }
        }
    }

    public static boolean command(Object server, Object sender, String[] args) {
        if (args.length != 2 || !"warfaretest".equals(args[0])) return false;
        Object uav = null;
        Object player = null;
        Object station = null;
        Object previous = null;
        Object previousUav = null;
        try {
            if (!(Boolean) call(type(BASE + "command.MCH_Command"), "checkCommandPermission", server, sender, args[0])) return true;
            player = call(call(server, "func_184103_al"), "func_152612_a", args[1]);
            if (player == null) throw new IllegalArgumentException("Test player is offline");
            previous = call(player, "func_184187_bx");
            if (previous != null) {
                if (type(BASE + "uav.MCH_EntityUavStation").isInstance(previous)) {
                    previousUav = call(previous, "getControlled");
                    call(type(BASE + "uav.MCH_UavControl"), "disconnect", previous);
                } else call(player, "func_184210_p");
            }
            Object world = field(player, "field_70170_p");
            Object registry = type("net.minecraftforge.fml.common.registry.ForgeRegistries").getField("ITEMS").get(null);
            Constructor<?> rl = type("net.minecraft.util.ResourceLocation").getConstructor(String.class);
            Object droneItem = call(registry, "getValue", rl.newInstance("mcheli:rc-goblin-bomb"));
            Object controlItem = call(registry, "getValue", rl.newInstance("mcheli:uav_tablet"));
            Constructor<?> stackCtor = type("net.minecraft.item.ItemStack").getConstructor(type("net.minecraft.item.Item"));
            Object droneStack = stackCtor.newInstance(droneItem);
            Object controlStack = stackCtor.newInstance(controlItem);
            double x = ((Number) field(player, "field_70165_t")).doubleValue();
            double y = ((Number) field(player, "field_70163_u")).doubleValue();
            double z = ((Number) field(player, "field_70161_v")).doubleValue();
            uav = call(droneItem, "createAircraft", world, x + 3.0, y + 1.0, z, droneStack);
            if (uav == null || !(Boolean) call(world, "func_72838_d", uav)) throw new IllegalStateException("Test UAV spawn failed");
            Object hand = type("net.minecraft.util.EnumHand").getField("MAIN_HAND").get(null);
            TestEvent event = new TestEvent(player, uav, world, hand, controlStack);
            if (!interact(event)) throw new IllegalStateException("Interaction was not handled");
            station = call(player, "func_184187_bx");
            if (!event.canceled || station == null || call(station, "getControlled") != uav
                    || call(uav, "getUavStation") != station || call(station, "getOperator") != player
                    || ((Number) call(uav, "getFuel")).intValue() <= 0) throw new IllegalStateException("Control link assertion failed");
            call(type(BASE + "uav.MCH_UavControl"), "disconnect", station);
            if (call(player, "func_184187_bx") != null || call(station, "getControlled") != null)
                throw new IllegalStateException("Disconnect assertion failed");
            System.out.println("[WarfareQuickUav] SELFTEST PASS: click, pairing, mount, two-way link, fuel, disconnect");
        } catch (Exception error) {
            System.out.println("[WarfareQuickUav] SELFTEST FAIL");
            error.printStackTrace();
        } finally {
            try {
                if (station != null) call(station, "func_70106_y");
                if (uav != null) call(uav, "func_70106_y");
                if (previous != null && !(Boolean) field(previous, "field_70128_L")) {
                    if (previousUav != null) call(type(BASE + "uav.MCH_UavControl"), "connect", player, previous, previousUav);
                    else call(player, "func_184205_a", previous, true);
                }
            } catch (Exception error) { error.printStackTrace(); }
        }
        return true;
    }

    public static final class TestEvent {
        private final Object player, target, world, hand, stack;
        public boolean canceled;
        TestEvent(Object player, Object target, Object world, Object hand, Object stack) {
            this.player = player; this.target = target; this.world = world; this.hand = hand; this.stack = stack;
        }
        public Object getEntityPlayer() { return player; }
        public Object getTarget() { return target; }
        public Object getWorld() { return world; }
        public Object getHand() { return hand; }
        public Object getItemStack() { return stack; }
        public void setCanceled(boolean value) { canceled = value; }
        public void setCancellationResult(Object value) { }
    }
}
