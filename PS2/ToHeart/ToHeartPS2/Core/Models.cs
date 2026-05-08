namespace ToHeartPS2;

internal sealed record NamedData(string Name, byte[] Data);

internal sealed class ListEntry
{
    public ListEntry(uint index, string path, int size)
    {
        Index = index;
        Path = path;
        Size = size;
    }

    public uint Index { get; }
    public string Path { get; }
    public int Size { get; }
    public Dictionary<string, string> Attributes { get; } = new(StringComparer.OrdinalIgnoreCase);
}

internal sealed record ElfNamedEntry(uint Index, string Path);

internal sealed record SfsIndexedEntry(uint Index, string Path, byte[] Data);

internal sealed record ImageMetaEntry(string Name, uint X, uint Y, uint Cols, uint Rows);

internal sealed record NamePointerArray(string Name, uint Address, IReadOnlyList<string> Values);

// sub_11AE30 会先填充运行时绘制队列，再交给 sub_13ECD0 刷出。
// 每行固定 0x50 字节 / 20 个 dword，前 12 个 dword 就是我们重建切图要用到的矩形字段。
internal sealed record RuntimeDrawEntryLayout(
    string Flags,
    string NamePtr,
    string DestX,
    string DestY,
    string Layer,
    string DestWidth,
    string DestHeight,
    string SourceX,
    string SourceY,
    string SourceWidth,
    string SourceHeight,
    string Color);

internal sealed record EndingDrawOp(
    string TextureName,
    int DestX,
    int DestY,
    int Layer,
    int DestWidth,
    int DestHeight,
    int SourceX,
    int SourceY,
    int SourceWidth,
    int SourceHeight,
    uint Color,
    string Notes = "");

internal sealed record EndingSceneSpec(
    string Name,
    uint CaseAddress,
    string Notes,
    IReadOnlyList<EndingDrawOp> Ops);

// 很多菜单 / UI 函数都会用到这种运行时绘制描述：
// { name_ptr, part_index, src_x, src_y, width, height }。
internal sealed class TppPartMeta
{
    public uint Width { get; init; }
    public uint Height { get; init; }
    public uint X { get; init; }
    public uint Y { get; init; }
    public string PartName { get; init; } = "";
    public ushort PartReserved { get; init; }
    public uint PartFlagA { get; init; }
    public uint PartFlagB { get; init; }
    public ushort Packed { get; init; }
    public bool Is4Bit { get; init; }
    public string PaletteHeaderHex { get; init; } = "";
    public string ImageHeaderHex { get; init; } = "";
    public string PaletteDataHex { get; init; } = "";
    public string ImageDataHex { get; init; } = "";
}

internal sealed class TppMeta
{
    public string Name { get; init; } = "";
    public uint HeaderReserved { get; init; }
    public bool HasPalette { get; set; }
    public bool SpecialStack { get; init; }
    public uint LayoutCols { get; init; } = 1;
    public uint LayoutRows { get; init; } = 1;
    public uint OriginX { get; init; }
    public uint OriginY { get; init; }
    public uint CanvasWidth { get; init; }
    public uint CanvasHeight { get; init; }
    public uint TrimX { get; set; }
    public uint TrimY { get; set; }
    public List<TppPartMeta> Parts { get; } = [];
}
