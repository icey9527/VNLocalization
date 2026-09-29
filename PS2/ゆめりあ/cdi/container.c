/*
 * container.c -- shell container (table A) and archive block (table B) split/join.
 *
 * - 外壳容器（表A 内嵌，819 个）: 拆成目录
 *     <dir>\<id>.hdr          原样头部（32B）
 *     <dir>\<id>.<n>.<ext>    子块（n 从 0 起）
 *   回包按 .hdr + 子块顺序拼接。
 *
 * - 归档块（表B，3196 个）: **索引模式**
 *     只输出 <id>.hdr（8 + 12*count 字节）；子文件不落地。
 *     因为 B 的每个子条目 = A 表同 id 的同一份内容（已全量验证 47649/47649），
 *     回包时从 A 侧按 id 取内容重建（公式见 docs/计划_CDI索引改造.md）。
 */
#include "cdi.h"

#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

/* --------------------------------------------------------------- 命名 */

static void child_name(char *buf, size_t n, const char *id, int k, const char *ext)
{
    snprintf(buf, n, "%s.%d.%s", id, k, ext);
}

/* "<id>.<k>.<ext>" -> k；不匹配返回 0 */
static int child_index(const char *name, const char *id, int *k)
{
    size_t l = strlen(id);
    const char *p;
    int v = 0;
    if (strncmp(name, id, l) != 0 || name[l] != '.') return 0;
    p = name + l + 1;
    if (*p < '0' || *p > '9') return 0;
    while (*p >= '0' && *p <= '9') { v = v * 10 + (*p - '0'); p++; }
    if (*p != '.') return 0;
    *k = v;
    return 1;
}

typedef struct { int k; char name[PATHSZ]; uint64_t size; } Child;

static int cmp_child(const void *a, const void *b)
{
    return ((const Child *)a)->k - ((const Child *)b)->k;
}

/* 收集目录里属于 <id> 的子块，按 n 排序；返回个数 */
static Child *collect(const char *dir, const char *id, int *out_n)
{
    Ent *v; int n, m = 0;
    Child *c;
    v = list_dir(dir, &n);
    c = malloc(sizeof(Child) * (n ? n : 1));
    if (!c) die("out of memory", NULL);
    for (int i = 0; i < n; i++) {
        int k;
        if (v[i].isdir) continue;
        if (!child_index(v[i].name, id, &k)) continue;
        c[m].k = k;
        snprintf(c[m].name, sizeof c[m].name, "%s", v[i].name);
        c[m].size = v[i].size;
        m++;
    }
    free(v);
    qsort(c, (size_t)m, sizeof(Child), cmp_child);
    *out_n = m;
    return c;
}

/* --------------------------------------------------------- 外壳容器(表A) */

int is_shell_container(const uint8_t *d, uint64_t n)
{
    return n >= CONT_HDR && rd32(d + 4) == 0xFFFFFFFFu && rd32(d + 0x10) == 0x20u;
}

void shell_split(const char *dir, const char *id, const uint8_t *d, uint64_t len)
{
    uint64_t b[8];
    int nb = 0;
    uint32_t t = rd32(d), n = rd32(d + 8);
    uint32_t f14 = rd32(d + 0x14), f18 = rd32(d + 0x18);

    b[nb++] = CONT_HDR;
    if (n >= 2) {
        uint64_t e = (t == 0x08u) ? (uint64_t)CONT_HDR + f14 : f14;
        if (e <= CONT_HDR || e > len) e = len;
        b[nb++] = e;
        if (n >= 3) {
            uint64_t e2 = (t == 0x08u) ? (uint64_t)CONT_HDR + f18 : f18;
            if (e2 <= b[nb - 1] || e2 > len) e2 = len;
            b[nb++] = e2;
        }
    }
    b[nb++] = len;

    if (mkpath(dir) != 0) die("cannot create directory", dir);
    {
        char path[PATHSZ * 3];
        snprintf(path, sizeof path, "%s\\%s.hdr", dir, id);
        write_all(path, d, CONT_HDR);
    }
    for (int k = 0; k + 1 < nb; k++) {
        uint64_t a = b[k], e = b[k + 1];
        char path[PATHSZ * 3], name[PATHSZ];
        if (a >= e) continue;
        child_name(name, sizeof name, id, k, sniff_ext(d + a, e - a, NULL, 0) + 1);
        snprintf(path, sizeof path, "%s\\%s", dir, name);
        write_all(path, d + a, e - a);
    }
}

