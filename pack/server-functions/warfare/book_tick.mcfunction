scoreboard players enable @a wbook
scoreboard players add @a wbOnce 0
scoreboard players add @a wbPending 0
scoreboard players add @a wbEdition 0
execute @a[score_wbOnce=0,score_wbPending=0] ~ ~ ~ function warfare:book_welcome
execute @a[score_wbOnce_min=1,score_wbEdition=1,score_wbPending=0] ~ ~ ~ function warfare:book_queue
execute @a[score_wbook_min=1] ~ ~ ~ function warfare:book_request
scoreboard players add @a[score_wbPending_min=1] wbWait 1
execute @a[score_wbPending_min=1,score_wbWait_min=20] ~ ~ ~ function warfare:book_check
