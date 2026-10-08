#ifndef SWEET_ZLIB_API_H
#define SWEET_ZLIB_API_H
/* Stable zlib C ABI. GCC links against the existing 32-bit zlib1.dll. */
typedef unsigned char Bytef;
typedef unsigned long uLong;
typedef unsigned long uLongf;
int uncompress(Bytef *dest, uLongf *destLen, const Bytef *source, uLong sourceLen);
int compress2(Bytef *dest, uLongf *destLen, const Bytef *source, uLong sourceLen, int level);
uLong compressBound(uLong sourceLen);
uLong crc32(uLong crc, const Bytef *buf, unsigned int len);
#endif
