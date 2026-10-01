package com.norwood.mcheli.vm;

import java.lang.reflect.*;
import java.util.concurrent.ConcurrentHashMap;

public final class VMReflect {
    private static final ConcurrentHashMap<String, Field> fields = new ConcurrentHashMap<String, Field>();
    private static final ConcurrentHashMap<String, Method> methods = new ConcurrentHashMap<String, Method>();
    private static final ConcurrentHashMap<String, Boolean> reported = new ConcurrentHashMap<String, Boolean>();

    public static Object get(Object target, String name) throws Exception {
        return field(target, name).get(target instanceof Class ? null : target);
    }

    public static void set(Object target, String name, Object value) throws Exception {
        field(target, name).set(target instanceof Class ? null : target, value);
    }

    private static Field field(Object target, String name) throws Exception {
        Class<?> cls = target instanceof Class ? (Class<?>) target : target.getClass();
        String key = cls.getName() + ":" + name;
        Field f = fields.get(key);
        if (f != null) return f;
        try { f=cls.getField(name); f.setAccessible(true); fields.put(key,f); return f; }
        catch(NoSuchFieldException ignored) { }
        for (Class<?> c = cls; c != null; c = c.getSuperclass()) {
            try { f = c.getDeclaredField(name); f.setAccessible(true); fields.put(key, f); return f; }
            catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(key);
    }

    public static Object call(Object target, String name, Object... args) throws Exception {
        Class<?> cls = target instanceof Class ? (Class<?>) target : target.getClass();
        String key = cls.getName() + ":" + name;
        for (Object arg : args) key += ":" + (arg == null ? "null" : arg.getClass().getName());
        Method found = methods.get(key);
        if (found == null) {
            for (Method m : cls.getMethods()) if (matches(m,name,args)) { found=m; break; }
            if(found==null)search: for (Class<?> c = cls; c != null; c = c.getSuperclass())
                for (Method m : c.getDeclaredMethods()) if(matches(m,name,args)){found=m;break search;}
            if (found == null) throw new NoSuchMethodException(key);
            found.setAccessible(true); methods.put(key, found);
        }
        return found.invoke(target instanceof Class ? null : target, args);
    }

    private static boolean matches(Method m,String name,Object[] args) {
        if (!m.getName().equals(name) || m.getParameterTypes().length != args.length) return false;
        Class<?>[] types=m.getParameterTypes();
        for(int i=0;i<types.length;i++){
            Class<?> t=types[i];
            if(args[i]==null){if(t.isPrimitive())return false;continue;}
            if(t.isPrimitive())t=t==boolean.class?Boolean.class:t==float.class?Float.class:t==double.class?Double.class:t==int.class?Integer.class:t==byte.class?Byte.class:t==long.class?Long.class:t;
            if(!t.isInstance(args[i]))return false;
        }
        return true;
    }

    public static double num(Object value) { return ((Number) value).doubleValue(); }
    public static boolean remote(Object entity) throws Exception { return (Boolean) get(get(entity, "field_70170_p"), "field_72995_K"); }
    public static void error(String area, Throwable error) {
        if (reported.putIfAbsent(area, true) == null) { System.err.println("[VM " + area + "] " + error); error.printStackTrace(); }
    }
}
