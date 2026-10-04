import argparse
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Warfare-1.12.2"

parser = argparse.ArgumentParser()
parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
parser.add_argument("--techguns", type=Path, default=ROOT / ".local/controls/techguns-1.12.2-2.0.2.0-rv-gameplay.jar")
parser.add_argument("--mcheli", type=Path, default=ROOT / ".local/controls/mcheli-ce-1.5.1-vm-controls1.jar")
args = parser.parse_args()

java = args.game / "runtime/bin/java.exe"
compiler = ROOT / ".local/tools/ecj-4.6.1.jar"
libraries = list((args.game / "libraries").rglob("*.jar"))
asm = next(path for path in libraries if path.name == "asm-debug-all-5.2.jar")
forge = next(path for path in libraries if path.name.startswith("forge-1.12.2-14.23.5.2860"))
classpath = os.pathsep.join(str(path) for path in libraries)

script = r'''var Jar=Java.type('java.util.jar.JarFile'),CR=Java.type('org.objectweb.asm.ClassReader'),CW=Java.type('org.objectweb.asm.ClassWriter'),CN=Java.type('org.objectweb.asm.tree.ClassNode'),MI=Java.type('org.objectweb.asm.tree.MethodInsnNode'),T=Java.type('com.norwood.mcheli.vm.VMPropsTransformer'),Bytes=Java.type('java.io.ByteArrayOutputStream');
var transformer=new T();
function assert(value,message){if(!value)throw new Error(message);}
function read(stream){var out=new Bytes(),data=new Array(4096);for(var i=0;i<data.length;i++)data[i]=0;var buffer=Java.to(data,'byte[]'),count;while((count=stream.read(buffer))>=0)out.write(buffer,0,count);return out.toByteArray();}
function transform(path,entry,name){var jar=new Jar(path),item=jar.getJarEntry(entry);assert(item!==null,'Missing '+entry+' in '+path);var bytes=read(jar.getInputStream(item)),output=transformer.transform(name,name,bytes),node=new CN();new CR(output).accept(node,0);return node;}
function calls(node,method,owner,name){var count=0;for(var n=0;n<node.methods.size();n++){var m=node.methods.get(n);if(String(m.name)!==method)continue;for(var i=m.instructions.getFirst();i!==null;i=i.getNext())if(i instanceof MI&&String(i.owner)===owner&&String(i.name)===name)count++;}return count;}
var tg=transform(arguments[0],'techguns/entities/projectiles/FlamethrowerProjectile.class','techguns.entities.projectiles.FlamethrowerProjectile');
assert(calls(tg,'hitBlock','com/norwood/mcheli/vm/VMProps','flamethrower')===1,'Techguns flame hook missing');
var mch=transform(arguments[1],'com/norwood/mcheli/helper/world/MCH_ExplosionV2.class','com.norwood.mcheli.helper.world.MCH_ExplosionV2');
assert(calls(mch,'doExplosionB','com/norwood/mcheli/vm/VMProps','explosionBlockId')===1,'MCH block cap hook missing');
assert(calls(mch,'doExplosionB','com/norwood/mcheli/vm/VMProps','explosionFire')===1,'MCH fire hook missing');
var writer=new CW(0);writer.visit(52,1,'net/minecraft/block/BlockFire',null,'java/lang/Object',null);var method=writer.visitMethod(1,'func_180650_b','(Lnet/minecraft/world/World;Lnet/minecraft/util/math/BlockPos;Lnet/minecraft/block/state/IBlockState;Ljava/util/Random;)V',null,null);method.visitCode();method.visitInsn(177);method.visitMaxs(0,5);method.visitEnd();writer.visitEnd();
var fire=transformer.transform('net.minecraft.block.BlockFire','net.minecraft.block.BlockFire',writer.toByteArray()),fireNode=new CN();new CR(fire).accept(fireNode,0);
assert(calls(fireNode,'func_180650_b','com/norwood/mcheli/vm/VMProps','fireTick')===1,'Managed fire tick hook missing');
var forgeJar=new Jar(arguments[2]),forgeBytes=read(forgeJar.getInputStream(forgeJar.getJarEntry('net/minecraftforge/event/ForgeEventFactory.class'))),forgeNode=new CN(),placeEvent=false;new CR(forgeBytes).accept(forgeNode,0);for(var fm=0;fm<forgeNode.methods.size();fm++){var forgeMethod=forgeNode.methods.get(fm);if(String(forgeMethod.name)==='onBlockPlace'){placeEvent=true;assert(String(forgeMethod.desc)==='(Lvg;Lnet/minecraftforge/common/util/BlockSnapshot;Lfa;)Lnet/minecraftforge/event/world/BlockEvent$EntityPlaceEvent;','Pinned Forge place-event signature changed: '+forgeMethod.desc);}}assert(placeEvent,'Pinned Forge place-event API missing');
Java.type('qa.VMPropsGuardHarness').run();
print('VMProps guardrail and bytecode checks passed: caps, permissions, TTL, Techguns, MCH, BlockFire');
'''

