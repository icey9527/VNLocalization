LABEL 0
FLAG 697, 1
LABEL 1
FLAG 698, 1
BGM_STOP 30
BGM_PLAY 18
BG 0
FACE 91
MESSAGE_NAME "クマ"
MESSAGE "……ねぇねぇ……ちゃん……"
KEY_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 542
MESSAGE "えっ？\n誰か……呼んだ？\nキューブ……じゃない……誰㌍"
KEY_WAIT
FACE 91
MESSAGE_NAME "クマ"
MESSAGE "ねぇねぇ……\nボクだよ？　ほらキミのすぐそばに\nいるよ。ずっと呼んでいたんだよ。"
KEY_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
VOICE 543
MESSAGE "もしかして……クマさん？"
KEY_WAIT
FACE 91
MESSAGE_NAME "クマ"
MESSAGE "ウフフ……\nやっと聞こえるようになったね。\nボクは……"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 544
MESSAGE "うわぁー！　すごいすごい！\nクマさんがしゃべってる！\nかわいい～！"
KEY_WAIT
CHAR 0, 2
FACE 1
VOICE 545
MESSAGE "そうだ！　お父さんにも\n教えてあげようっと！\n急げー！"
KEY_WAIT
OFF_CHAR 3
FACE 65535
OFF_FACE_WINDOW
SE_PLAY 7
SE_WAIT
SE_PLAY 2
SE_WAIT
SE_PLAY 3
FACE 91
MESSAGE_NAME "クマ"
MESSAGE "あっ、ちょ、ちょっと……"
KEY_WAIT
BG 64
FACE 1
MESSAGE_NAME "[娘の名前]"
VOICE 546
MESSAGE "あっ、お父さん！\n聞いて聞いて！"
KEY_WAIT
VOICE 547
MESSAGE "大変なの！　この子がね、\n急にしゃべり始めたの！\nすごいでしょ！"
KEY_WAIT
FACE 7
VOICE 548
MESSAGE "ほら、ねぇ、しゃべって！\n……あれ？　おかしいなぁ……\nでもウソじゃないよ！"
KEY_WAIT
VOICE 549
MESSAGE "ほんとにしゃべったのに！\n変だなぁ……照れてるのかなぁ……"
KEY_WAIT
FACE 65535
OFF_FACE_WINDOW
BG 176
BG 0
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "お呼びですか？\n旦那様。"
KEY_WAIT
FACE 23
MESSAGE "あのクマのぬいぐるみ……ですか？\nあれはイザベル様がお持たせに\nなったもので……"
KEY_WAIT
MESSAGE "魔族の血が目覚めると、クマが\n話しているのが聞こえるように\nなります。"
KEY_WAIT
FACE 25
MESSAGE "お嬢様がクマがしゃべったと\nおっしゃるなら、イザベル様の\n心配が当たってしまったようです。"
KEY_WAIT
FACE 23
MESSAGE "魔族の血を極力抑える方法を\nご説明いたしましょうか？"
SELECT 2, 2, "聞く", 3, "聞かない"
LABEL 2
FLAG 699, 1
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "教会の聖水などの抗魔具で\n魔族の血を抑えることが\nできます。"
KEY_WAIT
MESSAGE "ただし、効果には限界があります\nので、抑えるためには折につけ\n再度の手当てが必要になります。"
KEY_WAIT
MESSAGE "また、魔界に近づいたり魔界関係の\n装備品を着けたりしますと魔族の血\nはより活性化いたします。"
KEY_WAIT
FACE 28
MESSAGE "お嬢様の精神状態も鍵になります。\n旦那様の育て方が重要です。\nどうか、ご注意くださいませ。"
KEY_WAIT
BGM_STOP 30
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
END 0
LABEL 3
FLAG 700, 1
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "イザベル様はお嬢様の人としての\n成長を望んでおいででした。\n後は旦那様のご意志次第です。"
KEY_WAIT
BGM_STOP 30
FACE 65535
OFF_FACE_WINDOW
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
END 0