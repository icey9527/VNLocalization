#ifndef SWEET_SAF_INTERNAL_H
#define SWEET_SAF_INTERNAL_H
#include "io.h"
#define MANIFEST "list.xml"
#include "zlib_api.h"

#define FLAG_ZLIB 0x1000u
#define ALIGN(n) (((n) + 63u) & ~63u)

typedef struct {
    uint32_t flags, off, csize, rsize;
    char name[40];
    int t2, x, y;
} ENTRY;


int xml_start_write(const char *folder);
int xml_end_write(void);
int xml_start_read(const char *folder);
void xml_end_read(void);
int write_xml(const char *folder, uint32_t ver, uint32_t count, const ENTRY *tab);
int read_xml(const char *folder, uint32_t *ver, uint32_t *count, int *esz, ENTRY **tab);
#endif