uint8_t *shell_join(const char *dir, const char *id, uint64_t *outlen)
{
    char path[PATHSZ * 3], hname[PATHSZ];
    uint64_t hlen, total, off;
    uint8_t *hdr, *out;
    Child *c; int nc;

    snprintf(hname, sizeof hname, "%s\\%s.hdr", dir, id);
    hdr = read_all(hname, &hlen);
    c = collect(dir, id, &nc);

    total = hlen;
    for (int i = 0; i < nc; i++) total += c[i].size;
    out = malloc((size_t)total + 1);
    if (!out) die("out of memory", NULL);
    memcpy(out, hdr, (size_t)hlen);
    off = hlen;
    for (int i = 0; i < nc; i++) {
        FILE *f;
        snprintf(path, sizeof path, "%s\\%s", dir, c[i].name);
        f = xfopen(path, "rb");
        if (fread(out + off, 1, (size_t)c[i].size, f) != c[i].size) die("read failed", path);
        fclose(f);
        off += c[i].size;
    }
    free(hdr); free(c);
    *outlen = total;
    return out;
}

/* --------------------------------------------------------- 归档块(表B) */

int is_archive(const uint8_t *d, uint64_t n)
{
    uint32_t cnt;
    if (n < 8) return 0;
    if (rd32(d) == 0xFFFFFFFFu) return 0;        /* 那是外壳容器 */
    cnt = rd32(d + 4);
    if (cnt == 0) return 1;
    if (8 + 12ull * cnt > n) return 0;
    if (rd32(d + 16) != (uint32_t)align_up(8 + 12ull * cnt, 64)) return 0;
    return 1;
}

/* 归档块: 只写头部(<id>.hdr)。子文件内容由 A 侧提供(见 archive_join)。 */
void archive_split(const char *dir, const char *id, const uint8_t *d, uint64_t len)
{
    uint32_t cnt = rd32(d + 4);
    uint64_t hlen = 8 + 12ull * cnt;
    char path[PATHSZ * 3];

    if (hlen > len) die("archive header out of range", id);
    if (mkpath(dir) != 0) die("cannot create directory", dir);
    snprintf(path, sizeof path, "%s\\%s.hdr", dir, id);
    write_all(path, d, hlen);
}

/* --------- A 侧文件清单缓存: 只扫一次目录, 之后 O(1) 查 ------ */

typedef struct {
    uint32_t id;
    uint64_t size;          /* 普通文件: 文件大小; 目录(容器): 拼装后总长 */
    int      isdir;
    char     name[PATHSZ];
} AEnt;

static AEnt *g_aent = NULL;
static int   g_an = 0;
static char  g_adir[PATHSZ];

static int cmp_aent(const void *a, const void *b)
{
    uint32_t x = ((const AEnt *)a)->id, y = ((const AEnt *)b)->id;
    return (x < y) ? -1 : (x > y) ? 1 : 0;
}

