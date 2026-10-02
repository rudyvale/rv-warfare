scoreboard players set @s w_probe 0
scoreboard players add @s w_probe 1 {Inventory:[{id:"mcheli:rv_geran"}]}
function warfare:space
execute @s[score_w_probe=0,score_w_free_min=1] ~ ~ ~ give @s mcheli:rv_geran 1 0
execute @s[score_w_probe=0,score_w_free_min=1] ~ ~ ~ scoreboard players add @s w_given 1
