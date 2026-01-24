LABEL 0
FLAG 600, 1
FACE 55
MESSAGE_NAME "ナルサス"
MESSAGE "なんじゃ、初めての来院か？\nここは病院じゃよ。"
KEY_WAIT
MESSAGE "どんな病気もすぐに治してやろう。\nまっ、普段から気をつけておれば\nここの世話にはなるまいがな。"
KEY_WAIT
MESSAGE "しかし、油断は禁物じゃ。\nなにかあればすぐに来るようにな。"
KEY_WAIT
END 0
LABEL 1
FLAG 601, 1
FACE 55
MESSAGE_NAME "ナルサス"
MESSAGE "また来たのか？\nどれ、今日の症状は……"
KEY_WAIT
END 0
LABEL 2
FLAG 602, 1
MESSAGE "なんじゃ、どこも悪くないぞ。\n病気になってからまた来なさい。"
KEY_WAIT
END 0
LABEL 3
FLAG 603, 1
MESSAGE_NAME "ナルサス"
MESSAGE "ふむ、治療費は[汎用数値]Ｇだ。\nよろしいかな？"
LINE_FEED
SELECT 2, 4, "はい", 5, "いいえ"
LABEL 4
END 0
LABEL 5
END 1
LABEL 6
FLAG 604, 1
MESSAGE_NAME "ナルサス"
MESSAGE "これですぐにでも\n良くなるじゃろう。"
KEY_WAIT
END 0
LABEL 7
MESSAGE_NAME "ナルサス"
MESSAGE "金が足りないようじゃな。\nすまんが、お引取り願おう。"
KEY_WAIT
END 0
LABEL 8
FLAG 605, 1
MESSAGE_NAME "ナルサス"
MESSAGE "なんじゃ、\n治療を受けていかんのか？\nあまり無理せんようにな。"
KEY_WAIT
END 0