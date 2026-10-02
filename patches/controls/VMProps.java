package com.norwood.mcheli.vm;

import com.google.common.base.Predicate;
import java.util.*;

public final class VMProps {
    private static final Map<Object,LinkedHashMap<Object,Damage>> worlds=new WeakHashMap<Object,LinkedHashMap<Object,Damage>>();
    private static final Map<Predicate<Object>,Predicate<Object>> predicates=new IdentityHashMap<Predicate<Object>,Predicate<Object>>();
    private static final class Damage {Object state;double amount;long time;}
    public static synchronized Predicate<Object> targets(final Predicate<Object> original){
        Predicate<Object> result=predicates.get(original);
        if(result==null){result=new Predicate<Object>(){public boolean apply(Object entity){
            if(original.apply(entity))return true;
            try{return entity!=null&&entity.getClass().getName().equals("net.minecraft.entity.item.EntityItem")&&!(Boolean)VMReflect.get(entity,"field_70128_L");}
            catch(Exception e){return false;}
        }};predicates.put(original,result);}return result;
    }
    public static void block(Object bullet,Object hit){
        try{
            if(VMReflect.remote(bullet))return;
            Object world=VMReflect.get(bullet,"field_70170_p"),pos=VMReflect.call(hit,"func_178782_a"),state=VMReflect.call(world,"func_180495_p",pos);
            double hardness=VMReflect.num(VMReflect.call(state,"func_185887_b",world,pos)),damage=VMReflect.num(VMReflect.call(bullet,"getDamage"));
            if(hardness<0||hardness>20||!Double.isFinite(damage)||damage<=0)return;
            Object shooter=VMReflect.get(bullet,"shooter");
            if(shooter==null||!Class.forName("net.minecraft.entity.player.EntityPlayerMP").isInstance(shooter)){
                if(!(Boolean)VMReflect.call(VMReflect.call(world,"func_82736_K"),"func_82766_b","mobGriefing"))return;
            }
            Object material=VMReflect.call(state,"func_185904_a");Class<?> materials=Class.forName("net.minecraft.block.material.Material");
            double scale=material==VMReflect.get(materials,"field_151576_e")?8:material==VMReflect.get(materials,"field_151573_f")?12:1;
            double threshold=Math.max(4,hardness*16*scale);long now=System.nanoTime();
            LinkedHashMap<Object,Damage> entries=worlds.get(world);
            if(entries==null){entries=new LinkedHashMap<Object,Damage>();worlds.put(world,entries);}
            Damage record=entries.get(pos);
            if(record==null||record.state!=state||now-record.time>30000000000L){record=new Damage();record.state=state;entries.put(pos,record);}
            record.amount+=Math.min(damage,1000);record.time=now;
            int id=0x60000000^(pos.hashCode()&0x1fffffff);
            if(record.amount>=threshold){
                if(shooter!=null&&Class.forName("net.minecraft.entity.player.EntityPlayerMP").isInstance(shooter)){
                    Object mode=VMReflect.call(VMReflect.get(shooter,"field_71134_c"),"func_73081_b");
                    if(((Number)VMReflect.call(Class.forName("net.minecraftforge.common.ForgeHooks"),"onBlockBreakEvent",world,mode,shooter,pos)).intValue()<0){entries.remove(pos);VMReflect.call(world,"func_175715_c",id,pos,-1);return;}
                }
                VMReflect.call(world,"func_175655_b",pos,true);entries.remove(pos);VMReflect.call(world,"func_175715_c",id,pos,-1);
            }else VMReflect.call(world,"func_175715_c",id,pos,Math.min(9,(int)(record.amount/threshold*10)));
            if(entries.size()>4096){Iterator<Object> keys=entries.keySet().iterator();Object first=keys.next();keys.remove();VMReflect.call(world,"func_175715_c",0x60000000^(first.hashCode()&0x1fffffff),first,-1);}
        }catch(Exception|LinkageError e){VMReflect.error("projectile block damage",e);}
    }
}
