#include "png.h"
#include "io.h"
#include "zlib_api.h"
#include <windows.h>
#include <gdiplus.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>

static uint32_t big32(const uint8_t *p) { return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3]; }
static void put_big32(uint8_t *p, uint32_t n) { p[0]=n>>24; p[1]=n>>16; p[2]=n>>8; p[3]=n; }
static const uint8_t signature[8] = {137,80,78,71,13,10,26,10};

static int write_chunk(FILE *fp, const char *type, const uint8_t *data, uint32_t size)
{
    uint8_t head[8], crc[4];
    put_big32(head, size); memcpy(head+4, type, 4);
    uLong sum = crc32(0, head+4, 4);
    if (size) sum = crc32(sum, data, size);
    put_big32(crc, sum);
    return fwrite(head,1,8,fp)!=8 || (size && fwrite(data,1,size,fp)!=size) || fwrite(crc,1,4,fp)!=4;
}

/* Indexed PNG output: palette and indices stay exact, including unused colors. */
int png_write(const char *path, const PngImage *image)
{
    if (!image->w || !image->h || (size_t)image->h > SIZE_MAX/(image->w+1u)) return 1;
    size_t rows = (size_t)(image->w+1)*image->h;
    if (rows > ULONG_MAX) return 1;
    uint8_t *filtered = malloc(rows), *compressed = NULL;
    if (!filtered) return 1;
    for (unsigned y=0; y<image->h; y++) {
        filtered[(size_t)y*(image->w+1)] = 0;
        memcpy(filtered+(size_t)y*(image->w+1)+1, image->pixels+(size_t)y*image->w, image->w);
    }
    uLongf length = compressBound((uLong)rows);
    compressed = malloc(length);
    int failed = !compressed || compress2(compressed, &length, filtered, (uLong)rows, 9);
    free(filtered);
    if (failed) { free(compressed); return 1; }
    uint8_t ihdr[13] = {0}, rgb[768], alpha[256];
    put_big32(ihdr,image->w); put_big32(ihdr+4,image->h); ihdr[8]=8; ihdr[9]=3;
    for (unsigned i=0; i<256; i++) { memcpy(rgb+3*i,image->palette+4*i,3); alpha[i]=image->palette[4*i+3]; }
    FILE *fp = fopen(path,"wb");
    if (!fp) failed=1;
    else {
        failed = fwrite(signature,1,8,fp)!=8 || write_chunk(fp,"IHDR",ihdr,13) ||
            write_chunk(fp,"PLTE",rgb,768) || write_chunk(fp,"tRNS",alpha,256) ||
            (image->has_original_alpha && write_chunk(fp,"psAl",image->original_alpha,256)) ||
            write_chunk(fp,"IDAT",compressed,length) || write_chunk(fp,"IEND",NULL,0);
        if (fclose(fp)) failed=1;
    }
    free(compressed); return failed;
}

static unsigned paeth(unsigned a, unsigned b, unsigned c)
{
    int p=(int)a+(int)b-(int)c, pa=abs(p-(int)a), pb=abs(p-(int)b), pc=abs(p-(int)c);
    return pa<=pb && pa<=pc ? a : pb<=pc ? b : c;
}

/* Windows handles other PNG color depths/interlacing and edited RGBA images. */
static int read_rgba(const char *path, PngImage *image)
{
    static ULONG_PTR token;
    if (!token) {
        GdiplusStartupInput startup = {0}; startup.GdiplusVersion=1;
        if (GdiplusStartup(&token,&startup,NULL)!=Ok) return 1;
    }
    wchar_t name[1024];
    if (!MultiByteToWideChar(CP_ACP,0,path,-1,name,1024)) return 1;
    GpImage *bitmap=NULL;
    if (GdipLoadImageFromFile(name,&bitmap)!=Ok) return 1;
    UINT w=0,h=0;
    int failed = GdipGetImageWidth(bitmap,&w)!=Ok || GdipGetImageHeight(bitmap,&h)!=Ok ||
        w!=image->w || h!=image->h || (size_t)w>SIZE_MAX/(4*(size_t)h);
    BitmapData lock;
    GpRect rect = {0,0,(INT)w,(INT)h};
    if (!failed) failed = GdipBitmapLockBits((GpBitmap *)bitmap,&rect,ImageLockModeRead,PixelFormat32bppARGB,&lock)!=Ok;
    if (!failed) {
        image->pixels=malloc((size_t)w*h*4);
        if (!image->pixels) failed=1;
        else for (UINT y=0;y<h;y++) {
            const uint8_t *row=(const uint8_t *)lock.Scan0+(ptrdiff_t)y*lock.Stride;
            for (UINT x=0;x<w;x++) {
                uint8_t *dst=image->pixels+4*((size_t)y*w+x);
                dst[0]=row[4*x+2]; dst[1]=row[4*x+1]; dst[2]=row[4*x]; dst[3]=row[4*x+3];
            }
        }
        if (GdipBitmapUnlockBits((GpBitmap *)bitmap,&lock)!=Ok) failed=1;
    }
    GdipDisposeImage(bitmap); return failed;
}

