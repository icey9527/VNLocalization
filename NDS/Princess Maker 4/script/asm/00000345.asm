LABEL 0
BGM_PLAY 35
BG 0
FACE 26
MESSAGE_NAME "キューブ"
MESSAGE "本日は建国祭ですね。\n先ほど所用で見てまいりましたが、\n外はとてもにぎやかでしたよ。"
KEY_WAIT
END 0
LABEL 1
FACE 23
MESSAGE "建国祭とは、\n王国がこの地に誕生した日を祝う\nお祭りです。"
KEY_WAIT
MESSAGE "この日だけ、\nお城が一般市民に開放されます。"
KEY_WAIT
MESSAGE "貴族や王族の方々に会う絶好の機会\nですので、社交界へのデビューを\n目指すなら見逃せません。"
KEY_WAIT
END 0
LABEL 2
FACE 26
MESSAGE "特に、お城は\n開放日とあって盛況でした。"
KEY_WAIT
MESSAGE "旦那様も、\nお嬢様と見に行かれては\nいかがですか？"
SELECT 2, 3, "行く", 27, "行かない"
LABEL 3
END 0
LABEL 4
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "わかりました。\nでは、早速行く支度をしますね。"
KEY_WAIT
END 0
LABEL 5
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "お嬢様も舞踏会に出席できる\nお歳になりました。"
KEY_WAIT
FACE 28
MESSAGE "でも、お嬢様はドレスを\nお持ちではないので\n出席できません。"
KEY_WAIT
MESSAGE "せっかくのチャンスですのに\n残念です……"
KEY_WAIT
END 0
LABEL 6
FLAG 1708, 1
FACE 23
MESSAGE "お嬢様も舞踏会に出席できる\nお歳になりました。"
KEY_WAIT
MESSAGE "ドレスを着られれば\n出席できるのですが、"
KEY_WAIT
FACE 28
MESSAGE "お持ちのドレスは\nお嬢様には少々きついようです。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 2595
MESSAGE "えっ！\nわたし、そんなに\n太ってたかしら…"
KEY_WAIT
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "ドレスを着ないと舞踏会には\n出席できません。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2596
MESSAGE "わーん、\nそんなこと聞いてないわよー\n舞踏会楽しみだったのにー"
KEY_WAIT
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "せっかくのチャンスですのに\n残念です……"
KEY_WAIT
END 0
LABEL 7
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "わかりました。\nでは、支度をしましょう。"
KEY_WAIT
END 0
LABEL 8
FACE 26
MESSAGE "お嬢様も舞踏会に出席できる\nお歳になりました。\nドレスは何をお召しになりますか？"
END 0
LABEL 9
SE_STOP
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 10
SE_PLAY 15
SE_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
MESSAGE "パパ、お城の中ってこんなに\n広いんだね。プリンセスになって\n住んでみたいなぁ。"
KEY_WAIT
END 0
LABEL 11
SE_PLAY 15
SE_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
MESSAGE "パパ、お城の中ってこんなに\n広いんだね。鬼ごっこだって\n隠れんぼだってできちゃうね！"
KEY_WAIT
END 0
LABEL 12
SE_PLAY 15
SE_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
MESSAGE "本当にここに王様とか王妃様が住ん\nでるんだよね。"
KEY_WAIT
MESSAGE "こんなに大きなお家だと\n王様は迷子にならないのかなぁ？"
KEY_WAIT
END 0
LABEL 13
SE_PLAY 15
SE_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
MESSAGE "本当にここに王様とか王妃様が住ん\nでるんだよね。"
KEY_WAIT
MESSAGE "ねぇ、パパこんな大きいところだと\n王様も迷子になっちゃうかも\nしれないね。"
KEY_WAIT
END 0
LABEL 14
SE_PLAY 15
SE_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
MESSAGE "建国祭の日は普段お城に来ても\n入れてくれないところが見られる\nから楽しいね。"
KEY_WAIT
END 0
LABEL 15
SE_PLAY 15
SE_WAIT
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
MESSAGE "お城に来るとどうしても緊張\nしちゃうなぁ。お祭りなんだけど\nなんか楽しめないの。"
KEY_WAIT
END 0
LABEL 16
SE_PLAY 15
SE_WAIT
CHAR 0, 1
FACE 75
MESSAGE_NAME "パメラ"
MESSAGE "あら、あなたも王子様を探しに\n来たの？　あら違うの？\n私は絶対見つけて帰るんだから。"
KEY_WAIT
CHAR 0, 8
MESSAGE "顔は知ってるのかって？\n知らないわよ。でも、見たら\nきっとピンとくるわ。本当よ。"
KEY_WAIT
END 0
LABEL 17
SE_PLAY 15
SE_WAIT
CHAR 1, 1
CHAR 2, 15
FACE 14
MESSAGE_NAME "クリスチーナ"
MESSAGE "今日は、\n建国祭を祝うお茶会がありますの。\nよろしかったら、ご一緒しない？"
KEY_WAIT
CHAR 1, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
MESSAGE "ちょっと緊張しちゃうな。"
KEY_WAIT
CHAR 2, 16
FACE 15
MESSAGE_NAME "クリスチーナ"
MESSAGE "あなたなら大丈夫。リーゼさんのよ\nうながさつな人なら最初から誘いま\nせんから。さっ、行きましょう。"
KEY_WAIT
OFF_CHAR 2
OFF_CHAR 1
END 0
LABEL 18
SE_PLAY 15
SE_WAIT
CHAR 2, 1
CHAR 1, 18
FACE 17
MESSAGE_NAME "マリー"
MESSAGE "今日は、建国祭でしか見られない\n王宮魔道士の研究魔法の実演が\nあるんだけど見に行かない？"
KEY_WAIT
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
MESSAGE "へぇ、面白そう。行きましょ！"
OFF_CHAR 2
OFF_CHAR 1
END 0
LABEL 19
SE_PLAY 15
SE_WAIT
CHAR 1, 1
CHAR 2, 12
FACE 11
MESSAGE_NAME "リーゼ"
MESSAGE "今日は、建国祭の日にしか見られ\nない王立騎士団の馬上演武がある\nんだ。きっと参考になる。行こう！"
KEY_WAIT
CHAR 1, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
MESSAGE "面白そうね。行きましょ。"
OFF_CHAR 2
OFF_CHAR 1
END 0
LABEL 20
SE_PLAY 15
SE_WAIT
CHAR 1, 1
CHAR 2, 15
FACE 14
MESSAGE_NAME "クリスチーナ"
MESSAGE "あら、[娘の名前]さん！\nあなたも舞踏会の下見に\nいらしたの？"
KEY_WAIT
CHAR 1, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
MESSAGE "舞踏会？"
KEY_WAIT
CHAR 2, 17
FACE 16
MESSAGE_NAME "クリスチーナ"
MESSAGE "とぼけちゃイヤですわ。\n来年は私たちの舞踏会デビューの年\nじゃないですの？"
KEY_WAIT
CHAR 2, 16
FACE 15
MESSAGE "どんなドレスを着て行くか、\n楽しみで楽しみで。ああっ、"
LINE_FEED
CHAR 1, 1
MESSAGE "迷っちゃいますわ㍍"
KEY_WAIT
OFF_CHAR 2
OFF_CHAR 1
END 0
LABEL 21
LABEL 22
SE_PLAY 15
SE_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2592
MESSAGE "今日の舞踏会でクリスチーナが\nデビューするのね。"
KEY_WAIT
END 0
LABEL 23
CHAR 0, 8
FACE 7
VOICE 2593
MESSAGE "私もドレスを持っていれば\n出られたのになぁ。"
KEY_WAIT
END 0
LABEL 24
CHAR 0, 4
FACE 3
VOICE 2594
MESSAGE "でも、ドレスが着られないんじゃ\nしょうがないわよね……"
KEY_WAIT
END 0
LABEL 25
BG 157
SE_PLAY 15
SE_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 2597
MESSAGE "今日の舞踏会、素敵だったわ。"
KEY_WAIT
CHAR 0, 8
FACE 7
VOICE 2598
MESSAGE "それにしても、王子様とは\nどこかでお会いした気が\nするんだけど……"
KEY_WAIT
END 0
LABEL 26
CHAR 0, 2
FACE 1
VOICE 2599
MESSAGE "そんなはずないわよね。"
KEY_WAIT
END 0
LABEL 27
FACE 28
MESSAGE "せっかくのお祭りなのになあ……"
KEY_WAIT
SE_STOP
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 1
LABEL 28
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2666
MESSAGE "建国祭なんて行かないもーん。\n今日は、遊びに行くんだから。"
KEY_WAIT
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "そんなお嬢様\n年に一度の一般参賀なんですから\n旦那様と行きましょう。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2667
MESSAGE "別に\nいいもーん。"
KEY_WAIT
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "旦那様。\nお嬢様は建国祭には\n行かないそうです…"
KEY_WAIT
SE_STOP
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 29
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2631
MESSAGE "お城になんて興味ないわ。\n行くならお父さんとキューブで\n行ってきたら。"
KEY_WAIT
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "お嬢様ぁ、\n前はとっても楽しみにしてたじゃ\nないですか。"
KEY_WAIT
FACE 2
MESSAGE_NAME "[娘の名前]"
VOICE 2632
MESSAGE "いいの！\n行きたくないったら\n行きたくないの！"
KEY_WAIT
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "旦那様。\nお嬢様は建国祭には\n行かないそうです…"
KEY_WAIT
MESSAGE "難しい年頃ですねぇ…"
KEY_WAIT
SE_STOP
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 30
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2590
MESSAGE "私、行かなーい"
KEY_WAIT
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "年に一度の建国祭なんですから\nそんなへそ曲げないで\nくださいよー"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2591
MESSAGE "へそなんて曲げないわよ。\n私の行動に\nいちいち口ださないで！"
KEY_WAIT
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "旦那様。\nお嬢様は建国祭には\n行かないそうです…"
KEY_WAIT
FACE 27
LINE_FEED
LINE_FEED
MESSAGE "私と二人で行きましょうか…"
KEY_WAIT
SE_STOP
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 31
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "でも、お嬢様の\n容態は思わしくありません。"
KEY_WAIT
MESSAGE "残念ですが、お嬢様には、\n安静にしていただかないと\nいけませんね…"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2672
MESSAGE "コホッ、\n楽しみにしてたのに…\nざんねんだよぅ"
KEY_WAIT
SE_STOP
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 32
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "でも、お嬢様の\n容態は思わしくありません。"
KEY_WAIT
MESSAGE "残念ですが、お嬢様には、\n安静にしていただかないと\nいけませんね…"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2636
MESSAGE "ううっ\n年に一度のイベントに\n病気だなんて悲しいわ…"
KEY_WAIT
SE_STOP
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 33
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "でも、お嬢様の\n容態は思わしくありません。"
KEY_WAIT
MESSAGE "残念ですが、お嬢様には、\n安静にしていただかないと\nいけませんね…"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2605
MESSAGE "ごめんなさい、\nお父様と一緒に行けると\n思ったのに…"
KEY_WAIT
SE_STOP
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0