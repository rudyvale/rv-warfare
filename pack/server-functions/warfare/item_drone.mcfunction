scoreboard players set @s w_probe 0
stats entity @s set AffectedItems @s w_probe
clear @s mcheli:rc-goblin-bomb -1 0
stats entity @s clear AffectedItems
function warfare:space
execute @s[score_w_probe=2,score_w_free_min=1] ~ ~ ~ give @s mcheli:rc-goblin-bomb 1 0
execute @s[score_w_probe=2,score_w_free_min=1] ~ ~ ~ scoreboard players add @s w_given 1
scoreboard players set @s w_probe 0
stats entity @s set AffectedItems @s w_probe
clear @s mcheli:rc-goblin-bomb -1 0
stats entity @s clear AffectedItems
function warfare:space
execute @s[score_w_probe=2,score_w_free_min=1] ~ ~ ~ give @s mcheli:rc-goblin-bomb 1 0
execute @s[score_w_probe=2,score_w_free_min=1] ~ ~ ~ scoreboard players add @s w_given 1
scoreboard players set @s w_probe 0
stats entity @s set AffectedItems @s w_probe
clear @s mcheli:rc-goblin-bomb -1 0
stats entity @s clear AffectedItems
function warfare:space
execute @s[score_w_probe=2,score_w_free_min=1] ~ ~ ~ give @s mcheli:rc-goblin-bomb 1 0
execute @s[score_w_probe=2,score_w_free_min=1] ~ ~ ~ scoreboard players add @s w_given 1
