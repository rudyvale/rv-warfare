scoreboard players set @s w_given 0
function warfare:item_tablet
function warfare:item_drone
scoreboard players set @s drone 0
scoreboard players set @s w_drone 20
execute @s[score_w_given_min=1] ~ ~ ~ scoreboard players set @s w_drone 100
function warfare:space
function warfare:supply_result
execute @s[score_w_given_min=1,score_wlang=1,score_wlang_min=1] ~ ~ ~ function warfare:drone_tip_ru
execute @s[score_w_given_min=1,score_wlang=2,score_wlang_min=2] ~ ~ ~ function warfare:drone_tip_en
