namespace ToHeartPSE;

internal sealed record PakEntry(string Name, byte[] Data);
internal readonly record struct LffMeta(int X, int Y, int Width, int Height);
internal readonly record struct LfbMeta(int Width, int Height, string Kind);
internal sealed record LcfMeta(short OffsetX, short OffsetY, int Width, int Height, byte[] TailBytes);
