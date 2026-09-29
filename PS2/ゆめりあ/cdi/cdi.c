/*
 * cdi.c -- Yumeria (PS2) CDI image unpack / repack tool.
 * =====================================================================
 *   cdi u <image.bin> <dir>     unpack : image -> dir  (自动拆外壳容器/归档块)
 *   cdi p <dir> <image.bin>     pack   : dir   -> image
 *   cdi i <image.bin>           info   : header + content stats
 *
 * Build: build.bat
 *   gcc -O2 -Wall -Wextra -static -static-libgcc -s -o cdi.exe cdi.c container.c util.c
 *
 * 输出目录结构:
 *   <dir>\A\                      表A 条目
 *     <id>.<ext>                  普通文件(可带 _内嵌原名)
 *     <id>\<id>.hdr <id>.0.<ext>  外壳容器(819 个, 自动拆; 节号从 0 起)
 *   <dir>\B\                      表B 条目(每块一个目录)
 *     <id>\<id>.hdr <id>.0.<ext>  归档块(自动拆出全部子文件)
 *
 * 除 header version(三个镜像都是 1, 直接写死)之外, 一切都能从目录内容重算,
 * 不产生任何记录文件(没有 XML/JSON)。
 */
#include "cdi.h"

#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

typedef struct {
    uint32_t id, sector, flag;
    uint64_t size;          /* 原始文件长度(字节) */
    char     name[PATHSZ];
    int      isdir;
} Src;

static int cmp_id(const void *a, const void *b)
{
    uint32_t x = ((const Src *)a)->id, y = ((const Src *)b)->id;
    return (x < y) ? -1 : (x > y) ? 1 : 0;
}

static int cmp_u64(const void *a, const void *b)
{
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
    return (x < y) ? -1 : (x > y) ? 1 : 0;
}

static uint8_t *read_range(FILE *f, uint64_t off, uint64_t size)
{
    uint8_t *b = malloc((size_t)(size ? size : 1));
    if (!b) die("out of memory", NULL);
    seekf(f, off);
    if (size && fread(b, 1, (size_t)size, f) != (size_t)size) die("read failed", NULL);
    return b;
}

static void write_zeros(FILE *f, uint64_t n)
{
    static const uint8_t z[SECTOR] = { 0 };
    while (n) {
        size_t k = (n > SECTOR) ? SECTOR : (size_t)n;
        if (fwrite(z, 1, k, f) != k) die("write failed", NULL);
        n -= k;
    }
}

static void copy_range(FILE *in, uint64_t off, uint64_t size, FILE *out)
{
    static uint8_t *buf = NULL;
    if (!buf) buf = malloc(1u << 20);
    if (!buf) die("out of memory", NULL);
    seekf(in, off);
    while (size) {
        size_t k = (size > (1u << 20)) ? (1u << 20) : (size_t)size;
        if (fread(buf, 1, k, in) != k) die("read failed", NULL);
        if (fwrite(buf, 1, k, out) != k) die("write failed", NULL);
        size -= k;
    }
}

/* --------------------------------------------------------------- 解包 */

