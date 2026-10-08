#ifndef SWEET_SAF_ARCHIVE_H
#define SWEET_SAF_ARCHIVE_H
int saf_unpack(const char *input, const char *folder);
int saf_pack(const char *folder, const char *output);
#endif
