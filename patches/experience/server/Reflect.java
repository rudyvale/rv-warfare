package rv.experience.server;

import java.lang.reflect.Field;
import java.lang.reflect.Method;

public final class Reflect {
    public static Object field(Object target,String...names)throws Exception{
        Class<?> cls=target instanceof Class?(Class<?>)target:target.getClass();
        for(Class<?> type=cls;type!=null;type=type.getSuperclass())for(String name:names)try{Field f=type.getDeclaredField(name);f.setAccessible(true);return f.get(target instanceof Class?null:target);}catch(NoSuchFieldException ignored){}
        throw new NoSuchFieldException(names[0]);
    }
    public static Object call(Object target,String[] names,Object...args)throws Exception{
        Class<?> cls=target instanceof Class?(Class<?>)target:target.getClass();
        for(Class<?> type=cls;type!=null;type=type.getSuperclass())for(Method method:type.getDeclaredMethods()){
            boolean found=false;for(String name:names)if(name.equals(method.getName()))found=true;
            if(!found||method.getParameterTypes().length!=args.length)continue;
            Class<?>[] types=method.getParameterTypes();boolean match=true;
            for(int i=0;i<types.length;i++){Class<?> t=types[i];if(t.isPrimitive())t=t==int.class?Integer.class:t==long.class?Long.class:t==boolean.class?Boolean.class:t==double.class?Double.class:t==float.class?Float.class:t;if(args[i]==null?t.isPrimitive():!t.isInstance(args[i]))match=false;}
            if(!match)continue;method.setAccessible(true);return method.invoke(target instanceof Class?null:target,args);
        }
        for(Method method:cls.getMethods())for(String name:names)if(method.getName().equals(name)&&method.getParameterTypes().length==args.length)try{return method.invoke(target instanceof Class?null:target,args);}catch(IllegalArgumentException ignored){}
        throw new NoSuchMethodException(names[0]);
    }
    public static String id(Object player)throws Exception{return call(player,new String[]{"getUniqueID","func_110124_au"}).toString();}
    public static void schedule(Object server,Runnable task)throws Exception{
        for(Method method:server.getClass().getMethods())if(method.getParameterTypes().length==1&&method.getParameterTypes()[0]==Runnable.class&&method.getReturnType().getName().contains("ListenableFuture")){method.invoke(server,task);return;}
        throw new NoSuchMethodException("server_schedule");
    }
}