static void cmd_unpack(const char *img, const char *outdir)
{
    FILE *in = xfopen(img, "rb");
    uint8_t hdr[64], probe[0x820];
    uint32_t nA, nB, offA, offB;
    uint64_t total;
    char dA[PATHSZ * 2], dB[PATHSZ * 2], path[PATHSZ * 3];
    int warned = 0;

    if (fread(hdr, 1, sizeof hdr, in) < 36) die("file too small", img);
    if (memcmp(hdr, "CDI\0", 4) != 0) die("not a CDI image (bad magic)", img);
    nA = rd16(hdr + 8); nB = rd16(hdr + 10);
    offA = rd32(hdr + 16); offB = rd32(hdr + 20);
    total = fsize(in);

    snprintf(dA, sizeof dA, "%s\\A", outdir);
    snprintf(dB, sizeof dB, "%s\\B", outdir);
    if (mkpath(dA) != 0 || mkpath(dB) != 0) die("cannot create directory", outdir);

    for (uint32_t i = 0; i < nA; i++) {
        uint8_t b[16];
        uint32_t id, sec, size;
        uint64_t off, plen;
        char idbuf[16];
        seekf(in, offA + 16ull * i);
        if (fread(b, 1, 16, in) != 16) die("table A read failed", NULL);
        id = rd32(b); sec = rd32(b + 4); size = rd32(b + 8);
        off = (uint64_t)sec * SECTOR;
        if (off + size > total) { fprintf(stderr, "warn: id %u out of range\n", id); warned++; continue; }
        snprintf(idbuf, sizeof idbuf, "%04X", id);
        plen = (size < sizeof probe) ? size : sizeof probe;
        seekf(in, off);
        if (plen && fread(probe, 1, (size_t)plen, in) != plen) die("read failed", NULL);

        if (is_shell_container(probe, plen)) {
            uint8_t *d = read_range(in, off, size);
            snprintf(path, sizeof path, "%s\\%s", dA, idbuf);
            shell_split(path, idbuf, d, size);
            free(d);
        } else {
            char np[64];
            const char *ext = sniff_ext(probe, plen, np, sizeof np);
            FILE *o;
            snprintf(path, sizeof path, "%s\\%s%s%s", dA, idbuf, np, ext);
            o = xfopen(path, "wb");
            copy_range(in, off, size, o);
            fclose(o);
        }
    }

    /* ---- B 侧：索引模式，只写 .hdr + 生成 cdi.index ---- */
    for (uint32_t i = 0; i < nB; i++) {
        uint8_t b[12];
        uint32_t sec, ns;
        uint64_t off, blen;
        char idbuf[16];
        uint8_t *d;
        seekf(in, offB + 12ull * i);
        if (fread(b, 1, 12, in) != 12) die("table B read failed", NULL);
        sec = rd32(b); ns = rd32(b + 4);
        off = (uint64_t)sec * SECTOR;
        blen = (uint64_t)ns * SECTOR;
        if (off + blen > total) { fprintf(stderr, "warn: table B[%u] out of range\n", i); warned++; continue; }
        snprintf(idbuf, sizeof idbuf, "%04X", BIG_ID + i);
        d = read_range(in, off, blen);
        snprintf(path, sizeof path, "%s\\%s", dB, idbuf);
        archive_split(path, idbuf, d, blen);
        free(d);
    }

    /* ---- 索引文件 ---- */
    {
        FILE *x;
        snprintf(path, sizeof path, "%s\\cdi.index", outdir);
        x = xfopen(path, "wb");
        fprintf(x, "# CDI index v1 -- 由 cdi u 生成; 回包时读取\n");
        fprintf(x, "# 格式: A <id> <file>      / A <id> dir <dir>   / B <index> <hdr>\n");
        fprintf(x, "# 表B 归档为索引模式: 只存 .hdr (%u 个), 内容从 A 同名 id 重建\n", nB);
        /* A 侧: 重新扫一遍输出目录 */
        {
            Ent *v; int n;
            v = list_dir(dA, &n);
            for (int i = 0; i < n; i++) {
                uint32_t fid;
                if (parse_id(v[i].name, &fid) != 0) continue;
                if (v[i].isdir)
                    fprintf(x, "A %04X dir %s\n", fid, v[i].name);
                else
                    fprintf(x, "A %04X %s\n", fid, v[i].name);
            }
            free(v);
        }
        for (uint32_t i = 0; i < nB; i++)
            fprintf(x, "B %u %04X.hdr\n", i, BIG_ID + i);
        fclose(x);
    }

    fclose(in);
    printf("unpack: %s\n  A\\ %u entries, B\\ %u archives -> %s\n", img, nA, nB, outdir);
    printf("  index : %s\\cdi.index\n", outdir);
    if (warned) printf("  %d entries skipped\n", warned);
}

/* --------------------------------------------------------------- 回包 */

