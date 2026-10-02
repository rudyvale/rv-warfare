scoreboard players set @s w_probe 0
stats entity @s set AffectedItems @s w_probe
clear @s minecraft:cooked_beef 0 0
stats entity @s clear AffectedItems
function warfare:space
execute @s[score_w_probe=15,score_w_free_min=1] ~ ~ ~ give @s minecraft:cooked_beef 16 0
execute @s[score_w_probe=15,score_w_free_min=1] ~ ~ ~ scoreboard players add @s w_given 1
