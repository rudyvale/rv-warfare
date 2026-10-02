scoreboard players set @s w_given 0
function warfare:item_as50
function warfare:ammo_sniper
scoreboard players set @s w_class 2
scoreboard players set @s loadout 0
scoreboard players set @s w_supply 20
execute @s[score_w_given_min=1] ~ ~ ~ scoreboard players set @s w_supply 40
function warfare:space
function warfare:supply_result