static void cmd_pack(const char *dir, const char *img)
{
    char dA[PATHSZ * 2], dB[PATHSZ * 2];
    Ent *ea, *eb; int nea, neb, nA = 0, nB = 0;
    Src *A, *B;
    uint32_t *bcount, *tblD, *arcOfPhys, *params, *tblC, nsub = 0, base = 0, p = 0;
    uint64_t *key;
    uint32_t offA, offB, offC, offD;
    uint64_t offData, cur, outsize;
    FILE *out;
    uint8_t h[HDR_SIZE];

    snprintf(dA, sizeof dA, "%s\\A", dir);
    snprintf(dB, sizeof dB, "%s\\B", dir);

    /* --- 扫 A/ --- */
    ea = list_dir(dA, &nea);
    A = malloc(sizeof(Src) * (nea ? nea : 1));
    if (!A) die("out of memory", NULL);
    for (int i = 0; i < nea; i++) {
        uint32_t id;
        char sub[PATHSZ * 3];
        if (parse_id(ea[i].name, &id) != 0) continue;
        if (id >= BIG_ID) die("A/ contains a table-B id", ea[i].name);
        A[nA].id = id;
        A[nA].name[0] = 0; snprintf(A[nA].name, PATHSZ, "%s", ea[i].name);
        A[nA].isdir = ea[i].isdir;
        if (ea[i].isdir) {
            snprintf(sub, sizeof sub, "%s\\%s", dA, ea[i].name);
            A[nA].size = shell_size(sub, ea[i].name);
        } else {
            A[nA].size = ea[i].size;
        }
        if (A[nA].size > 0xFFFFFFFFull) die("file too large", ea[i].name);
        nA++;
    }
    qsort(A, (size_t)nA, sizeof(Src), cmp_id);

    /* --- 扫 B/ --- */
    eb = list_dir(dB, &neb);
    B = malloc(sizeof(Src) * (neb ? neb : 1));
    if (!B) die("out of memory", NULL);
    for (int i = 0; i < neb; i++) {
        uint32_t id;
        char sub[PATHSZ * 3];
        if (!eb[i].isdir) continue;
        if (parse_id(eb[i].name, &id) != 0 || id < BIG_ID) continue;
        B[nB].id = id;
        snprintf(B[nB].name, PATHSZ, "%s", eb[i].name);
        B[nB].isdir = 1;
        snprintf(sub, sizeof sub, "%s\\%s", dB, eb[i].name);
        B[nB].size = archive_size(sub, dA, eb[i].name);
        nB++;
    }
    qsort(B, (size_t)nB, sizeof(Src), cmp_id);
    for (int i = 0; i < nB; i++)
        if (B[i].id != BIG_ID + (uint32_t)i) die("table B index not contiguous", B[i].name);

    /* --- 读每个归档的头, 统计子条目 --- */
    bcount = malloc(sizeof(uint32_t) * (nB ? nB : 1));
    if (!bcount) die("out of memory", NULL);
    for (int i = 0; i < nB; i++) {
        char hp[PATHSZ * 3];
        uint64_t hl; uint8_t *hb;
        snprintf(hp, sizeof hp, "%s\\%s\\%s.hdr", dB, B[i].name, B[i].name);
        hb = read_all(hp, &hl);
        if (hl < 8) die("archive header too small", hp);
        bcount[i] = rd32(hb + 4);
        nsub += bcount[i];
        free(hb);
    }
    if (nsub > 0xFFFFu) die("too many sub-entries for u16 tables", NULL);

    /* --- 推导 param / 表C / 表D --- */
    tblD      = malloc(sizeof(uint32_t) * (nsub ? nsub : 1));
    arcOfPhys = malloc(sizeof(uint32_t) * (nsub ? nsub : 1));
    key       = malloc(sizeof(uint64_t) * (nsub ? nsub : 1));
    params    = malloc(sizeof(uint32_t) * (nB ? nB : 1));
    tblC      = malloc(sizeof(uint32_t) * (nsub ? nsub : 1));
    if (!tblD || !arcOfPhys || !key || !params || !tblC) die("out of memory", NULL);

    for (int i = 0; i < nB; i++) {
        char hp[PATHSZ * 3];
        uint64_t hl; uint8_t *hb;
        params[i] = ((bcount[i] & 0xFFFFu) << 16) | (base & 0xFFFFu);
        base += bcount[i];
        snprintf(hp, sizeof hp, "%s\\%s\\%s.hdr", dB, B[i].name, B[i].name);
        hb = read_all(hp, &hl);
        for (uint32_t k = 0; k < bcount[i]; k++) {
            tblD[p] = rd32(hb + 8 + 12 * k);
            arcOfPhys[p] = (uint32_t)i;
            key[p] = ((uint64_t)tblD[p] << 32) | (uint64_t)p;
            p++;
        }
        free(hb);
    }
    qsort(key, (size_t)nsub, sizeof(uint64_t), cmp_u64);
    for (uint32_t k = 0; k < nsub; k++)
        tblC[k] = arcOfPhys[(uint32_t)(key[k] & 0xFFFFFFFFull)];

    /* --- 表A 的 flag = (同 id 子条目数 << 16) | 排序起始秩 --- */
    for (int i = 0; i < nA; i++) {
        uint32_t fid = A[i].id, lo, l = 0, hh = nsub, cnt = 0;
        while (l < hh) {
            uint32_t m = l + (hh - l) / 2;
            if ((uint32_t)(key[m] >> 32) < fid) l = m + 1;
            else hh = m;
        }
        lo = l;
        for (uint32_t k = lo; k < nsub && (uint32_t)(key[k] >> 32) == fid; k++) cnt++;
        A[i].flag = ((cnt & 0xFFFFu) << 16) | (lo & 0xFFFFu);
    }

    if ((uint64_t)nA > 0xFFFFu || (uint64_t)nB > 0xFFFFu) die("too many entries for u16", NULL);

    /* --- 布局全部重算 --- */
    offA = HDR_SIZE;
    offB = offA + 16u * (uint32_t)nA;
    offC = offB + 12u * (uint32_t)nB;
    offD = offC + 2u * nsub;
    offData = align_up((uint64_t)offD + 2ull * nsub, SECTOR);
    if (offData > 0xFFFFFFFFull) die("header too large", NULL);

    cur = offData;
    for (int i = 0; i < nA; i++) { A[i].sector = (uint32_t)(cur / SECTOR); cur += align_up(A[i].size, SECTOR); }
    for (int i = 0; i < nB; i++) { B[i].sector = (uint32_t)(cur / SECTOR); cur += B[i].size; }
    outsize = cur;

    out = xfopen(img, "wb");
    memset(h, 0, sizeof h);
    memcpy(h, "CDI\0", 4);
    wr32(h + 4, CDI_VERSION);
    wr16(h + 8, (uint16_t)nA);
    wr16(h + 10, (uint16_t)nB);
    wr32(h + 12, nsub);
    wr32(h + 16, offA); wr32(h + 20, offB); wr32(h + 24, offC);
    wr32(h + 28, offD); wr32(h + 32, (uint32_t)offData);
    if (fwrite(h, 1, sizeof h, out) != sizeof h) die("write failed", NULL);

    for (int i = 0; i < nA; i++) {
        uint8_t b[16];
        wr32(b, A[i].id); wr32(b + 4, A[i].sector);
        wr32(b + 8, (uint32_t)A[i].size); wr32(b + 12, A[i].flag);
        if (fwrite(b, 1, 16, out) != 16) die("write failed", NULL);
    }
    for (int i = 0; i < nB; i++) {
        uint8_t b[12];
        wr32(b, B[i].sector); wr32(b + 4, (uint32_t)(B[i].size / SECTOR)); wr32(b + 8, params[i]);
        if (fwrite(b, 1, 12, out) != 12) die("write failed", NULL);
    }
    for (uint32_t i = 0; i < nsub; i++) {
        uint8_t b[2]; wr16(b, (uint16_t)tblC[i]);
        if (fwrite(b, 1, 2, out) != 2) die("write failed", NULL);
    }
    for (uint32_t i = 0; i < nsub; i++) {
        uint8_t b[2]; wr16(b, (uint16_t)tblD[i]);
        if (fwrite(b, 1, 2, out) != 2) die("write failed", NULL);
    }
    write_zeros(out, offData - (uint64_t)offD - 2ull * nsub);

    for (int i = 0; i < nA; i++) {
        char pth[PATHSZ * 3];
        if (A[i].isdir) {
            uint64_t dl; uint8_t *d;
            snprintf(pth, sizeof pth, "%s\\%s", dA, A[i].name);
            d = shell_join(pth, A[i].name, &dl);
            if (dl != A[i].size) die("container size changed", A[i].name);
            if (fwrite(d, 1, (size_t)dl, out) != dl) die("write failed", NULL);
            free(d);
        } else {
            FILE *f;
            snprintf(pth, sizeof pth, "%s\\%s", dA, A[i].name);
            f = xfopen(pth, "rb");
            copy_range(f, 0, A[i].size, out);
            fclose(f);
        }
        write_zeros(out, align_up(A[i].size, SECTOR) - A[i].size);
    }
    for (int i = 0; i < nB; i++) {
        char pth[PATHSZ * 3];
        uint64_t dl; uint8_t *d;
        snprintf(pth, sizeof pth, "%s\\%s", dB, B[i].name);
        d = archive_join(pth, dA, B[i].name, &dl);
        if (dl != B[i].size) die("archive size changed", B[i].name);
        if (fwrite(d, 1, (size_t)dl, out) != dl) die("write failed", NULL);
        free(d);
    }
    fclose(out);

    printf("pack: %s\n  A\\ %d files, B\\ %d archives, %u sub-entries\n",
           img, nA, nB, nsub);
    printf("  data at %" PRIu64 ", output %" PRIu64 " bytes\n", offData, outsize);

    free(ea); free(eb); free(A); free(B);
    free(bcount); free(tblD); free(arcOfPhys); free(key); free(params); free(tblC);
}

