/* lac_unpack.c - ToHeart PSE LAC 音频包解包器 (bgmfile.pak / soundds.pak / voice.pak)
 *
 * 用法: 把 .pak 拖到本 exe 图标上 (或命令行传路径)。
 *       会在 pak 同目录创建同名文件夹 (bgmfile.pak -> bgmfile\) 并解包。
 *
 * 格式: "LAC\0" + u32条目数, 每条目0x28字节:
 *       [0..8] 文件名9字节(按位取反, Shift-JIS, 超8字节被原打包器截断)
 *       [32..35] u32 长度, [36..39] u32 起始偏移。数据区原样存放不加密。
 *
 * 编译: gcc -O2 -static -s -o lac_unpack.exe lac_unpack.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

typedef unsigned char u8;
typedef unsigned int  u32;

#define ENTRY_SIZE 0x28

/* 取低32位小端 */
static u32 rd32(const u8 *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((u32)p[3] << 24); }

/* Shift-JIS 名字清洗: 解码后9字节 -> 合法窄字节串(仍是CP932字节)
 * 成对处理双字节字符, 去掉尾部悬空字节/无效字节, 去掉结尾的 '.' 和空格 */
static int sanitize_sjis(u8 *name, int len)
{
    int i = 0, w = 0;
    while (i < len) {
        u8 c = name[i];
        if (c == 0) break;                                  /* NUL 结束 */
        if (c == ' ' || (c >= 0x20 && c < 0x7F)) {          /* ASCII / 空格 */
            name[w++] = c; i++;
        } else if ((c >= 0x81 && c <= 0x9F) || (c >= 0xE0 && c <= 0xFC)) {
            if (i + 1 >= len) break;                        /* 悬空前导字节: 丢弃 */
            u8 t = name[i + 1];
            if (t < 0x40 || t == 0x7F || t > 0xFC) break;   /* 无效尾字节: 丢弃 */
            name[w++] = c; name[w++] = t; i += 2;
        } else {
            break;                                          /* 0x80/0xA0/0xFD-0xFF 等: 丢弃 */
        }
    }
    while (w > 0 && (name[w - 1] == '.' || name[w - 1] == ' '))
        w--;                                                /* Windows 不允许结尾是点 */
    return w;
}

