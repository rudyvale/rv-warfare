scoreboard players set @s drone 0
execute @s[score_wlang=1,score_wlang_min=1] ~ ~ ~ title @s actionbar {"text": "Дрон уже выдан.", "color": "gray"}
execute @s[score_wlang=2,score_wlang_min=2] ~ ~ ~ title @s actionbar {"text": "UAV already supplied.", "color": "gray"}
