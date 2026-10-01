package com.norwood.mcheli.uav;

import java.lang.reflect.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

public final class WarfareFpv {
    private static final Map<Object, Double> motors = Collections.synchronizedMap(new WeakHashMap<Object, Double>());
    private static final Map<String, Field> fields = new ConcurrentHashMap<String, Field>();
    private static final Map<String, Method> methods = new ConcurrentHashMap<String, Method>();
    private static int errors;
    private static final double GRAVITY = 9.81 / 400.0;

    private static Field field(Object object, String name) throws Exception {
        String key = object.getClass().getName() + ":" + name;
        Field result = fields.get(key);
        if (result != null) return result;
        result = object.getClass().getField(name);
        fields.put(key, result);
        return result;
    }

    private static Object get(Object object, String name) throws Exception { return field(object, name).get(object); }
    private static void set(Object object, String name, Object value) throws Exception { field(object, name).set(object, value); }
    private static double number(Object value) { return ((Number) value).doubleValue(); }

    private static Object call(Object object, String name, Object... arguments) throws Exception {
        String key = object.getClass().getName() + ":" + name;
        for (Object argument : arguments) key += ":" + (argument == null ? "null" : argument.getClass().getName());
        Method method = methods.get(key);
        if (method == null) {
            Class<?> type = object.getClass();
            outer: while (type != null) {
                for (Method candidate : type.getMethods()) {
                    if (!candidate.getName().equals(name) || candidate.getParameterTypes().length != arguments.length) continue;
                    Class<?>[] parameters = candidate.getParameterTypes();
                    boolean match = true;
                    for (int i = 0; i < parameters.length; i++) {
                        if (arguments[i] == null) continue;
                        if (parameters[i].isPrimitive()) {
                            if (parameters[i] == boolean.class) match &= arguments[i] instanceof Boolean;
                            else match &= arguments[i] instanceof Number;
                        } else match &= parameters[i].isInstance(arguments[i]);
                    }
                    if (match) { method = candidate; break outer; }
                }
                type = type.getSuperclass();
            }
            if (method == null) throw new NoSuchMethodException(key);
            method.setAccessible(true);
            methods.put(key, method);
        }
        return method.invoke(object, arguments);
    }

    private static void failure(Throwable error) {
        if (errors++ == 0) {
            System.err.println("[Warfare FPV] Physics fallback: " + error);
            error.printStackTrace();
        }
    }

    public static boolean enabled(Object aircraft) {
        try {
            String name = String.valueOf(call(aircraft, "getTypeName"));
            int colon = name.lastIndexOf(':');
            if (colon >= 0) name = name.substring(colon + 1);
            return name.equals("rc-goblin") || name.equals("rc-goblin-bomb");
        } catch (Exception | LinkageError error) { failure(error); return false; }
    }

    public static float yaw(Object aircraft) {
        try {
            if ((Boolean) call(aircraft, "isFreeLookMode")) return 0;
            return ((Boolean) get(aircraft, "moveRight") ? 35 : 0) - ((Boolean) get(aircraft, "moveLeft") ? 35 : 0);
        } catch (Exception | LinkageError error) { failure(error); return 0; }
    }

    public static boolean canRotate(Object aircraft) {
        try {
            return !(Boolean) get(aircraft, "field_70122_E") && (Boolean) call(aircraft, "canMouseRot");
        } catch (Exception | LinkageError error) { failure(error); return false; }
    }

    public static boolean angles(Object aircraft, float deltaSeconds) {
        return enabled(aircraft);
    }

