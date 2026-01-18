namespace VNTextractor.Core;

public static class PathNaming
{
    public static string ToPosixPath(string path) => path.Replace('\\', '/');

    public static string ToNativePath(string posixPath) => posixPath.Replace('/', Path.DirectorySeparatorChar);

    // Match user's python logic: "<original file name> + .txt"
    public static string MakeAllTxtPerFilePath(string alltxtDir, string relPosix)
    {
        var relNative = ToNativePath(relPosix);
        var relDir = Path.GetDirectoryName(relNative);
        var name = Path.GetFileName(relNative);
        var outName = name + ".txt";

        return relDir is null
            ? Path.Combine(alltxtDir, outName)
            : Path.Combine(alltxtDir, relDir, outName);
    }

    public static string MakeDlTxtPerFilePath(string dltxtDir, string relPosix)
    {
        var relNative = ToNativePath(relPosix);
        var relDir = Path.GetDirectoryName(relNative);
        var name = Path.GetFileName(relNative);
        var outName = name + ".txt";

        return relDir is null
            ? Path.Combine(dltxtDir, outName)
            : Path.Combine(dltxtDir, relDir, outName);
    }

    // IMPORTANT: do NOT strip original extension; keep "a.ks.json" style.
    public static string MakeParatranzPerFilePath(string jsonDir, string relPosix)
    {
        var relNative = ToNativePath(relPosix);
        var relDir = Path.GetDirectoryName(relNative);
        var name = Path.GetFileName(relNative);
        var outName = name + ".json";

        return relDir is null
            ? Path.Combine(jsonDir, outName)
            : Path.Combine(jsonDir, relDir, outName);
    }

    public static string StripTrailingExtension(string fileName, string extensionWithDot)
    {
        if (fileName.EndsWith(extensionWithDot, StringComparison.OrdinalIgnoreCase))
            return fileName[..^extensionWithDot.Length];
        return fileName;
    }
}
