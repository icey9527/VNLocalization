LABEL 0
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "このまま自宅でお休みさせるか、\n念のため病院に入院させるか\n……いかがいたしますか？"
SELECT 2, 7, "入院させる", 1, "自宅で療養する"
LABEL 1
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "わかりました、自宅療養ですね。\nそれでは、お嬢様に誰がついて\n看病しますか？"
LABEL 2
SELECT 2, 3, "自分で看病", 6, "キューブが看病"
LABEL 3
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "旦那様は、お休みになって\nお嬢様を看病することになります。"
KEY_WAIT
FACE 25
MESSAGE "その間、\n余計にお金がかかってしまいますが\nよろしいですか？"
SELECT 2, 5, "はい", 4, "いいえ"
LABEL 4
FACE 23
MESSAGE "いかがいたしますか？"
GOTO 2
LABEL 5
FACE 23
MESSAGE "わかりました。旦那様の所用は\n手配しておきますので、お嬢様を\nよろしくお願いします。"
KEY_WAIT
OFF_FACE_WINDOW
FACE 65535
END 1
LABEL 6
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "わかりました。\nそれでは、旦那様の代わりに不肖\n私めが、お嬢様の看病を承ります。"
KEY_WAIT
OFF_FACE_WINDOW
FACE 65535
END 2
LABEL 7
FACE 23
MESSAGE_NAME "キューブ"
MESSAGE "それでは、お嬢様は今日から\n入院することになります。"
KEY_WAIT
MESSAGE "退院するまで安静第一。\n仕事も勉強も控えさせて頂きます。\nでは。"
KEY_WAIT
OFF_FACE_WINDOW
FACE 65535
END 0