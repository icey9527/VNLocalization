LABEL 0
FACE 53
MESSAGE_NAME "アール"
MESSAGE "何だ、荷物がいっぱいなのか。\nそれじゃ、プレゼントは買えないな\nなにか売るかい？"
SELECT 2, 1, "売る", 2, "やめる"
LABEL 1
END 1
LABEL 2
FACE 53
MESSAGE_NAME "アール"
MESSAGE "なんだやめるのか。親父の\n笑顔だけでも嬉しいもんだぜ。\nはやく帰ってやんな。"
KEY_WAIT
END 0
LABEL 3
FACE 53
MESSAGE_NAME "アール"
MESSAGE "売らないと、\nプレゼントは買えないぜ。\nどうするよ？"
SELECT 2, 1, "売る", 2, "やめる"
LABEL 4
FACE 53
MESSAGE_NAME "アール"
MESSAGE "プレゼントは娘さんが\n喜びそうなものを選んでやれよ。"
KEY_WAIT
END 0
LABEL 5
FACE 53
MESSAGE_NAME "アール"
MESSAGE "娘に誕生日プレゼントだって？\nそういうことならまかしときな！"
KEY_WAIT
END 0
LABEL 6
FACE 53
MESSAGE_NAME "アール"
MESSAGE "なんだ、やめるのか？"
SELECT 2, 7, "買っていく", 8, "やめておく"
LABEL 7
END 0
LABEL 8
FACE 53
MESSAGE_NAME "アール"
MESSAGE "いや、親父の笑顔だけで\nうれしいもんだぜ……"
KEY_WAIT
END 1
LABEL 9
MESSAGE_NAME "アール"
MESSAGE "さあ、早く家に帰ってやんな。"
KEY_WAIT
END 0