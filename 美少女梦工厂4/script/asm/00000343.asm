LABEL 0
FLAG 678, 1
LABEL 1
FLAG 679, 1
BGM_STOP 30
BGM_PLAY 14
BG 0
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "お嬢様、お友だちが\n遊びにいらっしゃいましたよー"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 550
MESSAGE "え、本当？\nすぐ行くわ㍍"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
SE_PLAY 7
SE_WAIT
SE_PLAY 1
SE_WAIT
SE_PLAY 3
BG 160
CHAR 1, 12
FACE 11
MESSAGE_NAME "リーゼ"
MESSAGE "やあ、来たな、[娘の名前]。"
KEY_WAIT
CHAR 2, 15
FACE 14
MESSAGE_NAME "クリスチーナ"
MESSAGE "[娘の名前]さん、\nごきげんよう。"
KEY_WAIT
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 551
MESSAGE "あ、リーゼに、\nクリスチーナも……\n２人で一緒に来てくれたの？"
KEY_WAIT
CHAR 1, 13
FACE 12
MESSAGE_NAME "リーゼ"
MESSAGE "いやなに。\n今日は予定が空いたから\n釣りにでも誘おうと思ったんだ。"
KEY_WAIT
CHAR 1, 12
FACE 11
MESSAGE "そうしたら、ちょうどここで\nクリスチーナと鉢合わせした。"
KEY_WAIT
CHAR 2, 16
FACE 15
MESSAGE_NAME "クリスチーナ"
MESSAGE "そうなんですのよ。\n今日はお天気もよいですし、\n屋敷でご一緒にお茶でも……"
KEY_WAIT
CHAR 2, 15
FACE 14
MESSAGE "と思ったのですが、\n運悪くリーゼさんと\n出くわしてしまいましたの。"
KEY_WAIT
CHAR 1, 14
FACE 13
MESSAGE_NAME "リーゼ"
MESSAGE "そうそう、運悪く……\nっておい、それはどういう意味だ？"
KEY_WAIT
CHAR 2, 16
FACE 15
MESSAGE_NAME "クリスチーナ"
MESSAGE "あら、聞こえてました？\nごめんあそばせ、ほほほ……"
KEY_WAIT
CHAR 1, 12
FACE 11
MESSAGE_NAME "リーゼ"
MESSAGE "……と、とにかくだ。"
KEY_WAIT
CHAR 1, 13
FACE 12
MESSAGE "[娘の名前]、お前の分も\n用意してきたから、\n早いところ川に行こう。"
KEY_WAIT
CHAR 2, 16
FACE 15
MESSAGE_NAME "クリスチーナ"
MESSAGE "あら、[娘の名前]さんは\nわたくしと一緒に屋敷で\nお茶会ですのよ？"
KEY_WAIT
CHAR 2, 15
FACE 14
MESSAGE "釣りになど行っている暇は\nなくってよ。"
KEY_WAIT
CHAR 1, 12
FACE 11
MESSAGE_NAME "リーゼ"
MESSAGE "ふ、ふん……\nどうせ運動音痴のお前では、\n一緒に行ったところで……"
KEY_WAIT
CHAR 2, 15
FACE 14
MESSAGE_NAME "クリスチーナ"
MESSAGE "え？"
KEY_WAIT
CHAR 1, 12
FACE 11
MESSAGE_NAME "リーゼ"
MESSAGE "１匹も釣れないのは、火を\n見るよりも明らかだろうがな。"
KEY_WAIT
CHAR 2, 17
FACE 16
MESSAGE_NAME "クリスチーナ"
MESSAGE "な、なんですってェェーッ……"
KEY_WAIT
CHAR 2, 16
FACE 15
MESSAGE "あなたのようなガサツな方こそ、\n不作法をしでかして、皆から失笑を\nかう様子が目に浮かびますわ。"
KEY_WAIT
CHAR 1, 14
FACE 13
MESSAGE_NAME "リーゼ"
MESSAGE "おいっ！"
KEY_WAIT
CHAR 2, 15
FACE 14
MESSAGE_NAME "クリスチーナ"
MESSAGE "なんですの？"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 552
MESSAGE "ああ、ちょっと２人とも～……"
KEY_WAIT
BGM_PLAY 28
OFF_CHAR 1
OFF_CHAR 2
BG 65
FACE 13
MESSAGE_NAME "リーゼ"
MESSAGE "ぬぅぅぅぅ……"
KEY_WAIT
FACE 16
MESSAGE_NAME "クリスチーナ"
MESSAGE "むむむむむっ……"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 553
MESSAGE "ア、アハハ……"
LINE_FEED
FACE 7
MESSAGE "お、落ち着いて２人とも。\nねっ、ねっ？"
KEY_WAIT
FACE 13
MESSAGE_NAME "リーゼ"
MESSAGE "ええい、こうして\nにらみ合っていてもらちがあかん。"
KEY_WAIT
FACE 11
MESSAGE "ここは[娘の名前]に、\nどちらと一緒に行くか\n決めてもらおう！"
KEY_WAIT
FACE 16
MESSAGE_NAME "クリスチーナ"
MESSAGE "あら、あなたにしては\n気のきいた提案ですこと。"
KEY_WAIT
FACE 14
MESSAGE "もっとも、[娘の名前]さんが\nどちらをお選びになるかなんて、\n分かりきった事ですけれど。ねえ？"
KEY_WAIT
FACE 12
MESSAGE_NAME "リーゼ"
MESSAGE "よし、では[娘の名前]。\nどちらを選ぶんだ？"
KEY_WAIT
FACE 15
MESSAGE_NAME "クリスチーナ"
MESSAGE "もちろん、\nお茶会ですわよね？　ね？"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 554
MESSAGE "え、えぇ～？\nえっと、私は……"
SELECT 3, 2, "釣りに行く", 4, "お茶会に行く", 6, "３人で他のことをする"
LABEL 2
END 0
LABEL 3
FLAG 680, 1
FACE 12
MESSAGE_NAME "リーゼ"
MESSAGE "そうだろう、そうだろう！\nよ～し、今日はたくさん釣って、\nお土産にしような。"
KEY_WAIT
MESSAGE "ははははっ！"
KEY_WAIT
FACE 16
MESSAGE_NAME "クリスチーナ"
MESSAGE "く、くやしぃ～"
KEY_WAIT
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 4
END 1
LABEL 5
FLAG 681, 1
FACE 15
MESSAGE_NAME "クリスチーナ"
MESSAGE "ええ、ええ、そうですとも！\n年頃の女性ならば、休日には優雅に\nお茶をたしなむべきですわ。"
KEY_WAIT
FACE 13
MESSAGE_NAME "リーゼ"
MESSAGE "くう……\n釣りだって楽しいのに……"
KEY_WAIT
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 6
END 2
LABEL 7
FLAG 682, 1
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 555
MESSAGE "わざわざどっちかにしなくても……\nほら、みんなで一緒に\nピクニックに行くとか……"
KEY_WAIT
FACE 13
MESSAGE_NAME "リーゼ"
MESSAGE "それはイヤだ！"
KEY_WAIT
FACE 16
MESSAGE_NAME "クリスチーナ"
MESSAGE "それはイヤですわ！"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 556
MESSAGE "あうう㌍"
KEY_WAIT
FACE 3
VOICE 557
MESSAGE "ふ、ふたりともこんな時だけは\n息ぴったりなんだからぁ……"
KEY_WAIT
SELECT 2, 2, "釣りに行く", 4, "お茶会に行く"