/* CP932 -> 宽字符文件名并写出; 返回写入字节数, 失败返回 -1 */
static long write_entry(const wchar_t *dir, const u8 *name, int name_len,
                        const u8 *data, u32 size)
{
    wchar_t wname[64], path[MAX_PATH];
    int n = MultiByteToWideChar(932, 0, (const char *)name, name_len, wname, 32);
    if (n <= 0) return -1;
    wname[n] = 0;
    /* 重名时追加 _2 _3 ... (截断名可能冲突) */
    int dup = 0;
    for (;;) {
        if (dup == 0)
            _snwprintf(path, MAX_PATH, L"%s\\%s", dir, wname);
        else {
            wchar_t num[8];
            _snwprintf(num, 8, L"_%d", dup + 1);
            /* 插在扩展名前 */
            wchar_t *dot = wcsrchr(wname, L'.');
            if (dot && dot != wname) {
                wchar_t tmp[64];
                int pre = dot - wname;
                memcpy(tmp, wname, pre * sizeof(wchar_t));
                tmp[pre] = 0;
                _snwprintf(path, MAX_PATH, L"%s\\%s%s%s", dir, tmp, num, dot);
            } else
                _snwprintf(path, MAX_PATH, L"%s\\%s%s", dir, wname, num);
        }
        if (GetFileAttributesW(path) == INVALID_FILE_ATTRIBUTES)
            break;                                          /* 不存在, 可写 */
        dup++;
        if (dup > 99) return -1;
    }
    FILE *f = _wfopen(path, L"wb");
    if (!f) return -1;
    size_t wr = size ? fwrite(data, 1, size, f) : 0;
    fclose(f);
    return (wr == size) ? (long)wr : -1;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        printf("LAC Unpacker (ToHeart PSE)\nUsage: drag & drop a .pak file onto this program icon.\n");
        printf("Press Enter to exit...");
        getchar();
        return 1;
    }

    /* 读入整个 pak */
    FILE *f = fopen(argv[1], "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", argv[1]); return 1; }
    fseek(f, 0, SEEK_END);
    long fsz = ftell(f);
    fseek(f, 0, SEEK_SET);
    u8 *buf = malloc(fsz);
    if (!buf || fread(buf, 1, fsz, f) != (size_t)fsz) {
        fprintf(stderr, "read failed\n"); return 1;
    }
    fclose(f);

    if (fsz < 8 + ENTRY_SIZE || memcmp(buf, "LAC\0", 4) != 0) {
        fprintf(stderr, "%s is not a LAC archive\n", argv[1]);
        printf("Press Enter to exit..."); getchar();
        return 1;
    }
    u32 count = rd32(buf + 4);

    /* 输出目录 = pak 路径去掉扩展名 */
    char dir_a[MAX_PATH];
    strncpy(dir_a, argv[1], MAX_PATH - 1);
    char *dot = strrchr(dir_a, '.');
    char *slash = strpbrk(dir_a, "\\/");
    if (dot && (!slash || dot > slash)) *dot = 0;           /* 只去掉文件扩展名 */
    wchar_t dir[MAX_PATH];
    MultiByteToWideChar(CP_ACP, 0, dir_a, -1, dir, MAX_PATH);
    CreateDirectoryW(dir, NULL);

    printf("Output dir: %s\nEntries: %u\n", dir_a, count);
    int ok = 0, skip = 0, fixed = 0;
    for (u32 i = 0; i < count; i++) {
        const u8 *e = buf + 8 + i * ENTRY_SIZE;
        u8 name[16];
        for (int j = 0; j < 9; j++) name[j] = ~e[j];        /* 文件名按位取反 */
        int nl = sanitize_sjis(name, 9);
        u32 size = rd32(e + 0x20), start = rd32(e + 0x24);
        if (start + size > (u32)fsz) { skip++; continue; }
        if (nl == 0) {                                      /* 无有效名字: 用编号 */
            char tmp[32];
            sprintf(tmp, "unnamed_%03u", i);
            nl = strlen(tmp);
            memcpy(name, tmp, nl);
        }
        /* 原打包器名字段只有9字节, 超长名被截断 (MUS03_A.OGG -> MUS03_A.O)。
         * 按数据内容补全后缀: OggS -> .OGG, RIFF -> .WAV */
        const char *ext = NULL;
        if (size >= 4 && !memcmp(buf + start, "OggS", 4)) ext = "OGG";
        else if (size >= 4 && !memcmp(buf + start, "RIFF", 4)) ext = "WAV";
        if (ext) {
            u8 *dot = NULL;
            for (int j = nl - 1; j >= 0; j--)
                if (name[j] == '.') { dot = name + j; break; }
            if (!dot) {                                     /* 无后缀: 追加 */
                name[nl++] = '.';
                memcpy(name + nl, ext, 3); nl += 3;
                fixed++;
            } else {
                int cl = nl - (int)(dot - name) - 1;        /* 当前残缺后缀长度 */
                int el = strlen(ext);
                if (cl < el && !memcmp(dot + 1, ext, cl)) {
                    memcpy(dot + 1, ext, el);
                    nl = (int)(dot - name) + 1 + el;
                    fixed++;
                }
            }
        }
        if (write_entry(dir, name, nl, buf + start, size) >= 0)
            ok++;
        else {
            fprintf(stderr, "  [FAILED] entry %u\n", i);
            skip++;
        }
    }
    printf("Done: %d ok, %d skipped/failed, %d names repaired\nPress Enter to exit...", ok, skip, fixed);
    getchar();
    free(buf);
    return 0;
}
