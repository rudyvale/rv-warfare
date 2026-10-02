scoreboard players set @s w_given 0
execute @s[score_w_class=1] ~ ~ ~ function warfare:ammo_rifle
execute @s[score_w_class=2,score_w_class_min=2] ~ ~ ~ function warfare:ammo_sniper
execute @s[score_w_class=3,score_w_class_min=3] ~ ~ ~ function warfare:ammo_lmg
execute @s[score_w_class=3,score_w_class_min=3] ~ ~ ~ function warfare:ammo_minigun
execute @s[score_w_class=4,score_w_class_min=4] ~ ~ ~ function warfare:ammo_shotgun
scoreboard players set @s ammo 0
scoreboard players set @s w_ammo 20
execute @s[score_w_given_min=1] ~ ~ ~ scoreboard players set @s w_ammo 100
function warfare:space
function warfare:supply_result
