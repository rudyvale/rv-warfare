scoreboard players set @s wbWait 0
function warfare:book_verify
execute @s[score_wbPending_min=1,score_wlang_min=1,score_wlang=2] ~ ~ ~ function warfare:book_space
