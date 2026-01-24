LABEL 0
FLAG 648, 1
CHAR 0, 1
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "なんの用だい？\nお嬢ちゃん。\nここから先はダークタウンだ。"
KEY_WAIT
MESSAGE "子供の来るところじゃない。\nさぁさぁ、帰った帰った。"
KEY_WAIT
MESSAGE "大人になってきれいなねえちゃん\nになったら、またおいで。\nその時は大歓迎だぜ、イヒヒ。"
KEY_WAIT
END 0
LABEL 1
FACE 65535
MESSAGE "因業が上がった。"
KEY_WAIT
END 0
LABEL 2
FLAG 651, 1
CHAR 0, 1
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "よぅ、お前か。"
KEY_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
MESSAGE "はい、通行料！"
KEY_WAIT
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "いらねぇよ。"
KEY_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
MESSAGE "えっ、なんで㌍"
KEY_WAIT
MESSAGE "まさか、入れてくれないなんて\n言わないでしょうね㌍"
KEY_WAIT
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "逆だよ。お前はもう俺達の同類だ。\nさぁ、入れ。もう、ここに入るのを\n見咎める者は誰もいない。"
KEY_WAIT
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
MESSAGE "そ、そうなんだ……\n得したような、そうでないような\n……不思議な気分ね……"
KEY_WAIT
END 0
LABEL 3
FLAG 649, 1
CHAR 0, 1
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "なんの用だい？\nお嬢ちゃん。\nここから先はダークタウンだ。"
KEY_WAIT
MESSAGE "チンピラ、無法者に\nいかがわしい店……"
KEY_WAIT
MESSAGE "そんなのがひしめき合って\n暮らしている暗黒街だ。"
KEY_WAIT
MESSAGE "門番の俺としては、\nお嬢ちゃんのような子供を\n通すわけにはいかないな。"
KEY_WAIT
CHAR 0, 9
FACE 8
MESSAGE_NAME "[娘の名前]"
MESSAGE "お願い！\nどうしても行ってみたいの。\n……ダメ？"
KEY_WAIT
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "うーん……\nしようがないな。\n特別に許可しよう。"
KEY_WAIT
CHAR 0, 2
FACE 1
MESSAGE_NAME "[娘の名前]"
MESSAGE "ほんと㌍\nやったあ。"
KEY_WAIT
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "ただし、通行料を１０Ｇ頂くがね。"
KEY_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
MESSAGE "ええっ㌍\nお金取るの㌍"
KEY_WAIT
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "オッホン！\nそういう決まりになって\nいるんだよ。さあ、どうする？"
KEY_WAIT
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
MESSAGE "うーん……\nしかたないわね。"
KEY_WAIT
END 0
LABEL 4
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "おう、ありがとよ。\nまあ、せいぜい気をつけて\n行っておいで。"
KEY_WAIT
END 0
LABEL 5
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "おいおい……\nこれっぽっちじゃ\n通してやるわけにはいかないぜ。"
KEY_WAIT
MESSAGE "ほら、とっとと帰んな。"
KEY_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
MESSAGE "ええ～、そのくらいいいじゃない。\nケチッ！"
KEY_WAIT
END 0
LABEL 6
FLAG 650, 1
CHAR 0, 1
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "なんだ、また来たのか。\nこりないねぇ……"
KEY_WAIT
MESSAGE "それじゃあ、いつも通り……"
KEY_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
MESSAGE "はいはい、通行料でしょ。"
KEY_WAIT
END 0
LABEL 7
SELECT 2, 8, "魔界に行く", 9, "ダークタウンをぶらつく"
LABEL 8
END 0
LABEL 9
END 1
LABEL 10
FLAG 749, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
MESSAGE "ねぇ、よく背の高い無愛想な人が\nここにこない？"
KEY_WAIT
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "無愛想なやつ、ねぇ。"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
MESSAGE "大きな刀を背負ってて\nでも、怖そうな人には\n見えなかったな。"
KEY_WAIT
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "大きな刀…\nお嬢ちゃん、その人と話したのか？"
KEY_WAIT
FACE 0
MESSAGE_NAME "[娘の名前]"
MESSAGE "うん、ちょっとだけだけど。"
KEY_WAIT
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "お嬢ちゃん、\nその人はヴァロア様だぞ。"
KEY_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
MESSAGE "ヴァロアさん？"
KEY_WAIT
FACE 76
MESSAGE_NAME "ヨーダ"
MESSAGE "ああ、おいそれと口にはできねぇが\nダークタウンにはいろいろな奴らが\n集まるからな。へっへっへ。"
KEY_WAIT
CHAR 0, 1
MESSAGE "それより、\nダークタウンに入るのかい？"
KEY_WAIT
OFF_FACE_WINDOW
FACE 65535
OFF_FACE_WINDOW
MESSAGE_WINDOW 0
END 0
LABEL 11
FLAG 1536, 1
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "見慣れない顔ですが……\nあまりこの町を\nウロウロしないことです。"
KEY_WAIT
MESSAGE "無用のトラブルに巻き込まれたく\nないならね。"
KEY_WAIT
END 0
LABEL 12
FLAG 1537, 1
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "前から思ってたんだが……\nお前さん、実は魔族と\n深い関係でもあるのか？"
KEY_WAIT
MESSAGE "あ、いや、詮索は野暮だったな、\n忘れてくれ。\n多分、俺の思い過ごしだ……"
KEY_WAIT
END 0
LABEL 13
FLAG 1538, 1
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "闇ルートで流通する魔法石の量が\n増えてきましたね。"
KEY_WAIT
MESSAGE "どこかで鉱脈でも\n発見されたということでしょうか。"
KEY_WAIT
END 0
LABEL 14
FLAG 1539, 1
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "表の景気がよいときは、\nこちらも稼ぎ時と言えるでしょう。"
KEY_WAIT
MESSAGE "皆さん、気が大きくなって\n金離れもいいですからね。"
KEY_WAIT
END 0
LABEL 15
FLAG 1540, 1
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "不干渉の約定を破り、\nまた戦いを仕掛けますか……"
KEY_WAIT
MESSAGE "２度も裏切られた側は、\n腸が煮え繰り返る思いでしょうね。"
KEY_WAIT
MESSAGE "……いえ、どちら側のことかは、\n私の口からは、ちょっと…………"
KEY_WAIT
END 0
LABEL 16
FLAG 1541, 1
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "おいおいおい、戦争なんて正気か？\n魔族とコトを構えて\nただで済むはずがないだろうが……"
KEY_WAIT
MESSAGE "はなっから勝てない勝負に\n出るなんて、信じられないぜ！"
KEY_WAIT
END 0
LABEL 17
FLAG 1542, 1
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "魔法石を使った新兵器……\nなるほど、このために王家は石を\n溜め込んでいたわけですか。"
KEY_WAIT
END 0
LABEL 18
FLAG 1543, 1
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "世間では名君と名高い国王ですが、\n果たして本当に\nそうなのでしょうか？"
KEY_WAIT
MESSAGE "無用な争いを撒き散らし、\n国を２度も危うくさせるなど……"
KEY_WAIT
MESSAGE "もっとも、私としては\nその方が商売も\nやりやすくなるのですがね。"
KEY_WAIT
END 0
LABEL 19
FLAG 1544, 1
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "ええい、バカが起こした\n戦争のおかげで\n魔族の視線が痛いぜ……"
KEY_WAIT
MESSAGE "気にしてない奴が多いとはいえ、\nこっちゃいい迷惑だ。"
KEY_WAIT
END 0
LABEL 20
FLAG 1545, 1
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "噂によると、王室も極秘に軍を\n派遣して、魔法石の発掘に\n当たらせているようですね。"
KEY_WAIT
MESSAGE "どこに派遣しているかまでは\nはっきりしませんが、\n気になる動きですね。"
KEY_WAIT
END 0
LABEL 21
FLAG 1546, 1
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "どうやら今出回っている魔法石は\n王室がどこかで掘り出したものの\n横流し品のようですね。"
KEY_WAIT
MESSAGE "フフフ、どこにでも\n腐った輩はいるものです。"
KEY_WAIT
END 0
LABEL 22
FLAG 1547, 1
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "開戦ですか……\n前線に送られる兵隊の中には\n常連も多いですからね……"
KEY_WAIT
MESSAGE "店には手痛い事態ですな。"
KEY_WAIT
END 0
LABEL 23
FLAG 1548, 1
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "魔族に大勝ですか……\nどこまで信用してよいものやら。"
KEY_WAIT
END 0
LABEL 24
FLAG 1549, 1
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "予想通りですね。\n魔族を怒らせればどうなるか、\n既にわかっていたはずでしょうに。"
KEY_WAIT
END 0
LABEL 25
FLAG 1550, 1
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "聞いた話だと、この戦争で\n大儲けをしてるヤツが\nいるらしいんだ……"
KEY_WAIT
MESSAGE "たいしたもんだね、まったく……\n俺もあやかりたいよ。"
KEY_WAIT
END 0
LABEL 26
FLAG 1551, 1
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "ふむ、こう景気が低迷していると、\nこちらとしても商売がやりにくくて\n仕方がありません。"
KEY_WAIT
MESSAGE "どうにか回復して\nほしいものですが。"
KEY_WAIT
END 0
LABEL 27
FLAG 1552, 1
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "こりゃ人間の負けだな……\nだからあの時\nやめときゃいいって言ったんだ。"
KEY_WAIT
MESSAGE "これからどうなることやら……"
KEY_WAIT
END 0
LABEL 28
FLAG 1553, 1
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "そういや、クライスって成金野郎が\nよく顔を出すんだ。"
KEY_WAIT
MESSAGE "魔法石の取引で一山当てたらしくて\nうなるほど金を持ってるって\n話なんだが……"
KEY_WAIT
MESSAGE "賭け事はさっぱり弱くてな。"
KEY_WAIT
MESSAGE "スッテンテンになって\n帰ってったよ。\nざまあみろだぜ。"
KEY_WAIT
END 0
LABEL 29
FLAG 1554, 1
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "クライスの野郎、\nあんまり勝てないのに\n業を煮やしたのか、"
KEY_WAIT
MESSAGE "よりにもよってこの賭場を\n買収しようとしてきやがった！\n何考えてるんだ、あの男は㌍"
KEY_WAIT
END 0
LABEL 30
FLAG 1555, 1
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "この前の買収の話だけどな、\nここは賭場らしく賭けで勝負を\nつけようって持ちかけたのさ。"
KEY_WAIT
MESSAGE "俺が負けたらここはくれてやる。\nかわりに俺が買ったら、\nあいつの交易船団をよこせってな。"
KEY_WAIT
MESSAGE "さすがにビビったのか、\n捨て台詞はいて退散したよ。\nいい気味だねえ！"
KEY_WAIT
END 0
LABEL 31
FLAG 1556, 1
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "フムッ、華がある！"
KEY_WAIT
CHAR 0, 5
FACE 4
MESSAGE_NAME "[娘の名前]"
MESSAGE "えっ㌍"
KEY_WAIT
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "世の中、努力して身につくものと\nつかないものがある。"
KEY_WAIT
MESSAGE "パッと見た時に、人の目を\n惹きつけてしまう……\n稀なる資質だな。"
KEY_WAIT
MESSAGE "キミにはそれがある！"
KEY_WAIT
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
MESSAGE "は、はぁ……？"
KEY_WAIT
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "どうだね、キミの素晴らしさを\n生かせる仕事があるのだが、\nやってみないかね？"
KEY_WAIT
CHAR 0, 6
FACE 5
MESSAGE_NAME "[娘の名前]"
MESSAGE "えっ……\nどんなお仕事ですか？"
KEY_WAIT
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "カジノだよ。最初は雑用だが、\nやがてはキミ目当てにお客さんが\n来るようになる。"
KEY_WAIT
MESSAGE "そうなれば、お金は稼ぎ放題だ。"
KEY_WAIT
CHAR 0, 8
FACE 7
MESSAGE_NAME "[娘の名前]"
MESSAGE "えーーと……"
KEY_WAIT
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "ハハハ、ここで結論を出さなくても\nいいよ。よく考えな。"
KEY_WAIT
MESSAGE "でも、お金が稼ぎたいんだったら\nうちに勝るところはないよ。"
KEY_WAIT
CHAR 0, 1
FACE 0
MESSAGE_NAME "[娘の名前]"
MESSAGE "あのっ……\n（行っちゃった……カジノかぁ……\nちょっと興味はあるけど……）"
KEY_WAIT
END 0
LABEL 32
FLAG 1557, 1
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "ああ、そこの美しいお嬢さん。\n少し、お時間をいただいても\nよろしいでしょうか？"
KEY_WAIT
MESSAGE "貴女に大変よいお話が\nあるのですが……"
KEY_WAIT
CHAR 0, 9
FACE 8
MESSAGE_NAME "[娘の名前]"
MESSAGE "え？　ええと、あなたは……？"
KEY_WAIT
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "ああ、これは申し遅れました。"
KEY_WAIT
MESSAGE "私、グレージュといいまして\nこの町でその……酒場……\nそう、酒場を経営しております。"
KEY_WAIT
MESSAGE "声をおかけしたのは\n他でもありません。"
KEY_WAIT
MESSAGE "貴女のような美しい女性に、\nぜひ私の酒場で\n働いていただきたいのです。"
KEY_WAIT
MESSAGE "もちろん、それに見合うだけの\n十分な報酬はお払いします。"
KEY_WAIT
MESSAGE "どうでしょう、あなたの美しさを、\n活かしてみたいとは思いませんか？"
KEY_WAIT
CHAR 0, 7
FACE 6
MESSAGE_NAME "[娘の名前]"
MESSAGE "私の、美しさを……\nど、どうしよう……\n困っちゃうなぁ。"
KEY_WAIT
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "もちろん今すぐとは申しません。\nその気になっていただけましたら、\n私の店までおいでください。"
KEY_WAIT
MESSAGE "お待ちしていますよ。"
KEY_WAIT
END 0
LABEL 33
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "正規のルートでは\n流通しないような品も、\nこの街には数多く集まってきます。"
KEY_WAIT
MESSAGE "特に魔法に関連する品物は、\nここでしか手に入らないものも\n多いと思いますよ。"
KEY_WAIT
END 0
LABEL 34
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "表面的な倫理や道徳を説いただけで\n立派な人間ができあがると\n信じているなら、"
KEY_WAIT
MESSAGE "その人物はよほどの愚か者か、\nよほど幸せな育ち方を\nしてきたのでしょうな。"
KEY_WAIT
END 0
LABEL 35
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "１度、教会のシスターが\nこの町に押しかけてきて\n浄化を訴えかけたようですね。"
KEY_WAIT
MESSAGE "いわく「こんな地区は\n神罰が下されるであろう」だとか。"
KEY_WAIT
MESSAGE "いやはや、おめでたい思考を\nお持ちの方もいるものですな。"
KEY_WAIT
END 0
LABEL 36
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "普段からメイドの扮装をして\n街を闊歩する女性がいるよう\nですね。"
KEY_WAIT
MESSAGE "たとえ美しい方でも、そのように\n知性に欠けた振る舞いをなさる方は\n遠慮したいものです。"
KEY_WAIT
END 0
LABEL 37
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "カジノのオーナーも\nうちの得意客の１人ですね。"
KEY_WAIT
MESSAGE "荒稼ぎしては、\nこちらで散財なさる。"
KEY_WAIT
MESSAGE "金は天下の回りもの、とは\nよくいったものです。"
KEY_WAIT
END 0
LABEL 38
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "世間ではいろいろと言われている\nようですが、私にも私なりの\n経営哲学というものがあります。"
KEY_WAIT
MESSAGE "ただ儲ければよい、\nというわけではないのですよ。"
KEY_WAIT
END 0
LABEL 39
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "この街で店を持つことは、\n安全な街区でそうすることの\n何倍も難しいのですよ。"
KEY_WAIT
MESSAGE "貴女も同じ立場に立つことが\nあれば、それを痛感することに\nなるでしょう。"
KEY_WAIT
MESSAGE "フフフ、もっとも、だからこそ\n面白いし、儲かるわけですけどね。"
KEY_WAIT
END 0
LABEL 40
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "魔族とて、美しいものを\n好むことに変わりはないはず。"
KEY_WAIT
MESSAGE "であれば、私にとってはお客様で\nあることに違いはありませんね。"
KEY_WAIT
END 0
LABEL 41
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "まあ、ここの住人の間では\n公然の秘密となっていますが、"
KEY_WAIT
MESSAGE "このダークタウンにもかなりの数の\n魔族が存在しているんですよ。"
KEY_WAIT
MESSAGE "もちろん、ひと目ではわからぬよう\n姿を変えてはいるようですが。"
KEY_WAIT
END 0
LABEL 42
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "みな恐ろしい怪物ばかりのように\n思われている魔族ですが、"
KEY_WAIT
MESSAGE "意外なことに約束だけは\n絶対に破らないのですよ。"
KEY_WAIT
MESSAGE "いつ寝首をかかれるか\nわからないような人間を\n相手にするより、"
KEY_WAIT
MESSAGE "よほど商売も\nしやすいというものです。"
KEY_WAIT
MESSAGE "……もちろん、人間が彼らとの\n約束を破る分には、\n何の不自由もないのですがね。"
KEY_WAIT
MESSAGE "ククククッ……"
KEY_WAIT
END 0
LABEL 43
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "無能な人間ほど、見ていて\n腹立たしいものはありませんね。\nその自覚がない者はなおさらだ。"
KEY_WAIT
MESSAGE "貴女も、そう思うでしょう？"
KEY_WAIT
END 0
LABEL 44
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "そろそろ収穫祭の季節ですね。\n人材発掘にもいい機会ですから、\n見学に行くとしましょうか。"
KEY_WAIT
END 0
LABEL 45
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "ルールさえわかっていれば、\nそれほど恐ろしい場所でも\nないのですよ。この町はね。"
KEY_WAIT
END 0
LABEL 46
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "余計なことは聞かない、話さない。\n他人の事情に関わらない。\n強いものには逆らわない。"
KEY_WAIT
MESSAGE "この町で生きていくための\nルールですよ。"
KEY_WAIT
END 0
LABEL 47
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "また、役人たちがうるさくなって\nきましたね。"
KEY_WAIT
MESSAGE "少し付け届けを\n増やしてやりますか。"
KEY_WAIT
END 0
LABEL 48
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "火の粉を振り払う自信がないなら\n極力目立たないようにするか、\n誰かに庇護を求めるのが正解です。"
KEY_WAIT
MESSAGE "もちろん、何事にも\n金は必要ですがね。"
KEY_WAIT
END 0
LABEL 49
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "世間では魔窟だの掃き溜めだのと\n形容されるこの町ですが、\n想像してごらんなさい、"
KEY_WAIT
MESSAGE "この町がなかったらどうなるかを。\nはみだし者が道にあふれ、\n無法者が城下を闊歩する様子を。"
KEY_WAIT
MESSAGE "そして、遠からずどこかに\n第２、第３のダークタウンが\nできるでしょう。"
KEY_WAIT
MESSAGE "ここは、この国の負の部分を\n受け止める役割を\n果たしているんですよ。"
KEY_WAIT
MESSAGE "そう、この町は\nあるべくしてあるものなのです。"
KEY_WAIT
END 0
LABEL 50
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "今の世継ぎがどんな人物なのか、\nはっきりしたことは、私たちにも\nほとんどわかっていないのです。"
KEY_WAIT
MESSAGE "与し易い相手であれば\nいいのですがね……"
KEY_WAIT
END 0
LABEL 51
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "権力に執着のある人物ほど、\n金の力にも弱くなるものです。"
KEY_WAIT
MESSAGE "無用な暴力や手間をかけないで\n済みますし、私たちとしても、\nつきあい易い相手ですね。"
KEY_WAIT
MESSAGE "誰のことかって？\nさぁね、\nフフフフ……"
KEY_WAIT
END 0
LABEL 52
FACE 69
MESSAGE_NAME "グレージュ"
MESSAGE "行政を司る者たちから見れば、\n我々は目の上の\nたんこぶなのでしょうな。"
KEY_WAIT
MESSAGE "何かと目の敵にされていますよ。"
KEY_WAIT
END 0
LABEL 53
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "今日も客の入りは上々らしいな。\nさてさて、それじゃ今日も\n稼がせてもらいますか。"
KEY_WAIT
MESSAGE "よかったら、\nお前さんも遊んでいってくれよ。"
KEY_WAIT
END 0
LABEL 54
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "相変わらず胡散臭い所だろ？\nまあ、そこがいいんだけどな。"
KEY_WAIT
MESSAGE "逆にきれい過ぎる場所ってのは、\n誰だって居心地が悪いもんさ。\n賭けてもいいぜ？"
KEY_WAIT
END 0
LABEL 55
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "最近はカタギの連中が多くて\nやりにくいぜ……"
KEY_WAIT
MESSAGE "わかってないやつを\nカモにしちまうと、あとあと\n面倒になることも多くてな。"
KEY_WAIT
END 0
LABEL 56
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "確かにここは危険も多いが、\n最低限のルールさえ守ってりゃ\n過ごしやすい場所だぜ。"
KEY_WAIT
MESSAGE "もっとも、最近は仁義をわきまえて\nない奴らも増えたからな。\n油断は禁物だぜ。"
KEY_WAIT
END 0
LABEL 57
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "１度、こっち側にはまったら、\nもう２度と抜け出せないぞ……\n賭けてもいいね。"
KEY_WAIT
MESSAGE "おっと、\n脅かすつもりはないんだぜ？\nフフフフ……"
KEY_WAIT
END 0
LABEL 58
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "お前さん、意外と\n素質があるかもしれないな。"
KEY_WAIT
MESSAGE "おいおい、そんな怖い顔するなよ。\nほめてるんだぜ？"
KEY_WAIT
END 0
LABEL 59
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "まったく、王宮の人間ってのは、\nみんな世間知らずだな。"
KEY_WAIT
MESSAGE "俺たち一般人がどんな生活を\nしてるかなんて知らないままで、\n政治なんかできるわけがないんだ。"
KEY_WAIT
END 0
LABEL 60
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "偉いさんの中には、\nこの地区をつぶそうなんて\n動きもあるようだが……"
KEY_WAIT
MESSAGE "そんなことをしたら\nどうなるか……なんて事、\n考えてもいないだろうぜ。"
KEY_WAIT
MESSAGE "……っと、こんなもん、\n賭けにすらならないな。"
KEY_WAIT
END 0
LABEL 61
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "カイさんって、\n王宮魔導師やってた人だろう？"
KEY_WAIT
MESSAGE "よく魔法の資料やら資材やらを\n買いに来てるみたいだな。"
KEY_WAIT
MESSAGE "美人はどこにいても目立つし、\n見ててイイもんだよなぁ。"
KEY_WAIT
END 0
LABEL 62
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "サーナティアちゃんの\nステージは最高だな。\n俺も思わず熱くなっちまうぜ。"
KEY_WAIT
MESSAGE "ん？\nお前さんにはまだ早いかな……"
KEY_WAIT
END 0
LABEL 63
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "この地区はケンカが\n絶えないからな。"
KEY_WAIT
MESSAGE "ナルサスのじい様に\n世話になってるやつは多いぜ。"
KEY_WAIT
MESSAGE "俺か？　俺は……あれだ。\n野蛮なことには手を\n出さない主義さ。"
KEY_WAIT
END 0
LABEL 64
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "教会のシスターには\n困ったもんだな。"
KEY_WAIT
MESSAGE "事あるごとに浄化だなんだって\nここに乗り込んでこようと\nしやがる。"
KEY_WAIT
MESSAGE "きれいすぎる水にゃ\n魚も棲まないって言うだろ？"
KEY_WAIT
MESSAGE "多少は汚れたところが\nあったほうが、生き物ってのは\n過ごしやすいもんさ。"
KEY_WAIT
MESSAGE "もちろん、人間だって同じことだ。"
KEY_WAIT
END 0
LABEL 65
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "街中でレストランをやってる\nシラクってのはいい腕をしてるな。"
KEY_WAIT
MESSAGE "うちのマズイ料理に慣れた舌じゃ、\nうますぎてビックリしちまうぜ。"
KEY_WAIT
END 0
LABEL 66
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "レイブの旦那とは\n長い付き合いでな。"
KEY_WAIT
MESSAGE "おっと、別にやましいことを\nしてるわけじゃねえぜ。"
KEY_WAIT
MESSAGE "酒を飲みながら\nいろいろと話をするだけさ。\nいろいろと……な。"
KEY_WAIT
END 0
LABEL 67
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "メイド酒場か……\n確かに変わった店だが……\nありゃ、流行るぜ？"
KEY_WAIT
MESSAGE "もちろん、賭けてもいいぜ。"
KEY_WAIT
END 0
LABEL 68
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "俺も昔はケチなチンピラだったが、\n手先の器用さと度胸を\n先代に買われてな。"
KEY_WAIT
MESSAGE "小間使いから始まって、\n今じゃカジノのオーナー様\nってわけだ。"
KEY_WAIT
END 0
LABEL 69
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "人間なんてのは\nあまり信用しちゃいけねえ。"
KEY_WAIT
MESSAGE "裏切ったりガッカリさせられたり\nするもんだ、と思って\n付き合うことだな。"
KEY_WAIT
MESSAGE "俺は今までも、これからも\nそうやって生きて行くさ。"
KEY_WAIT
END 0
LABEL 70
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "金は大事だぜ。\n人間と違って金は嘘を\nつかねえからな。"
KEY_WAIT
MESSAGE "だが、あまり大事にしすぎて\nいざっていう時に賭けに\n踏み出せないようじゃ、"
KEY_WAIT
MESSAGE "そいつは２流ってことだな。\nそんな奴からは、\n金も自然と離れていくのさ。"
KEY_WAIT
END 0
LABEL 71
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "俺みたいな人間が言うのもなんだが\nグレージュの奴もなかなかアコギな\n商売をしてるぜ。"
KEY_WAIT
MESSAGE "使えない人間は\n端から使い捨てだからな。"
KEY_WAIT
MESSAGE "お前さんも、あいつに関わるときは\n注意しないと、痛い目を見るぜ。\nこんなの、賭けるまでもねえな。"
KEY_WAIT
END 0
LABEL 72
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "繁華街にいる占い師のバアさん、\n今でもたまに店を開いている\nらしいな。"
KEY_WAIT
MESSAGE "若い頃、あのバアさんに\n占ってもらったことがあってな。"
KEY_WAIT
MESSAGE "当時ははなから\n信用しちゃいなかったが、"
KEY_WAIT
MESSAGE "今思えば、俺がこの稼業につく事も\nぴったり当ててやがったよ。\nなかなか大した腕だって事だな。"
KEY_WAIT
END 0
LABEL 73
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "門番の奴、通行人から\n小遣いをせびっちゃ、\nうちの店でスっていくのさ。"
KEY_WAIT
MESSAGE "まあ、人の金だからどうでもいいが\nつまらねえ使い方してるよなぁ。"
KEY_WAIT
END 0
LABEL 74
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "世間じゃ、悪の化身だなんだと\n言われちゃいるが、魔族の連中とは\n付き合って損はないぞ。"
KEY_WAIT
MESSAGE "あれで気のいい連中も多いしな。\n嘘をつかねえから、\n人間よりよっぽど信用できるぜ。"
KEY_WAIT
END 0
LABEL 75
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "ここじゃあ、結構な数の魔族が\n人間と同じように\n暮らしてたりするんだぜ。"
KEY_WAIT
MESSAGE "それどころか、魔族だからと\n気にするような奴らは、\n逆に野暮だって思われるのさ。"
KEY_WAIT
MESSAGE "今までお前さんが会った奴の中にも\n魔族がいたかもな。"
KEY_WAIT
END 0
LABEL 76
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "魔族とつるむつもりなら\n気をつけな。"
KEY_WAIT
MESSAGE "あの連中は味方ならいいが、\n敵にまわせば最悪だからな……"
KEY_WAIT
MESSAGE "怒らせるようなことだけは\nしないのが身のためだぜ。\nこれは賭けてもいい。"
KEY_WAIT
END 0
LABEL 77
FACE 64
MESSAGE_NAME "トリタム"
MESSAGE "追い込まれた状況からの大逆転！\nこれに勝る快感はこの世にないね。"
KEY_WAIT
MESSAGE "相手のマヌケ面を見下ろして\n高笑いをかましたときは、\n天にも昇るような気分さ！"
KEY_WAIT
END 0
LABEL 78
FACE 48
MESSAGE_NAME "カイ"
MESSAGE "魔法の道具を揃えるなら、やっぱり\nこの界隈じゃないといけないわね。"
KEY_WAIT
MESSAGE "少しばかり高いけれど、\n品揃えには代えられないもの。\n次は何を買おうかしら。"
KEY_WAIT
END 0