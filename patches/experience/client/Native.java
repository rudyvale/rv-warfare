package rv.experience.client;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.concurrent.ConcurrentHashMap;
import java.util.Map;

public final class Native {
    private static final Map<String,Method> methods=new ConcurrentHashMap<String,Method>();
    private static final Map<String,Field> fields=new ConcurrentHashMap<String,Field>();
    private Native() { }
    public static Object call(Object target,String name,Object...args) {
        try {
            Class<?> type=target instanceof Class?(Class<?>)target:target.getClass();
            String key=type.getName()+"#"+name;
            for(Object arg:args)key+="/"+(arg==null?"null":arg.getClass().getName());
            Method method=methods.get(key);
            if(method==null){
                for(Method candidate:type.getMethods()){
                    if(!candidate.getName().equals(name)||candidate.getParameterTypes().length!=args.length)continue;
                    boolean match=true;Class<?>[] parameters=candidate.getParameterTypes();
                    for(int i=0;i<args.length;i++)if(args[i]!=null&&!box(parameters[i]).isInstance(args[i]))match=false;
                    if(match){method=candidate;break;}
                }
                if(method==null)throw new NoSuchMethodException(type.getName()+"."+name);
                methods.put(key,method);
            }
            return method.invoke(target instanceof Class?null:target,args);
        }catch(Exception error){throw new IllegalStateException(name,error);}
    }
    private static Class<?> box(Class<?> type){if(type==int.class)return Integer.class;if(type==boolean.class)return Boolean.class;if(type==float.class)return Float.class;if(type==double.class)return Double.class;if(type==long.class)return Long.class;return type;}
    public static Class<?> type(String name){try{return Class.forName(name);}catch(ClassNotFoundException e){throw new IllegalStateException(name,e);}}
    public static Object get(Object target,String name){try{Class<?> type=target instanceof Class?(Class<?>)target:target.getClass();String key=type.getName()+"#"+name;Field field=fields.get(key);if(field==null){field=type.getField(name);fields.put(key,field);}return field.get(target instanceof Class?null:target);}catch(Exception e){throw new IllegalStateException(name,e);}}
    public static void set(Object target,String name,Object value){try{target.getClass().getField(name).set(target,value);}catch(Exception e){throw new IllegalStateException(name,e);}}
    public static Object create(String name,Class<?>[] types,Object...args){try{Constructor<?> c=type(name).getConstructor(types);return c.newInstance(args);}catch(Exception e){throw new IllegalStateException(name,e);}}
    public static Object minecraft(){return call(type("net.minecraft.client.Minecraft"),"func_71410_x");}
    public static void display(Object screen){call(minecraft(),"func_147108_a",screen);}
    public static void schedule(Runnable task){call(minecraft(),"func_152344_a",task);}
    public static void rect(int x,int y,int x2,int y2,int color){call(type("net.minecraft.client.gui.Gui"),"func_73734_a",x,y,x2,y2,color);}
    public static void text(String text,int x,int y,int color,int width){Object font=get(minecraft(),"field_71466_p");String clipped=(String)call(font,"func_78269_a",text,Math.max(0,width));call(font,"func_78276_b",clipped,x,y,color);}
    public static int textWidth(String text){return ((Number)call(get(minecraft(),"field_71466_p"),"func_78256_a",text)).intValue();}
}
