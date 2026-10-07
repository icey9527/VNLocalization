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

    public static byte[] BuildStandardBmp32Pixels(Bitmap bitmap)
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
        return pixels;
    }

    public static byte[] BuildStandardBmp24Pixels(Bitmap bitmap)
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
        return pixels;
    }

    public static byte[] BuildStandardBmp8Pixels(Bitmap bitmap, int maxColors, out List<(byte R, byte G, byte B)> palette)
    {
        byte[] topDown = ExtractTopDownBgra32(bitmap);
        int width = bitmap.Width;
        int height = bitmap.Height;
        byte[] indices = IndexedQuantizer.Build(topDown, width, height, maxColors, out palette);
        int stride = (width + 3) & ~3;
        byte[] pixels = new byte[stride * height];
        for (int y = 0; y < height; y++)
        {
            int srcRow = (height - 1 - y) * width;
            int dstRow = y * stride;
            for (int x = 0; x < width; x++)
                pixels[dstRow + x] = indices[srcRow + x];
        }
        return pixels;
    }

    public static byte[] BuildCustomIndexedAlphaPixels(Bitmap bitmap, int maxColors, out List<(byte R, byte G, byte B)> palette)
    {
        int width = bitmap.Width;
        int height = bitmap.Height;
        byte[] topDown = ExtractTopDownBgra32(bitmap);
        byte[] indices = IndexedQuantizer.Build(topDown, width, height, maxColors, out palette);
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
        return pixels;
    }

    // 生成 LFB 的 BMP 头。游戏端全部 7 个 BMP 消费函数（4 条 bpp 绘制路径、
    // 位置/尺寸辅助 sub_415A50/AA0、加载器）读取的字段经逐一审计仅为：
    //   +10 offBits（像素起点，= 54 + 调色板字节数）、+14 biSize（=40，调色板定位）、
    //   +18/+22 宽高、+28 bpp、+38/+42（被 sub_415A50 挪用为默认绘制坐标 x/y）。
    // 其余字段（fileSize/sizeImage/clrUsed/clrImportant）无任何代码读取，按惯例
    // 生成：fileSize=精确值、sizeImage=0、clrUsed=有调色板时 256 否则 0、clrImportant=0。
    public static byte[] BuildBmpHeader(int width, int height, int bpp, int offBits, int pixelBytes,
        int posX, int posY, int clrUsed)
    {
        using var ms = new MemoryStream();
        using var bw = new BinaryWriter(ms, System.Text.Encoding.ASCII, leaveOpen: true);
        bw.Write((byte)'B');
        bw.Write((byte)'M');
        bw.Write(offBits + pixelBytes);
        bw.Write((ushort)0);
        bw.Write((ushort)0);
        bw.Write(offBits);
        bw.Write(40);
        bw.Write(width);
        bw.Write(height);
        bw.Write((ushort)1);
        bw.Write((ushort)bpp);
        bw.Write(0);
        bw.Write(0);
        bw.Write(posX);
        bw.Write(posY);
        bw.Write(clrUsed);
        bw.Write(0);
        return ms.ToArray();
    }
}
