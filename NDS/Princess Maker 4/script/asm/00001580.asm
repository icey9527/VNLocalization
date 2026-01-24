LABEL 0
SPECIAL 16
BG 236
FACE 65535
OFF_FACE_WINDOW
MESSAGE "青い海　白い砂浜\n燦々と輝く太陽――"
KEY_WAIT
MESSAGE "誰でも思いつくような陳腐な表現\nだが、正しく、その言葉どおりの\n光景が目の前に広がっていた。"
KEY_WAIT
MESSAGE "ここが避暑地として知られるように\nなってから日が浅く、人の姿は\nまばらにあるばかり。"
KEY_WAIT
MESSAGE "避暑に来たというのに人が多くて\nろくに遊べないようでは興ざめなの\nで、今の状況は嬉しい限りだ。"
KEY_WAIT
MESSAGE "もっともこれだけの場所だ。\n遠からず、人が押し寄せるように\nなるだろう。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
BG 0
BGM_PLAY 5
SPECIAL 19
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 3848
MESSAGE "あ～つ～い～。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "習い事から帰ってくるなり、\n娘はそう口にしてイスにぐったりと\n座り込んだ。"
KEY_WAIT
MESSAGE "確かに最近の暑さは厳しい。\nそれに加え、アルバイトや習い事で\n疲れが溜まっているようだし……"
KEY_WAIT
MESSAGE "幸い、懐具合に余裕があるので、\nどこか避暑地に出かけるのも\nいいかもしれない。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3849
MESSAGE "ホント？\nやったぁ！"
KEY_WAIT
OFF_CHAR 3
FACE 65535
OFF_FACE_WINDOW
MESSAGE "私がバカンスに行くことを告げると\n娘はイスから飛び上がって、\n喜びの声を上げた。"
KEY_WAIT
MESSAGE "さて、どこに行くとしようか？\nあまり人が多い場所では落ち着いて\n遊ぶことが出来ないし……"
KEY_WAIT
MESSAGE "そんなことを考えていると、\nキューブがやってきて、手紙を\n差し出してきた。"
KEY_WAIT
MESSAGE "手紙は古い友人からで、冒険者を\n廃業し、海の近くで宿屋を\n始めたという知らせだった。"
KEY_WAIT
MESSAGE "タイミングが良すぎて、\n何かご都合主義のような気もするが\n……まぁ、いい。"
KEY_WAIT
MESSAGE "久しぶりに友人の顔を見るのも\n悪くない。行き先はそこにしよう。"
KEY_WAIT
BG 176
SPECIAL 18
BGM_PLAY 36
BG 236
MESSAGE "こうして、この海にやってきたと\nいうわけだ。"
KEY_WAIT
MESSAGE "そして、友人に挨拶したあと、\n色々と積もる話があったのだが、\n娘に連れ出されてしまった。"
KEY_WAIT
MESSAGE "まぁ、話はあとでも出来る。\n今はこのひとときを楽しむことに\nしよう。"
KEY_WAIT
MESSAGE "……ところで、\n娘はまだ来ないのだろうか？"
KEY_WAIT
MESSAGE "水着に着替えるくらいで\nそれほど時間がかかるとは\n思えないのだが……"
KEY_WAIT
GOTO 1
LABEL 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3850
MESSAGE "お父さ～ん！"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "宿の方から娘の声が聞こえてくる。"
KEY_WAIT
MESSAGE "声の元へ視線をやると\n髪をなびかせ、こちらへと\n走ってくる娘の姿が見えた。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3851
MESSAGE "お待たせ。"
KEY_WAIT
VOICE 3852
MESSAGE "お父さん着替えるの早いね。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "男の着替えなんて、\nそんなものである。"
KEY_WAIT
MESSAGE "それよりも、どうしてこんなに\n時間がかかったのかを尋ねる。"
KEY_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3853
MESSAGE "え？　時間がかかりすぎ？"
KEY_WAIT
CHAR 0, 1
FACE 0
VOICE 3854
MESSAGE "そんなことないよ。\n女の子だもん。\nこれくらい普通だよ。"
KEY_WAIT
VOICE 3855
MESSAGE "ねぇ、それよりこの水着どう？\n似合ってるかな？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "そういうと、娘は手を腰にあてて\n扇情的なポーズをとった。"
KEY_WAIT
MESSAGE "……そういう仕草はまだ早いと\n思いつつも、私は……"
SELECT 3, 2, "似合う", 3, "少し派手じゃないか", 4, "う～ん"
LABEL 2
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3856
MESSAGE "ホント？\n良かった。"
KEY_WAIT
VOICE 3857
MESSAGE "これ、テレサさんのお店の\n新作なの。"
KEY_WAIT
VOICE 3858
MESSAGE "ちょっと高かったけど、\n奮発して、正解だったわね♪"
KEY_WAIT
CHAR 0, 1
FACE 0
VOICE 3859
MESSAGE "ちなみにこれって、水にぬれても、\n全然透けたりしないのよ。"
KEY_WAIT
VOICE 3860
MESSAGE "生地を染めるのに\nちょっと変わった海草を\n使ってるんだって。"
KEY_WAIT
CHAR 0, 2
FACE 1
VOICE 3861
MESSAGE "名前は……\nえ～と、忘れちゃった♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "照れくさそうに舌を出して\nおどける娘の姿に、私は自然と\n頬が緩むのを感じていた。"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 5
LABEL 3
CHAR 0, 9
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3862
MESSAGE "そう？\nこれくらい普通だと思うんだけど。"
KEY_WAIT
VOICE 3863
MESSAGE "テレサさんのお店にあったのは、\nみんなこんな感じだったし。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "テレサの店というといつも娘の服を\n買っているところか……"
KEY_WAIT
MESSAGE "……ふむ。少し考えた方が\nいいかもしれないな。"
KEY_WAIT
MESSAGE "私がそんなことを考えていること\nなどつゆも知らず、娘は楽しそうに\n水着について語り始めた。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3864
MESSAGE "これね。\nテレサさんのお店の新作なの。"
KEY_WAIT
VOICE 3865
MESSAGE "お父さんは派手だっていうけど\n今はこういうのが流行ってるのよ。"
KEY_WAIT
VOICE 3866
MESSAGE "それに、生地を染めるのに\n変わった海草を使ってて、\nぬれても透けないから人気なの。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_CHAR 3
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 5
LABEL 4
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3867
MESSAGE "あれ？　もしかして似合ってない？"
KEY_WAIT
VOICE 3868
MESSAGE "折角、テレサさんの新作を\n買ったのになぁ。"
KEY_WAIT
CHAR 0, 8
FACE 7
VOICE 3869
MESSAGE "水で透けないように変わった海草で\n生地を染めてるとかで、\n結構高かったんだけど……"
KEY_WAIT
VOICE 3870
MESSAGE "別のにすれば良かったかな。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "水着の肩紐をうりうりと\nいじりながら、娘は不満そうに\n口を尖らせた。"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 5
LABEL 5
BG 236
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3871
MESSAGE "あ、お父さん。\nお願いがあるんだけどいい？"
KEY_WAIT
VOICE 3872
MESSAGE "日焼け止め塗りたいんだけど、\n手が届かないから背中の方、\n塗ってほしいの。"
KEY_WAIT
CHAR 0, 2
FACE 1
VOICE 3873
MESSAGE "ね、いいでしょ？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……私が塗るのか？"
KEY_WAIT
MESSAGE "気恥ずかしい想いに囚われかけたが\n相手は娘だ。あまり気にしない方が\nいいだろう。"
KEY_WAIT
MESSAGE "了承の意を示すと、娘は日焼け止め\nの入ったビンを手渡し、砂浜に\n敷いたシートにうつぶせになった。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 238
SE_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3874
MESSAGE "それじゃぁ、お願いね。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "さて、ではどこから塗ろうか？"
SELECT 3, 6, "肩の辺りを重点的に", 7, "まずは背中だろう", 8, "足だな"
LABEL 6
FACE 65535
OFF_FACE_WINDOW
MESSAGE "では、肩の辺りを……"
KEY_WAIT
MESSAGE "ぬりぬり"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3875
MESSAGE "ふんふふ～ん♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "ぬりぬり"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3876
MESSAGE "ふふふふ～ん♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "ぬりぬり"
KEY_WAIT
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 3877
MESSAGE "ふふ～……ん？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "ぬりぬり\nぬりぬり"
KEY_WAIT
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 3878
MESSAGE "…………"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "ぬりぬり\nぬりぬり"
KEY_WAIT
MESSAGE "さらにぬりぬり"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3879
MESSAGE "お、お父さん？\nそんなに肩ばっかり塗らなくて\nいいよ㌍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……怒られてしまった。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 9
LABEL 7
FACE 65535
OFF_FACE_WINDOW
MESSAGE "透けるように白い、娘の柔肌に\nゆっくりと手を伸ばす。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3880
MESSAGE "ん～♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "心地よさそうに目を細め、\n娘が鼻歌を歌っている。"
KEY_WAIT
MESSAGE "それを聞きながら、塗り残しの\nないように、丁寧に日焼け止めを\n塗っていく。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 9
LABEL 8
FACE 65535
OFF_FACE_WINDOW
MESSAGE "健康のために運動をするよう\nいい含めていた為か、\n引き締まった身体つきをしている。"
KEY_WAIT
MESSAGE "私はそのすらりとした足に向かって\nおもむろに手を伸ばした。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3881
MESSAGE "ひゃっ㌍"
KEY_WAIT
VOICE 3882
MESSAGE "あ、ご、ごめん。\nいきなり足にきたから\nびっくりしちゃって。"
KEY_WAIT
FACE 0
VOICE 3883
MESSAGE "でも、こういう場合って\n足じゃなくて背中からじゃない？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "…………………………"
KEY_WAIT
MESSAGE "娘の希望に沿うように\n改めて背中に手を伸ばした。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 9
LABEL 9
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
BG 236
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3884
MESSAGE "お父さん、ありがと。"
KEY_WAIT
VOICE 3885
MESSAGE "じゃぁ、前の方も塗るから\nビンを返して。"
KEY_WAIT
VOICE 3886
MESSAGE "ん？　どうしたの？"
KEY_WAIT
CHAR 0, 2
FACE 1
VOICE 3887
MESSAGE "あっ、もしかして前の方も\n塗りたいの？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "チェシャ猫のような笑みを浮かべて\nこちらを見つめてくる娘に対し、\n私は……"
SELECT 2, 10, "慌ててビンを返す", 11, "男らしく頷く"
LABEL 10
FACE 65535
OFF_FACE_WINDOW
MESSAGE "ビンを取り落としそうになりながら\n慌てて返した。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3888
MESSAGE "お父さん、照れてるのー？"
KEY_WAIT
VOICE 3889
MESSAGE "アハハ、かーわいい♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "娘は笑いすぎて苦しいのか、\n目じりに涙を浮かべている。"
KEY_WAIT
MESSAGE "……少し悔しい。"
KEY_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3890
MESSAGE "ねえ、お父さん。\nさっき宿のおじさんから\nスイカもらってたよね。"
KEY_WAIT
VOICE 3891
MESSAGE "じゃあさ、\nそれでスイカ割りしようよ♪"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_CHAR 3
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 12
LABEL 11
FACE 65535
OFF_FACE_WINDOW
MESSAGE "男らしく頷いた。"
KEY_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3892
MESSAGE "え㌍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "もちろん、冗談だ。\nあまりからかわれるのも面白くない\nので頷いてみたのだが……"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3893
MESSAGE "ちょ、お、お父さん㌍\nじょ、冗談だよね？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "効果はてき面だったようだ。\n面白いくらいにうろたえている。"
KEY_WAIT
CHAR 0, 7
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 3894
MESSAGE "で、で、で、でも、\nお父さんだったら……"
KEY_WAIT
VOICE 3895
MESSAGE "って、わーー！\n何いってるの、わたし㌍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "少々、不穏な発言が聞こえたような\n気がするが……まぁ、いい。"
KEY_WAIT
MESSAGE "このままでは埒が明かないので\nそろそろ止めるとするか。"
KEY_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3896
MESSAGE "うー、なんか悔しい。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "からかわれたのが悔しいのか、\n娘はプリプリと頬を膨らませて、\n海の中へ入っていった。"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 17
LABEL 12
BGM_PLAY 21
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3897
MESSAGE "これでよし、と。"
KEY_WAIT
VOICE 3898
MESSAGE "お父さん、見える？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "声の方向から、私の正面に\n立っているであろう娘に向かって、\n首を横に振って答えた。"
KEY_WAIT
MESSAGE "タオルを何重にもぐるぐると巻いて\n目隠しをされたのだ。\n見えようはずもない。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3899
MESSAGE "うん、見えないみたいね。"
KEY_WAIT
VOICE 3900
MESSAGE "それじゃ、１０回回ったら\nスタートね。"
KEY_WAIT
VOICE 3901
MESSAGE "じゃあ、いくよ。\nい～ち、に～い、さ～ん……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "娘の声にあわせ、\nその場でぐるぐると回る。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3902
MESSAGE "……は～ち、きゅ～う、じゅう！"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "一線から退いたとはいえ、\n元々、身体は鍛えている。"
KEY_WAIT
MESSAGE "これくらいで目を回すような\nやわな平衡感覚は持ち合わせて\nいない。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3903
MESSAGE "あれ？　普通に歩いてる。\n回したりなかったのかなぁ。"
KEY_WAIT
FACE 0
VOICE 3904
MESSAGE "あ、お父さん、もうちょっと右よ。"
SELECT 3, 13, "右に曲がる", 14, "まっすぐ進む", 15, "左に曲がる"
LABEL 13
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3905
MESSAGE "ああ、行きすぎ、行きすぎ！\n少し左よ。"
KEY_WAIT
VOICE 3906
MESSAGE "……うん、そう、\nそのまままっすぐ。"
KEY_WAIT
VOICE 3907
MESSAGE "そう、そこ！"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "娘の声に従い、棒を振り下ろす。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3908
MESSAGE "わっ㌍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "ふむ、手ごたえはあったが……"
KEY_WAIT
BG 236
FACE 65535
OFF_FACE_WINDOW
MESSAGE "目隠しを外し、足元に視線をやると\nそこにはキレイにふたつに切れた\nスイカがあった。"
KEY_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3909
MESSAGE "ど、どうしたら棒でスイカが\n切れちゃうの㌍"
KEY_WAIT
VOICE 3910
MESSAGE "お父さん、すごすぎるよ。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……少々本気を出しすぎたか。"
KEY_WAIT
MESSAGE "興奮して詰め寄ってくる娘を\nなだめながら、少しばかり\nやりすぎたかと反省する。"
KEY_WAIT
MESSAGE "……まぁ、娘に尊敬のまなざしで\n見つめられるのは、悪くない\n気分だが。"
KEY_WAIT
MESSAGE "追記\nスイカは美味しかった。"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 16
LABEL 14
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……ひっかけだな。"
KEY_WAIT
MESSAGE "そう判断した私は、\nまっすぐ進むことにした。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3911
MESSAGE "そっちじゃないよ。\n右よ、右！"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……いや、ここだ。\n長年、戦士として鍛えてきた\n勘がそういっている。"
KEY_WAIT
MESSAGE "私は力の限り、棒を振り下ろした。"
KEY_WAIT
MESSAGE "……が、スイカを叩く手ごたえは\nなかった。"
KEY_WAIT
BG 236
CHAR 0, 3
FACE 2
MESSAGE_NAME "[娘の名前]"
VOICE 3912
MESSAGE "もう、なんで私のいうこと\n聞いてくれないの。"
KEY_WAIT
CHAR 0, 1
FACE 0
VOICE 3913
MESSAGE "まぁ、いいわ。\n今度は私がやるからね。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "娘は棒とタオルを受け取ると\nスタスタと離れていった。"
KEY_WAIT
OFF_CHAR 3
MESSAGE "結果だが……\nスイカは美味しかった、\nとだけいっておこう。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 16
LABEL 15
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……ひっかけだな。"
KEY_WAIT
MESSAGE "そう判断した私は、おもむろに\n進路を左に変えた。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3914
MESSAGE "え㌍\nちょ、ちょっと、そっちは違うよ！"
KEY_WAIT
VOICE 3915
MESSAGE "そこはダメだってば㌍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……いや、ここだ。\n長年、戦士として鍛えてきた\n勘がそういっている。"
KEY_WAIT
MESSAGE "私は力の限り、棒を振り下ろした。"
SE_PLAY 26
SPECIAL 20
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3916
MESSAGE "あー㌍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "ボグッという鈍い感触が\n棒を握る手に伝わってくる、\nが……"
KEY_WAIT
MESSAGE "スイカにしては\n感触が違うような……"
KEY_WAIT
BG 236
MESSAGE "目隠しを外すと、\n視界に入ってきたのは\n頭を抱える娘と……"
KEY_WAIT
MESSAGE "頭に巨大なコブを作って倒れ伏す、\n知人の姿だった……"
KEY_WAIT
SPECIAL 19
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
BG 0
FACE 65535
OFF_FACE_WINDOW
MESSAGE "結局、知人が入院してしまったため\nバカンスどころの話ではなくなって\nしまった。"
KEY_WAIT
MESSAGE "今更だが、娘のいうことを\n信じておけば良かったと思う。"
KEY_WAIT
MESSAGE "それにしても……"
KEY_WAIT
CHAR 0, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 3917
MESSAGE "……お父さんのばか。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "娘の視線がいたい……"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
END 0
LABEL 16
BGM_PLAY 5
BG 236
FACE 65535
OFF_FACE_WINDOW
MESSAGE "スイカ割りを満喫したあと、\n娘とふたりで泳ぎを楽しんでいた。"
KEY_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3918
MESSAGE "ねぇ、お父さん。"
KEY_WAIT
VOICE 3919
MESSAGE "お腹すかない？\nもうお昼みたいだし。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "空を見上げて、太陽の位置を\n確認する。"
KEY_WAIT
MESSAGE "……ふむ、確かに。"
KEY_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3920
MESSAGE "ね？\n一度、宿に戻ろう。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_CHAR 3
BG 176
MESSAGE "　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3921
MESSAGE "あ、すいませーん。\nデザートにカキ氷ひとつ\nください。"
KEY_WAIT
VOICE 3922
MESSAGE "あ、お父さんも食べる？"
KEY_WAIT
VOICE 3923
MESSAGE "それじゃ、ふたつで。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 239
SE_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3924
MESSAGE "冷たくて美味しい～☆"
KEY_WAIT
VOICE 3925
MESSAGE "さっき、ここのおじさんに\n聞いたんだけど、これ、魔法で\n作った氷を使ってるんだって。"
KEY_WAIT
VOICE 3926
MESSAGE "カイ師範にお願いして、\n氷の魔法を教えてもらおうかな。"
KEY_WAIT
VOICE 3927
MESSAGE "そうすれば、うちでカキ氷が\n食べられるし。\nね、いいと思わない？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "これが家で食べられるのか……\nふむ、いいかもしれないな。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3928
MESSAGE "でしょ♪\n戻ったら早速、師範のところに\n行ってみるね。"
KEY_WAIT
VOICE 3929
MESSAGE "でも、その前に……\nすいませーん、カキ氷\nもうひとつくださーい。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "いくら美味だとはいえ、\n食べ過ぎるのはよくないと\n思うのだが……"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3930
MESSAGE "大丈夫よ。これくらいじゃ、\nお腹こわしたりしないわ。"
KEY_WAIT
FACE 1
VOICE 3931
MESSAGE "ん～♪　おいしい～。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 240
SE_WAIT
FACE 7
VOICE 3932
MESSAGE "はう！？"
KEY_WAIT
VOICE 3933
MESSAGE "あ、あ、頭が……\n……キーンって……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "頭を抑え、もだえる娘の姿に\n自然と溜息が出てきた。"
KEY_WAIT
FACE 3
MESSAGE_NAME "[娘の名前]"
VOICE 3934
MESSAGE "あぅぅぅ……"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
MESSAGE "　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　"
KEY_WAIT
SE_WAIT
GOTO 18
LABEL 17
BGM_PLAY 36
BG 236
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3935
MESSAGE "お父さん、こっちよー！"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "沖の方から娘の声が\n聞こえてくる。"
KEY_WAIT
MESSAGE "どうやら機嫌は元に\n戻ったようだな。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3936
MESSAGE "こっちは気持ちいいよー♪\n早くおいでよー！"
KEY_WAIT
VOICE 3937
MESSAGE "この下、魚がいっぱいいるのよ。"
KEY_WAIT
BGM_STOP 30
FACE 65535
OFF_FACE_WINDOW
MESSAGE "娘の声に急かされるように\n海へ足を向けた。その時――"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3938
MESSAGE "きゃあっ㌍"
KEY_WAIT
BGM_PLAY 28
FACE 65535
OFF_FACE_WINDOW
MESSAGE "悲鳴を残し、娘の姿が\n波の合間に消えた。"
KEY_WAIT
MESSAGE "先ほど、からかわれた\n仕返しに私を脅かそうとして\nいるのだろうか？"
KEY_WAIT
MESSAGE "一瞬、そんな考えが頭をよぎったが\n娘が浮かび上がってくる様子は\nなかった。"
KEY_WAIT
MESSAGE "……まさか㌍"
KEY_WAIT
BG 176
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
BG 236
MESSAGE "不幸中の幸いか、海に潜って\nすぐに娘を見つけることができた。"
KEY_WAIT
MESSAGE "しかし、娘は息をしていなかった。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 241
SE_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "私はぐったりと脱力した娘の身体を\n浜に横たわらせ、血の気の失せた\n唇に口づけ、息を吹き込んだ。"
KEY_WAIT
MESSAGE "自分の息が切れそうになるまで\n懸命に息を吹き込み続ける。\nそして――"
KEY_WAIT
BGM_PLAY 37
FACE 3
MESSAGE_NAME "[娘の名前]"
VOICE 3939
MESSAGE "……んっ……けほ……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 242
SE_WAIT
VOICE 3940
MESSAGE "……おとう……さん？"
KEY_WAIT
SPECIAL 20
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3941
MESSAGE "きゃあっ！"
KEY_WAIT
FACE 6
VOICE 3942
MESSAGE "お、お、お、お父さん㌍\nわ、私たち親子なんだよ。\nそ、それなのにキスなんて！"
KEY_WAIT
VOICE 3943
MESSAGE "……って、あれ？\nここ、どこ？"
KEY_WAIT
BG 236
CHAR 0, 1
FACE 0
VOICE 3944
MESSAGE "そういえば、私……\n海で泳いでて……それで……\n……ああっ！"
KEY_WAIT
CHAR 0, 5
FACE 4
VOICE 3945
MESSAGE "私、おぼれたんだ！\nそ、それじゃ、今のって\nキスじゃなくて……㌍"
KEY_WAIT
CHAR 0, 8
FACE 7
VOICE 3946
MESSAGE "ご、ごめんなさい。\n勘違いしちゃって！"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "気にしなくていいといいながら\n娘の頭をなでてやる。"
KEY_WAIT
MESSAGE "一時はどうなることかと\n思ったが、無事で何よりだ。"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 3947
MESSAGE "本当にごめんね。"
KEY_WAIT
CHAR 0, 7
FACE 6
VOICE 3948
MESSAGE "……でも、私、\nはじめてだったんだよ……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "何か娘が囁いたようだが、\n波の音にかき消されてしまい、\n私の耳に届くことはなかった。"
KEY_WAIT
MESSAGE "それよりもこのあとの予定だが、\n今日は大事をとって\n宿に戻った方がいいだろう。"
KEY_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 3949
MESSAGE "え？　……あ、そうだね。\n今日はもう休んだ方がいいよね。"
KEY_WAIT
CHAR 0, 1
FACE 0
VOICE 3950
MESSAGE "うん、じゃあ行こう？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "折角のバカンスだというのに、\nこんなことになってしまったのは\n大変心残りだ。"
KEY_WAIT
MESSAGE "だが、一歩間違えれば娘を\n失っていたことを考えると、\n仕方がないといえる。"
KEY_WAIT
MESSAGE "ここにはまた、機会を作って、\n来ればいいというだけの話だ。"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
END 0
LABEL 18
BGM_PLAY 36
BG 236
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3951
MESSAGE "この貝殻キレイ㍍\nあ、他にもある。"
KEY_WAIT
VOICE 3952
MESSAGE "そうだ、これ、みんなへの\nお土産にしよう。"
KEY_WAIT
CHAR 0, 5
FACE 4
VOICE 3953
MESSAGE "ん？　何かしら、これ？\nえ、ええ㌍"
KEY_WAIT
OFF_CHAR 3
BG 176
BG 236
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……いかん、思ったより話が\n長引いてしまったようだ。"
KEY_WAIT
MESSAGE "昼食の後、\n知人に呼び止められたので\n娘に先に行くよう告げた。"
KEY_WAIT
MESSAGE "大人の話など子供には退屈なもの\nなので、娘は喜び勇んで海へと\n走っていった……"
KEY_WAIT
MESSAGE "……はずなのだが、\nその姿が見えない。"
KEY_WAIT
MESSAGE "まぁ、あの子のことだ。\n勝手に危ない場所へ行くような\nマネはしないだろう。"
KEY_WAIT
FACE 8
MESSAGE_NAME "[娘の名前]"
VOICE 3954
MESSAGE "キャーッ㌍"
KEY_WAIT
BGM_PLAY 24
FACE 65535
OFF_FACE_WINDOW
MESSAGE "突如、絹を引き裂くような\n若い女性の悲鳴が聞こえてきた。"
KEY_WAIT
MESSAGE "今のは、もしや！"
KEY_WAIT
MESSAGE "悲鳴が聞こえてきた方へ\n急ぎ駆け出す。"
KEY_WAIT
MESSAGE "次の瞬間……\n……あまりといえばあまりな光景に\n一瞬、呆然としてしまった。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 243
SE_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 3955
MESSAGE "なんなの、コレー！"
KEY_WAIT
VOICE 3956
MESSAGE "いやー！\n何かぬるぬるしてるー㌍"
KEY_WAIT
VOICE 3957
MESSAGE "ひゃっ㌍\nちょ、ちょっとそれはダメだって！"
KEY_WAIT
VOICE 3958
MESSAGE "どこ、触ってるのよー！！"
KEY_WAIT
FACE 4
VOICE 3959
MESSAGE "きゃー！　水着がー㌍"
KEY_WAIT
VOICE 3960
MESSAGE "お父さーん、たすけてー！"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "呆けている場合ではない！"
KEY_WAIT
MESSAGE "スイカ割りで使った棒を手に、\n砂浜を駆け出した。"
KEY_WAIT
BG 176
SE_PLAY 26
BG2 177
BG 176
SE_WAIT
MESSAGE "……………………"
KEY_WAIT
SE_PLAY 27
BG2 177
BG 176
SE_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
SE_PLAY 26
BG2 177
BG 176
SE_WAIT
SE_PLAY 27
BG2 177
BG 176
SE_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
BG 236
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……ふぅ、なんとか追い払うことが\n出来たか。"
KEY_WAIT
MESSAGE "巨大イソギンチャクはボロボロに\nなった、その巨体を気味悪く\nくねらせながら海へ逃げていった。"
KEY_WAIT
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 3961
MESSAGE "お父さ～ん！\nこわかったよ～。"
KEY_WAIT
CHAR 0, 5
FACE 4
VOICE 3962
MESSAGE "って、傷だらけじゃない。\n大丈夫なの㌍"
KEY_WAIT
VOICE 3963
MESSAGE "あ、そうだ、早く治療しないと！"
KEY_WAIT
VOICE 3964
MESSAGE "えっと、宿のおじさんのとこに\n行って包帯とあと……え？\nかすり傷程度だから心配ない？"
KEY_WAIT
CHAR 0, 1
FACE 0
VOICE 3965
MESSAGE "……そう、良かったぁ。"
KEY_WAIT
VOICE 3966
MESSAGE "でも、何だったのかしら、あれ。\n私の水着を取ろうとするし……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "あとで知人に聞いたのだが、\nあのイソギンチャクは本来、海草を\n食べる大人しい生物だという。"
KEY_WAIT
MESSAGE "今まで人を襲うことはなかった\nというのだが……海草と聞いて、\n思いついたことがあった。"
KEY_WAIT
MESSAGE "娘の水着である。"
KEY_WAIT
MESSAGE "水着を染めるのに変わった海草を\n使用していると娘はいっていた。"
KEY_WAIT
MESSAGE "それがあのイソギンチャクの\n餌と同じものだったのだろう。"
KEY_WAIT
MESSAGE "種がわかればなんてことのない\n話だ。"
KEY_WAIT
MESSAGE "しかし、疲れた……"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 19
LABEL 19
BG 285
BGM_PLAY 7
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3967
MESSAGE "も～、今日は疲れちゃったよ。"
KEY_WAIT
VOICE 3968
MESSAGE "とくにあのイソギンチャクとか。"
KEY_WAIT
CHAR 0, 7
FACE 6
VOICE 3969
MESSAGE "でも、ここに来ることができて\n良かったな……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "すでに日は傾き始めていた。\n夕日がとなりで涼む娘の顔を\n紅く染めあげる。"
KEY_WAIT
MESSAGE "穏やかな時が流れていた。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3970
MESSAGE "はぁ～、風が気持ちいい。"
KEY_WAIT
VOICE 3971
MESSAGE "ホント、いい場所ね、ここ。"
KEY_WAIT
VOICE 3972
MESSAGE "キューブも一緒に来れば\n良かったのになぁ。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……娘の気持ちはわかるが、\nそれは難しいだろう。"
KEY_WAIT
MESSAGE "かつての戦の名残か、\nいまだ魔族への偏見は強い。"
KEY_WAIT
MESSAGE "今はまだそれほどではないとはいえ\nここは避暑地である。各地から人が\n集まってくる場所なのだ。"
KEY_WAIT
MESSAGE "そんなところに魔族の青年が\n姿を現したら、好ましくない結果に\nなるのは目に見えている。"
KEY_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3973
MESSAGE "ん？　どうしたの。\nむずかしい顔しちゃって。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "心配そうに見つめてくる娘に\nなんでもないと答えを返すと、\nごまかすように海に視線を向けた。"
KEY_WAIT
MESSAGE "そろそろ日が完全に落ちそうだな。"
SELECT 2, 20, "もう少しここにいる", 21, "宿に戻る"
LABEL 20
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 22
LABEL 21
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 23
LABEL 22
BGM_PLAY 8
BG 285
FACE 65535
OFF_FACE_WINDOW
MESSAGE "いや、もう少し海を眺めていると\nしようか。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3974
MESSAGE "あ、そうだ。これ見て。\nさっき、そこで拾ったの。"
KEY_WAIT
VOICE 3975
MESSAGE "ね、キレイでしょ、この貝殻。\nリーゼたちのお土産にしようと\n思うんだけど喜んでくれるかなぁ。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "娘の楽しそうな声を聞きながら、\n夜の帳に包まれようとしている\n海を眺め続けていた。"
KEY_WAIT
OFF_CHAR 3
BG 176
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 286
CHAR 0, 4
FACE 3
MESSAGE_NAME "[娘の名前]"
VOICE 3976
MESSAGE "……お父さぁん。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "甘えた声が聞こえたかと思うと、\n肩に温かく、そして、やわらかい\n感触が伝わってきた。"
KEY_WAIT
MESSAGE "何故か、早まる動悸を無理矢理\n押さえつけ、娘の顔を覗き込んだ。"
KEY_WAIT
FACE 3
MESSAGE_NAME "[娘の名前]"
VOICE 3977
MESSAGE "う、ぅうん……"
KEY_WAIT
OFF_CHAR 3
VOICE 3978
MESSAGE "くー……すー……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "眠ってしまったか……\n無理もない。今日は色々なことが\nあったからな。"
KEY_WAIT
MESSAGE "日が完全に落ちて、風が冷たく\nなってきた。このままでは身体に\n良くないな。"
KEY_WAIT
MESSAGE "背と膝の裏に手を回し、\n娘のしなやかな肢体を抱き上げる。\n成長したとはいえ、まだまだ軽い。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3979
MESSAGE "……おとう、さん……\n明日も……いっぱい…………\nあそぼう、ね……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "私は寝息を立てる娘をかかえながら\n宿屋へと向かった。"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
END 0
LABEL 23
MESSAGE "　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　"
KEY_WAIT
BGM_PLAY 5
BG 237
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3980
MESSAGE "それじゃ、着替えようかな。"
KEY_WAIT
SE_PLAY 6
SE_WAIT
CHAR 0, 4
FACE 3
VOICE 3981
MESSAGE "ん？　なんだろ？"
KEY_WAIT
SE_PLAY 6
SE_WAIT
VOICE 3982
MESSAGE "あ、はーい！"
KEY_WAIT
OFF_CHAR 3
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……………………"
KEY_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3983
MESSAGE "お父さん。\n宿のおじさんがご飯とお風呂、\nどっちを先にするか、だって。"
KEY_WAIT
VOICE 3984
MESSAGE "ご飯は東の国の料理なんだって。\n珍しいよね～♪"
KEY_WAIT
VOICE 3985
MESSAGE "で、お風呂は露天風呂なんだって。\nどうしようか？"
SELECT 2, 24, "食事にしよう", 25, "風呂にしよう"
LABEL 24
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3986
MESSAGE "わかったわ。それじゃ、\nおじさんに伝えてくるね。"
KEY_WAIT
VOICE 3987
MESSAGE "……って、その前に着替えないと㌍"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
MESSAGE "　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　"
KEY_WAIT
SE_WAIT
GOTO 26
LABEL 25
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 3988
MESSAGE "わかったわ。それじゃ、\nおじさんに伝えてくるね。"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 31
LABEL 26
SPECIAL 21
BGM_PLAY 5
BG 237
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3989
MESSAGE "ねぇ、お父さん、この服って\nなんかスースーするね。"
KEY_WAIT
VOICE 3990
MESSAGE "それに腰のところを紐で\n縛ってるだけなんだよ。"
KEY_WAIT
VOICE 3991
MESSAGE "ちょっと動いたら\nはだけちゃうかも。"
KEY_WAIT
CHAR 0, 2
FACE 1
VOICE 3992
MESSAGE "それともお父さん、\n……見たい？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "いたずらっぽい笑みで見つめてくる\n娘の視線を軽く受け流しつつ、\n自分の格好を見下ろした。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 245
SE_WAIT
MESSAGE "私と娘は東の国の『ゆかた』と\nいう衣装を着ている。"
KEY_WAIT
MESSAGE "宿の主人が東の国の料理を\n食べるのだから服もあわせるべき、\nなどといって出してきたのだ。"
KEY_WAIT
MESSAGE "しかし、こんなもの何処で\n仕入れてきたのだろうか。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3993
MESSAGE "あ、お料理がきたよ。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 246
SE_WAIT
VOICE 3994
MESSAGE "わー、おいしそー♪"
KEY_WAIT
FACE 1
VOICE 3995
MESSAGE "それじゃ、いただきまーす☆"
KEY_WAIT
VOICE 3996
MESSAGE "まずは……と、これにしよ。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "そういって娘が選んだのは\n『てんぷら』という料理だ。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 3997
MESSAGE "……もぐもぐ……"
KEY_WAIT
FACE 4
VOICE 3998
MESSAGE "うわ、何、これ。\nすっごく美味しい㍍"
KEY_WAIT
VOICE 3999
MESSAGE "外のころもはサクサクで、\n中のえびはぷりぷりしてて、\nホント、最っ高♪"
KEY_WAIT
VOICE 4000
MESSAGE "キューブの作るフライも\n美味しいけど、これは別格ね。"
KEY_WAIT
FACE 1
VOICE 4001
MESSAGE "あ、今のはキューブに\n内緒にしてね㌍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "さて、どうしようかと、\nわざとらしくおどけていうと\n娘はひどいーと声を上げた。"
KEY_WAIT
MESSAGE "冗談はさておいて、\n私もいただくとするか。"
SELECT 3, 27, "てんぷら", 28, "さしみ", 29, "赤い実"
LABEL 27
FACE 65535
OFF_FACE_WINDOW
MESSAGE "目の前の大皿から、てんぷらを\n一切れとって、塩を振り、\n口に運ぶ。"
KEY_WAIT
MESSAGE "……ふむ、歯応えがコリコリしてて\nなかなかいけるな。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4002
MESSAGE "あ、お父さん、\nそれ、なにか知ってる？"
KEY_WAIT
VOICE 4003
MESSAGE "さっき、おじさんに\n聞いたんだけど……"
KEY_WAIT
FACE 1
VOICE 4004
MESSAGE "イソギンチャクなんだって☆"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "娘の言葉に噴出しそうになり、\n慌てて、口を押さえた。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4005
MESSAGE "あはは、うそよ、う・そ♪\nこの辺で獲れる貝なんだって。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 30
LABEL 28
FACE 65535
OFF_FACE_WINDOW
MESSAGE "確か、これは『さしみ』だったな。\n昔、食べたことがある。"
KEY_WAIT
MESSAGE "小船の形をした容器から、\n白身魚の刺身を一切れとる。\n……ふむ、美味い。"
KEY_WAIT
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 4006
MESSAGE "ね、ねえ、お父さん……\nそれって生のお魚なんでしょ。\n大丈夫なの？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "この国では生魚を食べる習慣が\nないので、娘が不安げな表情を\nするのも仕方がない。"
KEY_WAIT
MESSAGE "私は大丈夫だと首を縦に振り、\n続けて赤身の魚に箸を伸ばした。"
KEY_WAIT
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 4007
MESSAGE "本当に美味しいの？"
KEY_WAIT
VOICE 4008
MESSAGE "……う～ん、\n私も食べてみようかなぁ。"
KEY_WAIT
FACE 4
VOICE 4009
MESSAGE "あ、これ乗せるんだよね。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "娘は私が止める間もなく、\n大量のわさびを刺身に乗せて、\n口へ運んでしまった。"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 4010
MESSAGE "んんっ㌍\nか、からい！　みず、みず～！！"
KEY_WAIT
VOICE 4011
MESSAGE "ゴクゴク……ん～、はぁ。\n何なの、これ、すっごく辛いよ～。"
KEY_WAIT
FACE 4
VOICE 4012
MESSAGE "ええっ！\nほんのちょっとでいいの㌍\n先にいってよ～。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 30
LABEL 29
FACE 65535
OFF_FACE_WINDOW
MESSAGE "これは私も知らないな。\nまぁ、ここにある以上、\n食べられるものなんだろう。"
KEY_WAIT
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……ぐっ！\nす、すっぱい㌍"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 4013
MESSAGE "ど、どうしたの㌍"
KEY_WAIT
VOICE 4014
MESSAGE "え？　水がほしいの？"
KEY_WAIT
VOICE 4015
MESSAGE "あ、はい、お水。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "差し出された水を飲み、\n口の中を洗い流す。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4016
MESSAGE "あ、梅干食べちゃったんだ。\nすっぱいから気をつけるようにって\nおじさんがいってたよ。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……あいつ、私には黙っていたな。"
KEY_WAIT
MESSAGE "耳を澄ますと、調理場の方から\n笑い声が聞こえてきたような気が\nした。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 30
LABEL 30
BG 237
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
MESSAGE "食事を終えた後、\n宿の主人のすすめで、\n露天風呂に入ることにした。"
KEY_WAIT
MESSAGE "女湯の方から、しみるーなどと\nいった娘の叫び声が聞こえてきたが\nまぁ、おおむね満足できた。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
SE_WAIT
GOTO 32
LABEL 31
BGM_PLAY 5
FACE 65535
OFF_FACE_WINDOW
MESSAGE "満天の星空の下、\n潮騒の音を聞きながら、\n湯船につかる。"
KEY_WAIT
MESSAGE "なんとも贅沢なことだ。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 247
SE_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 4017
MESSAGE "し、しみる～。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "女湯の方から、\nなにやら、娘がもだえる声が\n聞こえてきた。"
KEY_WAIT
MESSAGE "知らず知らずのうちに\n溜息が漏れる。"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 4018
MESSAGE "う～……\nちゃんと日焼け止め塗ったのに\nしみるよ～。"
KEY_WAIT
VOICE 4019
MESSAGE "あ、お尻のところとか、\n結構、やけてる～！"
KEY_WAIT
VOICE 4020
MESSAGE "どうして～㌍"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "どうしてと、いわれても\n困るのだが……"
KEY_WAIT
MESSAGE "考えられるのは日焼け止めではなく\nサンオイルを塗ったとかいう\nくだらないオチではないだろうか。"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 4021
MESSAGE "え～、そんなことするわけ……あ。"
KEY_WAIT
FACE 4
VOICE 4022
MESSAGE "そ、そういえば、\nビンに日焼け止めって\n書いてなかったような……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "娘の声が途絶える。\nどうやら、私の考えが\n正解だったようだ。"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 4023
MESSAGE "うわ～ん、しっぱいした～！"
KEY_WAIT
BG 176
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……………………"
KEY_WAIT
MESSAGE "……………………\n………………"
KEY_WAIT
MESSAGE "……………………\n………………\n…………"
KEY_WAIT
BG 237
SPECIAL 21
CHAR 0, 1
FACE 65535
OFF_FACE_WINDOW
MESSAGE "しばらく湯船に浸かったあと、\n部屋に戻り、食事を取った。"
KEY_WAIT
MESSAGE "普段口にすることのない、\n珍しい料理に娘も機嫌を直したのか\n終始笑顔を浮かべていた。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
OFF_CHAR 3
BG 176
SE_WAIT
GOTO 32
LABEL 32
FACE 65535
OFF_FACE_WINDOW
MESSAGE "　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　"
KEY_WAIT
BGM_PLAY 10
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 248
SE_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4024
MESSAGE "……それでね、\nマリーにはこの面白い形の貝を\nあげようと思うの。"
KEY_WAIT
VOICE 4025
MESSAGE "リーゼにはこっちの白くて\n小さいのを……"
KEY_WAIT
VOICE 4026
MESSAGE "で、クリスチーナは……\nやっぱりこの大きくて\n派手なやつかな？"
KEY_WAIT
FACE 1
VOICE 4027
MESSAGE "ねぇ、どう思う？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "友人たちのお土産にと、昼間集めた\n貝殻をテーブルに広げていた娘の\n問いに、私は頷きを返した。"
KEY_WAIT
MESSAGE "もっとも、娘の友人たちのことを\n詳しく知っているわけではないので\n空返事となってしまうのだが……"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4028
MESSAGE "ふぁ～あ……"
KEY_WAIT
VOICE 4029
MESSAGE "あ、ごめんなさい。\nなんか眠くなっちゃって。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "今日は本当に色々とあったので、\n疲れたが出たのだろう。"
KEY_WAIT
MESSAGE "時間も遅いし、そろそろ休んだ方が\nいいかもしれないな。"
KEY_WAIT
FACE 8
MESSAGE_NAME "[娘の名前]"
VOICE 4030
MESSAGE "え～、まだ大丈夫だよ。"
KEY_WAIT
VOICE 4031
MESSAGE "……だめ？"
KEY_WAIT
FACE 1
VOICE 4032
MESSAGE "あ、じゃあ、ベッドに入って\nお話しするっていうのはどうかな？"
KEY_WAIT
VOICE 4033
MESSAGE "それなら途中で寝ちゃっても\n平気だし。ね、いいでしょ？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……まぁ、それなら問題ないか。"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 249
SE_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 4034
MESSAGE "ねぇ、お父さん……\n今日は楽しかったね。"
KEY_WAIT
VOICE 4035
MESSAGE "海はキレイで気持ちよかったし、\nスイカも美味しかったし。"
KEY_WAIT
VOICE 4036
MESSAGE "あのイソギンチャクには\n参ったよね。今度出てきたら\n私の魔法で丸焼きにしちゃうから。"
KEY_WAIT
VOICE 4037
MESSAGE "あ、今、笑わなかった？"
KEY_WAIT
VOICE 4038
MESSAGE "……笑ってない？\nなら、いいけど。"
KEY_WAIT
FACE 6
VOICE 4039
MESSAGE "…………あのね。"
KEY_WAIT
VOICE 4040
MESSAGE "最近、習い事とか忙しくて、\nお父さんとふたりで\n出かけることってなかったでしょ。"
KEY_WAIT
VOICE 4041
MESSAGE "だから、今回、お父さんと\n旅行にいけるって聞いたとき、\nすっごく嬉しかったの。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "……………………"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 4042
MESSAGE "……だからね。"
KEY_WAIT
VOICE 4043
MESSAGE "……また……ふたりで……\n来れると……いい、よね……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 250
SE_WAIT
FACE 65535
OFF_FACE_WINDOW
MESSAGE "娘の寝息が聞こえてくる。"
KEY_WAIT
MESSAGE "大人になるにつれ、\nこういった機会は自然と\n減っていくものだ。"
KEY_WAIT
MESSAGE "成人するまでの間に、どれだけ\nこういった機会があるのかは\nわからない。"
KEY_WAIT
MESSAGE "だからこそ、今を大切にし、\n思い出を重ねていきたい。"
KEY_WAIT
MESSAGE "そして、いつか娘に子供が\nできたとき……"
KEY_WAIT
MESSAGE "今日の日と同じような想い出を\n作れるようになってくれれば、\nと思う。"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 176
END 0