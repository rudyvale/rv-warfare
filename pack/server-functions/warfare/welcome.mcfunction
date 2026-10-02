execute @s[tag=!w_ui2] ~ ~ ~ function warfare:init_ui
scoreboard players add @s wlang 0
scoreboard players add @s kills 0
title @s times 10 50 20
title @s title {"text":"RV","color":"gold"}
scoreboard players tag @s add w_seen
execute @s[tag=!w_kit] ~ ~ ~ function warfare:kit
function warfare:help
