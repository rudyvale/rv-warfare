execute @s[tag=!w_ui2] ~ ~ ~ function warfare:init_ui
scoreboard players add @s wlang 0
scoreboard players add @s kills 0
title @s times 10 50 20
title @s title {"text":"RV","color":"gold"}
scoreboard players tag @s add w_seen
execute @s[tag=!w_kit] ~ ~ ~ function warfare:kit
execute @s[score_wlang=1,score_wlang_min=1] ~ ~ ~ function warfare:entry_ru
execute @s[score_wlang=2,score_wlang_min=2] ~ ~ ~ function warfare:entry_en
execute @s[score_wlang=0] ~ ~ ~ function warfare:language
