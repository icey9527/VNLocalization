LABEL 0
FLAG 1144, 1
BGM_STOP 30
BG 160
BGM_PLAY 32
CHAR 0, 9
FACE 8
MESSAGE_NAME "[娘の名前]"
VOICE 2045
MESSAGE "クライスさんに言われてきたけど、\nちょっと早く来すぎちゃったかなー"
KEY_WAIT
MESSAGE_NAME "[娘の名前]"
VOICE 2046
MESSAGE "あっクライスさん。\nでも、誰かとお話してる…"
KEY_WAIT
CHAR 0, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 2047
MESSAGE "あの人は、確かオズワルド大臣。\n何で、こんなところに？"
KEY_WAIT
MESSAGE_NAME "[娘の名前]"
VOICE 2048
MESSAGE "一体何をしているのかしら？"
KEY_WAIT
OFF_CHAR 3
FACE 65535
BG 176
FACE 43
MESSAGE_NAME "大臣"
MESSAGE "……そのことならば、心配ない。\n任せておけ。"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "これで、人間界はもっともっと\n発展する。\nいいことですよ。"
KEY_WAIT
FACE 43
MESSAGE_NAME "大臣"
MESSAGE "魔法石の力が必要だ。"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "はい。"
KEY_WAIT
OFF_FACE_WINDOW
FACE 65535
MESSAGE "　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　"
KEY_WAIT
BG 176
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2049
MESSAGE "話が終わったみたいね。"
KEY_WAIT
BG 84
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "やあ、来たね！\nこれが私の船だ。立派だろう？"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 728
MESSAGE "ええ……とても大きくて\n驚いちゃいました。"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "まだ他にも何隻か保有してるよ。\n今、航海中だからいないがね。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 729
MESSAGE "す、すごいなあ……"
KEY_WAIT
FACE 1
VOICE 730
MESSAGE "クライスさんってほんとに\nお金持ちだったんだ……"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "ハハハハ、これで信じて\nもらえたかな？"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2050
MESSAGE "ええ、\nところで、\nさっきお話してた人って…"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "ああ、新しい商売の話さ…\n君に話すわけには\nまだいかないがね。"
KEY_WAIT
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 2051
MESSAGE "そうですか…"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "もっと、商売を勉強したまえ。\n君には、その才能がある。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 2052
MESSAGE "えっ、わたしに？"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "ああ。僕は君が働いてるのを\n見ていたんだ。"
KEY_WAIT
MESSAGE "君には華がある。商売の世界で\nとても重要な事だ。"
KEY_WAIT
MESSAGE "今はいろいろな所で働いて、\n見聞を広めてみるといい。"
KEY_WAIT
MESSAGE "そして……早く僕らの世界に\n来たまえ。待っているよ。"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
BG 0
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 734
MESSAGE "ねえ、お父さん。\n今日ね、クライスさんって人から\nすごい物見せてもらっちゃった。"
KEY_WAIT
CHAR 0, 5
FACE 4
VOICE 735
MESSAGE "港にある大きな貿易船よ！"
KEY_WAIT
CHAR 0, 2
FACE 1
VOICE 736
MESSAGE "これからは貴族の時代から\n商人の時代になるんだって！\n本当かなぁ……？"
SELECT 3, 1, "肯定する", 2, "否定する", 3, "商人は嫌いだと言う"
LABEL 1
FLAG 1145, 1
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 737
MESSAGE "お父さんもそう思うんだ。"
KEY_WAIT
CHAR 0, 7
FACE 6
VOICE 738
MESSAGE "剣や魔法より座学中心に勉強した方\nがいいのかなぁ。私には商才が\nあるらしいし……うーん……"
KEY_WAIT
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 2
FLAG 1146, 1
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 739
MESSAGE "あは、そんなに簡単に世の中は\n変わらないよね。"
KEY_WAIT
CHAR 0, 2
FACE 1
VOICE 740
MESSAGE "でも、あの船はほんとに\nすごかったな。お父さんも見たら\nビックリするよ、きっと！"
KEY_WAIT
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 3
FLAG 1147, 1
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 741
MESSAGE "そう？　お父さんみたいに真面目な\n人から見ると、少しうさん臭く\n感じちゃうのかな。"
KEY_WAIT
CHAR 0, 9
FACE 8
VOICE 742
MESSAGE "大丈夫、心配しないで。\n欲に目がくらんだりしないように\n気をつけて接するから。"
KEY_WAIT
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 4
FLAG 759, 1
LABEL 5
FLAG 760, 1
BGM_STOP 30
BGM_PLAY 32
BG 84
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "やあ、来たね！\nこれが私の船だ。立派だろう？"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 728
MESSAGE "ええ……とても大きくて\n驚いちゃいました。"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "まだ他にも何隻か保有してるよ。\n今、航海中だからいないがね。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 729
MESSAGE "す、すごいなあ……"
KEY_WAIT
FACE 1
VOICE 730
MESSAGE "クライスさんってほんとに\nお金持ちだったんだ……"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "ハハハハ、これで信じて\nもらえたかな？"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 731
MESSAGE "う、うん……\nこんな物見せられたら……"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "そう！これからは商人の時代だよ。\n貴族の時代はもう終わりだ。"
KEY_WAIT
MESSAGE "これから世の中を動かすのは私達\n商人だ。そして、その象徴が\nこの船ってわけさ。"
KEY_WAIT
FACE 8
MESSAGE_NAME "[娘の名前]"
VOICE 732
MESSAGE "これからは商人の時代……か。"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "君には見どころがある。\n頑張り次第で、こんな船だって\n持てるようになるさ。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 733
MESSAGE "えっ？　私が……？"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "ああ。僕は君が働いてるのを\n見ていたんだ。"
KEY_WAIT
MESSAGE "君には華がある。商売の世界で\nとても重要な事だ。"
KEY_WAIT
MESSAGE "今はいろいろな所で働いて、\n見聞を広めてみるといい。"
KEY_WAIT
MESSAGE "そして……早く僕らの世界に\n来たまえ。待っているよ。"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
BG 0
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 734
MESSAGE "ねえ、お父さん。\n今日ね、クライスさんって人から\nすごい物見せてもらっちゃった。"
KEY_WAIT
CHAR 0, 5
FACE 4
VOICE 735
MESSAGE "港にある大きな貿易船よ！"
KEY_WAIT
CHAR 0, 2
FACE 1
VOICE 736
MESSAGE "これからは貴族の時代から\n商人の時代になるんだって！\n本当かなぁ……？"
SELECT 3, 6, "肯定する", 7, "否定する", 8, "商人は嫌いだと言う"
LABEL 6
FLAG 761, 1
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 737
MESSAGE "お父さんもそう思うんだ。"
KEY_WAIT
CHAR 0, 7
FACE 6
VOICE 738
MESSAGE "剣や魔法より座学中心に勉強した方\nがいいのかなぁ。私には商才が\nあるらしいし……うーん……"
KEY_WAIT
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 7
FLAG 762, 1
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 739
MESSAGE "あは、そんなに簡単に世の中は\n変わらないよね。"
KEY_WAIT
CHAR 0, 2
FACE 1
VOICE 740
MESSAGE "でも、あの船はほんとに\nすごかったな。お父さんも見たら\nビックリするよ、きっと！"
KEY_WAIT
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 8
FLAG 763, 1
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 741
MESSAGE "そう？　お父さんみたいに真面目な\n人から見ると、少しうさん臭く\n感じちゃうのかな。"
KEY_WAIT
CHAR 0, 9
FACE 8
VOICE 742
MESSAGE "大丈夫、心配しないで。\n欲に目がくらんだりしないように\n気をつけて接するから。"
KEY_WAIT
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 9
FLAG 948, 1
LABEL 10
FLAG 949, 1
BGM_PLAY 31
SE_PLAY 14
BG 159
CHAR 2, 1
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "やぁ、来たね。さぁ、行こうか。"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1540
MESSAGE "えっ、どこにですか？"
KEY_WAIT
CHAR 2, 6
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "この市場の中だよ。\n心配しないで付いてきたまえ。"
KEY_WAIT
SE_STOP
OFF_CHAR 2
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
BG 176
BG 159
SE_PLAY 14
CHAR 2, 1
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "ほら、この店が私の店だ。"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1541
MESSAGE "えっ、この店は㌍"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "そう、この間までは違った。\n買収したんだよ。"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1542
MESSAGE "買収㌍\nでも……"
KEY_WAIT
CHAR 2, 8
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "ああ、確かに働いている人達は\nこの前と同じだ。でも、私の店\nなんだ。"
KEY_WAIT
CHAR 2, 6
MESSAGE "そのうち、この市場全体を私の\nものにしてみせる。"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1543
MESSAGE "えーーーっ㌍"
KEY_WAIT
CHAR 2, 6
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "信用してないな。\nよかろう。１ヵ月後に街道まで\n来たまえ。港に私の交易船が着く。"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1544
MESSAGE "えっ、船を持っているんですか㌍"
KEY_WAIT
CHAR 2, 9
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "貿易こそ富を生むんだ。\n最初の船を手に入れるのには\n苦労したけどね。"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1545
MESSAGE "すごいお金持ちなんですね。"
KEY_WAIT
CHAR 2, 9
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "ようやく分かってくれたか。\n自分で働いているうちはダメだ。\n人と金に働かさないとな。"
KEY_WAIT
CHAR 2, 6
MESSAGE "君は見どころがある。商売をやる\nならいろいろ教えてあげるよ。\nハッハッハッハッハ。"
KEY_WAIT
CHAR 2, 9
FACE 8
MESSAGE_NAME "[娘の名前]"
VOICE 1546
MESSAGE "（尊大でイヤな人……\nでも、彼の言う大きな商売って\nちょっと見てみたい。）"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 0
LABEL 11
FLAG 946, 1
LABEL 12
FLAG 947, 1
BGM_PLAY 31
SE_PLAY 14
BG 159
CHAR 2, 1
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "あっ、キミ？"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1535
MESSAGE "えっ、私ですか？"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "ここらへんで、よく見かけるね。\n商売に興味あるのかい？"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1536
MESSAGE "えっ……ええ。\nよく仕事させてもらってます。"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "だめだ、だめだ。"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1537
MESSAGE "えっ㌍"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
CHAR 2, 8
MESSAGE "売り子をやったってビジネスは\nいつまで経っても覚えられないよ。"
KEY_WAIT
CHAR 2, 1
MESSAGE "本当の商売に興味があれば、\nまたここで会おう。"
KEY_WAIT
FACE 65535
CHAR 2, 9
FACE 8
MESSAGE_NAME "[娘の名前]"
VOICE 1538
MESSAGE "何、あの人……"
KEY_WAIT
CHAR 2, 3
FACE 2
VOICE 1539
MESSAGE "失礼な人！"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 0
LABEL 13
FLAG 815, 1
LABEL 14
FLAG 816, 1
BGM_STOP 30
BGM_PLAY 22
SE_PLAY 1
BG 163
SE_WAIT
SE_PLAY 3
CHAR 2, 1
SE_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1044
MESSAGE "こんにちは……"
KEY_WAIT
SE_PLAY 32
SE_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1045
MESSAGE "きゃあ！　な、何？"
KEY_WAIT
FACE 65535
MESSAGE_NAME "メイド"
MESSAGE "いらっしゃいませ[娘の名前]様。"
LINE_FEED
CHAR 2, 8
MESSAGE "お持ちしておりました。"
KEY_WAIT
MESSAGE "旦那様がお待ちです。\nこちらへどうぞ。"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1046
MESSAGE "えっ？　えっ？\nだ、旦那様？\nここってメイド酒場じゃ……"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "やあ、[娘の名前]さん！"
LINE_FEED
CHAR 2, 5
MESSAGE "待っていたよ！"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1047
MESSAGE "あっ！　ク、クライスさん！"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
BG 105
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "ハハハッ！\n君を驚かせたくてね！\nどうだい？　すごいだろう？"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1048
MESSAGE "あ、あの……\nこれって……"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "ああ、言ってなかったね。\n私がこのメイド酒場を\n買収したんだよ。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1049
MESSAGE "ば、買収㌍"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "そういうこと。"
KEY_WAIT
MESSAGE "つまり、今日から私はここの\nオーナー！　まさに\n「旦那様」ってわけさ！"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1050
MESSAGE "だ、旦那様……\nほ、本物の……？"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "すごいだろう？"
KEY_WAIT
MESSAGE "ボクのビジネスセンスが、この\n商売は儲かるー！ってビンビン\n反応しちゃってね。"
KEY_WAIT
MESSAGE "そこにボクの資金を投入すれば、\nもう成功まちがいなし！"
KEY_WAIT
MESSAGE "明るい娯楽に飢えた人たちに\n憩いと安らぎを与える清楚な\nメイド達！　実にいいじゃないか！"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1051
MESSAGE "は、はあ……"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "で、今日はリニューアル記念\nパーティーって事になってるんだ。"
KEY_WAIT
MESSAGE "じゃんじゃんやってくれたまえ！\nおおいに飲み、食べ、そして\n……ビジネスの話をしよう！"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1052
MESSAGE "ビ、ビジネス、ですか㌍"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "もう貴族たちの時代は終わりだ。\n私達、商人の時代が来る。\nいや来てる！"
KEY_WAIT
MESSAGE "ボクのビジネスセンスが告げて\nいるんだ。キミを得ることが、\nさらなる発展につながると！"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1053
MESSAGE "えっ㌍　な、なんで\nそうなっちゃうんですか！"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "ボクと一緒に商売をすれば\nそれもわかるさ！"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1054
MESSAGE "そんなあ……"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "もしくは……うん、ボクの\n私生活のパートナーになると\nいう手もあるな。それもいい！"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1055
MESSAGE "えっ、えーっ㌍\nちょっと㌍"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "アハハ、驚かしてしまったね。"
KEY_WAIT
MESSAGE "そちらは冗談だよ。\n今のところは……ね。"
KEY_WAIT
MESSAGE "ボクは強引にキミを\n巻き込むつもりはないんだ。"
KEY_WAIT
MESSAGE "戦争だって、いつかは終わる。\nボクたちの時代が来る。"
KEY_WAIT
MESSAGE "よく考えるんだ。身分だけ高くて\n刺激のない貴族婦人なんかより、\nずっと刺激的な人生が待っている。"
KEY_WAIT
MESSAGE "キミなら、理解できるはずだ。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1056
MESSAGE "クライスさん……"
KEY_WAIT
FACE 89
MESSAGE_NAME "クライス"
MESSAGE "待っている。いつでも大歓迎だ。\n乾杯！"
KEY_WAIT
SE_PLAY 33
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0