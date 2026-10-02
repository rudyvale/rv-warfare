scoreboard players set @s w_probe 0
scoreboard players add @s w_probe 1 {Inventory:[{Slot:100b}]}
execute @s[score_w_probe=0] ~ ~ ~ replaceitem entity @s slot.armor.feet minecraft:iron_boots
execute @s[score_w_probe=0] ~ ~ ~ scoreboard players add @s w_given 1
