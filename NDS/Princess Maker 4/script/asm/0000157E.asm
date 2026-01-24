LABEL 0
FLAG 1730, 1
BGM_PLAY 8
BG 0
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
TEXT_MODE 1
MESSAGE "ソファに腰を下ろし、ゆっくりと息を吐く。\nそれと同時に身体中の力が抜け、\nかわりに気だるさが身体を満たす。"
KEY_WAIT
MESSAGE "\n自分でいうのもなんだが、\n体力には自信がある。"
KEY_WAIT
MESSAGE "\n日頃やりなれていないとはいえ、\n家事くらいなんとでもなると思っていたが、\n今日は予想以上に疲れた。"
KEY_WAIT
MESSAGE "\n毎日、家事を引き受けてくれている\nキューブには感謝の念がたえない。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
MESSAGE "…今後は強制的にでも休みをとらせるように\nしたほうがいいかもしれない。"
KEY_WAIT
MESSAGE "\n今回のように何かしらの用事がなければ、\n自分から休みが欲しいとはいい出さない\nからな。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
MESSAGE "ふと気がつけば、窓の外はすっかり\n夜のとばりに包まれていた。"
KEY_WAIT
MESSAGE "\nあまり遅くまで起きていると明日に響く。\n今日はそろそろ寝るとしようか。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
TEXT_MODE 0
END 0
LABEL 1
SE_PLAY 1
SE_WAIT
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 3040
MESSAGE "パパぁ、いる……？"
KEY_WAIT
CHAR 0, 4
FACE 3
VOICE 3041
MESSAGE "あのね……\nひとりだとさみしくて\n眠れないの。"
KEY_WAIT
VOICE 3042
MESSAGE "いつもだと寝ちゃうまで\nキューブがいてくれるから\n平気なの。"
KEY_WAIT
CHAR 0, 8
FACE 7
VOICE 3043
MESSAGE "それでね、今日はとっても\n楽しかったからひとりでも\n大丈夫だと思ったんだけど……"
KEY_WAIT
VOICE 3044
MESSAGE "だからね、パパ。\nいっしょに寝てもいい？"
KEY_WAIT
VOICE 3045
MESSAGE "いいの？"
LINE_FEED
CHAR 0, 1
FACE 0
MESSAGE "……よかったぁ。"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
BG 280
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3046
MESSAGE "えへへ、あったかーい㍍"
KEY_WAIT
VOICE 3047
MESSAGE "ねえ、パパ。\n今日は楽しかったね。"
KEY_WAIT
END 0
LABEL 2
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3048
MESSAGE "パパがお料理できるなんて\nびっくりしちゃったよ。"
KEY_WAIT
VOICE 3049
MESSAGE "でも、パパのお料理\nおいしかったなぁ。\nまた今度作ってね。"
KEY_WAIT
FACE 4
VOICE 3050
MESSAGE "え？　あんまりパパのお料理を\nほめるとキューブがすねちゃう？"
KEY_WAIT
FACE 5
VOICE 3051
MESSAGE "えー、そうかなぁ。\n大丈夫だよ。"
KEY_WAIT
GOTO 5
LABEL 3
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3052
MESSAGE "お風呂きもちよかったなぁ。"
KEY_WAIT
FACE 0
VOICE 3053
MESSAGE "パパの背中おっきいから\n洗うの大変だったよ。"
KEY_WAIT
FACE 1
VOICE 3054
MESSAGE "でも、またやってあげるから\nいっしょに入ろうね。"
KEY_WAIT
GOTO 5
LABEL 4
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3055
MESSAGE "あぅ、かいだんのこと\n思い出しちゃった。"
KEY_WAIT
VOICE 3056
MESSAGE "本当にこわかったんだよ。"
KEY_WAIT
VOICE 3057
MESSAGE "もう、ぜーったいに\nかいだんなんてしないんだから。"
KEY_WAIT
LABEL 5
FACE 3
VOICE 3058
MESSAGE "ふぁ～……おはなししてたら、\nなんか眠くなってきちゃった。"
KEY_WAIT
VOICE 3059
MESSAGE "うみゅ……お休みなさぁい。"
KEY_WAIT
LABEL 6
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
FACE 65535
OFF_FACE_WINDOW
BGM_STOP 30
END 0