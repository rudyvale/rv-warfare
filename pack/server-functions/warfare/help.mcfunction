execute @s[score_wlang=0] ~ ~ ~ function warfare:language
execute @s[score_wlang=1,score_wlang_min=1] ~ ~ ~ function warfare:help_ru
execute @s[score_wlang=2,score_wlang_min=2] ~ ~ ~ function warfare:help_en
scoreboard players set @s menu 0
scoreboard players enable @s menu
