using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

namespace ToHeartPSE;

internal static class BitmapTools
{
    public static Bitmap CreateArgb(int width, int height, out BitmapData data, out int stride)
    {
        var bmp = new Bitmap(width, height, PixelFormat.Format32bppArgb);
        data = bmp.LockBits(new Rectangle(0, 0, width, height), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
        stride = data.Stride;
        return bmp;
    }

    public static void CopyRow(BitmapData data, int y, byte[] row, int stride)
    {
        IntPtr dest = IntPtr.Add(data.Scan0, y * stride);
        Marshal.Copy(row, 0, dest, row.Length);
    }

    public static Bitmap CloneToArgb(Bitmap source)
    {
        Rectangle rect = new(0, 0, source.Width, source.Height);
        return source.Clone(rect, PixelFormat.Format32bppArgb);
    }

    public static Bitmap FromBottomUpBgr24(int width, int height, byte[] pixels)
    {
        var bmp = CreateArgb(width, height, out BitmapData data, out int stride);
        try
        {
            byte[] rowOut = new byte[width * 4];
            int rowSize = width * 3;
            for (int srcY = 0; srcY < height; srcY++)
            {
                int row = srcY * rowSize;
                for (int x = 0; x < width; x++)
                {
                    int src = row + x * 3;
                    int dst = x * 4;
                    rowOut[dst + 0] = pixels[src + 0];
                    rowOut[dst + 1] = pixels[src + 1];
                    rowOut[dst + 2] = pixels[src + 2];
                    rowOut[dst + 3] = 255;
                }
                CopyRow(data, height - 1 - srcY, rowOut, stride);
            }
        }
        finally
        {
            bmp.UnlockBits(data);
        }
        return bmp;
    }

    public static byte[] ExtractTopDownBgra32(Bitmap bitmap)
    {
        Rectangle rect = new(0, 0, bitmap.Width, bitmap.Height);
        BitmapData data = bitmap.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
        try
        {
            byte[] buffer = new byte[bitmap.Width * bitmap.Height * 4];
            for (int y = 0; y < bitmap.Height; y++)
            {
                IntPtr src = IntPtr.Add(data.Scan0, y * data.Stride);
                Marshal.Copy(src, buffer, y * bitmap.Width * 4, bitmap.Width * 4);
            }
            return buffer;
        }
        finally
        {
            bitmap.UnlockBits(data);
        }
    }

    public static byte[] ExtractBottomUpBgr24(Bitmap bitmap)
    {
        byte[] topDown = ExtractTopDownBgra32(bitmap);
        byte[] output = new byte[bitmap.Width * bitmap.Height * 3];
        int srcStride = bitmap.Width * 4;
        int dstStride = bitmap.Width * 3;
        for (int y = bitmap.Height - 1; y >= 0; y--)
        {
            int srcRow = y * srcStride;
            int dstRow = (bitmap.Height - 1 - y) * dstStride;
            for (int x = 0; x < bitmap.Width; x++)
            {
                int src = srcRow + x * 4;
                int dst = dstRow + x * 3;
                output[dst + 0] = topDown[src + 0];
                output[dst + 1] = topDown[src + 1];
                output[dst + 2] = topDown[src + 2];
            }
        }
        return output;
    }

    public static byte[] BuildStandardBmp32(Bitmap bitmap)
    {
        byte[] topDown = ExtractTopDownBgra32(bitmap);
        int width = bitmap.Width;
        int height = bitmap.Height;
        int stride = width * 4;
        byte[] pixels = new byte[topDown.Length];
        for (int y = 0; y < height; y++)
        {
            int srcRow = (height - 1 - y) * stride;
            Buffer.BlockCopy(topDown, srcRow, pixels, y * stride, stride);
        }

        using var ms = new MemoryStream();
        using var bw = new BinaryWriter(ms, System.Text.Encoding.ASCII, leaveOpen: true);
        bw.Write((byte)'B');
        bw.Write((byte)'M');
        bw.Write(14 + 40 + pixels.Length);
        bw.Write((ushort)0);
        bw.Write((ushort)0);
        bw.Write(54);
        bw.Write(40);
        bw.Write(width);
        bw.Write(height);
        bw.Write((ushort)1);
        bw.Write((ushort)32);
        bw.Write(0);
        bw.Write(pixels.Length);
        bw.Write(2835);
        bw.Write(2835);
        bw.Write(0);
        bw.Write(0);
        bw.Write(pixels);
        return ms.ToArray();
    }

    public static byte[] BuildCustomIndexedAlphaBmp(Bitmap bitmap)
    {
        int width = bitmap.Width;
        int height = bitmap.Height;
        byte[] topDown = ExtractTopDownBgra32(bitmap);
        byte[] palette;
        byte[] pixels = TryCreateExactPalette(topDown, out palette)
            ? BuildCustomPixelsExact(topDown, width, height, palette)
            : BuildCustomPixelsQuantized(topDown, width, height, out palette);

        using var ms = new MemoryStream();
        using var bw = new BinaryWriter(ms, System.Text.Encoding.ASCII, leaveOpen: true);
        bw.Write((byte)'B');
        bw.Write((byte)'M');
        bw.Write(14 + 40 + 256 * 4 + pixels.Length);
        bw.Write((ushort)0);
        bw.Write((ushort)0);
        bw.Write(14 + 40 + 256 * 4);
        bw.Write(40);
        bw.Write(width);
        bw.Write(height);
        bw.Write((ushort)1);
        bw.Write((ushort)16);
        bw.Write(0);
        bw.Write(pixels.Length);
        bw.Write(2835);
        bw.Write(2835);
        bw.Write(256);
        bw.Write(0);
        bw.Write(palette);
        bw.Write(pixels);
        return ms.ToArray();
    }

    static bool TryCreateExactPalette(byte[] topDown, out byte[] palette)
    {
        var colors = new List<int>(256);
        var seen = new HashSet<int>();
        for (int i = 0; i < topDown.Length; i += 4)
        {
            int rgb = topDown[i + 2] << 16 | topDown[i + 1] << 8 | topDown[i + 0];
            if (!seen.Add(rgb))
                continue;
            if (colors.Count >= 256)
            {
                palette = Array.Empty<byte>();
                return false;
            }
            colors.Add(rgb);
        }

        palette = new byte[256 * 4];
        for (int i = 0; i < colors.Count; i++)
        {
            int rgb = colors[i];
            palette[i * 4 + 0] = (byte)(rgb & 0xFF);
            palette[i * 4 + 1] = (byte)((rgb >> 8) & 0xFF);
            palette[i * 4 + 2] = (byte)((rgb >> 16) & 0xFF);
        }
        return true;
    }

    static byte[] BuildCustomPixelsExact(byte[] topDown, int width, int height, byte[] palette)
    {
        var lookup = new Dictionary<int, byte>();
        for (int i = 0; i < 256; i++)
        {
            int rgb = palette[i * 4 + 2] << 16 | palette[i * 4 + 1] << 8 | palette[i * 4 + 0];
            if (!lookup.ContainsKey(rgb))
                lookup.Add(rgb, (byte)i);
        }

        byte[] pixels = new byte[width * height * 2];
        int dst = 0;
        for (int y = height - 1; y >= 0; y--)
        {
            int row = y * width * 4;
            for (int x = 0; x < width; x++)
            {
                int src = row + x * 4;
                int rgb = topDown[src + 2] << 16 | topDown[src + 1] << 8 | topDown[src + 0];
                pixels[dst++] = topDown[src + 3];
                pixels[dst++] = lookup[rgb];
            }
        }
        return pixels;
    }

    static byte[] BuildCustomPixelsQuantized(byte[] topDown, int width, int height, out byte[] palette)
    {
        palette = new byte[256 * 4];
        for (int r = 0; r < 8; r++)
        for (int g = 0; g < 8; g++)
        for (int b = 0; b < 4; b++)
        {
            int index = (r << 5) | (g << 2) | b;
            palette[index * 4 + 0] = (byte)(b * 255 / 3);
            palette[index * 4 + 1] = (byte)(g * 255 / 7);
            palette[index * 4 + 2] = (byte)(r * 255 / 7);
        }

        byte[] pixels = new byte[width * height * 2];
        int dst = 0;
        for (int y = height - 1; y >= 0; y--)
        {
            int row = y * width * 4;
            for (int x = 0; x < width; x++)
            {
                int src = row + x * 4;
                int ri = (topDown[src + 2] * 7 + 127) / 255;
                int gi = (topDown[src + 1] * 7 + 127) / 255;
                int bi = (topDown[src + 0] * 3 + 127) / 255;
                pixels[dst++] = topDown[src + 3];
                pixels[dst++] = (byte)((ri << 5) | (gi << 2) | bi);
            }
        }
        return pixels;
    }
}
