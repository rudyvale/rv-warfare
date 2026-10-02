scoreboard players set @s w_probe 0
stats entity @s set AffectedItems @s w_probe
clear @s firstaid:bandage -1 0
stats entity @s clear AffectedItems
function warfare:space
execute @s[score_w_probe=0,score_w_probe_min=0,score_w_free_min=1] ~ ~ ~ give @s firstaid:bandage 4 0
execute @s[score_w_probe=0,score_w_probe_min=0,score_w_free_min=1] ~ ~ ~ scoreboard players add @s w_given 1
execute @s[score_w_probe=1,score_w_probe_min=1,score_w_free_min=1] ~ ~ ~ give @s firstaid:bandage 3 0
execute @s[score_w_probe=1,score_w_probe_min=1,score_w_free_min=1] ~ ~ ~ scoreboard players add @s w_given 1
execute @s[score_w_probe=2,score_w_probe_min=2,score_w_free_min=1] ~ ~ ~ give @s firstaid:bandage 2 0
execute @s[score_w_probe=2,score_w_probe_min=2,score_w_free_min=1] ~ ~ ~ scoreboard players add @s w_given 1
execute @s[score_w_probe=3,score_w_probe_min=3,score_w_free_min=1] ~ ~ ~ give @s firstaid:bandage 1 0
execute @s[score_w_probe=3,score_w_probe_min=3,score_w_free_min=1] ~ ~ ~ scoreboard players add @s w_given 1
