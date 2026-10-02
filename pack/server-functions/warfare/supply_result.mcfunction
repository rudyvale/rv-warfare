execute @s[score_w_given_min=1,score_wlang=1,score_wlang_min=1] ~ ~ ~ tellraw @s {"text": "Снаряжение пополнено.", "color": "green"}
execute @s[score_w_given_min=1,score_wlang=2,score_wlang_min=2] ~ ~ ~ tellraw @s {"text": "Supplies added.", "color": "green"}
execute @s[score_w_given=0,score_w_free_min=1,score_wlang=1,score_wlang_min=1] ~ ~ ~ title @s actionbar {"text": "Снаряжение уже есть.", "color": "gray"}
execute @s[score_w_given=0,score_w_free_min=1,score_wlang=2,score_wlang_min=2] ~ ~ ~ title @s actionbar {"text": "Already supplied.", "color": "gray"}
execute @s[score_w_free=0,score_wlang=1,score_wlang_min=1] ~ ~ ~ title @s actionbar {"text": "Инвентарь полон. Освободи один слот.", "color": "yellow"}
execute @s[score_w_free=0,score_wlang=2,score_wlang_min=2] ~ ~ ~ title @s actionbar {"text": "Inventory full. Make one free slot.", "color": "yellow"}
