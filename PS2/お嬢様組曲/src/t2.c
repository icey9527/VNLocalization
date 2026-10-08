#include "t2.h"
#include "png.h"
#include "quantize.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned read16(const uint8_t *p) { return p[0] | (unsigned)p[1] << 8; }
static void write16(uint8_t *p, unsigned v) { p[0] = v; p[1] = v >> 8; }
static unsigned swap_index(unsigned i) { return (i & ~31u) | (i & 7) | ((i & 8) << 1) | ((i & 16) >> 1); }
static unsigned alpha_display(unsigned a) { return a < 128 ? a * 2 : 255; }

int t2_export(const uint8_t *data, size_t size, const char *path, int *x, int *y)
{
    if (size < 1040 || memcmp(data,"T2",2) || read16(data+2)!=0x1313 || read16(data+4) || read16(data+6)) goto invalid;
    PngImage image = {0};
    image.w=read16(data+12); image.h=read16(data+14);
    if (!image.w || !image.h || size!=1040+(size_t)image.w*image.h) goto invalid;
    *x=(int16_t)read16(data+8); *y=(int16_t)read16(data+10);
    image.pixels=(uint8_t *)data+1040; image.indexed=1; image.has_original_alpha=1;
    for (unsigned i=0;i<256;i++) {
        const uint8_t *c=data+16+4*swap_index(i);
        memcpy(image.palette+4*i,c,3);
        image.palette[4*i+3]=alpha_display(c[3]); image.original_alpha[i]=c[3];
    }
    return png_write(path,&image);
invalid:
    printf("Error: unsupported/truncated T2: %s\n",path); return 1;
}

uint8_t *t2_import(const char *path, int x, int y, size_t *size)
{
    PngImage image;
    if (png_read(path,&image)) return NULL;
    size_t n=(size_t)image.w*image.h;
    uint8_t *raw=calloc(1,1040+n);
    if (!raw) goto done;
    if (image.indexed) memcpy(raw+1040,image.pixels,n);
    else if (image_palette(image.pixels,image.w,image.h,raw+1040,image.palette)) {
        free(raw); raw=NULL; goto done;
    }
    for (unsigned i=0;i<256;i++) {
        uint8_t *dst=raw+16+4*swap_index(i);
        memcpy(dst,image.palette+4*i,3);
        unsigned a=image.palette[4*i+3];
        dst[3]=image.has_original_alpha && alpha_display(image.original_alpha[i])==a ? image.original_alpha[i] : a==255?128:(a+1)/2;
    }
    memcpy(raw,"T2",2); write16(raw+2,0x1313);
    write16(raw+8,x); write16(raw+10,y); write16(raw+12,image.w); write16(raw+14,image.h);
    *size=1040+n;
done:
    free(image.pixels);
    if (!raw) printf("Error: importing T2 PNG: %s\n",path);
    return raw;
}
