scoreboard objectives add wlang dummy
scoreboard objectives add w_supply dummy
scoreboard objectives add w_drone dummy
scoreboard objectives add w_wing dummy
scoreboard objectives add w_ammo dummy
scoreboard objectives add w_class dummy
scoreboard objectives add w_probe dummy
scoreboard objectives add w_used dummy
scoreboard objectives add w_free dummy
scoreboard objectives add w_given dummy
scoreboard objectives add w_admin dummy
scoreboard objectives add kills playerKillCount Kills
scoreboard objectives add ammo trigger
scoreboard objectives add arsenal trigger
scoreboard objectives add blue trigger
scoreboard objectives add drone trigger
scoreboard objectives add guide trigger
scoreboard objectives add kit trigger
scoreboard objectives add lang_en trigger
scoreboard objectives add lang_ru trigger
scoreboard objectives add loadout trigger
scoreboard objectives add lobby trigger
scoreboard objectives add menu trigger
scoreboard objectives add red trigger
scoreboard objectives add sound trigger
scoreboard objectives add spawn trigger
scoreboard objectives add training trigger
scoreboard objectives add ui_admin trigger
scoreboard objectives add ui_ctrl trigger
scoreboard objectives add ui_friend trigger
scoreboard objectives add ui_start trigger
scoreboard objectives add ui_uav trigger
scoreboard objectives add wing trigger
function warfare:book_setup
scoreboard teams add blue Blue
scoreboard teams add red Red
scoreboard teams option blue color blue
scoreboard teams option red color red
scoreboard teams option blue friendlyfire false
scoreboard teams option red friendlyfire false
scoreboard objectives setdisplay sidebar kills
gamerule keepInventory true
gamerule doMobSpawning false
gamerule doFireTick true
gamerule mobGriefing true
gamerule spawnRadius 0
setworldspawn 0 65 -210
gamerule gameLoopFunction warfare:tick
worldborder center 0 0
worldborder set 2560
