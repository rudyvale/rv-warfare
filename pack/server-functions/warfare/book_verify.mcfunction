scoreboard players set @s wbHas 0
scoreboard players set @s wbHas 1 {Inventory:[{id:"minecraft:written_book",tag:{rvGuide:1b,rvGuideVersion:4}}]}
execute @s[score_wbHas_min=1] ~ ~ ~ function warfare:book_confirm
