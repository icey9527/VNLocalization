LABEL 0
FLAG 542, 1
BG 147
END 0
LABEL 1
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3705
MESSAGE "あっ、お父様！\nこの子……見覚えがあるわ！"
KEY_WAIT
FACE 1
VOICE 3706
MESSAGE "おぼえてないかしら？\nほら、去年ここで怪我してた\n……そう、あの子よ！"
KEY_WAIT
FACE 0
VOICE 3707
MESSAGE "え？　大きすぎる、ですって？\nそうね。ふふ、でも……"
KEY_WAIT
VOICE 3708
MESSAGE "本人がそう言ってるの。\n間違いないわ。私もすぐ\n気づいたもの。"
KEY_WAIT
FACE 1
VOICE 3709
MESSAGE "よかった……元気になって！"
END 0
LABEL 2
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3710
MESSAGE "ふふふ……高くていい眺め……\nええ、とても気持ちいいわ。"
KEY_WAIT
FACE 1
VOICE 3711
MESSAGE "お父様～！　こっちです！\nお父様も乗ってみませんか？"
END 0
LABEL 3
SELECT 3, 4, "娘を呼ぶ", 5, "動物を威嚇する", 6, "静かに見守る"
LABEL 4
FLAG 544, 1
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3712
MESSAGE "え？　降りて来い、ですって？"
KEY_WAIT
FACE 0
VOICE 3713
MESSAGE "ふふふ、大丈夫。この子は\n悪さなんてしないって言ってます。\n怖がらないで欲しい、って。"
END 0
LABEL 5
FLAG 545, 1
FACE 2
MESSAGE_NAME "[娘の名前]"
VOICE 3714
MESSAGE "あっ！　お父様ー、ダメですよ\nそんなことしちゃ。"
KEY_WAIT
FACE 0
VOICE 3715
MESSAGE "この子、結構強いんだから。\nお父様のほうが負けちゃうかも\n知れませんよ。ふふふ……"
END 1
LABEL 6
FLAG 546, 1
END 2
LABEL 7
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3716
MESSAGE "ええ……私も再会できて\n嬉しいわ。ホントよ？\n……うふふ、いい子ね。"
KEY_WAIT
LABEL 8
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3717
MESSAGE "え……なに？\n今度はあっちに行きたいの？\nいいわよ。つきあってあげる。"
END 2
LABEL 9
FLAG 547, 1
BG 148
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3718
MESSAGE "きれいな海……"
KEY_WAIT
VOICE 3719
MESSAGE "こんなに透きとおって……\n魚たちも気持ちよさそう。"
SELECT 3, 10, "正しい潜水法を教える", 11, "魚をつつく", 12, "水面に上がる"
LABEL 10
FLAG 548, 1
MESSAGE_NAME "[娘の名前]"
VOICE 3720
MESSAGE "へぇ……そうやって\n泳ぐのね。なるほど……"
KEY_WAIT
VOICE 3721
MESSAGE "えっと……こんな感じかしら？\n確かにずっと速く進めるわ。\nさすが、お父様ね！"
END 0
LABEL 11
FLAG 549, 1
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3722
MESSAGE "あっ。そんな事をしたら\n魚たちが逃げちゃ……\n行っちゃった……"
KEY_WAIT
FACE 7
VOICE 3723
MESSAGE "もう。お父様ったら、いたずら\nばかりして。魚たちが\nかわいそうじゃない……"
END 1
LABEL 12
FLAG 550, 1
MESSAGE_NAME "[娘の名前]"
VOICE 3724
MESSAGE "ぷはっ……"
KEY_WAIT
FACE 1
VOICE 3725
MESSAGE "あっ、お父様、もう上がってる。\n私の方が長く潜ってられたのね。\nふふふ……"
KEY_WAIT
VOICE 3726
MESSAGE "私、もっと泳いでいるから、\nお父様は休んでて。\n……それっ！"
END 2
LABEL 13
FLAG 551, 1
BG 149
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3727
MESSAGE "えっ、何……？"
KEY_WAIT
VOICE 3728
MESSAGE "これは……\n風……？\n風の声が……聞こえるの……？"
KEY_WAIT
FACE 0
VOICE 3729
MESSAGE "どうしたの？　いったい私に\n何を聞かせたいの？"
SELECT 3, 14, "声をかける", 15, "服をおさえる", 16, "櫛を渡す"
LABEL 14
FLAG 552, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3730
MESSAGE "あ……\nお父、様……？\nううん、なんでもないの。"
KEY_WAIT
VOICE 3731
MESSAGE "ええ、大丈夫。何かが聞こえた\nような気がしただけ……\n行きましょ、お父様。"
END 0
LABEL 15
FLAG 553, 1
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3732
MESSAGE "きゃっ、風が……"
KEY_WAIT
FACE 0
VOICE 3733
MESSAGE "ありがとう、お父様。\n風も強くなってきたし、\nそろそろ戻りましょうか。"
END 1
LABEL 16
FLAG 554, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3734
MESSAGE "あら……ありがとう、お父様。"
KEY_WAIT
VOICE 3735
MESSAGE "もう、せっかくきれいに整えて\nきたのに風で台無し……\n髪、しばっちゃった方がいいかな。"
END 2
LABEL 17
FLAG 555, 1
BG 150
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3736
MESSAGE "お父様ー！　ほら、見てください！"
KEY_WAIT
VOICE 3737
MESSAGE "私、こんなに滑れるように\nなったのよ。すごいでしょう？"
SELECT 3, 18, "いっしょに滑る", 19, "絶賛する", 20, "静かにながめる"
LABEL 18
FLAG 556, 1
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3738
MESSAGE "あら、お父様も滑るの？\nわあ……速い……！"
KEY_WAIT
FACE 1
VOICE 3739
MESSAGE "さすがはお父様ね。\n私も負けていられないわ！\nふふふ……競争ね！"
END 0
LABEL 19
FLAG 557, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3740
MESSAGE "ふふふ……ありがとう！\n氷の上で踊れるなんて、\n思いもしなかったわ。"
KEY_WAIT
FACE 1
VOICE 3741
MESSAGE "まるで鳥か風になったみたいよ！\nお父様、見ていてくださいねー！\nふふふ……"
END 1
LABEL 20
FLAG 558, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3742
MESSAGE "え……どうしたの、お父様？\nそんなにボーッとして……"
KEY_WAIT
FACE 6
VOICE 3743
MESSAGE "あら……もしかして、私の\n姿に見とれてたのね？\nふふふ……"
END 2