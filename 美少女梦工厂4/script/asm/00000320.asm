LABEL 0
LABEL 1
FLAG 737, 1
BGM_STOP 30
BGM_PLAY 31
BG 71
FACE 29
MESSAGE_NAME "軽そうな男"
MESSAGE "ハイ、彼女㍍"
LINE_FEED
FACE 30
MESSAGE "ねぇねぇ、一緒にお茶でもどーお？"
SELECT 2, 2, "ＯＫする", 3, "冷たく断る"
LABEL 2
END 1
LABEL 3
END 2
LABEL 4
FLAG 736, 1
FACE 30
MESSAGE_NAME "軽そうな男"
MESSAGE "エヘヘ、そう来なくっちゃ！"
KEY_WAIT
FACE 29
MESSAGE "キミってキレイだね。お世辞じゃな\nいよ。この辺じゃ見られない、すご\nくキレイなオーラが出ているよ。"
KEY_WAIT
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 608
MESSAGE "オ、オーラ？"
KEY_WAIT
FACE 29
MESSAGE_NAME "軽そうな男"
MESSAGE "そ。オーラ。"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 609
MESSAGE "それって……どこに？\nなんの、こと？"
KEY_WAIT
FACE 29
MESSAGE_NAME "軽そうな男"
MESSAGE "ん、わからない？\nまぁいいや。それはそれ。"
KEY_WAIT
FACE 30
MESSAGE "ねぇねぇ、そっちに面白い店が\nあるんだ。２人で覗いてみようよ。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 610
MESSAGE "えっ……うん。いいけど。"
KEY_WAIT
FACE 30
MESSAGE_NAME "軽そうな男"
MESSAGE "おっ、ノリがいいなぁ。\nボク達、気が合いそうだね㍍"
KEY_WAIT
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 5
FLAG 739, 1
FACE 29
MESSAGE_NAME "軽そうな男"
MESSAGE "えーっ、冷たいなぁ。\nちぇーーーっ。"
KEY_WAIT
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 6
FLAG 855, 1
LABEL 7
FLAG 856, 1
BGM_PLAY 32
BG 158
SE_PLAY 14
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "ふふーん……\nど・ち・ら・に\nし・よ・う・か・なぁ～♪"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1396
MESSAGE "あら？\n何してるの、リー？"
KEY_WAIT
CHAR 2, 1
FACE 0
VOICE 1397
MESSAGE "うっ……㌍"
KEY_WAIT
OFF_CHAR 3
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "あっ、[娘の名前]ちゃん。\n……どうしたの、変な顔して？"
KEY_WAIT
CHAR 2, 9
FACE 8
MESSAGE_NAME "[娘の名前]"
VOICE 1398
MESSAGE "あ、あなた……\nその、両手に\n持ってるのって……"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "え？　ああ、コレ？\nこれはイモリにヤモリだよ。\n見たことないかな？"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "エヘヘ……\nどっちもおいしいんだよ～！"
KEY_WAIT
CHAR 2, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 1399
MESSAGE "おいしいって…㌍"
KEY_WAIT
CHAR 2, 5
FACE 4
VOICE 1400
MESSAGE "ダ、ダダダダメよ、\nそんなの食べちゃ！"
KEY_WAIT
CHAR 2, 3
FACE 2
VOICE 1401
MESSAGE "早く捨てなさい！"
KEY_WAIT
CHAR 1, 26
FACE 31
MESSAGE_NAME "リー"
MESSAGE "ええっ㌍\nせっかく捕まえたのになぁ～"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1402
MESSAGE "ううっ……そんなものが\nおいしいだなんて、リーって\nまさかゲテモノ好きなの？"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "ゲテモノ、って？\nよく分からないや。"
KEY_WAIT
MESSAGE "んー、キミの表情からすると、\nイモリやヤモリは嫌い、って事\n……なのかな？"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1403
MESSAGE "そ、そうね。\n間違ってないわ……\n味覚の違いなのかしら……"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "そうなのかな？　まぁ、いいや。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "ボクは、君が楽しく食事が\nできるところに行きたいな。"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE "ね、そうしようよ！"
SELECT 2, 8, "行く", 9, "行かない"
LABEL 8
FLAG 857, 1
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1404
MESSAGE "え？　そうね、どこが\nいいかな……"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "ボクはキミと一緒なら\nどこでも楽しいよ！　エヘヘ……"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 6
LABEL 9
FLAG 901, 1
END 3
LABEL 10
FLAG 902, 1
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "そっか、残念だなぁ……\nいいよ、また今度誘うね。\nエヘヘ……"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 0
LABEL 11
FLAG 903, 1
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "ちぇーっ。\nじゃあ、今度は行こうね。"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 0
LABEL 12
FLAG 904, 1
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "はぁ～つれないなぁ。\nもしかして、ボクの事……\n嫌い？"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 0
LABEL 13
FLAG 858, 1
LABEL 14
FLAG 859, 1
BGM_PLAY 31
BG 161
SE_PLAY 14
CHAR 1, 24
CHAR 2, 2
SE_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1405
MESSAGE "あら、リー。\nこんにちは。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "あっ、[娘の名前]ちゃん！\n奇遇だねえ。会えてうれしいよ。"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1406
MESSAGE "めずらしいわね、こんな所で。"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "この辺り、人がいっぱいいて\n面白いからね。よく来るよ。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "ねえ、せっかく会ったんだし、\nこれからどこか行こうよ！"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1407
MESSAGE "えっ？\nでも私、これから買い物に\n行かなくちゃいけないの。"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "買い物かぁ……\nそれじゃあ、ボクもお付き合い！"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1408
MESSAGE "うーん、そうね……"
SELECT 2, 15, "ＯＫ", 9, "ダメ"
LABEL 15
FLAG 860, 1
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1409
MESSAGE "うん。荷物持ちしてくれるなら、\nいいかな㍍"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "うんうん！　力仕事なら任せて！\nいくつでも持ってあげるよ！\nエヘヘッ♪"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE "さあ、早く行こうよっ！"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1410
MESSAGE "（買い物に行くだけなのに、\nリーったらはしゃいじゃって……\n子供みたいね。ふふふっ）"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 4
LABEL 16
FLAG 757, 1
LABEL 17
FLAG 758, 1
BGM_STOP 30
BGM_PLAY 15
SE_PLAY 14
FACE 65535
OFF_FACE_WINDOW
OFF_CHAR 3
BG 82
FACE 29
MESSAGE_NAME "リー"
MESSAGE "ねぇねぇ！　次はあそこ行こうよ！"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 692
MESSAGE "ま、待ってよ～。\nそんなに急がなくても……"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "エヘヘ。だって楽しいんだもん。\nほら、次はこっちこっち！"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 693
MESSAGE "んもう……\nしょうがないなぁ。"
KEY_WAIT
FACE 5
VOICE 694
MESSAGE "……あれ？"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 695
MESSAGE "ねえリー、ちょっと待って！\nこれ、なにかしら……？"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "なになに？"
KEY_WAIT
MESSAGE "……ああ、それは\nドラゴンの牙だよ。\nこんな所でも売ってるんだなぁ。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 696
MESSAGE "ドラゴンの牙？\nへぇ、これがそうなんだ……\nよく知ってたわね、リー。"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "そりゃわかるよ。\nだってボクもドラゴンだもん。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 697
MESSAGE "ふ～ん、そうなんだ……"
KEY_WAIT
FACE 4
VOICE 698
MESSAGE "………………\n…………………\n……………えっ？"
KEY_WAIT
VOICE 699
MESSAGE "リ、リー……\nあなた、今、なんて……"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "えっ？　分かるよって……"
KEY_WAIT
FACE 8
MESSAGE_NAME "[娘の名前]"
VOICE 700
MESSAGE "その前っ。\n自分がドラゴンだって……\n言わなかった？"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "言ったけど……\nあれ？　[娘の名前]ちゃんに\n言ったことなかったっけ？"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 701
MESSAGE "じょ、冗談はやめてよ。\nあなたどう見ても人間じゃない㌍"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "人間形態になってるだけだよ。\nまさか、街にいるときにそのまま\nでいるのはマズイでしょ？"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 702
MESSAGE "……本当なの？"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "ほんとだってば。エヘヘ、\n退屈だったからこっちに\n来てるんだよ。"
KEY_WAIT
FACE 29
MESSAGE "ボクの故郷は本当に変化が\nなくてね。何も起きなくて、平和\nって言えば平和なんだけどさ。"
KEY_WAIT
FACE 30
MESSAGE "人間の町はヘンテコだけど、変化が\nあって刺激的で大好きさ。エヘッ、\n[娘の名前]ちゃんもいるし……"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 703
MESSAGE "あなたがドラゴン……\nうーん……だめ、やっぱり\n信じられないわ……"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "じゃあ、今度、谷においでよ。\n案内してあげるよ。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 704
MESSAGE "谷？"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "うん。僕たちドラゴン族が\n住んでいる谷だよ。魔界の南に\nあるんだ。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 705
MESSAGE "あはは……頭痛くなってきたわ。"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "ハハハ、考えてみたら、人間が\n来るのは無理か。どうもキミなら\nって思っちゃうんだよな。"
KEY_WAIT
SE_PLAY 7
MESSAGE "じゃあ、次はあそこに行こう！\nさあ、レッツゴー！"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 706
MESSAGE "ね、ねえっ！\nやっぱり嘘じゃないの？\nねえったら～！"
KEY_WAIT
BGM_STOP 30
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 18
FLAG 870, 1
LABEL 19
FLAG 871, 1
BGM_PLAY 31
BG 159
SE_PLAY 14
CHAR 2, 1
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "やっほー\n[娘の名前]ちゃん！"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "えへへ……\nキミの姿が見えたからさ、\n走って追いかけてきちゃった！"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1433
MESSAGE "リー……\nあなたっていつも元気ね～"
LINE_FEED
CHAR 1, 24
MESSAGE "なんだかうらやましいわ。"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "ん？"
KEY_WAIT
MESSAGE "そういう[娘の名前]ちゃんは\nもしかして元気ないの？"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1434
MESSAGE "え？　そ、そんな事は……"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "うーん、よし！"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "それなら今から遊びに行こうよ！\n思いっきり遊べば、きっと\n元気も出るって！"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1435
MESSAGE "えっ、だ、ダメよ㌍\n私、これから\n行かなきゃいけない場所が……"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "いいからいいから！\nほら、行こう！"
SELECT 2, 20, "行く", 9, "行かない"
LABEL 20
FLAG 872, 1
SE_PLAY 7
SE_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1436
MESSAGE "きゃー！\nちょ、ちょっと待ってよ！"
KEY_WAIT
FACE 7
VOICE 1437
MESSAGE "（もう、しょうがないなぁ……）"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 5
LABEL 21
FLAG 861, 1
LABEL 22
FLAG 862, 1
BGM_PLAY 32
SE_PLAY 14
BG 160
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "おーい、[娘の名前]ちゃん！"
KEY_WAIT
MESSAGE "こっち、こっちー！"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1411
MESSAGE "あら？\nリーじゃない。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "エヘヘ、やっと見つけた。"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE "ねぇ、これからデートしようよ。\nほら、今日は天気もいいし！"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1412
MESSAGE "天気がいいのは認めるけど、\nそうね……"
KEY_WAIT
CHAR 2, 8
FACE 7
VOICE 1413
MESSAGE "私、これから行くところが\nあるのよね……"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "え、どこどこ？\nキミさえよければ\nボクも一緒に行くよ！"
KEY_WAIT
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1414
MESSAGE "そう？　じゃあ、一緒に行く？\n教会なんだけど……"
KEY_WAIT
CHAR 1, 26
FACE 31
MESSAGE_NAME "リー"
MESSAGE "ええっ㌍\nきょ、教会ぃ～？"
KEY_WAIT
MESSAGE "や、やややっぱりボク\n遠慮するよ！　そ、それじゃあ！"
KEY_WAIT
SE_PLAY 7
OFF_CHAR 1
SE_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1415
MESSAGE "あっ、リー㌍"
KEY_WAIT
CHAR 2, 8
FACE 7
VOICE 1416
MESSAGE "行っちゃった……"
KEY_WAIT
CHAR 2, 6
FACE 5
VOICE 1417
MESSAGE "ずいぶん慌てていたけれど、\n教会が嫌いなのかしら？"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 0
LABEL 23
FLAG 864, 1
LABEL 24
FLAG 865, 1
BGM_PLAY 32
SE_PLAY 14
BG 158
CHAR 2, 1
SE_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1418
MESSAGE "あら？\nあれは……"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "ハハハ、くすぐったいよ。\nやめろって、ハハ……\nやめろってばぁ～♪"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1419
MESSAGE "リー。こんなところで\n何してるの？"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "あっ、[娘の名前]ちゃん。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "エヘヘ、今ね、こいつらと\n遊んでたの。ハハ……"
KEY_WAIT
CHAR 2, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 1420
MESSAGE "こいつらって……\nこのネコちゃんたち？"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "うん。いつもね、ボクを\n見つけるとすぐ寄ってきてさ……"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "アハハ……くすぐったいってば！"
KEY_WAIT
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1421
MESSAGE "ふふふ……\nリーって動物に\n好かれやすいのかもねぇ。"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "え？"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1422
MESSAGE "あなたのやさしいところ、\n動物にはすぐわかるのよ、きっと。"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "エヘヘ……そうかなぁ？"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "あ、あははは……もうダメ、\n笑い死んじゃうよボク！"
KEY_WAIT
MESSAGE "ね、ねえ[娘の名前]ちゃんも\n見てないで、助けて！\n一緒に遊ぼうよー！"
SELECT 2, 25, "遊ぶ", 9, "遊ばない"
LABEL 25
FLAG 866, 1
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1423
MESSAGE "ふふ……そうね。猫ちゃんたち、\n私にもなついてくれるかな？\nはーい、ごろごろごろ……"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 6
LABEL 26
FLAG 873, 1
LABEL 27
FLAG 874, 1
BGM_PLAY 32
BG 158
SE_PLAY 14
CHAR 2, 5
SE_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1438
MESSAGE "あら？\n広場に人だかりが……\n何かあったのかしら？"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "あっ、\n[娘の名前]ちゃん！\nやっほー！"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1439
MESSAGE "リー㌍"
KEY_WAIT
CHAR 2, 3
FACE 2
VOICE 1440
MESSAGE "ちょ、ちょっと！　往来の\n真ん中に寝転がったりして\n何してるのよ？"
KEY_WAIT
CHAR 1, 24
CHAR 2, 8
FACE 7
VOICE 1441
MESSAGE "あっ！　み、皆さん！\n別に行き倒れでも大道芸でも\nありませんのでー！"
KEY_WAIT
CHAR 2, 4
FACE 3
VOICE 1442
MESSAGE "うう、恥ずかしいなあ、もう……"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "エヘヘ。陽射しがぽかぽかして\n気持ちよかったからさ。\n日向ぼっこ。"
KEY_WAIT
CHAR 1, 24
FACE 29
CHAR 2, 5
MESSAGE "[娘の名前]ちゃんもやる？"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1443
MESSAGE "わ、私は遠慮しておくわよ！"
KEY_WAIT
CHAR 2, 6
FACE 5
VOICE 1444
MESSAGE "それより、こんな所で寝てたら\n皆の迷惑よ。ほら、起きて……"
KEY_WAIT
CHAR 2, 8
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "あ、そうなの？\nあはは、ごめんね、みんな～"
SE_PLAY 16
SE_WAIT
KEY_WAIT
SE_PLAY 14
CHAR 2, 1
SE_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1445
MESSAGE "（リーの無邪気な様子を見て\n安心したのか、街の人たちも\n散らばっていくわ……）"
KEY_WAIT
CHAR 2, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 1446
MESSAGE "幸せそうな顔しちゃって。\nリー。あなた、時々\nとんでもない事をするわよね……"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "キミも、ゴメンね。もしかして\n迷惑かけちゃってるかな……？"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1447
MESSAGE "えっ？　そ、そうね……\n恥ずかしかったり、驚いたりは\nするけど……"
KEY_WAIT
CHAR 2, 1
FACE 0
VOICE 1448
MESSAGE "迷惑だなんて思ったこと無いわよ？\n……きっと、街の人も。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "エヘヘ……良かったあ。\nじゃ、じゃあさ。今日もその、\n遊びに行こうよ！"
SELECT 2, 28, "行く", 9, "行かない"
LABEL 28
FLAG 875, 1
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1449
MESSAGE "え？　あ、うん……いいけど。"
KEY_WAIT
CHAR 2, 8
FACE 7
VOICE 1450
MESSAGE "もう……少しは懲りた方が\nいいのかも知れないわね、\nリーは……"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "え？　何か言った？\nさあ、早く早くー！"
SE_PLAY 7
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1451
MESSAGE "ちょっ、待ってよリー！"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 4
LABEL 29
FLAG 867, 1
LABEL 30
FLAG 868, 1
BGM_PLAY 31
SE_PLAY 14
BG 161
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "う～ん……"
KEY_WAIT
CHAR 1, 26
FACE 31
MESSAGE "フシギだなぁ……\nわっかんないなあ～……"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1424
MESSAGE "どうしたの？　めずらしく\nむずかしい顔をして？"
KEY_WAIT
CHAR 2, 1
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "あっ、[娘の名前]ちゃん！\nこれ見てよ、これ。"
KEY_WAIT
CHAR 2, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 1425
MESSAGE "何を見てたの……？"
KEY_WAIT
CHAR 2, 1
FACE 0
VOICE 1426
MESSAGE "ああ、有名な\n画家さんの絵ね。"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "んー、なんでこんなものに\n高い値段がつくのかなあ？\nボク、さっぱりわからないんだ。"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1427
MESSAGE "まあ……それが芸術って\nものなのよ……たぶん。"
KEY_WAIT
CHAR 2, 1
FACE 0
VOICE 1428
MESSAGE "絵の善し悪しなんて、\n私たちには……"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "コレって紙に色つけて、木の\n枠をはめただけだよね？\nなんでこんな値段が……"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1429
MESSAGE "あ、あはは……"
KEY_WAIT
CHAR 2, 8
FACE 7
VOICE 1430
MESSAGE "……そういう問題じゃない\nみたいね、あなたには……"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "うーん……\nやっぱり、よくわからないよ。\n人間って難しいなぁ……"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1431
MESSAGE "ヘンな事いうのね、リーは。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "ま、いいや。"
KEY_WAIT
MESSAGE "せっかくキミに声かけて\nもらえたんだもんね！\nどっか遊びに行こ？"
SELECT 2, 31, "行く", 9, "行かない"
LABEL 31
FLAG 869, 1
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1432
MESSAGE "ウフフ、そうね。"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "わーい！　じゃあ、\nレッツゴー！　エヘヘ……"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 4
LABEL 32
FLAG 685, 1
LABEL 33
FLAG 686, 1
BGM_STOP 30
BGM_PLAY 30
SE_PLAY 39
BG 173
SE_WAIT
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 707
MESSAGE "ここは……魔界の谷？\n変なところに来ちゃったなぁ……"
KEY_WAIT
SE_PLAY 20
SE_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 708
MESSAGE "キャッ㌍"
KEY_WAIT
CHAR 0, 4
FACE 3
VOICE 709
MESSAGE "い、今の鳴き声……\nモンスターとか、かな。\nやっぱり……"
KEY_WAIT
VOICE 710
MESSAGE "も、もう帰ろう……\n何だか悪い予感が……"
KEY_WAIT
SE_PLAY 21
SE_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 711
MESSAGE "キャアアア！\nな、なに㌍"
KEY_WAIT
SE_PLAY 24
OFF_FACE_WINDOW
FACE 65535
SE_PLAY 22
OFF_CHAR 3
BG 83
FACE 4
MESSAGE_NAME "[娘の名前]"
MESSAGE "…………"
KEY_WAIT
VOICE 712
MESSAGE "ド、ドラゴン……"
KEY_WAIT
FACE 65535
MESSAGE_NAME "ドラゴン"
SE_PLAY 21
MESSAGE "グオオオォォォ……"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 713
MESSAGE "あっ……ああ……\nどうしよう……\n魔法通用するかしら……"
KEY_WAIT
FACE 65535
MESSAGE_NAME "ドラゴン"
MESSAGE "……やっぱり……\nキミのオーラが見えたんだ。\nまさかって思ったけど……"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 714
MESSAGE "うぅ……"
KEY_WAIT
VOICE 715
MESSAGE "って、あ、あれっ？\nしゃ、しゃべっ……た？"
KEY_WAIT
FACE 65535
MESSAGE_NAME "ドラゴン"
MESSAGE "アハハ！\nほんとに来てくれたんだね？"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 716
MESSAGE "う、うそ……\nドラゴンと……私、\nお話してる……"
KEY_WAIT
FACE 65535
MESSAGE_NAME "ドラゴン"
MESSAGE "[娘の名前]ちゃん、すごいね！\nどうやってここまで来たの？"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 717
MESSAGE "はいぃっ㌍\nな、なんで私の名前を……"
KEY_WAIT
FACE 65535
MESSAGE_NAME "ドラゴン"
MESSAGE "なんでって……\nあっ、そっか！"
KEY_WAIT
MESSAGE "説明するのも面倒だし……"
KEY_WAIT
BG 177
MESSAGE "ん……うぉぉぉーーーーーっ！"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 718
MESSAGE "きゃあーーっ、何㌍\n何が始まるの？"
KEY_WAIT
SE_PLAY 23
BG 173
CHAR 2, 24
CHAR 1, 9
FACE 29
MESSAGE_NAME "リー"
MESSAGE "ふぅ……"
KEY_WAIT
CHAR 1, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 719
MESSAGE "あっ……\nああっーーー！\nリ、リー㌍"
KEY_WAIT
CHAR 2, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "エヘヘ……\n驚いた？"
KEY_WAIT
CHAR 1, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
MESSAGE "…………"
KEY_WAIT
VOICE 720
MESSAGE "ほ、本当にドラゴンだったんだ……"
KEY_WAIT
CHAR 2, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "うん！　今、見てたでしょ？"
KEY_WAIT
CHAR 1, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 721
MESSAGE "見た……見てた、けど……\nまだ信じられない……\nかも……"
KEY_WAIT
CHAR 2, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "アハハ！　しょうがないなあ。\nでも、これでわかったでしょ？\nボクがほんとにドラゴンだって。"
KEY_WAIT
CHAR 1, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 722
MESSAGE "う、うん。\nこんなの見ちゃったら……\nお、驚いたあ～っ……"
KEY_WAIT
CHAR 2, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "エヘヘヘヘ、\nびっくりさせちゃったかな？\nそうだ！　おもしろいことしよう！"
KEY_WAIT
CHAR 1, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 723
MESSAGE "えっ？　な、なに？"
KEY_WAIT
CHAR 2, 26
FACE 31
MESSAGE_NAME "リー"
MESSAGE "はっ！　……うぉぉぉーっ！"
BG 177
KEY_WAIT
SE_PLAY 23
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BG 177
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
BG 83
FACE 65535
MESSAGE_NAME "リー"
MESSAGE "ほら、ボクの背中に乗って。\n魔界を空から案内してあげる。\n楽しいよ！"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 724
MESSAGE "ええっ㌍\nむ、無理よ、そんなの……\nすごく怖そうだし……"
KEY_WAIT
FACE 65535
MESSAGE_NAME "リー"
MESSAGE "大丈夫だってば！\nほらほら！"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 725
MESSAGE "……強引なトコとか、変わって\nないね。"
KEY_WAIT
FACE 65535
MESSAGE_NAME "リー"
MESSAGE "ボクはボクさ。そうだろ？"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 726
MESSAGE "うん。……ドラゴンの姿でも\nリーはリーだよ。"
KEY_WAIT
FACE 5
VOICE 727
MESSAGE "……ほんとに気をつけてよ？"
KEY_WAIT
FACE 65535
MESSAGE_NAME "リー"
MESSAGE "アハハハハ！　じゃあ、いくよー！"
KEY_WAIT
SE_PLAY 24
SE_STOP
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 34
FLAG 914, 1
LABEL 35
FLAG 915, 1
BGM_PLAY 30
SE_PLAY 39
BG 173
CHAR 1, 25
FACE 30
CHAR 2, 1
MESSAGE_NAME "リー"
MESSAGE "[娘の名前]ちゃん㌍\nこんな所まで\nまた来てくれたんだね！"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1526
MESSAGE "リーがいるかと思って来てみたの。"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "エヘヘ、うれしいなぁ㍍"
KEY_WAIT
MESSAGE "ボクの一方的な片思いだったらって\nちょっと心配だったんだ。"
KEY_WAIT
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1527
MESSAGE "へぇ、リーでもそんなこと"
LINE_FEED
CHAR 1, 24
MESSAGE "心配するのね。"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "あー、ひどいなぁ。\nボクだってデリケートな\nところあるんだよ。もう～"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1528
MESSAGE "ウフフ、ごめんなさい。"
KEY_WAIT
CHAR 2, 1
FACE 29
MESSAGE_NAME "リー"
MESSAGE "……最近、魔界にちょくちょく\n来てるみたいだね。"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1529
MESSAGE "えっ、わかるの？"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "……言っちゃっていいか\nどうか分からないけどさ。"
KEY_WAIT
MESSAGE "魔の影響を受けすぎちゃってる\nからかなあ。"
KEY_WAIT
MESSAGE "君はもうボクの目からは魔族に\n近いように見えちゃってるよ。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1530
MESSAGE "え～っ㌍　そうなの㌍"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "うん。イヤかな？　やっぱり。"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1531
MESSAGE "あ、違うの。いやってわけじゃ\n無いんだけれど……困るかも。"
KEY_WAIT
VOICE 1532
MESSAGE "どうしよう……"
KEY_WAIT
BGM_STOP 30
BGM_PLAY 22
FACE 29
MESSAGE_NAME "リー"
MESSAGE "そっか。そういう事なら……\nこれを持っておいきよ。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "実はさ、プレゼントしようと\n思って持ってたんだよね。\nエヘヘ……"
KEY_WAIT
CHAR 2, 1
CHAR 1, 24
FACE 29
MESSAGE "これを着ているとね、魔族の森に\n来ても魔の影響を受けにくいんだ。\n龍の鱗でできているからね。"
KEY_WAIT
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1533
MESSAGE "わ、すごいじゃない！\n私がもらっちゃっていいの？"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "キミにもらって欲しいんだよぅ。\nプレゼントだって言ったでしょ？"
KEY_WAIT
CHAR 2, 7
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 1534
MESSAGE "うわーっ。ありがとう。\n大事にするわ！"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "エヘヘ、どういたしまして。\nこっちに来る時は着ておいで。"
KEY_WAIT
SE_PLAY 57
FACE 65535
OFF_FACE_WINDOW
MESSAGE "龍のドレスを手に入れた！"
KEY_WAIT
SE_STOP
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 36
FLAG 898, 1
LABEL 37
FLAG 899, 1
BGM_PLAY 31
SE_PLAY 14
BG 161
CHAR 2, 1
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "やぁ！"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1518
MESSAGE "あら、リーじゃない。\nこんにちは。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "そろそろ収穫祭の季節だねえ。\n街も賑やかになって、\nなんだかソワソワしちゃうなァ。"
KEY_WAIT
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1519
MESSAGE "ふふふ、そうねぇ。\nお祭りって、準備の時からどこか\n落ち着かない気分になるわね。"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "広場の方はもう結構準備が\n進んでいるみたいだよ。\nこれから見に行かない？"
KEY_WAIT
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1520
MESSAGE "リーって、お祭り好きそうよね？"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "うんうん大好き！　故郷にいた頃は\nこんな催し物なんて全然なかったし\nあー、今年も楽しみだな、収穫祭。"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1521
MESSAGE "そういえば、あなたは何か\n競技に出たりしないの？"
KEY_WAIT
CHAR 1, 24
VOICE 1522
MESSAGE "武闘大会とか、出場すれば\nいいところまで進めると\n思うんだけどなぁ……"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "う～ん、あんまり殺伐としたのって\n好きじゃないんだよねえ。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "ボクはおいしい物を食べたり、\n遊んだりできればそれで十分だよ。\nあははっ♪"
KEY_WAIT
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1523
MESSAGE "やっぱり怠け者なんだから～"
KEY_WAIT
CHAR 1, 26
FACE 31
MESSAGE_NAME "リー"
MESSAGE "え～、そんなことないよ。"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1524
MESSAGE "ウフフ、私の目は\nごまかせないわよ。"
KEY_WAIT
CHAR 2, 1
FACE 0
VOICE 1525
MESSAGE "（でも、本当に出れば\nいいのに……）"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 0
LABEL 38
FLAG 764, 1
LABEL 39
FLAG 765, 1
BGM_STOP 30
BGM_PLAY 31
SE_PLAY 14
OFF_CHAR 3
BG 161
CHAR 2, 1
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "おーい、[娘の名前]ちゃん！"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1411
MESSAGE "あら？\nリーじゃない。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "ねぇ、これからデートしようよ。\nほら、今日は天気もいいし！"
KEY_WAIT
SELECT 2, 40, "デートする", 9, "ダメ"
LABEL 40
BG 176
CHAR 2, 7
CHAR 1, 25
BG 161
FACE 30
MESSAGE_NAME "リー"
MESSAGE "デート、デート、\n今日も楽しくデート。"
KEY_WAIT
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 743
MESSAGE "も、もう、やめてよ。\nほら、あの人笑ってるよ。\n恥ずかしいなぁ……"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "いいじゃん。\nだって楽しいんだもん。"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 744
MESSAGE "んもう……\nで、今日はどこに行くの？"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "今日はダークタウンに\n行こうよ。"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 745
MESSAGE "ダ、ダークタウン？\nなんであんなところに……"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "たまにはいいじゃない。\nいろんな刺激があって\n面白いよ。"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE "ボクがいれば何が起きても\n大丈夫だしさ。"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 746
MESSAGE "大丈夫って、そ、そうねぇ……\nじゃあ……行ってみよっか？"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "決まり！\nハハッ、行こう！"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 747
MESSAGE "あっ、そんなに\n引っ張らないでよ～！"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
BGM_STOP 30
BGM_PLAY 30
BG 168
CHAR 1, 24
CHAR 2, 1
FACE 29
MESSAGE_NAME "リー"
MESSAGE "ほんとはもっと遅い方が\nおもしろいんだけどね～。\nま、いいや。探検といこうよ。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 748
MESSAGE "いいかげんねえ。\n探検って、あてはあるの？"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "エヘヘヘヘ、ない！"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 749
MESSAGE "あ、あはは……"
KEY_WAIT
CHAR 2, 1
FACE 0
VOICE 750
MESSAGE "……あれ？"
KEY_WAIT
OFF_CHAR 1
CHAR 1, 27
FACE 32
MESSAGE_NAME "ヴァロア"
MESSAGE "……ふん。\n今日は妙なのと一緒にいるな。"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 751
MESSAGE "ヴァ、ヴァロアさん！"
KEY_WAIT
FACE 32
MESSAGE_NAME "ヴァロア"
MESSAGE "まあいい。いっしょに来い。\n案内なら俺がしてやる。\nここは俺のテリトリーだからな。"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 752
MESSAGE "わっ、ちょ、ちょっと㌍"
KEY_WAIT
CHAR 1, 26
FACE 31
MESSAGE_NAME "リー"
MESSAGE "ま、待ってよ！"
KEY_WAIT
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
BGM_STOP 30
BGM_PLAY 28
BG 85
FACE 31
MESSAGE_NAME "リー"
MESSAGE "[娘の名前]ちゃんは今、\nボクとデートしてるんだから\n邪魔しないでよ！"
KEY_WAIT
FACE 32
MESSAGE_NAME "ヴァロア"
MESSAGE "ん？　なんだ、お前は……"
KEY_WAIT
FACE 31
MESSAGE_NAME "リー"
MESSAGE "おい……知ってて言ってるだろ㌍\n相変わらず性格の暗いヤツ！"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 753
MESSAGE "ちょ、ちょっと、２人とも……"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "ねっ？　そうだよね。\n今日はボクと遊ぶんだよね？"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 754
MESSAGE "え、えっと……"
SELECT 3, 41, "リーを優先", 42, "ヴァロアを優先", 43, "２人一緒に……"
LABEL 41
FLAG 766, 1
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 755
MESSAGE "そうね。今日はリーと遊びに\n来たから……"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "ほ～らみろ！"
KEY_WAIT
FACE 32
MESSAGE_NAME "ヴァロア"
MESSAGE "ふん、くだらん……"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 756
MESSAGE "あっ、ヴァロアさん……"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "べろべろべ～だ。\n[娘の名前]ちゃん、\nほっときなよ。"
KEY_WAIT
MESSAGE "ほらほら、行こうよ！"
KEY_WAIT
OFF_FACE_WINDOW
FACE 65535
BGM_STOP 30
BGM_PLAY 30
BG 168
CHAR 1, 24
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 757
MESSAGE "うん……そうね。\nでもビックリしちゃった。\nケンカでもするんじゃないかって。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "アハハ、そんなことしないよ。\nそんなことしたら、ダークタウン\nどころか王国中が火の海だ。"
KEY_WAIT
CHAR 2, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 758
MESSAGE "何それ？"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "何でもないよ。\nほら、行こう！"
KEY_WAIT
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 7
LABEL 42
FLAG 767, 1
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 759
MESSAGE "リー……ごめんね。\n私、ヴァロアさんと……"
KEY_WAIT
FACE 31
MESSAGE_NAME "リー"
MESSAGE "え～㌍\nそ、そんなぁ……"
KEY_WAIT
FACE 32
MESSAGE_NAME "ヴァロア"
MESSAGE "行くぞ。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 760
MESSAGE "あっ、ま、待ってよ。\nヴァロアさんったら！"
KEY_WAIT
OFF_FACE_WINDOW
FACE 65535
BGM_STOP 30
BGM_PLAY 30
BG 168
CHAR 1, 27
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 761
MESSAGE "もう……２人ともケンカ\nしそうで怖かったんだから。"
KEY_WAIT
FACE 32
MESSAGE_NAME "ヴァロア"
MESSAGE "そんなことしたらダークタウンが\n吹き飛んでしまう。俺はここが\n好きだからな。"
KEY_WAIT
CHAR 2, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 762
MESSAGE "えっ、どういうこと？"
KEY_WAIT
FACE 32
MESSAGE_NAME "ヴァロア"
MESSAGE "いいから来い。行くぞ。"
OFF_CHAR 1
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 763
MESSAGE "ああん、もう。\n勝手なんだからぁ……"
OFF_CHAR 2
KEY_WAIT
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 8
LABEL 43
FLAG 768, 1
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 764
MESSAGE "じゃ、じゃあ……\nみんなで一緒に……"
KEY_WAIT
FACE 31
MESSAGE_NAME "リー"
MESSAGE "そんなのヤダ！"
KEY_WAIT
FACE 32
MESSAGE_NAME "ヴァロア"
MESSAGE "ふざけるな。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 765
MESSAGE "あうぅ……"
SELECT 2, 41, "リーを優先", 42, "ヴァロアを優先"
LABEL 44
FLAG 799, 1
LABEL 45
FLAG 800, 1
BGM_STOP 30
BGM_PLAY 32
SE_PLAY 14
BG 160
CHAR 2, 1
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "やぁ、[娘の名前]ちゃん。"
KEY_WAIT
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 944
MESSAGE "リー！\nどうしてたの？"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "え、なにが？　ボクは\nいつもどおりさ。"
KEY_WAIT
CHAR 2, 1
CHAR 1, 25
FACE 30
MESSAGE "エヘヘ、君が来そうな\n気がしてたんだ。\nさあ、遊びに行こうよ！"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 945
MESSAGE "えっ、でも……"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "いいから、いいから。\nほら、早く！"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 946
MESSAGE "キャッ、そんなに\n引っ張らないでよ！\nもうー！"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "アハハハ……楽しいなぁ……"
OFF_CHAR 1
OFF_CHAR 2
KEY_WAIT
OFF_FACE_WINDOW
FACE 65535
BG 158
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "ハハハッ！\nねえ、今度はどこへ行く？"
KEY_WAIT
CHAR 2, 3
FACE 2
MESSAGE_NAME "[娘の名前]"
VOICE 947
MESSAGE "リ、リーってば！\nちょっと待ってよ！"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "え？\nどうしたの？"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 948
MESSAGE "どうしたって、その……"
KEY_WAIT
CHAR 2, 9
FACE 8
VOICE 949
MESSAGE "今は戦争中なのよ？　こんな時に\n遊んでたら、いけないような\n気がするの……"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "ん、そうかな？\nそんなの関係ないよ。\nボクたちのせいじゃないもん。"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 950
MESSAGE "うん……\nそうかもしれないけど……"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "んー、何を心配してるのか\n良くわからないけどさ。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "大丈夫。ボクは強い！\n何があってもキミだけは守って\nあげるよ。だから、さぁ！"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 951
MESSAGE "そういうことじゃなくて……"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "うーん……戦争がイヤなのかな？"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "なら、２人で戦争のないところに\n行こうよ。いいところ知ってるよ。\n人はいないけど綺麗でさー。"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 952
MESSAGE "私……ここが好きだから……"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "うん！　ボクもここは退屈しなくて\n大好きだよ、アハハ。"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 953
MESSAGE "はあ……リーったら、こんな時でも\nお気楽なんだから……"
KEY_WAIT
OFF_CHAR 1
OFF_CHAR 2
OFF_FACE_WINDOW
FACE 65535
BGM_STOP 30
BGM_PLAY 22
SE_PLAY 14
BG 100
FACE 29
MESSAGE_NAME "リー"
MESSAGE "よ～し！\nじゃあ、今度は繁華街の方に\n遊びに行こうよ！"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 954
MESSAGE "あっ、リー！　ちょっと待って！\nそれに戦争で店も閉まってる\nかも……"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "ダメダメ！\n時間がもったいないよ。\n早く早く、アハハハハ！"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 955
MESSAGE "もう、リーってば……"
KEY_WAIT
FACE 8
VOICE 956
MESSAGE "でも、そうよね。私なんかが\nどんなに心を痛めても、戦争を\n防ぐことはできないのだし……"
KEY_WAIT
FACE 0
VOICE 957
MESSAGE "今を……この今を大切に\n生きた方がいいのかも……"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "[娘の名前]ちゃん？\nどうしたの、黙り込んじゃって？\nさぁ楽しもうよ、いつものように！"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 958
MESSAGE "いつものように、か。\nそうね……"
KEY_WAIT
FACE 6
VOICE 959
MESSAGE "（そうできたら、とても幸せかも\n知れないわね……）"
KEY_WAIT
BGM_STOP 30
OFF_CHAR 3
OFF_FACE_WINDOW
FACE 65535
END 0
LABEL 46
FLAG 888, 1
LABEL 47
FLAG 889, 1
BGM_PLAY 31
BG 163
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "うーん、満足！\nなかなかおいしかったなぁ、\nここの料理……"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1487
MESSAGE "あら、リーじゃない。\n今日はここでお食事？"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "やあ、[娘の名前]ちゃん。\nちょうど今、ただ飯に\nありついてきたところなんだ㍍"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1488
MESSAGE "た、ただ飯～？\nいったいどういう事……"
KEY_WAIT
CHAR 2, 1
FACE 0
VOICE 1489
MESSAGE "……あら？　お店の前に何か\n書かれてるわね……"
KEY_WAIT
VOICE 1490
MESSAGE "『当店の特別大盛りメニュー……\n１時間で１０人前完食できた\n方は無料……』"
KEY_WAIT
CHAR 2, 6
FACE 5
VOICE 1491
MESSAGE "『……は、終了しました』"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1492
MESSAGE "最後だけ紙が\n付け足されてるわ……"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "タダで食べさせてくれるなんて\nいいお店だよねー！"
KEY_WAIT
CHAR 2, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 1493
MESSAGE "念のために聞くけど……\n１０人前、ちゃんと\n食べられたの？"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "うん、食べたよー㍍\nおいしかったなぁ。"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE "まだ食べられたんだけど、店の人が\nつぶれるって泣き出しちゃったから"
LINE_FEED
CHAR 2, 8
MESSAGE "途中でやめたんだ。"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1494
MESSAGE "はあ……\nよっぽどすごい食べっぷり\nだったんでしょうね……"
KEY_WAIT
CHAR 2, 1
FACE 0
VOICE 1495
MESSAGE "（それで紙が付け足されてたのね。\n文字が殴り書きだったし……）"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "エヘヘ、見たい？　だったらさ、\nこれから一緒に食べに行こうよ！"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1496
MESSAGE "ええっ㌍"
SELECT 2, 48, "行く", 9, "行かない"
LABEL 48
FLAG 890, 1
CHAR 2, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 1497
MESSAGE "いいけど……あなた、まだ\n食べる気なの？"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "エヘヘ、おいしい料理なら\nまだまだ入るよー。"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1498
MESSAGE "すごいお腹してるわね……"
KEY_WAIT
CHAR 2, 9
FACE 8
VOICE 1499
MESSAGE "でも、いい？　もうタダじゃ\n無くなっちゃったのよ？"
KEY_WAIT
CHAR 2, 6
FACE 5
VOICE 1500
MESSAGE "あなたのお腹がふくれる前に、\nきっとお財布の中身が\nからっぽになっちゃうわ。"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "あ、そっか……"
KEY_WAIT
CHAR 2, 8
CHAR 1, 25
FACE 30
MESSAGE "腹の調子よりそっちの方が問題\nだったね、エヘヘ……"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 0
LABEL 49
FLAG 891, 1
LABEL 50
FLAG 892, 1
BGM_PLAY 32
SE_PLAY 14
BG 158
SE_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1501
MESSAGE "えっ……㌍"
KEY_WAIT
CHAR 2, 7
FACE 6
VOICE 1502
MESSAGE "何かしら、あれ？\nキラキラ光って、飛んでる……？"
KEY_WAIT
VOICE 1503
MESSAGE "綺麗……"
KEY_WAIT
CHAR 2, 1
FACE 0
VOICE 1504
MESSAGE "あ……飛んでいった先に\nいるのは……"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "あっ、[娘の名前]ちゃん。\nこんなところで会えるなんて、\nうれしいなぁ～㍍"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1505
MESSAGE "（あ、いなくなったわ……）"
KEY_WAIT
CHAR 2, 1
FACE 0
VOICE 1506
MESSAGE "ねえ、リー。"
KEY_WAIT
VOICE 1507
MESSAGE "今、あなたの周りに何か\nいなかった？"
KEY_WAIT
CHAR 1, 24
VOICE 1508
MESSAGE "こう、小さくて、\nキラキラ光る……"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "ん？　アハ、驚いたな。\n……キミにも見えたの？"
KEY_WAIT
CHAR 2, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 1509
MESSAGE "見えたの？って、変な言い方ねぇ。\n実際に、そこに飛んでたじゃない。\nこう、ひらひら～って……"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "へえ……\n[娘の名前]ちゃん、\nキミって意外と……"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1510
MESSAGE "意外と……なに？"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "え……あ、ううん！\nなんでもないよ！"
KEY_WAIT
MESSAGE "それじゃあ、またね！"
SE_PLAY 7
KEY_WAIT
OFF_CHAR 1
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1511
MESSAGE "あっ、ちょっと、リーったら㌍"
KEY_WAIT
CHAR 2, 1
FACE 0
VOICE 1512
MESSAGE "……行っちゃった？\nいつもみたいに誘われると\n思ったのに……"
KEY_WAIT
CHAR 2, 6
FACE 5
VOICE 1513
MESSAGE "（結局、あれって\n何だったのかしら……？）"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 0
LABEL 51
FLAG 894, 1
LABEL 52
FLAG 895, 1
BGM_PLAY 31
SE_PLAY 14
BG 158
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "はははっ、あはははっ！\n待て待て～！"
KEY_WAIT
FACE 65535
MESSAGE_NAME "子供"
MESSAGE "わ～い、こっちこっちぃ～！"
KEY_WAIT
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1514
MESSAGE "あらあら、今日もご機嫌ね、リー。\n子供たちに遊んでもらってるの？"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "わ、ひどいなァ、\n[娘の名前]ちゃん！"
KEY_WAIT
MESSAGE "ボクがこの子たちと\n遊んであげてるんだよー"
KEY_WAIT
FACE 1
VOICE 1515
MESSAGE "ウフフ、あら、そうだったの？\nじゃあ、そういう事にしておくわ。"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "もう……！"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "まあいいや、キミも一緒に遊ぶ？\nおもしろいよ！"
SELECT 2, 53, "遊ぶ", 54, "遊ばない"
LABEL 53
FLAG 896, 1
CHAR 1, 24
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1516
MESSAGE "行くところあるんだけど……\nウフフ、遊んじゃおうかな。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "そー来なくっちゃ！\nみんな、おねーちゃんも\n一緒に遊ぶって！"
KEY_WAIT
FACE 65535
MESSAGE_NAME "子供たち"
MESSAGE "わぁ～！！"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "アハハハ……\nじゃあ、ボクが鬼だぞーっ！"
SE_PLAY 7
OFF_CHAR 1
KEY_WAIT
FACE 65535
MESSAGE_NAME "子供たち"
MESSAGE "わーっ！"
KEY_WAIT
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1517
MESSAGE "でも、なんだかんだ言って、\n１番楽しんでるのよね、彼。\nフフッ♪"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 0
LABEL 54
FLAG 897, 1
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "そっかぁ。\nじゃあ、また今度遊ぼうね。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "よーし、お待たせ、\n試合再開だぞー！\nヒャッホウ！"
SE_PLAY 7
OFF_CHAR 1
KEY_WAIT
FACE 65535
MESSAGE_NAME "子供たち"
MESSAGE "わぁ～い！！"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 9
LABEL 55
FLAG 879, 1
LABEL 56
FLAG 880, 1
BGM_PLAY 31
SE_PLAY 14
BG 161
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "大丈夫かい？\nもう、だから言ったのになー"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1465
MESSAGE "あら、リーじゃない。\nこんにち……わわっ㌍"
KEY_WAIT
CHAR 2, 5
FACE 4
VOICE 1466
MESSAGE "た、倒れてるっ！\nひ、人が！　ひの、ふの……\nいっぱい㌍　ど、どうしたのよ？"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "ああ、[娘の名前]ちゃんか。"
KEY_WAIT
MESSAGE "いやぁ、ケンカをしようって\n言ってきたからさ、相手を\nしてあげてたんだ。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "あ、でもでも、ボクはやめたほうが\nいいよ、って警告はしたんだよ？\nなのに全然聞いてくれなくてさ。"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE "力比べでもしたかったのかな、\nこの人たち。困っちゃったよー。"
KEY_WAIT
CHAR 2, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 1467
MESSAGE "それで……この人たち全員、\nやっつけちゃったの？\n……１人で？"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "うん。\nあ、もちろん手加減はしたよ。"
KEY_WAIT
CHAR 2, 9
MESSAGE "殺気はあったけど、力がどうにも\n弱いんだもん、みんな。"
KEY_WAIT
FACE 8
MESSAGE_NAME "[娘の名前]"
VOICE 1468
MESSAGE "そ、そう……"
KEY_WAIT
VOICE 1469
MESSAGE "それにしても、１０人以上いる\n相手をたった１人でって……\nリーって本当は強いのね……"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "そう？　ハハハ……\nそんなことはいいからさ、\n遊びに行こうよ。"
SELECT 2, 57, "行く", 9, "行かない"
LABEL 57
FLAG 881, 1
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1470
MESSAGE "でも、このままじゃあ……"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "大丈夫、大丈夫。\n言ったでしょ、手加減したって。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "こんなに人通りあるしさ、\n誰かが助けてくれるよ。"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1471
MESSAGE "う～ん、騒ぎになる前に行った\n方がいいかもしれないわね。"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "そうそう、さっ行こっ！"
KEY_WAIT
SE_PLAY 7
SE_PLAY 7
SE_STOP
BGM_STOP 30
END 0
LABEL 58
FLAG 882, 1
LABEL 59
FLAG 883, 1
BGM_PLAY 31
SE_PLAY 14
BG 161
CHAR 2, 1
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "やっ、[娘の名前]ちゃん！\n今日はお買い物？"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1472
MESSAGE "そうよ。\nこれから服を買いに\n行こうかな……って。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "ねぇねぇ、一緒に\n行っていい？"
SELECT 2, 60, "ＯＫ", 9, "ダメ"
LABEL 60
FLAG 884, 1
FACE 30
MESSAGE_NAME "リー"
MESSAGE "わーい、ありがと。"
KEY_WAIT
MESSAGE "キミはどんな服を着てても\nかわいいけど、新しい服も"
LINE_FEED
CHAR 2, 2
MESSAGE "見てみたいな。エヘヘ……"
KEY_WAIT
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1473
MESSAGE "ふふふ、ありがと。\nそういえば、リーって\nいつもその服なのね。"
KEY_WAIT
CHAR 1, 24
CHAR 2, 1
FACE 0
VOICE 1474
MESSAGE "そのファッション、気に\nいってるんだろうけど……\n冬とか寒くないの？"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "全然。\nボクらって体が丈夫だからね。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "このまま雪山の頂上に行ったって\n平気だよ。"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1475
MESSAGE "はぁー……\nすごいのね。\n私なら凍えちゃうわ。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "あははっ、なんならこれから\n万年雪でも取ってこようか？"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1476
MESSAGE "え、遠慮しておくわ……"
KEY_WAIT
CHAR 2, 8
FACE 7
VOICE 1477
MESSAGE "（本当に取ってきちゃいそうなの\nよね、リーって……）"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 0
LABEL 61
FLAG 885, 1
LABEL 62
FLAG 886, 1
BGM_PLAY 31
SE_PLAY 14
BG 161
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "ふん、ふん、ふーん♪\n今日も楽しいなあ～♪"
KEY_WAIT
CHAR 2, 1
CHAR 1, 25
FACE 30
MESSAGE "あっ、[娘の名前]ちゃん！\nエヘヘ、今日はどこ行くの～？\n一緒に遊ぼうよー！"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1478
MESSAGE "こんにちは、リー。\n残念だけど遊びには\n行けないわよ。"
KEY_WAIT
CHAR 1, 24
CHAR 2, 8
FACE 7
VOICE 1479
MESSAGE "今日はこれから病院に\n行くの。ごめんね。"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "びょういん……って、\nあの病院の事㌍"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1480
MESSAGE "あの？　って言われても……"
KEY_WAIT
CHAR 1, 26
FACE 31
MESSAGE_NAME "リー"
MESSAGE "ええっ㌍　って事はどこか\nケガしたのかい？"
LINE_FEED
CHAR 2, 1
MESSAGE "大丈夫、痛くない？"
KEY_WAIT
CHAR 2, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 1481
MESSAGE "あは、心配してくれてありがとう。\nでも大丈夫よ。今日はちょっと"
LINE_FEED
CHAR 1, 24
MESSAGE "お薬をもらいに行くだけだから。"
KEY_WAIT
CHAR 2, 1
FACE 29
MESSAGE_NAME "リー"
MESSAGE "そうなんだ……安心したよ。\nねぇねぇ、一緒に行っていい？\n病院って見てみたいんだ。"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "ケガや病気を治してくれる\n場所だよね！　街のお年寄りに\n聞いたことがあるよ！"
SELECT 2, 63, "ＯＫ", 9, "ダメ"
LABEL 63
FLAG 887, 1
FACE 30
MESSAGE_NAME "リー"
MESSAGE "やった！　ありがとー！"
KEY_WAIT
CHAR 2, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 1482
MESSAGE "もう……連れてってもいいけど、\n病院についたら静かにしてね？"
LINE_FEED
CHAR 1, 24
MESSAGE "大声出したら怒られちゃうわよ？"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "わ、そうなんだ。おっけー。"
KEY_WAIT
CHAR 2, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1483
MESSAGE "いつも元気ねえ、リーは。"
KEY_WAIT
CHAR 2, 6
FACE 5
VOICE 1484
MESSAGE "そういえば……リーの\n調子の悪そうなところって\n見たことないわね……？"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE_NAME "リー"
MESSAGE "エへへ……自慢じゃないけど、\nボクは産まれてから１度も"
LINE_FEED
CHAR 2, 5
MESSAGE "病気になんてなったことないよ。"
KEY_WAIT
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1485
MESSAGE "そ、そうなの㌍"
KEY_WAIT
CHAR 2, 8
FACE 7
VOICE 1486
MESSAGE "そこまで行くと、\nうらやましいというより、"
LINE_FEED
CHAR 1, 26
MESSAGE "呆れちゃうわね……"
KEY_WAIT
FACE 31
MESSAGE_NAME "リー"
MESSAGE "ええー、なんでだよう～\nひどいなぁ……"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 0
LABEL 64
FLAG 876, 1
LABEL 65
FLAG 877, 1
BGM_PLAY 31
SE_PLAY 14
BG 161
SE_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 1452
MESSAGE "あら……？\nあそこにいるのは……"
KEY_WAIT
FACE 5
VOICE 1453
MESSAGE "リーと……女の子？\n珍しい組み合わせね……"
KEY_WAIT
FACE 4
VOICE 1454
MESSAGE "あっ、女の子が泣き出したわ！\nど、どうしたのかしら？"
KEY_WAIT
FACE 65535
BG 176
MESSAGE "　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　"
KEY_WAIT
BG 161
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "うーん、悪いこと\nしちゃったのかなぁ……"
KEY_WAIT
MESSAGE "でも、しょうがないよね。\nボクが好きなのは……"
KEY_WAIT
CHAR 2, 6
FACE 5
VOICE 1455
MESSAGE "ちょっと、リー？\nさっきの何なの？"
KEY_WAIT
CHAR 1, 26
FACE 31
MESSAGE_NAME "リー"
MESSAGE "えっ……うわっ！\n[娘の名前]ちゃん㌍"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1456
MESSAGE "な、何よ、そんなに\nビックリして……"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "あ……もしかして見てたの？\nその……全部？"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1457
MESSAGE "えっ？　全部って言われても……\nあなたが街の女の子と一緒に\nいたのを見かけただけで……"
KEY_WAIT
CHAR 2, 3
FACE 2
VOICE 1458
MESSAGE "そ、そうよ！\nリー、あなた女の子を\nいじめちゃダメじゃない！"
KEY_WAIT
CHAR 1, 26
FACE 31
MESSAGE_NAME "リー"
MESSAGE "えっ㌍　いじめてなんて\nいないよー？"
KEY_WAIT
CHAR 2, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 1459
MESSAGE "あら、だって泣いてる様に\n見えたわよ？"
KEY_WAIT
CHAR 1, 26
FACE 31
MESSAGE_NAME "リー"
MESSAGE "それは……"
KEY_WAIT
FACE 5
MESSAGE_NAME "[娘の名前]"
VOICE 1460
MESSAGE "それは？"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "はあ……\n[娘の名前]ちゃんには\nわからないのかなぁ……"
KEY_WAIT
CHAR 2, 3
FACE 2
MESSAGE_NAME "[娘の名前]"
VOICE 1461
MESSAGE "あーっ、何よ\nためいきなんてついて。\nバカにしてるの？"
KEY_WAIT
FACE 29
MESSAGE_NAME "リー"
MESSAGE "ち、違うよ。\nボクの事、一人の男性として\n見てくれてないのかな、って……"
KEY_WAIT
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1462
MESSAGE "え？　男性？"
KEY_WAIT
CHAR 1, 26
FACE 31
MESSAGE_NAME "リー"
CHAR 2, 6
MESSAGE "な、何でもない！"
KEY_WAIT
CHAR 1, 25
FACE 30
MESSAGE "そ、そうだ！\nこれからどこか遊びに行こう！\nうん、行こう行こう！"
SELECT 2, 66, "行く", 67, "行かない"
LABEL 66
FLAG 878, 1
CHAR 2, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 1463
MESSAGE "きゃあ！\nちょ、ちょっと、リー㌍"
KEY_WAIT
FACE 30
MESSAGE_NAME "リー"
MESSAGE "いいからいいから！\nねっ？"
KEY_WAIT
CHAR 2, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 1464
MESSAGE "し、仕方ないわねぇ……"
KEY_WAIT
CHAR 1, 24
FACE 29
MESSAGE_NAME "リー"
MESSAGE "（はあ……[娘の名前]ちゃん、\n恋愛にはにぶいみたいだなあ……）"
KEY_WAIT
SE_STOP
BGM_STOP 30
END 0
LABEL 67
FLAG 901, 1
END 9