execute @a[tag=!w_ui2] ~ ~ ~ function warfare:init_ui
execute @a[tag=!w_seen] ~ ~ ~ function warfare:welcome
scoreboard players add @a w_wing 0
scoreboard players remove @a[score_w_supply_min=1] w_supply 1
scoreboard players remove @a[score_w_drone_min=1] w_drone 1
scoreboard players remove @a[score_w_wing_min=1] w_wing 1
scoreboard players remove @a[score_w_ammo_min=1] w_ammo 1
scoreboard players set @a w_admin 0
scoreboard players set @a[tag=v_owner] w_admin 1
execute @a[score_kit_min=1,score_kit=1,score_w_supply_min=1] ~ ~ ~ function warfare:wait_supply
execute @a[score_loadout_min=1,score_loadout=4,score_w_supply_min=1] ~ ~ ~ function warfare:wait_supply
execute @a[score_kit_min=1,score_kit=1,score_w_supply=0] ~ ~ ~ function warfare:kit
execute @a[score_loadout_min=1,score_loadout=1,score_w_supply=0] ~ ~ ~ function warfare:loadout_assault
execute @a[score_loadout_min=2,score_loadout=2,score_w_supply=0] ~ ~ ~ function warfare:loadout_sniper
execute @a[score_loadout_min=3,score_loadout=3,score_w_supply=0] ~ ~ ~ function warfare:loadout_support
execute @a[score_loadout_min=4,score_loadout=4,score_w_supply=0] ~ ~ ~ function warfare:loadout_breacher
execute @a[score_drone_min=1,score_drone=1,score_w_drone_min=1] ~ ~ ~ function warfare:wait_drone
execute @a[score_drone_min=1,score_drone=1,score_w_drone=0] ~ ~ ~ function warfare:drone
execute @a[score_ammo_min=1,score_ammo=1,score_w_ammo_min=1] ~ ~ ~ function warfare:wait_ammo
execute @a[score_ammo_min=1,score_ammo=1,score_w_ammo=0] ~ ~ ~ function warfare:ammo
execute @a[score_wing_min=1,score_wing=1,score_w_wing_min=1] ~ ~ ~ function warfare:wait_wing
execute @a[score_wing_min=1,score_wing=1,score_w_wing=0] ~ ~ ~ function warfare:wing
execute @a[score_menu_min=1,score_menu=1] ~ ~ ~ function warfare:help
execute @a[score_blue_min=1,score_blue=1] ~ ~ ~ function warfare:blue
execute @a[score_red_min=1,score_red=1] ~ ~ ~ function warfare:red
execute @a[score_lobby_min=1,score_lobby=1] ~ ~ ~ function warfare:lobby
execute @a[score_spawn_min=1,score_spawn=1] ~ ~ ~ function warfare:spawn
execute @a[score_sound_min=1,score_sound=1] ~ ~ ~ function warfare:sound
execute @a[score_lang_ru_min=1,score_lang_ru=1] ~ ~ ~ function warfare:lang_ru
execute @a[score_lang_en_min=1,score_lang_en=1] ~ ~ ~ function warfare:lang_en
execute @a[score_guide_min=1,score_guide=1] ~ ~ ~ function warfare:guide
execute @a[score_ui_start_min=1,score_ui_start=1] ~ ~ ~ function warfare:ui_start
execute @a[score_ui_ctrl_min=1,score_ui_ctrl=1] ~ ~ ~ function warfare:ui_ctrl
execute @a[score_ui_uav_min=1,score_ui_uav=1] ~ ~ ~ function warfare:ui_uav
execute @a[score_ui_friend_min=1,score_ui_friend=1] ~ ~ ~ function warfare:ui_friend
execute @a[score_arsenal_min=1,score_arsenal=1] ~ ~ ~ function warfare:arsenal
execute @a[score_training_min=1,score_training=1] ~ ~ ~ function warfare:training
execute @a[tag=v_owner,score_ui_admin_min=1,score_ui_admin=1] ~ ~ ~ function warfare:ui_admin
scoreboard players set @a[tag=!v_owner] ui_admin 0
scoreboard players enable @a[tag=v_owner] ui_admin
scoreboard players set @a[score_menu=-1] menu 0
scoreboard players set @a[score_menu_min=2] menu 0
scoreboard players enable @a menu
scoreboard players set @a[score_blue=-1] blue 0
scoreboard players set @a[score_blue_min=2] blue 0
scoreboard players enable @a blue
scoreboard players set @a[score_red=-1] red 0
scoreboard players set @a[score_red_min=2] red 0
scoreboard players enable @a red
scoreboard players set @a[score_lobby=-1] lobby 0
scoreboard players set @a[score_lobby_min=2] lobby 0
scoreboard players enable @a lobby
scoreboard players set @a[score_spawn=-1] spawn 0
scoreboard players set @a[score_spawn_min=2] spawn 0
scoreboard players enable @a spawn
scoreboard players set @a[score_sound=-1] sound 0
scoreboard players set @a[score_sound_min=2] sound 0
scoreboard players enable @a sound
scoreboard players set @a[score_lang_ru=-1] lang_ru 0
scoreboard players set @a[score_lang_ru_min=2] lang_ru 0
scoreboard players enable @a lang_ru
scoreboard players set @a[score_lang_en=-1] lang_en 0
scoreboard players set @a[score_lang_en_min=2] lang_en 0
scoreboard players enable @a lang_en
scoreboard players set @a[score_guide=-1] guide 0
scoreboard players set @a[score_guide_min=2] guide 0
scoreboard players enable @a guide
scoreboard players set @a[score_ui_start=-1] ui_start 0
scoreboard players set @a[score_ui_start_min=2] ui_start 0
scoreboard players enable @a ui_start
scoreboard players set @a[score_ui_ctrl=-1] ui_ctrl 0
scoreboard players set @a[score_ui_ctrl_min=2] ui_ctrl 0
scoreboard players enable @a ui_ctrl
scoreboard players set @a[score_ui_uav=-1] ui_uav 0
scoreboard players set @a[score_ui_uav_min=2] ui_uav 0
scoreboard players enable @a ui_uav
scoreboard players set @a[score_ui_friend=-1] ui_friend 0
scoreboard players set @a[score_ui_friend_min=2] ui_friend 0
scoreboard players enable @a ui_friend
scoreboard players set @a[score_arsenal=-1] arsenal 0
scoreboard players set @a[score_arsenal_min=2] arsenal 0
scoreboard players enable @a arsenal
scoreboard players set @a[score_training=-1] training 0
scoreboard players set @a[score_training_min=2] training 0
scoreboard players enable @a training
scoreboard players set @a[score_kit=-1] kit 0
scoreboard players set @a[score_kit_min=2] kit 0
scoreboard players enable @a kit
scoreboard players set @a[score_drone=-1] drone 0
scoreboard players set @a[score_drone_min=2] drone 0
scoreboard players enable @a drone
scoreboard players set @a[score_wing=-1] wing 0
scoreboard players set @a[score_wing_min=2] wing 0
scoreboard players enable @a wing
scoreboard players set @a[score_ammo=-1] ammo 0
scoreboard players set @a[score_ammo_min=2] ammo 0
scoreboard players enable @a ammo
scoreboard players set @a[score_loadout=-1] loadout 0
scoreboard players set @a[score_loadout_min=5] loadout 0
scoreboard players enable @a loadout
scoreboard players set @a[score_ui_admin=-1] ui_admin 0
scoreboard players set @a[score_ui_admin_min=2] ui_admin 0
function warfare:book_tick
