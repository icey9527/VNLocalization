namespace ToHeartPSE;

internal sealed record PakEntry(string Name, byte[] Data);
internal readonly record struct LffMeta(int X, int Y, int Width, int Height);
// LFB 元数据。引擎把 BMP 头 +38/+42（biXPelsPerMeter/biYPelsPerMeter）挪用为
// 默认绘制坐标（sub_415A50），故 PosX/PosY 必须原样保留；bpp 决定绘制路径分派。
// 调色板统一按 256 槽生成（offBits 恒 1078），槽位数本身无代码依赖。
internal readonly record struct LfbMeta(int Width, int Height, int Bpp, int PosX, int PosY);
internal sealed record LcfMeta(short OffsetX, short OffsetY, int Width, int Height, byte[] TailBytes);
