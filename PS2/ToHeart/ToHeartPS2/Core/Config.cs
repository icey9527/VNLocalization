namespace ToHeartPS2;

internal sealed class Config
{
    // DATA 归档在 ELF 里使用的目录表地址。
    public uint EntryAddr { get; private set; } = 0x231610;
    public uint NameAddr { get; private set; } = 0x246A00;
    public uint BaseAddr { get; private set; } = 0x000FFF80;

    // 游戏内 TPP 加载器会读取的 0x24 字节图片元数据表。
    public uint CharMetaAddr { get; private set; } = 0x2E66D0;
    public uint CharMetaCountAddr { get; private set; } = 0x2936D0;
    public uint EtcMetaAddr { get; private set; } = 0x2ED4D0;
    public uint EtcMetaCountAddr { get; private set; } = 0x2936D8;

    // UI 代码还会使用多组 6 word 的绘制描述表：
    // { name_ptr, part_index, src_x, src_y, width, height }。
    // 这些并不是一张总表，而是按场景 / 函数分散存放的。
    public uint SaveMenuSpecAddr { get; private set; } = 0x293DC0;
    public uint SaveMenuSpecCount { get; private set; } = 236;
    public uint AlbumSpecAddr { get; private set; } = 0x290780;
    public uint AlbumSpecCount { get; private set; } = 22;
    public uint MenuBg2SpecAddr { get; private set; } = 0x294210;
    public uint MenuBg2SpecCount { get; private set; } = 6;
    public uint MenuSbgSpecAddr { get; private set; } = 0x2942A0;
    public uint MenuSbgSpecCount { get; private set; } = 6;
    public uint MenuFrameSpecAddr { get; private set; } = 0x294FA8;
    public uint MenuFrameSpecCount { get; private set; } = 6;
    public uint OptionMenuSpecAAddr { get; private set; } = 0x28F980;
    public uint OptionMenuSpecACount { get; private set; } = 4;
    public uint OptionMenuSpecBAddr { get; private set; } = 0x28F9B0;
    public uint OptionMenuSpecBCount { get; private set; } = 4;
    public uint OptionMenuSpecCAddr { get; private set; } = 0x28FA10;
    public uint OptionMenuSpecCCount { get; private set; } = 4;
    public uint OptionMenuSpecDAddr { get; private set; } = 0x28FB78;
    public uint OptionMenuSpecDCount { get; private set; } = 4;

    // sub_11AE30 结局场景会用到的名字数组。
    // 它们本质上是同一片有序名字表里的若干指针切片，不是彼此独立的完整表。
    public uint EndingMainNameArrayAddr { get; private set; } = 0x28DC20;
    public uint EndingSkNameArrayAddr { get; private set; } = 0x28DC74;
    public uint EndingSihoEndNameArrayAddr { get; private set; } = 0x28DC88;
    public uint EndingSihoEndSepiaNameArrayAddr { get; private set; } = 0x28DC8C;
    public uint EndingRollNameArrayAddr { get; private set; } = 0x28DC90;

    public static Config Load() => new();
}