    public static boolean control(Object aircraft) {
        if (!enabled(aircraft)) return false;
        try {
            if ((Boolean) call(aircraft, "isHoveringMode")) call(aircraft, "switchHoveringMode", false);
            if ((Boolean) call(aircraft, "isHovering")) call(aircraft, "switchGunnerMode", false);
            Object pilot = call(aircraft, "getRiddenByEntity");
            double throttle = number(call(aircraft, "getCurrentThrottle"));
            boolean powered = pilot != null && !(Boolean) call(aircraft, "isDestroyed") && (Boolean) call(aircraft, "canUseFuel", true);
            if (powered) {
                if ((Boolean) get(aircraft, "throttleUp")) throttle += 0.018;
                if ((Boolean) get(aircraft, "throttleDown")) throttle -= 0.018;
            } else throttle = Math.max(0, throttle - 0.12);
            throttle = Math.max(0, Math.min(1, throttle));
            Object world = get(aircraft, "field_70170_p");
            if ((Boolean) get(world, "field_72995_K")) {
                boolean local = false;
                if (pilot != null) {
                    Class<?> wrapper = Class.forName("com.norwood.mcheli.wrapper.W_Lib");
                    Class<?> entity = Class.forName("net.minecraft.entity.Entity");
                    local = (Boolean) wrapper.getMethod("isClientPlayer", entity).invoke(null, pilot);
                }
                if (!local) throttle = number(call(aircraft, "getThrottle"));
            } else call(aircraft, "setThrottle", throttle);
            call(aircraft, "setCurrentThrottle", throttle);
            double rotor = number(get(aircraft, "rotationRotor"));
            set(aircraft, "prevRotationRotor", rotor);
            double rotorSpeed = number(get(call(aircraft, "getAcInfo"), "rotorSpeed"));
            set(aircraft, "rotationRotor", (rotor + (1 - Math.pow(1 - throttle, 5)) * rotorSpeed) % 360);
            return true;
        } catch (Exception | LinkageError error) { failure(error); return false; }
    }

    public static double[] step(double motor, double throttle, double vx, double vy, double vz, double yaw, double pitch, double roll, boolean ground, boolean water) {
        motor += (Math.max(0, Math.min(1, throttle)) - motor) * (1 - Math.exp(-0.05 / 0.10));
        double p = Math.toRadians(pitch), r = Math.toRadians(roll), y = Math.toRadians(yaw);
        double ux = -Math.sin(r) * Math.cos(y) - Math.cos(r) * Math.sin(p) * Math.sin(y);
        double uy = Math.cos(r) * Math.cos(p);
        double uz = -Math.sin(r) * Math.sin(y) + Math.cos(r) * Math.sin(p) * Math.cos(y);
        double thrust = 4 * GRAVITY * motor * motor;
        double speed = Math.sqrt(vx * vx + vy * vy + vz * vz);
        double drag = water ? 0.18 : Math.min(0.25, 0.0025 + 0.009 * speed);
        vx = vx * (1 - drag) + ux * thrust;
        vy = vy * (1 - drag) + uy * thrust - GRAVITY;
        vz = vz * (1 - drag) + uz * thrust;
        if (ground) {
            vx *= 0.65;
            vz *= 0.65;
            if (vy < 0) vy = -0.001;
        }
        if (!Double.isFinite(vx + vy + vz)) throw new IllegalStateException("Nonfinite FPV motion");
        return new double[] {motor, vx, vy, vz};
    }

    public static boolean motion(Object aircraft) {
        if (!enabled(aircraft)) return false;
        try {
            double throttle = number(call(aircraft, "getCurrentThrottle"));
            if ((Boolean) call(aircraft, "isDestroyed") || !(Boolean) call(aircraft, "canUseFuel", true)) throttle = 0;
            Double motor = motors.get(aircraft);
            double[] result = step(motor == null ? 0 : motor, throttle,
                    number(get(aircraft, "field_70159_w")), number(get(aircraft, "field_70181_x")), number(get(aircraft, "field_70179_y")),
                    number(call(aircraft, "getYaw")), number(call(aircraft, "getPitch")), number(call(aircraft, "getRoll")),
                    (Boolean) get(aircraft, "field_70122_E"), (Boolean) call(aircraft, "func_70090_H"));
            motors.put(aircraft, result[0]);
            set(aircraft, "field_70159_w", result[1]);
            set(aircraft, "field_70181_x", result[2]);
            set(aircraft, "field_70179_y", result[3]);
            Object self = Class.forName("net.minecraft.entity.MoverType").getField("SELF").get(null);
            call(aircraft, "func_70091_d", self, result[1], result[2], result[3]);
            call(aircraft, "warfareUpdateBlocks");
            Object pilot = call(aircraft, "getRiddenByEntity");
            if (pilot != null && (Boolean) get(pilot, "field_70128_L")) call(aircraft, "unmountEntity");
            return true;
        } catch (Exception | LinkageError error) { failure(error); return false; }
    }

    private static void require(boolean condition, String name) {
        if (!condition) throw new IllegalStateException(name);
    }

