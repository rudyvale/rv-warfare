scoreboard players set @s w_given 0
function warfare:item_m4
function warfare:ammo_rifle
function warfare:ammo_food
function warfare:armor_head
function warfare:armor_chest
function warfare:armor_legs
function warfare:armor_feet
function warfare:item_tablet
function warfare:item_drone
function warfare:item_geran
function warfare:item_fp1
function warfare:item_bandage
function warfare:item_plaster
scoreboard players set @s kit 0
scoreboard players tag @s add w_kit
scoreboard players set @s w_supply 20
execute @s[score_w_given_min=1] ~ ~ ~ scoreboard players set @s w_supply 100
function warfare:space
function warfare:supply_result