/* 扫描 A 目录一次, 建立 id 索引 (含容器目录的总长) */
static void a_cache_build(const char *adir)
{
    Ent *v; int n;
    snprintf(g_adir, sizeof g_adir, "%s", adir);
    v = list_dir(adir, &n);
    g_aent = malloc(sizeof(AEnt) * (n ? n : 1));
    if (!g_aent) die("out of memory", NULL);
    for (int i = 0; i < n; i++) {
        uint32_t fid;
        if (parse_id(v[i].name, &fid) != 0) continue;
        AEnt *e = &g_aent[g_an];
        e->id = fid;
        e->isdir = v[i].isdir;
        snprintf(e->name, sizeof e->name, "%s", v[i].name);
        if (v[i].isdir) {
            char dpath[PATHSZ * 3], hname[PATHSZ * 3], idbuf[16];
            Child *c; int nc;
            uint64_t total, hlen;
            snprintf(idbuf, sizeof idbuf, "%04X", fid);
            snprintf(dpath, sizeof dpath, "%s\\%s", adir, v[i].name);
            c = collect(dpath, idbuf, &nc);
            snprintf(hname, sizeof hname, "%s\\%s.hdr", dpath, idbuf);
            { FILE *f = xfopen(hname, "rb"); hlen = fsize(f); fclose(f); }
            total = hlen;
            for (int k = 0; k < nc; k++) total += c[k].size;
            free(c);
            e->size = total;
        } else {
            e->size = v[i].size;
        }
        g_an++;
    }
    free(v);
    qsort(g_aent, (size_t)g_an, sizeof(AEnt), cmp_aent);
}

static AEnt *a_cache_find(uint32_t id)
{
    int lo = 0, hi = g_an;
    while (lo < hi) {
        int m = lo + (hi - lo) / 2;
        if (g_aent[m].id < id) lo = m + 1;
        else hi = m;
    }
    if (lo < g_an && g_aent[lo].id == id) return &g_aent[lo];
    return NULL;
}

static void a_cache_ensure(const char *adir)
{
    if (g_aent == NULL || strcmp(g_adir, adir) != 0) {
        free(g_aent); g_aent = NULL; g_an = 0;
        a_cache_build(adir);
    }
}

/* A 侧某 id 的长度 (容器目录为拼装后总长); 返回 0=成功, -1=不存在 */
static int a_file_size(const char *adir, uint32_t id, uint64_t *out)
{
    AEnt *e;
    a_cache_ensure(adir);
    e = a_cache_find(id);
    if (!e) return -1;
    *out = e->size;
    return 0;
}

/* 读取 A 侧某 id 的内容 (普通文件直读; 容器目录则拼 hdr+子块)。
 * 返回 malloc 缓冲; 不存在返回 NULL。 */
uint8_t *load_a_file(const char *adir, uint32_t id, uint64_t *outlen)
{
    AEnt *e;
    char path[PATHSZ * 3];
    a_cache_ensure(adir);
    e = a_cache_find(id);
    if (!e) return NULL;
    if (!e->isdir) {
        snprintf(path, sizeof path, "%s\\%s", adir, e->name);
        return read_all(path, outlen);
    } else {
        char idbuf[16], dpath[PATHSZ * 3];
        Child *c; int nc;
        uint64_t k, total, hlen;
        uint8_t *out, *hdr;
        snprintf(idbuf, sizeof idbuf, "%04X", id);
        snprintf(dpath, sizeof dpath, "%s\\%s", adir, e->name);
        c = collect(dpath, idbuf, &nc);
        snprintf(path, sizeof path, "%s\\%s.hdr", dpath, idbuf);
        hdr = read_all(path, &hlen);
        total = hlen;
        for (k = 0; k < (uint64_t)nc; k++) total += c[k].size;
        out = malloc((size_t)total + 1);
        if (!out) die("out of memory", NULL);
        memcpy(out, hdr, (size_t)hlen);
        {
            uint64_t off = hlen;
            for (k = 0; k < (uint64_t)nc; k++) {
                FILE *f;
                snprintf(path, sizeof path, "%s\\%s", dpath, c[k].name);
                f = xfopen(path, "rb");
                if (fread(out + off, 1, (size_t)c[k].size, f) != c[k].size)
                    die("read failed", path);
                fclose(f);
                off += c[k].size;
            }
        }
        free(hdr); free(c);
        *outlen = total;
        return out;
    }
}

/* 用 <dir>\<id>.hdr + A 侧内容重建整个归档块。
 * 注意: 头里的 size/offset 只是提示 —— 权威是 A 侧的实际数据
 * (翻译等改动会使 A 侧文件变长/变短); 这里一律按 A 侧重算并重写块头。 */
