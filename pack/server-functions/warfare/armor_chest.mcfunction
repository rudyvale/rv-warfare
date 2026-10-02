scoreboard players set @s w_probe 0
scoreboard players add @s w_probe 1 {Inventory:[{Slot:102b}]}
execute @s[score_w_probe=0] ~ ~ ~ replaceitem entity @s slot.armor.chest minecraft:iron_chestplate
execute @s[score_w_probe=0] ~ ~ ~ scoreboard players add @s w_given 1