stubs = {
    "net/minecraft/util/math/BlockPos.java": """package net.minecraft.util.math;
import net.minecraft.util.EnumFacing;
public class BlockPos {
    public final int x,y,z;
    public BlockPos(int x,int y,int z){this.x=x;this.y=y;this.z=z;}
    public BlockPos func_177972_a(EnumFacing side){return new BlockPos(x+side.x,y+side.y,z+side.z);}
    public BlockPos func_177977_b(){return new BlockPos(x,y-1,z);}
    public int func_177958_n(){return x;}
    public int func_177956_o(){return y;}
    public int func_177952_p(){return z;}
    public int hashCode(){return (x*31+y)*31+z;}
    public boolean equals(Object o){if(!(o instanceof BlockPos))return false;BlockPos p=(BlockPos)o;return x==p.x&&y==p.y&&z==p.z;}
}""",
    "net/minecraft/util/EnumFacing.java": """package net.minecraft.util;
public enum EnumFacing { UP(0,1,0),DOWN(0,-1,0),NORTH(0,0,-1),SOUTH(0,0,1),WEST(-1,0,0),EAST(1,0,0); public final int x,y,z; EnumFacing(int x,int y,int z){this.x=x;this.y=y;this.z=z;} }""",
    "net/minecraft/world/IBlockAccess.java": """package net.minecraft.world;
public interface IBlockAccess {}""",
    "net/minecraft/block/Block.java": """package net.minecraft.block;
import net.minecraft.util.EnumFacing;
import net.minecraft.util.math.BlockPos;
import net.minecraft.world.IBlockAccess;
public class Block {
    public final int flammability;
    public Block(int flammability){this.flammability=flammability;}
    public int getFlammability(IBlockAccess world,BlockPos pos,EnumFacing side){return flammability;}
    public net.minecraft.block.state.IBlockState func_176223_P(){return new net.minecraft.block.state.IBlockState(this);}
}""",
    "net/minecraft/block/BlockFire.java": """package net.minecraft.block;
public class BlockFire extends Block { public final Object field_176543_a=new Object(); public BlockFire(){super(0);} }""",
    "net/minecraft/block/state/IBlockState.java": """package net.minecraft.block.state;
import net.minecraft.block.Block;
public class IBlockState {
    private final Block block;
    public IBlockState(Block block){this.block=block;}
    public Block func_177230_c(){return block;}
    public IBlockState func_177226_a(Object property,Integer value){return new IBlockState(block);}
}""",
    "net/minecraft/world/GameRules.java": """package net.minecraft.world;
public class GameRules {
    public boolean grief=true;
    public boolean func_82766_b(String key){return grief;}
}""",
    "net/minecraft/world/World.java": """package net.minecraft.world;
import java.util.*;
import net.minecraft.block.Block;
import net.minecraft.block.state.IBlockState;
import net.minecraft.util.math.BlockPos;
import net.minecraft.init.Blocks;
public class World implements IBlockAccess {
    public boolean field_72995_K;
    public boolean loaded=true;
    public long tick;
    public int scheduled;
    public int cleared;
    public boolean failRestore;
    public boolean failSchedule;
    public final Map<BlockPos,IBlockState> states=new HashMap<BlockPos,IBlockState>();
    public final GameRules rules=new GameRules();
    public boolean func_175668_a(BlockPos p,boolean allowEmpty){return loaded;}
    public boolean func_175623_d(BlockPos p){return func_180495_p(p).func_177230_c()==Blocks.field_150350_a;}
    public IBlockState func_180495_p(BlockPos p){IBlockState state=states.get(p);return state==null?Blocks.field_150350_a.func_176223_P():state;}
    public boolean func_175656_a(BlockPos p,IBlockState state){if(failRestore&&state.func_177230_c()==Blocks.field_150350_a)return false;states.put(p,state);return true;}
    public GameRules func_82736_K(){return rules;}
    public long func_82737_E(){return tick;}
    public void func_175684_a(BlockPos p,Block block,int delay){if(failSchedule)throw new IllegalStateException("schedule unavailable");scheduled=delay;}
    public void func_175698_g(BlockPos p){cleared++;states.put(p,Blocks.field_150350_a.func_176223_P());}
}""",
    "net/minecraft/init/Blocks.java": """package net.minecraft.init;
import net.minecraft.block.Block;
import net.minecraft.block.BlockFire;
public class Blocks { public static final Block field_150350_a=new Block(0); public static final BlockFire field_150480_ab=new BlockFire(); }""",
    "net/minecraftforge/common/util/BlockSnapshot.java": """package net.minecraftforge.common.util;
import net.minecraft.world.World;
import net.minecraft.util.math.BlockPos;
public class BlockSnapshot { public final World world; public final BlockPos pos; private BlockSnapshot(World world,BlockPos pos){this.world=world;this.pos=pos;} public static BlockSnapshot getBlockSnapshot(World world,BlockPos pos){return new BlockSnapshot(world,pos);} }""",
    "net/minecraftforge/event/ForgeEventFactory.java": """package net.minecraftforge.event;
import net.minecraft.entity.player.EntityPlayer;
import net.minecraft.util.EnumFacing;
import net.minecraftforge.common.util.BlockSnapshot;
import net.minecraft.block.Block;
import net.minecraft.block.state.IBlockState;
public class ForgeEventFactory {
    public static boolean canceled;
    public static boolean throwEvent;
    public static boolean replace;
    public static EntityPlayer lastPlayer;
    public static final class PlaceEvent { private final boolean canceled; public PlaceEvent(boolean canceled){this.canceled=canceled;} public boolean isCanceled(){return canceled;} }
    public static PlaceEvent onBlockPlace(EntityPlayer player,BlockSnapshot snapshot,EnumFacing side){
        lastPlayer=player;
        if(throwEvent)throw new IllegalStateException("event bus unavailable");
        if(replace)snapshot.world.func_175656_a(snapshot.pos,new IBlockState(new Block(0)));
        return new PlaceEvent(canceled);
    }
}""",
    "net/minecraft/entity/player/EntityPlayer.java": """package net.minecraft.entity.player;
public class EntityPlayer {}""",
    "net/minecraft/entity/player/PlayerInteractionManager.java": """package net.minecraft.entity.player;
public class PlayerInteractionManager { public Object func_73081_b(){return this;} }""",
    "net/minecraft/entity/player/EntityPlayerMP.java": """package net.minecraft.entity.player;
public class EntityPlayerMP extends EntityPlayer { public final PlayerInteractionManager field_71134_c=new PlayerInteractionManager(); }""",
    "net/minecraftforge/common/ForgeHooks.java": """package net.minecraftforge.common;
import net.minecraft.world.World;
import net.minecraft.util.math.BlockPos;
import net.minecraft.entity.player.EntityPlayerMP;
public class ForgeHooks {
    public static boolean allowed=true;
    public static int onBlockBreakEvent(World world,Object mode,EntityPlayerMP player,BlockPos pos){return allowed?1:-1;}
}""",
    "com/norwood/mcheli/wrapper/W_WorldFunc.java": """package com.norwood.mcheli.wrapper;
import net.minecraft.world.World;
public class W_WorldFunc { public static int getBlockId(World world,int x,int y,int z){return 1;} }""",
    "qa/VMPropsGuardHarness.java": """package qa;
import com.norwood.mcheli.vm.VMProps;
import net.minecraft.block.Block;
import net.minecraft.block.state.IBlockState;
import net.minecraft.entity.player.EntityPlayer;
import net.minecraft.entity.player.EntityPlayerMP;
import net.minecraft.init.Blocks;
import net.minecraft.util.EnumFacing;
import net.minecraft.util.math.BlockPos;
import net.minecraft.world.World;
import net.minecraftforge.common.ForgeHooks;
import net.minecraftforge.event.ForgeEventFactory;
import java.lang.reflect.*;
import java.util.*;
public class VMPropsGuardHarness {
    public static final class Explosion {
        public Object explodedPlayer;
        public Object exploder;
        public Object field_77283_e;
        public double field_77284_b,field_77285_c,field_77282_d;
    }
    private static void check(boolean ok,String label){if(!ok)throw new AssertionError(label);}
    @SuppressWarnings("unchecked")
    private static Map<Object,LinkedHashMap<Object,Object>> registry() throws Exception {
        Field field=VMProps.class.getDeclaredField("fires");
        field.setAccessible(true);
        return (Map<Object,LinkedHashMap<Object,Object>>)field.get(null);
    }
    private static LinkedHashMap<Object,Object> fires(World world) throws Exception {
        Map<Object,LinkedHashMap<Object,Object>> map=registry();
        LinkedHashMap<Object,Object> entries=map.get(world);
        if(entries==null){entries=new LinkedHashMap<Object,Object>();map.put(world,entries);}
        return entries;
    }
    private static Object record(Object state,long expiry) throws Exception {
        Class<?> type=Class.forName("com.norwood.mcheli.vm.VMProps$FireRecord");
        Constructor<?> constructor=type.getDeclaredConstructor(Object.class,long.class);
        constructor.setAccessible(true);
        return constructor.newInstance(state,Long.valueOf(expiry));
    }
    private static Object stateAt(Map<Object,Object> entries,Object pos) throws Exception {
        Object record=entries.get(pos);
        Field field=record.getClass().getDeclaredField("state");
        field.setAccessible(true);
        return field.get(record);
    }
    private static boolean tracked(World world,BlockPos pos) throws Exception {return fires(world).containsKey(pos);}
    private static boolean ignite(World world,int x,Block support,Object source) {
        BlockPos pos=new BlockPos(x,0,0);
        world.states.put(pos.func_177977_b(),new IBlockState(support));
        Explosion explosion=new Explosion();
        explosion.field_77284_b=x;
        explosion.exploder=source;
        explosion.field_77283_e=source;
        return VMProps.explosionFire(world,pos,Blocks.field_150480_ab.func_176223_P(),explosion);
    }
    public static void run() {
        try {
            System.setErr(new java.io.PrintStream(new java.io.ByteArrayOutputStream()));
            World world=new World();
            Explosion explosion=new Explosion();
            for(int i=0;i<4;i++)check(VMProps.explosionBlockId(world,i,0,0,explosion)==1,"block allowance "+i);
            check(VMProps.explosionBlockId(world,4,0,0,explosion)==0,"four-block tick cap");
            world.tick++;
            check(VMProps.explosionBlockId(world,5,0,0,explosion)==1,"tick rollover");
            world.tick++;
            world.loaded=false;
            check(VMProps.explosionBlockId(world,6,0,0,explosion)==0,"unloaded chunk");
            world.loaded=true;
            world.field_72995_K=true;
            check(VMProps.explosionBlockId(world,7,0,0,explosion)==0,"client world");
            world.field_72995_K=false;
            world.tick++;
            explosion.explodedPlayer=new EntityPlayerMP();
            ForgeHooks.allowed=false;
            check(VMProps.explosionBlockId(world,8,0,0,explosion)==0,"Forge break cancellation");
            ForgeHooks.allowed=true;
            check(VMProps.explosionBlockId(world,8,0,0,explosion)==1,"canceled break does not consume budget");
            world.tick++;
            explosion.explodedPlayer=null;
            world.rules.grief=false;
            check(VMProps.explosionBlockId(world,9,0,0,explosion)==0,"mobGriefing disabled");

            ForgeEventFactory.canceled=false;
            ForgeEventFactory.throwEvent=false;
            ForgeEventFactory.replace=false;
            World stone=new World();
            check(!ignite(stone,0,new Block(0),null),"stone support cannot ignite");
            check(stone.func_175623_d(new BlockPos(0,0,0))&&!tracked(stone,new BlockPos(0,0,0)),"stone rejection leaves no fire");

            World flammable=new World();
            Object mob=new Object();
            check(ignite(flammable,0,new Block(12),mob),"flammable face can ignite");
            check(ForgeEventFactory.lastPlayer==null,"nonplayer source passes null to Forge place event");
            check(flammable.scheduled==100&&tracked(flammable,new BlockPos(0,0,0)),"accepted fire is managed and scheduled");

            World playerWorld=new World();
            EntityPlayer actor=new EntityPlayer();
            check(ignite(playerWorld,0,new Block(12),actor)&&ForgeEventFactory.lastPlayer==actor,"player source is preserved for Forge place event");

            World capped=new World();
            check(ignite(capped,0,new Block(12),null),"first fire placement");
            check(ignite(capped,1,new Block(12),null),"second fire placement");
            check(!ignite(capped,2,new Block(12),null),"two-fire tick cap");

            World cancelled=new World();
            ForgeEventFactory.canceled=true;
            check(!ignite(cancelled,0,new Block(12),null),"Forge place event cancellation");
            check(cancelled.func_175623_d(new BlockPos(0,0,0))&&!tracked(cancelled,new BlockPos(0,0,0)),"canceled fire rolls back and forgets marker");

            World eventFailure=new World();
            ForgeEventFactory.canceled=false;
            ForgeEventFactory.throwEvent=true;
            check(!ignite(eventFailure,0,new Block(12),null),"Forge place event failure");
            check(eventFailure.func_175623_d(new BlockPos(0,0,0))&&!tracked(eventFailure,new BlockPos(0,0,0)),"event failure rolls back and forgets marker");

            World schedulingFailure=new World();
            ForgeEventFactory.throwEvent=false;
            schedulingFailure.failSchedule=true;
            check(!ignite(schedulingFailure,0,new Block(12),null),"TTL scheduling failure");
            check(schedulingFailure.func_175623_d(new BlockPos(0,0,0))&&!tracked(schedulingFailure,new BlockPos(0,0,0)),"schedule failure rolls back");

            World replacement=new World();
            schedulingFailure.failSchedule=false;
            ForgeEventFactory.replace=true;
            check(!ignite(replacement,0,new Block(12),null),"Forge replacement detected");
            check(replacement.func_180495_p(new BlockPos(0,0,0)).func_177230_c()!=Blocks.field_150480_ab&&!tracked(replacement,new BlockPos(0,0,0)),"replacement is preserved and marker forgotten");

            World rollbackFailure=new World();
            ForgeEventFactory.replace=false;
            ForgeEventFactory.canceled=true;
            rollbackFailure.failRestore=true;
            check(!ignite(rollbackFailure,0,new Block(12),null),"rollback refusal still denies event");
            BlockPos stuck=new BlockPos(0,0,0);
            check(rollbackFailure.func_180495_p(stuck).func_177230_c()==Blocks.field_150480_ab&&tracked(rollbackFailure,stuck),"failed rollback stays tracked");
            rollbackFailure.failRestore=false;
            rollbackFailure.tick=100;
            check(VMProps.fireTick(rollbackFailure,stuck,rollbackFailure.func_180495_p(stuck))&&rollbackFailure.cleared==1,"failed rollback marker still expires");

            World ttl=new World();
            Object state=new Object();
            BlockPos pos=new BlockPos(1,2,3);
            fires(ttl).put(pos,record(state,100));
            ttl.tick=99;
            check(VMProps.fireTick(ttl,pos,state)&&ttl.scheduled==1&&ttl.cleared==0,"fire waits until TTL");
            ttl.tick=100;
            check(VMProps.fireTick(ttl,pos,state)&&ttl.cleared==1,"fire expires at TTL");
            World changed=new World();
            Object oldState=new Object();
            fires(changed).put(pos,record(oldState,100));
            check(!VMProps.fireTick(changed,pos,new Object())&&changed.cleared==0,"replacement fire is preserved");

            World cleanup=new World();
            LinkedHashMap<Object,Object> entries=fires(cleanup);
            for(int i=0;i<17;i++)entries.put(new BlockPos(i,2,4),record(new Object(),10));
            cleanup.tick=10;
            for(int i=0;i<17;i++) {
                BlockPos cell=new BlockPos(i,2,4);
                VMProps.fireTick(cleanup,cell,stateAt(entries,cell));
            }
            check(cleanup.cleared==16&&cleanup.scheduled==1&&entries.size()==1,"sixteen-cell cleanup cap");
        } catch(Exception e) { throw new RuntimeException(e); }
    }
}""",
}

with tempfile.TemporaryDirectory(prefix="vmprops-qa-") as directory:
    temp = Path(directory)
    classes = temp / "classes"
    classes.mkdir()
    sources = sorted((ROOT / "patches/controls").glob("*.java"))
    stub_paths = []
    for relative, contents in stubs.items():
        source = temp / "stubs" / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(contents, encoding="utf-8")
        stub_paths.append(source)
    subprocess.run([str(java), "-jar", str(compiler), "-1.8", "-encoding", "UTF-8", "-nowarn", "-classpath", classpath, "-d", str(classes), *map(str, sources + stub_paths)], check=True)
    script_path = temp / "verify.js"
    script_path.write_text(script, encoding="utf-8")
    runtime_cp = os.pathsep.join([str(args.game / "runtime/lib/ext/nashorn.jar"), str(asm), str(classes), classpath])
    subprocess.run([str(java), "-cp", runtime_cp, "jdk.nashorn.tools.Shell", str(script_path), "--", str(args.techguns), str(args.mcheli), str(forge)], check=True)
