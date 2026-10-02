scoreboard players set @s w_probe 0
stats entity @s set AffectedItems @s w_probe
clear @s techguns:itemshared 2 0
stats entity @s clear AffectedItems
function warfare:space
execute @s[score_w_probe=31,score_w_free_min=1] ~ ~ ~ give @s techguns:itemshared 32 2
execute @s[score_w_probe=31,score_w_free_min=1] ~ ~ ~ scoreboard players add @s w_given 1
