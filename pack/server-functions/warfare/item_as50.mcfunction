scoreboard players set @s w_probe 0
scoreboard players add @s w_probe 1 {Inventory:[{id:"techguns:as50"}]}
function warfare:space
execute @s[score_w_probe=0,score_w_free_min=1] ~ ~ ~ give @s techguns:as50 1 0
execute @s[score_w_probe=0,score_w_free_min=1] ~ ~ ~ scoreboard players add @s w_given 1