uint8_t *archive_join(const char *dir, const char *adir, const char *id, uint64_t *outlen)
{
    char hname[PATHSZ];
    uint64_t hlen, total, off;
    uint8_t *hdr, *out;
    uint32_t cnt, *sids;
    uint64_t *szs;

    snprintf(hname, sizeof hname, "%s\\%s.hdr", dir, id);
    hdr = read_all(hname, &hlen);
    if (hlen < 8) die("archive header too small", hname);
    cnt = rd32(hdr + 4);
    if (hlen != 8 + 12ull * cnt) die("archive header size mismatch", hname);

    sids = malloc(sizeof(uint32_t) * (cnt ? cnt : 1));
    szs  = malloc(sizeof(uint64_t) * (cnt ? cnt : 1));
    if (!sids || !szs) die("out of memory", NULL);

    /* 总长 + 各子文件长度: 从 A 侧取实际值 */
    total = align_up(hlen, 64);
    for (uint32_t k = 0; k < cnt; k++) {
        uint32_t sid = rd32(hdr + 8 + 12 * k);
        sids[k] = sid;
        if (a_file_size(adir, sid, &szs[k]) != 0) {
            fprintf(stderr, "error: archive %s needs id %u (%04X) but it is missing in A\\\n",
                    id, sid, sid);
            exit(1);
        }
        total += align_up(szs[k], 64);
    }
    total = align_up(total, SECTOR);

    out = calloc((size_t)total + 1, 1);
    if (!out) die("out of memory", NULL);
    /* 重写块头: count + {id, size, offset} */
    wr32(out + 4, cnt);
    off = align_up(hlen, 64);
    for (uint32_t k = 0; k < cnt; k++) {
        uint64_t alen = 0;
        uint8_t *data;
        wr32(out + 8 + 12 * k, sids[k]);
        wr32(out + 8 + 12 * k + 4, (uint32_t)szs[k]);
        wr32(out + 8 + 12 * k + 8, (uint32_t)off);
        data = load_a_file(adir, sids[k], &alen);
        if (!data) die("read failed in A", id);
        memcpy(out + off, data, (size_t)alen);
        free(data);
        off += align_up(szs[k], 64);
    }
    free(hdr); free(sids); free(szs);
    *outlen = total;
    return out;
}

/* ------------------------------------------------------------ 尺寸(回包预扫) */

uint64_t shell_size(const char *dir, const char *id)
{
    char hname[PATHSZ];
    uint64_t t;
    Child *c; int nc;
    snprintf(hname, sizeof hname, "%s\\%s.hdr", dir, id);
    { FILE *f = xfopen(hname, "rb"); t = fsize(f); fclose(f); }
    c = collect(dir, id, &nc);
    for (int i = 0; i < nc; i++) t += c[i].size;
    free(c);
    return t;
}

/* 归档块重建后总长 = ALIGN64(hdr) + Σ ALIGN64(A侧实际长度), 再 ALIGN2048。
 * 头里的 size 过时也算得对 —— 以 A 侧为准。 */
uint64_t archive_size(const char *dir, const char *adir, const char *id)
{
    char hname[PATHSZ];
    uint64_t hlen, t;
    uint8_t *hdr;
    uint32_t cnt;

    snprintf(hname, sizeof hname, "%s\\%s.hdr", dir, id);
    hdr = read_all(hname, &hlen);
    if (hlen < 8) die("archive header too small", hname);
    cnt = rd32(hdr + 4);
    if (hlen != 8 + 12ull * cnt) die("archive header size mismatch", hname);

    t = align_up(hlen, 64);
    for (uint32_t k = 0; k < cnt; k++) {
        uint32_t sid = rd32(hdr + 8 + 12 * k);
        uint64_t sz = 0;
        if (a_file_size(adir, sid, &sz) != 0) {
            fprintf(stderr, "error: archive %s needs id %u (%04X) but it is missing in A\\\n",
                    id, sid, sid);
            exit(1);
        }
        t += align_up(sz, 64);
    }
    free(hdr);
    return align_up(t, SECTOR);
}