int png_read(const char *path, PngImage *image)
{
    memset(image,0,sizeof *image);
    size_t size=0, pos=8, idat_size=0;
    uint8_t *file=read_file(path,&size), *idat=NULL, *filtered=NULL;
    int failed=1, header=0, ended=0, palette_count=0, interlace=0, color=0, depth=0, transparency=0, data_started=0, data_ended=0;
    if (!file || size<8 || memcmp(file,signature,8)) goto done;
    for (unsigned i=0;i<256;i++) image->palette[4*i+3]=255;
    while (pos+12<=size) {
        uint32_t length=big32(file+pos);
        if (length>size-pos-12 || length>UINT_MAX-4) goto done;
        uint8_t *type=file+pos+4, *data=file+pos+8;
        if (crc32(0,type,length+4)!=big32(data+length)) goto done;
        if (!header && memcmp(type,"IHDR",4)) goto done;
        if (!memcmp(type,"IHDR",4)) {
            if (header || length!=13) goto done;
            image->w=big32(data); image->h=big32(data+4); depth=data[8]; color=data[9]; interlace=data[12];
            if (!image->w || !image->h || image->w>65535 || image->h>65535 || data[10] || data[11] || interlace>1) goto done;
            header=1;
        } else if (!memcmp(type,"PLTE",4)) {
            if (palette_count || data_started || !length || length%3 || length>768) goto done;
            palette_count=length/3;
            for (int i=0;i<palette_count;i++) memcpy(image->palette+4*i,data+3*i,3);
        } else if (!memcmp(type,"tRNS",4)) {
            if (transparency || data_started) goto done;
            transparency=1;
            if (color==3) {
                if (!palette_count || length>(unsigned)palette_count) goto done;
                for (unsigned i=0;i<length;i++) image->palette[4*i+3]=data[i];
            }
        } else if (!memcmp(type,"psAl",4)) {
            if (image->has_original_alpha || length!=256) goto done;
            memcpy(image->original_alpha,data,256); image->has_original_alpha=1;
        } else if (!memcmp(type,"IDAT",4)) {
            if (data_ended || length>SIZE_MAX-idat_size) goto done;
            data_started=1;
            uint8_t *next=realloc(idat,idat_size+length+1);
            if (!next) goto done;
            idat=next; memcpy(idat+idat_size,data,length); idat_size+=length;
        } else if (!memcmp(type,"IEND",4)) {
            if (length || !data_started || pos+12!=size) goto done;
            ended=1; break;
        } else {
            if (!(type[0]&32)) goto done; /* Unknown critical chunk. */
            if (data_started) data_ended=1;
        }
        pos+=12+length;
    }
    if (!ended || !header) goto done;
    if (color==3 && depth==8 && !interlace) {
        if (!palette_count || (size_t)image->h>SIZE_MAX/(image->w+1u)) goto done;
        size_t row_size=image->w+1, length=row_size*image->h;
        if (length>ULONG_MAX) goto done;
        filtered=malloc(length); image->pixels=malloc((size_t)image->w*image->h);
        uLongf decoded=length;
        if (!filtered || !image->pixels || uncompress(filtered,&decoded,idat,idat_size) || decoded!=length) goto done;
        for (unsigned y=0;y<image->h;y++) {
            const uint8_t *row=filtered+(size_t)y*row_size;
            uint8_t *out=image->pixels+(size_t)y*image->w;
            if (*row>4) goto done;
            for (unsigned x=0;x<image->w;x++) {
                unsigned a=x?out[x-1]:0, b=y?out[(ptrdiff_t)x-(ptrdiff_t)image->w]:0, c=y&&x?out[(ptrdiff_t)x-(ptrdiff_t)image->w-1]:0;
                unsigned add=*row==1?a:*row==2?b:*row==3?(a+b)/2:*row==4?paeth(a,b,c):0;
                out[x]=(uint8_t)(row[x+1]+add);
                if (out[x]>=palette_count) goto done;
            }
        }
        image->indexed=1; failed=0;
    } else {
        image->has_original_alpha=0;
        failed=read_rgba(path,image);
    }
done:
    free(file); free(idat); free(filtered);
    if (failed) { free(image->pixels); image->pixels=NULL; printf("Error: unsupported/corrupt PNG: %s\n",path); }
    return failed;
}