/* --------------------------------------------------------------- 信息 */

static void cmd_info(const char *img)
{
    FILE *in = xfopen(img, "rb");
    uint8_t hdr[64];
    uint32_t nA, nB, nC, offA, offB, offC, offD, offData;
    uint64_t total;

    if (fread(hdr, 1, sizeof hdr, in) < 36) die("file too small", img);
    if (memcmp(hdr, "CDI\0", 4) != 0) die("not a CDI image (bad magic)", img);
    nA = rd16(hdr + 8); nB = rd16(hdr + 10); nC = rd32(hdr + 12);
    offA = rd32(hdr + 16); offB = rd32(hdr + 20);
    offC = rd32(hdr + 24); offD = rd32(hdr + 28); offData = rd32(hdr + 32);
    total = fsize(in);

    printf("file      : %s\n", img);
    printf("size      : %" PRIu64 " bytes (%" PRIu64 " sectors)\n", total, total / SECTOR);
    printf("version   : %u\n", rd32(hdr + 4));
    printf("table A   : %u entries @ 0x%X (16B: id/sector/size/flag)\n", nA, offA);
    printf("table B   : %u archives @ 0x%X (12B: sector/nsectors/param)\n", nB, offB);
    printf("table C   : %u entries @ 0x%X (u16: archive of each sub-entry, id sorted)\n", nC, offC);
    printf("table D   : @ 0x%X (%u entries, u16 sub-ids in physical order)\n", offD, (offData - offD) / 2);
    printf("data area : 0x%X\n", offData);
    fclose(in);
}

/* --------------------------------------------------------------- main */

static void usage(void)
{
    fprintf(stderr,
        "Yumeria CDI image tool\n"
        "usage:\n"
        "  cdi u <image.bin> <dir>    unpack (image -> dir, auto-splits containers)\n"
        "  cdi p <dir> <image.bin>    pack   (dir   -> image)\n"
        "  cdi i <image.bin>          show header info\n");
    exit(1);
}

int main(int argc, char **argv)
{
    if (argc < 3) usage();
    if (argv[1][0] == 'u' && argv[1][1] == 0) {
        if (argc < 4) usage();
        cmd_unpack(argv[2], argv[3]);
    } else if (argv[1][0] == 'p' && argv[1][1] == 0) {
        if (argc < 4) usage();
        cmd_pack(argv[2], argv[3]);
    } else if (argv[1][0] == 'i' && argv[1][1] == 0) {
        cmd_info(argv[2]);
    } else {
        usage();
    }
    return 0;
}
