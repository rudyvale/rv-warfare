scoreboard players set @s w_probe 0
scoreboard players add @s w_probe 1 {Inventory:[{Slot:103b}]}
execute @s[score_w_probe=0] ~ ~ ~ replaceitem entity @s slot.armor.head minecraft:iron_helmet
execute @s[score_w_probe=0] ~ ~ ~ scoreboard players add @s w_given 1
