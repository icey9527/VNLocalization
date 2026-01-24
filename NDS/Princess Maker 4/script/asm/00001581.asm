LABEL 0
SPECIAL 17
BGM_PLAY 1
BG 0
FACE 65535
OFF_FACE_WINDOW
MESSAGE "彼女に娘を託されてから、\n十数年の月日が流れた。"
KEY_WAIT
MESSAGE "私は元々、無骨な戦士である。\n果たして無事に育てあげることなど\nできるのだろうか？"
KEY_WAIT
MESSAGE "正直、不安はあった。"
KEY_WAIT
MESSAGE "それでも、できる限りの愛情を\n注いできたつもりだ。"
KEY_WAIT
MESSAGE "その娘も今や独り立ちしようかと\nしている。\nそんなある日のこと……"
KEY_WAIT
MESSAGE "娘が私の書斎へやってきた。\nその瞳に決意の色をたたえて……"
KEY_WAIT
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 4044
MESSAGE "あの……\n聞いてほしいことがあるの……"
KEY_WAIT
VOICE 4045
MESSAGE "私、言うべきなのか\nどうか迷っていたけど……\nでも、もう、決心したの。"
KEY_WAIT
CHAR 0, 7
FACE 6
VOICE 4046
MESSAGE "お父様が好き……\n一番大好き……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "私はその想いを受け止めた。"
KEY_WAIT
MESSAGE "世間的には許されることでは\nないのかもしれない。"
KEY_WAIT
MESSAGE "だが、年々美しく成長していく姿に\n親としての愛情以上の感情を\n抱いてしまったのも確かなのだ。"
KEY_WAIT
MESSAGE "私は想いのままに\n突き進むことを決めた。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
BG 15
SE_WAIT
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4047
MESSAGE "ウフフ、２人だけの結婚式ね……"
KEY_WAIT
VOICE 4048
MESSAGE "でも、うれしい。\nこうしてお父様と２人っきりで……"
KEY_WAIT
VOICE 4049
MESSAGE "それだけで私、とっても幸せ……"
KEY_WAIT
VOICE 4050
MESSAGE "あっ、お父様って呼び方は\nもう変えたほうがいいかしら？"
KEY_WAIT
VOICE 4051
MESSAGE "ねぇ……\nなんて呼べばいい？"
SELECT 3, 1, "お父様", 2, "あなた", 3, "ダーリン"
LABEL 1
FLAG 1781, 1
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 4052
MESSAGE "もう！　それじゃあ、変わらない\nじゃない……"
KEY_WAIT
FACE 1
VOICE 4053
MESSAGE "でも……それでもいいかもね。\n私たちも急には変われないから……"
KEY_WAIT
VOICE 4054
MESSAGE "お父様……"
KEY_WAIT
FACE 6
VOICE 4055
MESSAGE "これからもずっと一緒よ㍍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
END 0
GOTO 4
LABEL 2
FLAG 1782, 1
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4056
MESSAGE "そうね。なんだか新婚さんって\n感じがするわ。"
KEY_WAIT
FACE 6
VOICE 4057
MESSAGE "ちょ、ちょっと恥ずかしいけど……\nでも……いうわね。"
KEY_WAIT
VOICE 4058
MESSAGE "あ、あなた……"
KEY_WAIT
VOICE 4059
MESSAGE "大好き……㍍"
KEY_WAIT
VOICE 4060
MESSAGE "これまでも……\nそしてこれからも……"
KEY_WAIT
VOICE 4061
MESSAGE "決して私を離さないでね……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
END 1
GOTO 4
LABEL 3
FLAG 1783, 1
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4062
MESSAGE "アハハ！\nそんなのがいいの？\nじゃあ……"
KEY_WAIT
FACE 6
VOICE 4063
MESSAGE "ねぇ、ダーリン㍍\n私のこと好き？"
KEY_WAIT
VOICE 4064
MESSAGE "私は大好き㍍\n私たち絶対に……幸せになろうね、\nマイダーリン㍍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
END 2
GOTO 4
LABEL 4
MESSAGE "　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　"
KEY_WAIT
BGM_PLAY 9
END 0
LABEL 5
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4065
MESSAGE "……起きて、お父様。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "…………………………"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4066
MESSAGE "お父様ってば……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "…………………………"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4067
MESSAGE "ふぅ、しょうがないわね。\nそれじゃ……ん……㍍"
KEY_WAIT
GOTO 8
LABEL 6
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4068
MESSAGE "……あなた。\n朝よ、起きて。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "…………………………"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4069
MESSAGE "どうすれば、\n起きてくれるのかしら。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "…………………………"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4070
MESSAGE "あ、そうだ……\nえっと……ん……㍍"
KEY_WAIT
GOTO 8
LABEL 7
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4071
MESSAGE "ダーリン、起きてる？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "…………………………"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 4072
MESSAGE "まだ寝てるの？\n……最近、寝るのが遅いから\n仕方ないかのな。"
KEY_WAIT
FACE 1
VOICE 4073
MESSAGE "それじゃあ……んっ……㍍"
KEY_WAIT
GOTO 8
LABEL 8
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
MESSAGE "！？"
KEY_WAIT
MESSAGE "……はぁ、はぁ、はぁ……\nな、何が起きたんだ。\nと、突然、息ができなくなって……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 251
SE_WAIT
END 0
LABEL 9
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4074
MESSAGE "おはよう、お父様♪"
KEY_WAIT
GOTO 12
LABEL 10
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4075
MESSAGE "おはよう、あなた♪"
KEY_WAIT
GOTO 12
LABEL 11
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4076
MESSAGE "ダーリン、お・は・よ㍍"
KEY_WAIT
GOTO 12
LABEL 12
FACE 65535
OFF_FACE_WINDOW
MESSAGE "枕元に娘が、いや、妻が立って、\n私の顔を覗き込んでいた。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4077
MESSAGE "もうすぐご飯ができるから、\n早く着替えてね㍍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "何をしたのか問いただそうと私が\n口を開くより早く、妻はエプロンを\n軽やかに翻して寝室を出ていった。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
BG 252
SE_WAIT
MESSAGE "娘の想いを受け止めたあの日から、\n一月が過ぎようとしている。"
KEY_WAIT
MESSAGE "当初、周囲には拒絶されるかと\n思っていたが、幸いにも私たちの\n関係は受け入れられた。"
KEY_WAIT
MESSAGE "正直、拍子抜けだった。\n場合によっては国を捨てる覚悟も\nしていたのだが……"
KEY_WAIT
MESSAGE "あとで聞いた話によると、\nキューブが裏で色々と動いてくれた\nとのことだった。"
KEY_WAIT
MESSAGE "彼にはどれだけ感謝しても、\nし足りないのではないかと思う。"
KEY_WAIT
MESSAGE "私たちの恩人ともいえる、\nキューブだが、実は今、\nこの家にいない。"
KEY_WAIT
MESSAGE "新婚生活の邪魔をするわけに\nいかないといって、魔界に\n帰ってしまったのだ。"
KEY_WAIT
MESSAGE "私も妻も気にすることは\nないといったのだが、\n聞き入られることはなかった。"
KEY_WAIT
MESSAGE "そういえば、キューブは話し合いの\n最中、胸を押さえ、苦しそうな顔を\nしていた。"
KEY_WAIT
MESSAGE "もしかして、身体を悪くしていて\nそれが原因で……"
KEY_WAIT
MESSAGE "……いや、それはないだろう。\n普段、そんな素振は一切なかったし\nそれにあの表情は見覚えがある。"
KEY_WAIT
MESSAGE "確か、あれは娘が作りすぎた\nお菓子を食べ過ぎて胸焼けしたとき\nの……"
KEY_WAIT
MESSAGE "ん？　何故、キューブはそんな顔を\nしたのだろう。"
KEY_WAIT
MESSAGE "それに私が魔界に帰ることを\n許可したとき、ほっと胸を\nなでおろしていたし……"
KEY_WAIT
MESSAGE "ううむ、わからん。"
KEY_WAIT
BG 176
SE_WAIT
BG 0
END 0
LABEL 13
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4078
MESSAGE "お父様ー♪"
KEY_WAIT
GOTO 16
LABEL 14
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4079
MESSAGE "あなたー♪"
KEY_WAIT
GOTO 16
LABEL 15
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4080
MESSAGE "ダーリン㍍"
KEY_WAIT
GOTO 16
LABEL 16
FACE 65535
OFF_FACE_WINDOW
MESSAGE "台所の方から私を呼ぶ声が\n聞こえてきた。そろそろいかないと\nまずそうだ。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 17
LABEL 17
BGM_PLAY 9
BG 253
SE_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4081
MESSAGE "はい、召し上がれ㍍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "テーブルの上には妻が作った\n朝食が並べられている。"
KEY_WAIT
MESSAGE "こんがりと焼けたトーストに\nデミグラスソースのかかった\nふわふわのオムレツ。"
KEY_WAIT
MESSAGE "新鮮な野菜にお手製ドレッシングを\nかけたサラダと自家製のクルトンが\n浮いたポタージュスープ。"
KEY_WAIT
MESSAGE "香りをかいだだけで、\n口の中に唾液が満ちてくる。"
KEY_WAIT
MESSAGE "妻が席に座るのを待って、\n料理に手を伸ばした。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4082
MESSAGE "どう美味しい？"
SELECT 3, 18, "美味しいよ", 19, "味がうすいな", 20, "おかわり！"
LABEL 18
FLAG 1784, 1
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4083
MESSAGE "ホント？　よかった㍍"
KEY_WAIT
VOICE 4084
MESSAGE "あ、おかわりあるけど、\nどうする？"
KEY_WAIT
VOICE 4085
MESSAGE "それじゃ用意するわね。"
KEY_WAIT
GOTO 21
LABEL 19
FLAG 1785, 1
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4086
MESSAGE "え？　うそ？"
KEY_WAIT
FACE 3
VOICE 4087
MESSAGE "……ほんとだ。ごめんなさい。\n次はもっと頑張るから。"
KEY_WAIT
GOTO 21
LABEL 20
FLAG 1786, 1
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4088
MESSAGE "え？　早すぎない？\nちゃんとかまないと身体に\n悪いわよ。"
KEY_WAIT
FACE 1
VOICE 4089
MESSAGE "でも、喜んでもらえたみたいで\n良かったわ。"
KEY_WAIT
VOICE 4090
MESSAGE "はい、スープのおかわり、\n熱いから気をつけてね㍍"
KEY_WAIT
GOTO 21
LABEL 21
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4091
MESSAGE "あ、ちょっと待って。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "身を乗り出した妻のひとさし指が、\n私の唇に触れた。"
KEY_WAIT
MESSAGE "やわらかな感触を持つ、それが\nゆっくりと横に動いていく。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4092
MESSAGE "うん、とれたみたいね♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "そういうと、娘は茶色いソースが\nついた指を口に含んだ。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4093
MESSAGE "ん、おいし♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "子ども扱いされた気がして\n少々面白くなかった。\nだから……"
KEY_WAIT
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4094
MESSAGE "え？　なに……って、んんっ㍍"
KEY_WAIT
VOICE 4095
MESSAGE "……っはぁ。\nと、突然どうしたの？\nえ？　ソースがついてた？"
KEY_WAIT
VOICE 4096
MESSAGE "もう、いきなりだったから\n驚いちゃったわ。"
KEY_WAIT
OFF_CHAR 3
BG 176
SE_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
BG 0
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4097
MESSAGE "ごちそうさまでした。"
KEY_WAIT
VOICE 4098
MESSAGE "お皿は私が片付けるから\nリビングで休んでて。"
KEY_WAIT
VOICE 4099
MESSAGE "あ、それとこのあとちょっと\nお願いがあるんだけど、いい？"
KEY_WAIT
VOICE 4100
MESSAGE "ほら、ここ数日、\n雨が続いたでしょ？"
KEY_WAIT
VOICE 4101
MESSAGE "それで洗濯物がたまっちゃって……\n干すのだけでいいから\n手伝ってもらえないかしら。"
SELECT 2, 22, "手伝う", 23, "手伝わない"
LABEL 22
FLAG 1787, 1
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4102
MESSAGE "ありがとう。\nそれじゃ、洗いものが終わったら\n声かけるからちょっと待ってて。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 53
LABEL 23
FLAG 1788, 1
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 4103
MESSAGE "……そう。\nなら仕方ないわね。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
MESSAGE "　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　"
KEY_WAIT
GOTO 24
LABEL 24
BGM_PLAY 12
BG 0
FACE 65535
OFF_FACE_WINDOW
MESSAGE "朝食後、私は部屋に戻り、\n友人たちから送られてきた祝いの\n品を片付けることにした。"
KEY_WAIT
MESSAGE "祝福してくれるのは嬉しいのだが、\n置き場所に困るものが多く、\n部屋は足の踏み場もないほどだ。"
KEY_WAIT
MESSAGE "黙々と片づけを行い、\nやっと終わりが見えてきた頃――"
KEY_WAIT
SE_PLAY 6
SE_WAIT
END 0
LABEL 25
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4104
MESSAGE "ねぇ、お父様。\nちょっといい？"
KEY_WAIT
GOTO 28
LABEL 26
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4105
MESSAGE "ねぇ、あなた。\nちょっといい？"
KEY_WAIT
GOTO 28
LABEL 27
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4106
MESSAGE "ダーリン㍍　ちょっといい？"
KEY_WAIT
GOTO 28
LABEL 28
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 4107
MESSAGE "お買い物に行きたいんだけど、\n一緒に来てくれないかしら。"
KEY_WAIT
VOICE 4108
MESSAGE "最近、雨が多くてあんまり買い物に\nいけなかったから食材の買い置きが\nなくなっちゃったのよ。"
KEY_WAIT
VOICE 4109
MESSAGE "他にも色々と買い足しておきたい\nから、手伝ってほしいんだけど……"
KEY_WAIT
CHAR 0, 2
FACE 1
VOICE 4110
MESSAGE "……いいの？　ありがとう♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
BG 254
SE_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4111
MESSAGE "……うふふ♪"
KEY_WAIT
FACE 1
VOICE 4112
MESSAGE "え？　なんでそんなに機嫌が\nいいのかって？"
KEY_WAIT
VOICE 4113
MESSAGE "だって、さっきのお店で……"
KEY_WAIT
BG 162
FACE 53
MESSAGE_NAME "店主"
MESSAGE "おや、若奥さん。\n今日はだんなさんと一緒かい？"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4114
MESSAGE "ええ、そうよ♪"
KEY_WAIT
FACE 53
MESSAGE_NAME "店主"
MESSAGE "いや～、仲よさそうで\nうらやましいね。\nお似合いですよ～。"
KEY_WAIT
MESSAGE "だんなさんも幸せだね。\nこんな美人の奥さん、\nもらっちゃって。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4115
MESSAGE "あら、そんな……♪"
KEY_WAIT
VOICE 4116
MESSAGE "……ねぇ、お似合いですって㍍"
KEY_WAIT
FACE 53
MESSAGE_NAME "店主"
MESSAGE "うちの古女房ととっかえて\nほしいくらい……って、だんな、\n目がこわいですよ。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4117
MESSAGE "もう、そんなこといったら\n奥さんに怒られちゃいますよ♪"
KEY_WAIT
CHAR 0, 7
FACE 6
VOICE 4118
MESSAGE "それに、私、この人しか\n考えられませんから♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "楽しげな表情を浮かべて\n妻が身を寄せてくる。"
KEY_WAIT
MESSAGE "それにあわせて、私が彼女の肩を\n抱き寄せると、店主はなんとも\nいえない表情を浮かべた。"
KEY_WAIT
FACE 53
MESSAGE_NAME "店主"
MESSAGE "まいったな、こりゃ。\nいや、冗談抜きで。"
KEY_WAIT
MESSAGE "……で、何にします？"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4119
MESSAGE "うふふ♪\nそれじゃ、そこの棚のやつと\nこっちのと……それに……"
KEY_WAIT
VOICE 4120
MESSAGE "あと、アレとコレとソレも\nください。あ、あっちのも\n貰おうかしら？"
KEY_WAIT
FACE 53
MESSAGE_NAME "店主"
MESSAGE "あいよ、毎度ありぃ！"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 254
SE_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4121
MESSAGE "ん～、ちょっと買いすぎちゃった\nかしら？"
KEY_WAIT
END 0
LABEL 29
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4122
MESSAGE "でも、お父様なら、これくらい\n大丈夫よね。"
KEY_WAIT
GOTO 32
LABEL 30
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4123
MESSAGE "でも、あなたなら、これくらい\n大丈夫よね。"
KEY_WAIT
GOTO 32
LABEL 31
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4124
MESSAGE "でも、ダーリンなら、これくらい\n大丈夫でしょ？"
KEY_WAIT
GOTO 32
LABEL 32
FACE 65535
OFF_FACE_WINDOW
MESSAGE "信頼の色をその瞳に浮かべて、\n私が持つ荷物に視線を向ける妻。"
KEY_WAIT
MESSAGE "そういわれて重いなどと\n泣き言はいえるだろうか、\nいや、いえない。"
KEY_WAIT
MESSAGE "とはいえ……\n前が見えないほどの量は、\n……少々、きつい……"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4125
MESSAGE "あ、おでこに汗が……"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4126
MESSAGE "拭いてあげるから、\n動かないでね。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "よし！　家までもう少しだ。\n頑張るとしよう。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 33
LABEL 33
BGM_PLAY 9
BG 0
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4127
MESSAGE "ただいま～。"
KEY_WAIT
VOICE 4128
MESSAGE "ふぅ、重かったぁ。"
KEY_WAIT
END 0
LABEL 34
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4129
MESSAGE "あ、台所に置いてくるから、\nお父様は部屋で休んでて。"
KEY_WAIT
VOICE 4130
MESSAGE "大丈夫よ、これくらい。"
KEY_WAIT
OFF_CHAR 3
GOTO 37
LABEL 35
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4131
MESSAGE "あ、台所に置いてくるから、\nあなたは部屋で休んでて。"
KEY_WAIT
VOICE 4132
MESSAGE "え？　運んでくれるの？\nじゃあ、お願いしちゃおうかしら。"
KEY_WAIT
OFF_CHAR 3
GOTO 37
LABEL 36
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4133
MESSAGE "あ、台所に置いてくるから、\nダーリンは部屋で休んでて㍍"
KEY_WAIT
VOICE 4134
MESSAGE "え？　運んでくれるの？\nありがと㍍"
KEY_WAIT
OFF_CHAR 3
GOTO 37
LABEL 37
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4135
MESSAGE "紅茶いれたんだけど、\n飲まない？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 255
SE_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "一息ついていると、隣に座った\n妻が紅茶の満たされたカップを\n差し出してきた。"
KEY_WAIT
MESSAGE "それを受け取り、口をつけようと\nするが……むぅ、熱い。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4136
MESSAGE "あ、ちょっと熱すぎた？"
KEY_WAIT
FACE 0
VOICE 4137
MESSAGE "それじゃ、ふー、ふー……\n……はい、どーぞ♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "適温になった紅茶を口に含む。\n少し甘めだが、重い荷物を持って\n疲れた身体にはちょうどいい。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4138
MESSAGE "疲れてると思ったから\n少し砂糖を多めにしたんだけど、\nどう？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "妻の心遣いに礼を述べる。"
KEY_WAIT
MESSAGE "紅茶の味と香りを楽しんでいると、\n妻が隣に腰を下ろし、\nいつものように身体を寄せてきた。"
KEY_WAIT
MESSAGE "わたしもまた普段通りに、\n妻の肩に手を回す。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4139
MESSAGE "うふふ㍍"
KEY_WAIT
VOICE 4140
MESSAGE "じゃあ、私も飲もうかな？"
KEY_WAIT
VOICE 4141
MESSAGE "……うん、美味し♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 256
SE_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "カップの中の紅茶が空になった頃、\n隣りからおだやかな寝息が\n聞こえてきた。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4142
MESSAGE "……すー、すー。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "朝から色々と忙しそうに\nしていたので疲れたのだろう。"
KEY_WAIT
MESSAGE "それに最近、夜も遅いし……"
KEY_WAIT
MESSAGE "幸せそうに眠る妻の頭を\nいたわりの気持ちを込めて、\nそっとなでる。"
KEY_WAIT
END 0
LABEL 38
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4143
MESSAGE "ん……おとう、さま……"
KEY_WAIT
GOTO 41
LABEL 39
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4144
MESSAGE "ん……あなたぁ……\nくー、すー……"
KEY_WAIT
GOTO 41
LABEL 40
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4145
MESSAGE "ぁん……だーりぃん……㍍"
KEY_WAIT
GOTO 41
LABEL 41
FACE 65535
OFF_FACE_WINDOW
MESSAGE "穏やかな寝息を立てる妻を\n起こさないように、\n優しく抱き上げて寝室へと運んだ。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 42
LABEL 42
BGM_PLAY 9
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4146
MESSAGE "……んっ……ふぁ～あ……\n……あれ？"
KEY_WAIT
BG 284
FACE 65535
OFF_FACE_WINDOW
MESSAGE "ふむ、これでいいだろう。"
KEY_WAIT
MESSAGE "テーブルの上に並べられた\n料理を見て、満足げに頷く。"
KEY_WAIT
MESSAGE "久しぶりに料理をしたのだが、\nそれなりに上手くできたのでは\nないかと思う。"
KEY_WAIT
MESSAGE "あとは妻を起こして……"
KEY_WAIT
END 0
LABEL 43
CHAR 0, 4
FACE 3
MESSAGE_NAME "[娘の名前]"
VOICE 4147
MESSAGE "お父様、ごめんなさい。\n急いでご飯の支度するから！"
KEY_WAIT
GOTO 46
LABEL 44
CHAR 0, 4
FACE 3
MESSAGE_NAME "[娘の名前]"
VOICE 4148
MESSAGE "あ、あなた、ごめんなさい。\nすぐお夕飯作るから！"
KEY_WAIT
GOTO 46
LABEL 45
CHAR 0, 4
FACE 3
MESSAGE_NAME "[娘の名前]"
VOICE 4149
MESSAGE "ダ、ダーリン、ごめんなさい。\n寝坊しちゃった！"
KEY_WAIT
VOICE 4150
MESSAGE "すぐご飯にするから、\nちょっと待ってて㌍"
KEY_WAIT
GOTO 46
LABEL 46
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4151
MESSAGE "……って、あれ？"
KEY_WAIT
VOICE 4152
MESSAGE "なんで、料理ができてるの？\nあ、もしかして……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "料理が冷めてしまっては、もったい\nないので申し訳なさそうにしている\n妻に早く食べるよう促した。"
KEY_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4153
MESSAGE "えと、いただきます……\nあ、おいしい。"
KEY_WAIT
VOICE 4154
MESSAGE "こっちは何かしら？"
KEY_WAIT
VOICE 4155
MESSAGE "……んっ、ちょっと苦いけど\n癖になりそうな味ね。"
KEY_WAIT
VOICE 4156
MESSAGE "これは……\nすっぱ辛くて面白い味がするわ。"
KEY_WAIT
VOICE 4157
MESSAGE "どこでこういう料理覚えてきたの？\nもしかして昔、冒険をしてた頃？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
CHAR 0, 4
FACE 3
MESSAGE_NAME "[娘の名前]"
VOICE 4158
MESSAGE "……ごちそうさまでした。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "食事が進むにつれ、妻の口数が減り\n表情から笑顔が失われていった。"
KEY_WAIT
MESSAGE "料理は好評だったと思うのだが、\nもしかして、気を使わせてしまった\nのではないだろうか？"
KEY_WAIT
MESSAGE "そうだとしたら、\n大変申し訳ないことをした。"
KEY_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4159
MESSAGE "あ、そ、そうじゃないの㌍"
KEY_WAIT
END 0
LABEL 47
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4160
MESSAGE "お父様のお料理、\nすっごく美味しかったわよ。"
KEY_WAIT
GOTO 50
LABEL 48
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4161
MESSAGE "あなたのお料理\nすっごく美味しかったわよ。"
KEY_WAIT
GOTO 50
LABEL 49
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4162
MESSAGE "ダーリンのお料理、\nすっごく美味しかったわよ。"
KEY_WAIT
GOTO 50
LABEL 50
CHAR 0, 4
FACE 3
MESSAGE_NAME "[娘の名前]"
VOICE 4163
MESSAGE "でもね……"
KEY_WAIT
VOICE 4164
MESSAGE "私、こんなお料理作れないし……"
KEY_WAIT
VOICE 4165
MESSAGE "それに、今日だって\n寝過ごしちゃって、\nご飯の支度できなかったし……"
KEY_WAIT
VOICE 4166
MESSAGE "そう考えてたら、私って\nだめだなって思っちゃって……"
SELECT 2, 51, "そんなことはない", 52, "………………"
LABEL 51
FLAG 1789, 1
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4167
MESSAGE "……うん、落ち込んでても\n仕方がないわよね。"
KEY_WAIT
VOICE 4168
MESSAGE "次はちゃんとやるから。\nまずは明日の朝食……の前に、\nお皿洗わないと。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4169
MESSAGE "私がやっておくから、\n先にお風呂入っちゃって。"
KEY_WAIT
VOICE 4170
MESSAGE "それとも、一緒に入りたい？\n……うふふ、冗談よ㍍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "いたずらっぽい笑みを浮かべて、\n妻は食器を片付け始めた。"
KEY_WAIT
MESSAGE "……一緒に入りたかった、とは\n口に出さない。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
GOTO 93
LABEL 52
FLAG 1790, 1
CHAR 0, 4
FACE 3
MESSAGE_NAME "[娘の名前]"
VOICE 4171
MESSAGE "ごめんなさい、\nお皿片付けちゃうから……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "視線をそらしたまま、妻は黙々と\n食器を片付け始めた。"
KEY_WAIT
MESSAGE "その日から数日の間、妻はろくに\n口をきいてくれなかった……"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
END 0
LABEL 53
BGM_PLAY 12
BG 257
SE_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4172
MESSAGE "んー、いい天気♪"
KEY_WAIT
VOICE 4173
MESSAGE "これなら、お洗濯物が\nよく乾くわね♪"
KEY_WAIT
END 0
LABEL 54
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4174
MESSAGE "あ、お父様、\nそっちのかごの中身、\n干してもらえます？"
KEY_WAIT
GOTO 57
LABEL 55
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4175
MESSAGE "あ、あなた、\nそっちのかごの中身、\n干してもらえます？"
KEY_WAIT
GOTO 57
LABEL 56
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4176
MESSAGE "あ、ダーリンはそっちの方のかごを\n干してね㍍"
KEY_WAIT
GOTO 57
LABEL 57
VOICE 4177
MESSAGE "でも、今日は晴れてよかったわ。"
KEY_WAIT
VOICE 4178
MESSAGE "最近、雨が多かったでしょ。"
KEY_WAIT
VOICE 4179
MESSAGE "そのせいで洗濯ができなくて\n困ってたのよ。"
KEY_WAIT
VOICE 4180
MESSAGE "……シーツがもうなくなりそう\nだったし。"
KEY_WAIT
VOICE 4181
MESSAGE "あ、そうだわ。折角だし、\nお布団も干しましょうか？"
KEY_WAIT
VOICE 4182
MESSAGE "そうしたら、今夜はふかふかの\nお布団で寝られるわよ♪"
SELECT 2, 58, "そうしよう", 59, "別にいいんじゃないか"
LABEL 58
FLAG 1791, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4183
MESSAGE "それじゃあ、悪いんだけど\nお布団を持ってきて\nもらえないかしら？"
KEY_WAIT
VOICE 4184
MESSAGE "お願いね㍍"
KEY_WAIT
VOICE 4185
MESSAGE "……ねぇ、\n何かにやけてるみたいだけど……"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4186
MESSAGE "あ、もしかして……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "さて、さっさと布団を\n持ってくるとしようか。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4187
MESSAGE "あ、逃げたわね。"
KEY_WAIT
VOICE 4188
MESSAGE "うふふ㍍\nしょうがないんだから♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 60
LABEL 59
FLAG 1792, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4189
MESSAGE "そうね。\n洗濯物がいっぱいで\n干す場所がなさそうだし……"
KEY_WAIT
VOICE 4190
MESSAGE "今日は我慢しましょうか。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 60
LABEL 60
BGM_PLAY 9
BG 0
FACE 65535
OFF_FACE_WINDOW
MESSAGE "洗濯物を干し終わった後、私は部屋\nに戻り、友人たちから送られてきた\n祝いの品を片付けることにした。"
KEY_WAIT
MESSAGE "祝福してくれるのは嬉しいのだが、\n置き場所に困るものが多く、\n部屋は足の踏み場もないほどだ。"
KEY_WAIT
MESSAGE "まずは不要なものを処分して、\nそれから祝いの品を\nしまっていくとしよう。"
KEY_WAIT
END 0
LABEL 61
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4191
MESSAGE "お父様、なにしてるの？"
KEY_WAIT
GOTO 64
LABEL 62
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4192
MESSAGE "あなた、いるー？"
KEY_WAIT
VOICE 4193
MESSAGE "あら、何してるの？"
KEY_WAIT
GOTO 64
LABEL 63
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4194
MESSAGE "ダーリン、どこにいるのー？"
KEY_WAIT
VOICE 4195
MESSAGE "あ、ダーリン㍍"
KEY_WAIT
VOICE 4196
MESSAGE "あら、何してるの？"
KEY_WAIT
GOTO 64
LABEL 64
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4197
MESSAGE "すごい状況ね。\n私も手伝いましょうか？"
SELECT 2, 65, "よろしく頼む", 70, "いや、大丈夫だ"
LABEL 65
FLAG 1793, 1
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4198
MESSAGE "ええ、それじゃ、何から\n片付けましょうか？"
KEY_WAIT
VOICE 4199
MESSAGE "そこの棚のいらないものを\n処分するのね。わかったわ。"
KEY_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4200
MESSAGE "あ、これ……"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4201
MESSAGE "きゃ～、懐かしい～♪\nまだあったのね。"
KEY_WAIT
VOICE 4202
MESSAGE "ほら、見て。\n昔、おままごとで使った\n食器が出てきたの。"
KEY_WAIT
VOICE 4203
MESSAGE "……ねぇ、覚えてる？\n私が小さい頃、これで一緒に\n遊んだこと。"
KEY_WAIT
VOICE 4204
MESSAGE "私がママで、クマのぬいぐるみが\n赤ちゃん。"
KEY_WAIT
END 0
LABEL 66
CHAR 0, 7
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4205
MESSAGE "それでお父様がパパの役。"
KEY_WAIT
VOICE 4206
MESSAGE "今、考えてみると\nすごい偶然だと思うわ。"
KEY_WAIT
VOICE 4207
MESSAGE "ううん、やっぱり子どものころから\nお父様のお嫁さんになりたかったの\nかもね㍍"
KEY_WAIT
GOTO 69
LABEL 67
CHAR 0, 7
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4208
MESSAGE "それであなたがパパの役。"
KEY_WAIT
VOICE 4209
MESSAGE "今、考えてみると\nすごい偶然だと思うわ。"
KEY_WAIT
VOICE 4210
MESSAGE "ううん、やっぱり子どものころから\nあなたのお嫁さんになりたかったの\nかもね㍍"
KEY_WAIT
GOTO 69
LABEL 68
CHAR 0, 7
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4211
MESSAGE "それでダーリンがパパの役。"
KEY_WAIT
VOICE 4212
MESSAGE "今、考えてみるとすごい偶然よね。"
KEY_WAIT
VOICE 4213
MESSAGE "でも、やっぱり子どものころから\nダーリンのお嫁さんになりたかった\nのかもね㍍"
KEY_WAIT
GOTO 69
LABEL 69
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4214
MESSAGE "あ、話し込んじゃって\nごめんなさい。\nすぐ片付けるわね。"
KEY_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4215
MESSAGE "……あ、これ、\nとっておいてもいい？"
KEY_WAIT
OFF_CHAR 3
BG 176
SE_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
BG 0
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4216
MESSAGE "ふぅ、これで終わりね。"
KEY_WAIT
VOICE 4217
MESSAGE "それじゃ、ご飯の支度するわね。\n……あっ！"
KEY_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4218
MESSAGE "パン屋さんに焼き立てのパンを\nお願いしていたんだけど、\n取りに行くの忘れてたわ！"
KEY_WAIT
VOICE 4219
MESSAGE "どうしよう。取りに行ってると\n夕飯の準備が……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "考えるまでもない。\n私が取りにいけば済むことだな。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4220
MESSAGE "え？　でも……本当にいいの？\nじゃあ、悪いけどお願いね。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 74
LABEL 70
FLAG 1794, 1
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4221
MESSAGE "本当にいいの？\nじゃあ、私は隣の部屋にいるから\n何かあったら、読んでね。"
KEY_WAIT
OFF_CHAR 3
FACE 65535
OFF_FACE_WINDOW
MESSAGE "さて、さっさと片付けてしまうか。"
KEY_WAIT
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
MESSAGE "ふぅ、やっと終わったか。\n思ったよりも時間がかかって\nしまったな。"
KEY_WAIT
MESSAGE "そういえば、妻は何をしているの\nだろう？　気になった私は\n隣の部屋を覗いてみた。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4222
MESSAGE "……すー、すー。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "ソファに寄りかかるようにして、\nぐっすりと眠っている。"
KEY_WAIT
MESSAGE "朝から色々と忙しそうに\nしていたので疲れたのだろう。"
KEY_WAIT
MESSAGE "それに最近、夜も遅いし……"
KEY_WAIT
MESSAGE "もう少し眠らせておいて\nあげるとするか。"
KEY_WAIT
END 0
LABEL 71
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4223
MESSAGE "ん……おとう、さま……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
GOTO 42
LABEL 72
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4224
MESSAGE "ん……あなたぁ……\nくー、すー……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
GOTO 42
LABEL 73
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4225
MESSAGE "ぁん……だーりぃん……㍍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
GOTO 42
LABEL 74
BGM_STOP 30
FACE 65535
OFF_FACE_WINDOW
MESSAGE "妻に頼まれたパンを受け取り、\n家路を急ぐ。"
KEY_WAIT
MESSAGE "香ばしい焼き立てのパンの香りと\n両手に抱えた袋から伝わってくる\n温もり。"
KEY_WAIT
MESSAGE "なんでもないようなことが、\n不思議と幸せに感じられた。"
KEY_WAIT
BGM_PLAY 10
BG 284
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4226
MESSAGE "お帰りなさい♪"
KEY_WAIT
VOICE 4227
MESSAGE "あ、いい匂い㍍\nやっぱり注文しておいて\n正解だったわね。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4228
MESSAGE "じゃあ、すぐご飯に……\nあ、そうだ♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "何か面白いことでも思いついたのか\n妻はにんまりと口元に笑みを浮かべ\n楽しそうに告げた。"
KEY_WAIT
CHAR 0, 7
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4229
MESSAGE "……コホン、\nお帰りなさい、旦那様㍍"
KEY_WAIT
VOICE 4230
MESSAGE "ご飯にします？\nお風呂にします？\nそれとも……？"
SELECT 3, 75, "ご飯にします", 76, "お風呂にします", 77, "それとも……にします"
LABEL 75
FLAG 1795, 1
FACE 65535
OFF_FACE_WINDOW
MESSAGE "帰宅途中、ずっとパンの香りに\n胃を刺激されていたので、\n私は迷わず食事を選んだ。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4231
MESSAGE "はい♪\nそれじゃ、すぐに準備しますから、\nちょっと待っててくださいね。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 78
LABEL 76
FLAG 1796, 1
FACE 65535
OFF_FACE_WINDOW
MESSAGE "食事の前に汗を流して\nさっぱりするというのも\n捨てがたい。"
KEY_WAIT
MESSAGE "風呂に入ることにしよう。\n食事はそれからだ。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4232
MESSAGE "はい♪　それじゃ、お風呂に\n入っている間にご飯の支度して\nおきますね。"
KEY_WAIT
VOICE 4233
MESSAGE "あ、着替えとかはあとで\n持っていきますから。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 83
LABEL 77
FLAG 1797, 1
FACE 65535
OFF_FACE_WINDOW
MESSAGE "それとも……にします！\n私は男らしく宣言した。"
KEY_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4234
MESSAGE "あれ？　えーと……"
KEY_WAIT
VOICE 4235
MESSAGE "それじゃ、準備しますから\n部屋で待っててもらえます？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 92
LABEL 78
BGM_PLAY 10
BG 284
FACE 65535
OFF_FACE_WINDOW
MESSAGE "テーブルの上には、ほかほかと\n湯気を立てるシチューをはじめと\nしてさまざまな料理が並んでいた。"
KEY_WAIT
MESSAGE "さて、どれもうまそうだが、\nなにから手をつけようか。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4236
MESSAGE "今日のメインは、愛情たーっぷりの\n特製クリームシチューよ♪"
KEY_WAIT
VOICE 4237
MESSAGE "そのまま食べてもいいんだけど、\n買ってきてもらったパンにつけても\n美味しいのよ。"
KEY_WAIT
VOICE 4238
MESSAGE "というわけで、はい、あーん♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "差し出されたパンをぱくりと\n食べる。"
KEY_WAIT
CHAR 0, 7
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4239
MESSAGE "あんっ㌍\nもう、指まで口にしないでよ。"
KEY_WAIT
VOICE 4240
MESSAGE "……それでどう、美味しい？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "ふむ、表面はかりっとしていて、\n中はふわふわなパンに、濃厚な\nシチューがよく合っていて……"
KEY_WAIT
MESSAGE "……これはいける。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4241
MESSAGE "ほんと♪　よかったぁ。"
KEY_WAIT
VOICE 4242
MESSAGE "じゃあ、今度は食べさせて\nほしいな㍍"
KEY_WAIT
VOICE 4243
MESSAGE "ね、いいでしょ。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 258
SE_WAIT
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4244
MESSAGE "あーん。"
KEY_WAIT
VOICE 4245
MESSAGE "ねぇ、はやくぅ㍍"
KEY_WAIT
VOICE 4246
MESSAGE "……ん、美味しい㍍"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4247
MESSAGE "今度は私の番ね。\nはい、あーん㍍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4248
MESSAGE "ごちそうさまでした。"
KEY_WAIT
VOICE 4249
MESSAGE "ん～、少し食べ過ぎちゃった\nかしら。"
KEY_WAIT
END 0
LABEL 79
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4250
MESSAGE "あ、私、後片付けしちゃうから\nお父様は先にお風呂に入ってて。"
KEY_WAIT
GOTO 82
LABEL 80
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4251
MESSAGE "あ、私、後片付けしちゃうから\nあなたは先にお風呂に入ってて。"
KEY_WAIT
GOTO 82
LABEL 81
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4252
MESSAGE "あ、私、後片付けしちゃうから\nダーリンは先にお風呂に入ってて。"
KEY_WAIT
FACE 0
VOICE 4253
MESSAGE "なんか残念そうな顔してる～。\nもしかして、一緒に入りたい？"
KEY_WAIT
FACE 2
VOICE 4254
MESSAGE "だ～め㍍\n早く洗っちゃわないと、汚れが\n落ちなくなっちゃうんだから。"
KEY_WAIT
GOTO 82
LABEL 82
FACE 65535
OFF_FACE_WINDOW
MESSAGE "妻に促されて、風呂場へ向かう。"
KEY_WAIT
BG 176
MESSAGE "妻が入ってくるまで待とうかと\n思ったが、のぼせそうになったので\nあきらめた。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
GOTO 93
LABEL 83
BGM_PLAY 10
SE_PLAY 44
SE_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "身体を洗おうと湯船から\n立ち上がる。"
KEY_WAIT
MESSAGE "妻はというと、口の辺りまで湯船に\nつかり、視線を天井に向けていた。"
KEY_WAIT
MESSAGE "……どうしたのだろうか？"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 259
SE_WAIT
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4255
MESSAGE "……ん～、まだ、\nちょっと恥ずかしいかなって。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "子供のころから一緒に入浴していた\nので、今更、恥ずかしがらなくても\nいいと思うのだが……"
KEY_WAIT
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4256
MESSAGE "子どものころとは\nやっぱり違うわよ。"
KEY_WAIT
VOICE 4257
MESSAGE "私も色々と成長したし……って、\nもう、恥ずかしいっていってるのに\nジロジロ見るんだから。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "妻のすねたような視線を\n受け流しつつ、\n湯船から立ち上がる。"
KEY_WAIT
END 0
LABEL 84
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4258
MESSAGE "もう、お父様のいぢわる。"
KEY_WAIT
GOTO 87
LABEL 85
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4259
MESSAGE "あなたって、いぢわるね。"
KEY_WAIT
GOTO 87
LABEL 86
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4260
MESSAGE "もう、ダーリンのいぢわるぅ。"
KEY_WAIT
GOTO 87
LABEL 87
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4261
MESSAGE "あ、そうだ。\n背中流してあげましょうか？"
KEY_WAIT
VOICE 4262
MESSAGE "だから、あっち向いて、ね㌍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 260
SE_WAIT
VOICE 4263
MESSAGE "こんな感じでいい？"
KEY_WAIT
VOICE 4264
MESSAGE "もう少し強い方がいいのね。\nじゃあ、これくらい？"
KEY_WAIT
VOICE 4265
MESSAGE "うん、それじゃ、\n続きするわね。"
KEY_WAIT
VOICE 4266
MESSAGE "かゆい所あったら、\nいってね。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……………………"
KEY_WAIT
END 0
LABEL 88
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4267
MESSAGE "……ふぅ、\nお父様の背中って、大きいから\n洗うのも大変ね。"
KEY_WAIT
GOTO 91
LABEL 89
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4268
MESSAGE "……ふぅ、\nあなたの背中って、大きいから\n洗うのも大変ね。"
KEY_WAIT
GOTO 91
LABEL 90
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4269
MESSAGE "……ふぅ、\nダーリンの背中、\n大きいから洗うのも大変ね。"
KEY_WAIT
GOTO 91
LABEL 91
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4270
MESSAGE "それじゃ、流すわね。\n……きゃっ㌍"
KEY_WAIT
SPECIAL 20
FACE 65535
OFF_FACE_WINDOW
MESSAGE "っ㌍"
KEY_WAIT
MESSAGE "足を滑らせた妻が、\n背中に覆いかぶさってきた。"
KEY_WAIT
MESSAGE "タオル越しに感じられる\n柔らかな肢体に、心臓の鼓動が\n跳ね上がる。"
KEY_WAIT
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4271
MESSAGE "ごめんなさい。\n大丈……あ……㍍"
KEY_WAIT
VOICE 4272
MESSAGE "えっと……じゃあ、流すから\nあっち向いてて㍍"
KEY_WAIT
SE_PLAY 44
SE_WAIT
FACE 65535
OFF_FACE_WINDOW
BG 176
SE_WAIT
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
SPECIAL 22
BG 284
CHAR 0, 7
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4273
MESSAGE "ふぅ～、いいお湯だったわね。"
KEY_WAIT
VOICE 4274
MESSAGE "じゃあ、ご飯の用意するから、\nちょっと待っててね㍍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "上気した頬に笑みを浮かべると、\n妻はパタパタとスリッパを鳴らして\n部屋を出ていった。"
KEY_WAIT
MESSAGE "夕食は絶品だった。"
KEY_WAIT
MESSAGE "ただ、体力のつくものが\n多かった気がするが……\nまぁ、気のせいだろう。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 93
LABEL 92
BGM_PLAY 10
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 261
SE_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4275
MESSAGE "それじゃあ……いくわね。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "っ㌍"
KEY_WAIT
MESSAGE "敏感な箇所に与えられる\n強い刺激に思わず声が\n漏れそうになる。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4276
MESSAGE "ねぇ、これ、気持ちいい？"
KEY_WAIT
VOICE 4277
MESSAGE "我慢しているの？\nそれなら、もう少し強くしちゃおう\nかしら。"
KEY_WAIT
VOICE 4278
MESSAGE "うふふ♪"
KEY_WAIT
VOICE 4279
MESSAGE "ほら、我慢しないで、\n声出してもいいのよ㍍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "妻の指先がピアノを\n弾くかのような繊細なタッチで\n身体のあちこちに触れていく。"
KEY_WAIT
MESSAGE "動きが止まったかと思うと、\n次の瞬間、衝撃が身体を貫く。"
KEY_WAIT
MESSAGE "気を失いそうなほど強く、\nそして、鮮烈に与えられる刺激。"
KEY_WAIT
MESSAGE "必死に耐えていたが、\n刻一刻と限界が近づいてくる。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4280
MESSAGE "ふ～ん、まだ耐えるんだ。\nだったら……うふふふ♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "私は何か悪いことをしたの\nだろうか？　そんな覚えは\n微塵もないのだが……"
KEY_WAIT
MESSAGE "遠くなっていく意識を\n必死につなぎとめつつ、\n妻の責めにただ耐え続けた。"
KEY_WAIT
SPECIAL 22
BG 176
SE_WAIT
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
BG 284
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4281
MESSAGE "で、どうだったかしら、\n足つぼマッサージは？"
KEY_WAIT
VOICE 4282
MESSAGE "ナルサス先生に教えてもらったの。\n悪いところがあると、\n凄く痛くなるんですって。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "息も絶え絶えに、ソファに\nぐったりと寄りかかった。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4283
MESSAGE "今の感じだと胃の調子とか、\n悪そうね。一度、ナルサス先生に\n診てもらいましょうか？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "息を整えると、妻にソファに\n座るよう促し、告げた。"
KEY_WAIT
MESSAGE "次は私がやろう、と……"
KEY_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4284
MESSAGE "え？　わ、私はいいわよ㌍"
KEY_WAIT
VOICE 4285
MESSAGE "ひゃっ㌍"
KEY_WAIT
SPECIAL 20
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4286
MESSAGE "ちょ、ちょっと待って……"
KEY_WAIT
VOICE 4287
MESSAGE "きゃー㍍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 93
LABEL 93
MESSAGE "　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 262
SE_WAIT
BGM_PLAY 11
FACE 65535
OFF_FACE_WINDOW
MESSAGE "就寝前のひととき。"
KEY_WAIT
MESSAGE "寄り添うように座る妻から\n立ち上る、ほのかな石鹸の香りが\n鼻腔をくすぐる。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4288
MESSAGE "うふふ♪"
KEY_WAIT
END 0
LABEL 94
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4289
MESSAGE "ねぇ、お父様♪"
KEY_WAIT
GOTO 97
LABEL 95
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4290
MESSAGE "ねぇ、あなた♪"
KEY_WAIT
GOTO 97
LABEL 96
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4291
MESSAGE "ねぇ、ダーリン㍍"
KEY_WAIT
GOTO 97
LABEL 97
FACE 65535
OFF_FACE_WINDOW
MESSAGE "妻が身体を摺り寄せてくる。\nその姿は猫がごろごろと鳴きながら\n甘える仕草を連想させた。"
KEY_WAIT
MESSAGE "彼女の髪を優しくすきながら、\nどうしたのかと続きを促す。"
KEY_WAIT
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 4292
MESSAGE "ん？　呼んでみただけ㍍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "惚けた声で答える妻に、\n私は「そうか」とだけ答える。"
KEY_WAIT
MESSAGE "そして、いまだに猫のように\n甘える妻の顎に手を伸ばした。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4293
MESSAGE "あん、くすぐったいわ㍍"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4294
MESSAGE "私、猫じゃないわよ。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "くすぐったそうにしつつも、\n妻が上げる静止の声を無視して、\n尚も顎の下をくすぐる。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4295
MESSAGE "もう、それじゃあ……"
KEY_WAIT
VOICE 4296
MESSAGE "にゃ～㍍"
KEY_WAIT
VOICE 4297
MESSAGE "どう、これで満足？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "次の瞬間、いたずらに成功した\n子供のような笑みを浮かべる妻を、\n私は抱きしめていた。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4298
MESSAGE "きゃっ♪"
KEY_WAIT
VOICE 4299
FACE 6
MESSAGE "もう、びっくりするじゃない㍍"
KEY_WAIT
VOICE 4300
MESSAGE "……ねぇ、時間も遅いし、\nそろそろ寝ましょうか？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "私は無言のまま、妻を抱き上げた。"
KEY_WAIT
BG 176
SE_WAIT
MESSAGE "そして……"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
SE_WAIT
END 0