    public static void verifyMath() {
        double[] fall = step(0, 0, 0, 0, 0, 0, 0, 0, false, false);
        require(Math.abs(fall[2] + GRAVITY) < 1e-10, "gravity");
        double[] hover = step(0.5, 0.5, 0, 0, 0, 0, 0, 0, false, false);
        require(Math.abs(hover[1]) + Math.abs(hover[2]) + Math.abs(hover[3]) < 1e-10, "hover");
        double[] tilt = step(0.5, 0.5, 0, 0, 0, 0, 45, 0, false, false);
        require(tilt[3] > 0 && tilt[2] < 0, "tilted thrust");
        double[] bank = step(0.5, 0.5, 0, 0, 0, 0, 0, -45, false, false);
        require(bank[1] > 0 && bank[2] < 0, "bank thrust");
        double[] inverse = step(0.5, 0.5, 0, 0, 0, 0, 0, 180, false, false);
        require(Math.abs(inverse[2] + 2 * GRAVITY) < 1e-10, "inverted thrust");
        double[] coast = step(0, 0, 1, 0, 0, 0, 0, 0, false, false);
        require(coast[1] > 0.9 && coast[1] < 1, "momentum");
        double[] spool = step(0, 1, 0, 0, 0, 0, 0, 0, false, false);
        require(spool[0] > 0 && spool[0] < 1, "motor lag");
        double[] landing = step(0, 0, 0, -2, 0, 0, 0, 0, true, false);
        require(landing[2] >= -0.001, "ground");
        double[] state = {0, 0, 0, 0};
        for (int i = 0; i < 12000; i++) state = step(state[0], 1, state[1], state[2], state[3], i % 360, 45, 0, false, false);
        require(Math.abs(state[1]) + Math.abs(state[2]) + Math.abs(state[3]) < 10, "long flight stability");
    }

    public static boolean command(Object server, Object sender, String[] args) {
        if (args.length != 2 || !"warfarefpvtest".equals(args[0])) return false;
        try {
            verifyMath();
            Object players = call(server, "func_184103_al");
            Object player = call(players, "func_152612_a", args[1]);
            if (player == null) throw new IllegalStateException("Player must be online");
            Object world = get(player, "field_70170_p");
            Class<?> type = Class.forName("com.norwood.mcheli.helicopter.MCH_EntityHeli");
            Object drone = type.getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);
            call(drone, "setTypeName", "rc-goblin");
            call(drone, "func_70107_b", number(get(player, "field_70165_t")), 220.0, number(get(player, "field_70161_v")));
            call(drone, "setFuel", call(drone, "getMaxFuel"));
            require(enabled(drone), "FPV type");
            int before = errors;
            call(drone, "setCurrentThrottle", 0.6);
            call(drone, "warfareCheckControl");
            require(Math.abs(number(call(drone, "getCurrentThrottle")) - 0.48) < 1e-8, "disconnect throttle cut and control hook");
            call(drone, "setCurrentThrottle", 0.5);
            motors.put(drone, 0.5);
            double y0 = number(get(drone, "field_70163_u"));
            call(drone, "warfareCheckMotion");
            require(motors.containsKey(drone), "motion hook");
            require(Math.abs(number(get(drone, "field_70163_u")) - y0) < 0.001, "runtime hover");
            call(drone, "setRotPitch", 45.0F);
            call(drone, "warfareCheckMotion");
            require(Math.abs(number(get(drone, "field_70179_y"))) > 0.001, "runtime tilt");
            set(drone, "moveRight", true);
            require(number(call(drone, "getControlRotYaw", 0F, 0F, 1F)) == 35, "yaw input hook");
            call(drone, "setRotRoll", 45F);
            call(drone, "onUpdateAngles", 0.05F);
            require(number(call(drone, "getRoll")) == 45, "no auto level hook");
            require(errors == before, "reflection failure");
            call(drone, "func_70106_y");
            motors.remove(drone);
            System.out.println("[Warfare FPV] PASS gravity, hover, tilt, bank, inverted, inertia, motor lag, ground, long flight, runtime hooks");
        } catch (Exception | LinkageError error) {
            System.err.println("[Warfare FPV] TEST FAILED");
            error.printStackTrace();
        }
        return true;
    }

    public static void main(String[] args) {
        verifyMath();
        System.out.println("FPV math: 9 checks passed");
    }
}
