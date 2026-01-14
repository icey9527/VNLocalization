LABEL 0
CHAR 0, 1
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
END 0
LABEL 1
SE_PLAY 6
SE_WAIT
SE_PLAY 1
SE_WAIT
SE_PLAY 3
SE_WAIT
BGM_PLAY 22
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "失礼します旦那様、\n執事のキューブです。"
KEY_WAIT
FACE 26
MESSAGE "お嬢様は今日も元気です。"
KEY_WAIT
MESSAGE "いつの間にか\nお嬢様も大きくなられましたねぇ…"
KEY_WAIT
FACE 25
MESSAGE "でも、これからが難しい\n年頃なのかもしれません。"
KEY_WAIT
FACE 23
MESSAGE "よりいっそう注意して\nお育てしないといけませんね。"
KEY_WAIT
MESSAGE "お嬢様の今後の育成について\nなにかご相談は\nございますでしょうか？"
SELECT 2, 3, "はい", 2, "いいえ"
LABEL 2
MESSAGE "わかりました。"
KEY_WAIT
GOTO 4
LABEL 3
SPECIAL 0
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "それでは、下画面を見ながら説明を\nきいていただけますか？"
KEY_WAIT
SPECIAL 1
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "「Ｈｅａｌｔｈ」では、\n基本的な育成方針が決められます。"
KEY_WAIT
MESSAGE "ここでの調整は、健康状態の他、\nお嬢様の身長や体重、スリーサイズ\nなどに反映されることになります。"
KEY_WAIT
SPECIAL 2
SPECIAL 3
FACE 23
MESSAGE "「活発に育てる」では、\n養育費がかかりますが\n丈夫に育てられます。"
KEY_WAIT
MESSAGE "ただし、食べすぎには\n気をつけてください。"
KEY_WAIT
SPECIAL 4
FACE 23
MESSAGE "「ダイエットさせる」は\n体力に負担をかけますので\n注意してください。"
KEY_WAIT
SPECIAL 5
FACE 23
MESSAGE "「おしとやかに育てる」は、\nそれほど養育費はかかりません。"
KEY_WAIT
MESSAGE "ただし、体力に自信がない場合は\nお勧めできません。"
KEY_WAIT
SPECIAL 11
FACE 26
MESSAGE "普段は「無理はさせない」で\nよいと思います。"
KEY_WAIT
SPECIAL 0
SPECIAL 6
FACE 23
MESSAGE "「Ｓｃｈｅｄｕｌｅ」でお嬢様の\n月の行動を決めてください。"
KEY_WAIT
SPECIAL 7
SPECIAL 8
FACE 23
MESSAGE "「勉強」でお嬢様の才能を\n伸ばしたり「アルバイト」で\n社会勉強するのもいいですね。"
KEY_WAIT
SPECIAL 9
FACE 26
MESSAGE "でも、お休みに街へ出かけて\n世間を知ることやバカンスでの\n親子のふれあいも大切ですよ。"
KEY_WAIT
FACE 23
MESSAGE "その行動でどのくらいお金がかかる\nか、またはアルバイトでどのくらい\n稼げるか所持金欄に表示されます。"
KEY_WAIT
SPECIAL 12
MESSAGE "あくまで、だいたいの目安ですが、\n参考にしてくださいね。"
KEY_WAIT
SPECIAL 0
SPECIAL 13
MESSAGE "「Ｔａｌｋ」でお嬢様とお話が\nできます。"
KEY_WAIT
FACE 26
MESSAGE "お嬢様を寂しがらせぬよう、\n毎月１度はお話してさしあげて\nくださいね。"
KEY_WAIT
SPECIAL 14
FACE 23
MESSAGE "お嬢様の状態を考えて、適切な\n会話をしてあげてください。"
KEY_WAIT
MESSAGE "何が適切かを知るのも、親として\n重要だと思いますよ。"
KEY_WAIT
SPECIAL 0
SPECIAL 15
MESSAGE "「Ｓｔａｔｕｓ」で、お嬢様の\n現在の状態がわかります。"
KEY_WAIT
SPECIAL 10
MESSAGE "このメニュー以外でもお嬢様の\n状態は表示されていますので\n常に参考して下さい。"
KEY_WAIT
MESSAGE "また、この画面でＬキーかＲキーを\n押すことで、画面上部の表示を\n切り替えることができます。"
KEY_WAIT
SPECIAL 0
MESSAGE "この画面でも切り替えは可能です。\n全部で４行あるうち、３行が表示\nされます。"
KEY_WAIT
MESSAGE "必要に応じて切り替えて下さい。"
KEY_WAIT
SPECIAL 10
MESSAGE "また、Ｙボタンを押すことで\nウィンドウを消して、下の画面を\n見ることができます。"
KEY_WAIT
MESSAGE "ただしハートマークの絵が出ている\n時しか消すことができませんので\n注意して下さいね。"
KEY_WAIT
MESSAGE "Ｘボタンはメッセージを高速で\n早送りします。一度読んだ所とかで\n使えば便利だと思います。"
KEY_WAIT
LABEL 4
FACE 65535
OFF_FACE_WINDOW
MESSAGE "　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　\n　　　　　　　　・　　　　　　　"
KEY_WAIT
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
BGM_STOP 60
FACE 65535
MESSAGE_NAME "[娘の名字]"
MESSAGE "このキューブは、\n[娘の名前]を引き取った時に\n執事として主従の契約をした。"
KEY_WAIT
MESSAGE "その契約とは、\n娘の行動を見守ること。"
KEY_WAIT
MESSAGE "そしてその行動を、私に\nうそ偽りなく報告することだ。"
KEY_WAIT
MESSAGE "契約を違えることなく\n何かと役に立ってくれている。"
KEY_WAIT
MESSAGE "イザベルは、[娘の名前]と\nキューブを託した。"
KEY_WAIT
MESSAGE "将来[娘の名前]が\n大きくなったとき、イザベルと会う\n機会ができるだろうか？"
KEY_WAIT
MESSAGE "そんな時でも\n自分の複雑な境遇を受け止め、\n負けない子に育って欲しい。"
KEY_WAIT
MESSAGE "立派な大人に育てなければ……\n私の残りの人生は\n娘のためにあるのだから……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
SE_PLAY 1
SE_WAIT
SE_PLAY 3
SE_WAIT
ROOM_BGM_PLAY
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 2668
MESSAGE "パパ、おはよう！\n今日はとってもいい天気\n気持ちいいねぇ～"
KEY_WAIT
VOICE 2669
MESSAGE "私もパパと一緒にがんばるぞー\nあははっ！"
KEY_WAIT
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "さて、旦那様\n最初に何をなさいますか？"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
END 0
LABEL 5
CHAR 0, 0
FACE 65535
OFF_FACE_WINDOW
MESSAGE "娘が病気になった。"
KEY_WAIT
END 0
LABEL 6
CHAR 0, 0
FACE 65535
OFF_FACE_WINDOW
MESSAGE "娘が不良になった。\nいくつかのバイトが\nできなくなった。"
KEY_WAIT
END 0
LABEL 7
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "だっ、旦那様！　今しがた、\nお嬢様が倒られましたよっ㌍\nあ、はいっ。幸い大事には……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
END 0
LABEL 8
FLAG 1702, 1
CHAR 0, 0
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "最近、お嬢様の体調が思わしくない\nようです。少し、お休みさせて\nあげてはいかがでしょうか。"
KEY_WAIT
MESSAGE "私は魔族ですが、病魔はやはり\n嫌いですから……はい。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
END 0
LABEL 9
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "旦那様！\nお嬢様が、全快なされました！"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
END 0
LABEL 10
FLAG 1703, 1
CHAR 0, 0
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "旦那様。\n最近、お嬢様の素行がよろしくない\nという評判が聞こえてまいります。"
KEY_WAIT
MESSAGE "わたしにも最近冷たいというか\nよそよそしいと言いますか……\nお話もそっけ無くて…ううっ……"
KEY_WAIT
MESSAGE "やはりお嬢様の心を開く事が\nできるのは旦那様です。\nどうか、よろしくお願いします。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
END 0
LABEL 11
CHAR 0, 1
FACE 24
MESSAGE_NAME "キューブ"
MESSAGE "旦那様、た、大変です！\nお嬢様がなんだか悪い子に～！"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2502
MESSAGE "キューブ、うるさい！\n私のことはほっといてよー！"
KEY_WAIT
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "そ、そんなぁ……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
CHAR 0, 1
END 0
LABEL 12
CHAR 0, 1
FACE 24
MESSAGE_NAME "キューブ"
MESSAGE "旦那様、た、大変です！\nお嬢様が、お嬢様が\n不良にい～っ……㌍"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2503
MESSAGE "うるさいわよキューブ！\n私がどうなろうと貴方には\n関係ないでしょう？"
KEY_WAIT
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "そ、そんなぁ……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
CHAR 0, 1
END 0
LABEL 13
CHAR 0, 1
FACE 24
MESSAGE_NAME "キューブ"
MESSAGE "旦那様、た、大変です！\nお嬢様が……お嬢様が……"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
VOICE 2504
MESSAGE "騒ぐような事じゃないわよ、\nキューブ。私がどうなろうと、\n私の勝手よ。"
KEY_WAIT
VOICE 2505
MESSAGE "そう、みんな自分勝手。\nお父様だって……"
KEY_WAIT
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "そ、そんなぁ……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
CHAR 0, 1
END 0
LABEL 14
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 2506
MESSAGE "キューブ。あ、あの、この前は\nひどい事言っちゃって、ごめんね。"
KEY_WAIT
FACE 27
MESSAGE_NAME "キューブ"
MESSAGE "お嬢様……\nそんな、いいんですよ。\n気にしないでくださいね。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 2507
MESSAGE "うん♪　ありがとねっ。"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
CHAR 0, 0
END 0
LABEL 15
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 2508
MESSAGE "ごめんなさい、キューブ。\nこの前の私、どうかしてた……"
KEY_WAIT
FACE 27
MESSAGE_NAME "キューブ"
MESSAGE "お顔をあげて下さい、お嬢様。\n私は気にしていませんから。\nでも、ちょっとホッとしました。"
KEY_WAIT
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 2509
MESSAGE "心配させちゃってるよね、\nキューブ。\nごめんなさい……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
CHAR 0, 0
END 0
LABEL 16
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 2510
MESSAGE "キューブ、ごめんなさい。\n貴方のこと考えないで、私……\nひどい事言っちゃって……"
KEY_WAIT
FACE 27
MESSAGE_NAME "キューブ"
MESSAGE "いえいえ。正直な気持ちを\nぶつけて下さって、わたしは\nうれしく思います。"
KEY_WAIT
MESSAGE "これからも無理はなさらないで。\nつらかった時は、またわたしに\nあたって下さい。ね、お嬢様。"
KEY_WAIT
CHAR 0, 7
FACE 6
MESSAGE_NAME "[娘の名前]"
VOICE 2511
MESSAGE "……キューブ。私……貴方が\nそばに居てくれて、本当に\n良かった……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
CHAR 0, 0
END 0
LABEL 17
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 2687
MESSAGE "パパ、わたしの誕生日おぼえてる？\n悪い子だからお祝いして\nもらえないのかなぁ…"
KEY_WAIT
CHAR 0, 0
END 0
LABEL 18
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 2648
MESSAGE "今年の誕生日は、\nなんだかさびしいわ………"
MESSAGE "　　　　　　　　　　　"
MESSAGE "私のことなんて興味ないのかしら…"
KEY_WAIT
CHAR 0, 0
END 0
LABEL 19
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
VOICE 2619
MESSAGE "お父様、贅沢なんて言わないけど\n誕生日って特別なものだと思うわ…"
KEY_WAIT
CHAR 0, 0
END 0
LABEL 20
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "旦那様。お城から今年の\n給付金が届いてますよ。\n大切に使いましょうねっ。"
KEY_WAIT
END 0
LABEL 21
FACE 28
MESSAGE_NAME "キューブ"
MESSAGE "今のお嬢様の体形では、\n少々きついようですね。"
KEY_WAIT
MESSAGE "……着替えていただきます。"
KEY_WAIT
END 0
LABEL 22
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 2673
MESSAGE "えー、きつくないもん。\n頑張ればきられるもん…\nパパわたし太ってるの？"
KEY_WAIT
END 0
LABEL 23
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 2637
MESSAGE "あーん。\n私ってそんなに太っちゃったの！\nどうしよう…"
KEY_WAIT
END 0
LABEL 24
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 2606
MESSAGE "ああっ…\n私ったらいつのまに太っちゃった\nのかしら…"
KEY_WAIT
END 0
LABEL 25
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "宿屋のファットマンさんが\nアルバイトを募集している\nようです。"
KEY_WAIT
END 0
LABEL 26
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "魔界の店が追加されました。\nＳｈｏｐから買い物ができます。"
KEY_WAIT
END 0