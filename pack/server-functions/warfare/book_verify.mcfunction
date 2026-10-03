scoreboard players set @s wbHas 0
scoreboard players set @s[score_wlang_min=1,score_wlang=1] wbHas 1 {Inventory:[{id:"minecraft:written_book",tag:{rvGuide:1b,rvGuideLang:1b,rvGuideVersion:4}}]}
scoreboard players set @s[score_wlang_min=2,score_wlang=2] wbHas 1 {Inventory:[{id:"minecraft:written_book",tag:{rvGuide:1b,rvGuideLang:2b,rvGuideVersion:4}}]}
execute @s[score_wbHas_min=1] ~ ~ ~ function warfare:book_confirm
