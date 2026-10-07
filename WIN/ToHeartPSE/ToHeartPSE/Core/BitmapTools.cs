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
            int dstRow = y * stride;
            for (int x = 0; x < width; x++)
            {
                int src = srcRow + x * 4;
                int dst = dstRow + x * 4;
                // Standard LFB uses 32bpp BMP headers, but stores pixels as A,B,G,R.
                pixels[dst + 0] = topDown[src + 3];
                pixels[dst + 1] = topDown[src + 0];
                pixels[dst + 2] = topDown[src + 1];
                pixels[dst + 3] = topDown[src + 2];
            }
        }

        return BuildBmpHeader(width, height, 32, 54, pixels.Length, 0, null)
            .Concat(pixels).ToArray();
    }

    public static byte[] BuildStandardBmp24(Bitmap bitmap)
    {
        byte[] topDown = ExtractTopDownBgra32(bitmap);
        int width = bitmap.Width;
        int height = bitmap.Height;
        int srcStride = width * 4;
        int stride = (width * 3 + 3) & ~3;
        byte[] pixels = new byte[stride * height];
        for (int y = 0; y < height; y++)
        {
            int srcRow = (height - 1 - y) * srcStride;
            int dstRow = y * stride;
            for (int x = 0; x < width; x++)
            {
                int src = srcRow + x * 4;
                int dst = dstRow + x * 3;
                pixels[dst + 0] = topDown[src + 0];
                pixels[dst + 1] = topDown[src + 1];
                pixels[dst + 2] = topDown[src + 2];
            }
        }

        return BuildBmpHeader(width, height, 24, 54, pixels.Length, 0, null)
            .Concat(pixels).ToArray();
    }

    public static byte[] BuildStandardBmp8(Bitmap bitmap)
    {
        byte[] topDown = ExtractTopDownBgra32(bitmap);
        int width = bitmap.Width;
        int height = bitmap.Height;
        byte[] indices = IndexedQuantizer.Build(topDown, width, height, 256, out var palette);
        int stride = (width + 3) & ~3;
        byte[] pixels = new byte[stride * height];
        for (int y = 0; y < height; y++)
        {
            int srcRow = (height - 1 - y) * width;
            int dstRow = y * stride;
            for (int x = 0; x < width; x++)
                pixels[dstRow + x] = indices[srcRow + x];
        }

        return BuildBmpHeader(width, height, 8, 14 + 40 + 256 * 4, pixels.Length, 0, palette)
            .Concat(pixels).ToArray();
    }

    public static byte[] BuildCustomIndexedAlphaBmp(Bitmap bitmap)
    {
        int width = bitmap.Width;
        int height = bitmap.Height;
        byte[] topDown = ExtractTopDownBgra32(bitmap);
        byte[] indices = IndexedQuantizer.Build(topDown, width, height, 256, out var palette);
        byte[] pixels = new byte[width * height * 2];
        int dst = 0;
        for (int y = height - 1; y >= 0; y--)
        {
            int row = y * width * 4;
            for (int x = 0; x < width; x++)
            {
                int src = row + x * 4;
                pixels[dst++] = topDown[src + 3];
                pixels[dst++] = indices[y * width + x];
            }
        }

        return BuildBmpHeader(width, height, 16, 14 + 40 + 256 * 4, pixels.Length, 0, palette)
            .Concat(pixels).ToArray();
    }

    // 原版 LFB 的 BMP 头除 width/height/planes/bpp/offBits 外全部为 0
    // （sizeImage/xppm/yppm/clrUsed 原版不统一，但游戏端四条绘制路径都不读），
    // 这里统一写 0，保持与原版尽可能字节对齐。
    static byte[] BuildBmpHeader(int width, int height, int bpp, int offBits, int pixelBytes,
        int sizeImage, List<(byte R, byte G, byte B)>? palette)
    {
        using var ms = new MemoryStream();
        using var bw = new BinaryWriter(ms, System.Text.Encoding.ASCII, leaveOpen: true);
        bw.Write((byte)'B');
        bw.Write((byte)'M');
        int paletteBytes = palette != null ? 256 * 4 : 0;
        bw.Write(14 + 40 + paletteBytes + pixelBytes);
        bw.Write((ushort)0);
        bw.Write((ushort)0);
        bw.Write(offBits);
        bw.Write(40);
        bw.Write(width);
        bw.Write(height);
        bw.Write((ushort)1);
        bw.Write((ushort)bpp);
        bw.Write(0);
        bw.Write(sizeImage);
        bw.Write(0);
        bw.Write(0);
        bw.Write(0);
        bw.Write(0);
        if (palette != null)
        {
            for (int i = 0; i < 256; i++)
            {
                if (i < palette.Count)
                {
                    bw.Write(palette[i].B);
                    bw.Write(palette[i].G);
                    bw.Write(palette[i].R);
                }
                else
                {
                    bw.Write((byte)0);
                    bw.Write((byte)0);
                    bw.Write((byte)0);
                }
                bw.Write((byte)0);
            }
        }
        return ms.ToArray();
    }
}
