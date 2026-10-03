package rv.experience.server;

import java.lang.reflect.Field;
import java.lang.reflect.Method;

public final class Reflect {
    private static final Api[] APIS={
        new Api("net.minecraftforge.fml.common.event.FMLServerAboutToStartEvent","getServer"),
        new Api("net.minecraftforge.fml.common.event.FMLServerStartingEvent","getServer"),
        new Api("net.minecraft.command.ICommandSender","getServer|func_184102_h"),
        new Api("net.minecraft.entity.Entity","getUniqueID|func_110124_au"),
        new Api("net.minecraft.util.IThreadListener","addScheduledTask|func_152344_a","java.lang.Runnable"),
        new Api("net.minecraftforge.registries.IForgeRegistry","getValue","net.minecraft.util.ResourceLocation"),
        new Api("net.minecraft.item.ItemStack","isEmpty|func_190926_b"),
        new Api("net.minecraft.item.ItemStack","getCount|func_190916_E"),
        new Api("net.minecraft.item.ItemStack","setCount|func_190920_e","int"),
        new Api("net.minecraft.item.ItemStack","getMetadata|func_77960_j"),
        new Api("net.minecraft.item.ItemStack","getItem|func_77973_b"),
        new Api("net.minecraft.item.ItemStack","copy|func_77946_l"),
        new Api("net.minecraft.item.ItemStack","getMaxStackSize|func_77976_d"),
        new Api("net.minecraft.item.ItemStack","areItemStackTagsEqual|func_77970_a","net.minecraft.item.ItemStack","net.minecraft.item.ItemStack"),
        new Api("net.minecraftforge.registries.IForgeRegistryEntry","getRegistryName"),
        new Api("net.minecraft.inventory.IInventory","markDirty|func_70296_d"),
        new Api("net.minecraft.inventory.Container","detectAndSendChanges|func_75142_b"),
        new Api("net.minecraft.world.World","isBlockLoaded|func_175667_e","net.minecraft.util.math.BlockPos"),
        new Api("net.minecraft.world.World","getChunkProvider|func_72863_F"),
        new Api("net.minecraft.world.gen.ChunkProviderServer","isChunkGeneratedAt|func_191062_e","int","int"),
        new Api("net.minecraft.world.World","getChunkFromChunkCoords|func_72964_e","int","int"),
        new Api("net.minecraft.world.IBlockAccess","getBlockState|func_180495_p","net.minecraft.util.math.BlockPos"),
        new Api("net.minecraft.block.state.IBlockProperties","getMaterial|func_185904_a"),
        new Api("net.minecraft.block.material.Material","blocksMovement|func_76230_c"),
        new Api("net.minecraft.block.material.Material","isLiquid|func_76224_d"),
        new Api("net.minecraft.entity.EntityLivingBase","setPositionAndUpdate|func_70634_a","double","double","double"),
        new Api("net.minecraft.server.MinecraftServer","getWorld|func_71218_a","int"),
        new Api("net.minecraft.world.World","getSaveHandler|func_72860_G"),
        new Api("net.minecraft.world.storage.ISaveHandler","getWorldDirectory|func_75765_b"),
        new Api("net.minecraft.server.MinecraftServer","getCommandManager|func_71187_D"),
        new Api("net.minecraft.command.CommandSenderWrapper","create|func_193998_a","net.minecraft.command.ICommandSender"),
        new Api("net.minecraft.command.CommandSenderWrapper","withPermissionLevel|func_193999_a","int"),
        new Api("net.minecraft.command.ICommandManager","executeCommand|func_71556_a","net.minecraft.command.ICommandSender","java.lang.String"),
        new Api("net.minecraft.entity.player.EntityPlayer","getWorldScoreboard|func_96123_co"),
        new Api("net.minecraft.scoreboard.Scoreboard","getObjective|func_96518_b","java.lang.String"),
        new Api("net.minecraft.scoreboard.Scoreboard","addScoreObjective|func_96535_a","java.lang.String","net.minecraft.scoreboard.IScoreCriteria"),
        new Api("net.minecraft.scoreboard.Scoreboard","getOrCreateScore|func_96529_a","java.lang.String","net.minecraft.scoreboard.ScoreObjective"),
        new Api("net.minecraft.command.ICommandSender","getName|func_70005_c_"),
        new Api("net.minecraft.scoreboard.Score","getScorePoints|func_96652_c"),
        new Api("net.minecraft.scoreboard.Score","setScorePoints|func_96647_c","int"),
        new Api("net.minecraft.command.ICommandSender","getCommandSenderEntity|func_174793_f"),
        new Api("net.minecraft.command.CommandHandler","registerCommand|func_71560_a","net.minecraft.command.ICommand"),
        new Api("net.minecraftforge.event.entity.living.LivingEvent","getEntityLiving"),
        new Api("net.minecraftforge.event.entity.living.LivingAttackEvent","getSource"),
        new Api("net.minecraftforge.event.entity.living.LivingDeathEvent","getSource"),
        new Api("net.minecraft.util.DamageSource","getTrueSource|func_76346_g")
    };
    private static final class Api {
        final String owner,names;final String[] parameters;Class<?> type;Method method;
        Api(String owner,String names,String...parameters){this.owner=owner;this.names="|"+names+"|";this.parameters=parameters;}
        Method resolve(String name)throws Exception{
            if(method!=null)return method;
            Class<?>[] args=new Class<?>[parameters.length];for(int i=0;i<args.length;i++)args[i]=parameters[i].equals("int")?int.class:parameters[i].equals("double")?double.class:Class.forName(parameters[i]);
            for(String alias:names.split("\\|"))if(!alias.isEmpty())try{method=type.getMethod(alias,args);return method;}catch(NoSuchMethodException ignored){}
            throw new NoSuchMethodException(owner+"."+name);
        }
    }
    public static Object field(Object target,String...names)throws Exception{
        Class<?> cls=target instanceof Class?(Class<?>)target:target.getClass();
        for(Class<?> type=cls;type!=null;type=type.getSuperclass())for(String name:names)try{Field f=type.getDeclaredField(name);f.setAccessible(true);return f.get(target instanceof Class?null:target);}catch(NoSuchFieldException ignored){}
        throw new NoSuchFieldException(names[0]);
    }
    public static Object call(Object target,String[] names,Object...args)throws Exception{
        if(target==null)throw new IllegalArgumentException("null_target");
        for(String name:names)for(Api api:APIS){
            if(api.parameters.length!=args.length||!api.names.contains("|"+name+"|"))continue;
            if(api.type==null)api.type=Class.forName(api.owner);
            if(target instanceof Class?!api.type.isAssignableFrom((Class<?>)target):!api.type.isInstance(target))continue;
            Method method=api.resolve(name);return method.invoke(target instanceof Class?null:target,args);
        }
        throw new NoSuchMethodException(names[0]);
    }
    public static String id(Object player)throws Exception{return call(player,new String[]{"getUniqueID","func_110124_au"}).toString();}
    public static void schedule(Object server,Runnable task)throws Exception{
        call(server,new String[]{"addScheduledTask","func_152344_a"},task);
    }
}
