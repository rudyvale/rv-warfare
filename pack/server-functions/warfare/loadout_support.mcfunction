scoreboard players set @s w_given 0
function warfare:item_lmg
function warfare:item_minigun
function warfare:ammo_lmg
function warfare:ammo_minigun
scoreboard players set @s w_class 3
scoreboard players set @s loadout 0
scoreboard players set @s w_supply 20
execute @s[score_w_given_min=1] ~ ~ ~ scoreboard players set @s w_supply 40
function warfare:space
function warfare:supply_result
