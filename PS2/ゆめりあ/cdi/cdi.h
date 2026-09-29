/*
 * cdi.h -- shared declarations for the Yumeria CDI tool.
 *
 * Files:  cdi.c (main + image level)   container.c (shell container / archive)
 *         util.c (helpers)             build.bat
 */
#ifndef CDI_H
#define CDI_H

#include <stdint.h>
#include <stdio.h>
#include <stddef.h>

#define SECTOR      2048u
#define HDR_SIZE    0x24u       /* CDI 头部长度 */
#define CONT_HDR    0x20u       /* 外壳容器头部长度 */
#define BIG_ID      0x100000u   /* id >= 0x100000 走表 B */
#define PATHSZ      1024
#define CDI_VERSION 1u          /* 三个镜像都是 1，直接写死，不再需要记录文件 */

/* 目录项 */
typedef struct {
    char     name[PATHSZ];
    uint64_t size;
    int      isdir;
} Ent;

/* ---- util.c ---- */
void        die(const char *msg, const char *arg);
FILE       *xfopen(const char *path, const char *mode);
void        seekf(FILE *f, uint64_t off);
uint64_t    fsize(FILE *f);
uint32_t    rd32(const uint8_t *p);
uint16_t    rd16(const uint8_t *p);
void        wr32(uint8_t *p, uint32_t v);
void        wr16(uint8_t *p, uint16_t v);
uint64_t    align_up(uint64_t n, uint64_t a);
int         mkpath(const char *path);
/* 按内容魔数判定扩展名(含 mov 在 +0x810 的 MPEG 流); namepart 收内嵌原名,可传 NULL */
const char *sniff_ext(const uint8_t *d, uint64_t len, char *namepart, size_t npsz);
uint8_t    *read_all(const char *path, uint64_t *len);
void        write_all(const char *path, const uint8_t *d, uint64_t len);
Ent        *list_dir(const char *dir, int *count);
void        stem_of(const char *name, char *out, size_t n);
/* 文件名前导十六进制数字(即 id)，后面只能跟 '.' 或 结束 */
int         parse_id(const char *name, uint32_t *out);

/* ---- container.c ---- */
/* 外壳容器(表A): +0x04==0xFFFFFFFF && +0x10==0x20 (819 个) */
int      is_shell_container(const uint8_t *d, uint64_t n);
void     shell_split(const char *dir, const char *id, const uint8_t *d, uint64_t len);
uint8_t *shell_join(const char *dir, const char *id, uint64_t *outlen);
uint64_t shell_size(const char *dir, const char *id);
/* 归档块(表B): { u32 reserved(=0); u32 count; { u32 id; u32 size; u32 offset; }[count] }
 * 索引模式: 只存 .hdr; 内容从 A 侧按 id 取(全量验证过 B == A 副本)。 */
int      is_archive(const uint8_t *d, uint64_t n);
void     archive_split(const char *dir, const char *id, const uint8_t *d, uint64_t len);
uint8_t *archive_join(const char *dir, const char *adir, const char *id, uint64_t *outlen);
uint64_t archive_size(const char *dir, const char *adir, const char *id);

#endif
