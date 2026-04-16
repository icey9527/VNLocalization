#ifndef ONE_BIN_H
#define ONE_BIN_H

static const char *NAMES[] = {
    "ScrChrSet",
    "ScrChrSetXY",
    "ScrChrSetDisp",
    "ScrChrDel",
    "ScrChrSetARGB",
    "ScrChrMove",
    "ScrUpDateNormal",
    "ScrUpDateCross",
    "ScrUpDateZoom",
    "ScrUpDateZoomR",
    "ScrUpDateImage",
    "ScrShake",
    "ScrReversal",
    "ScrMov",
    "ScrInc",
    "ScrRnd",
    "ScrIf",
    "ScrJump",
    "ScrJumpR",
    "ScrReturn",
    "ScrSelect",
    "ScrWinFrame",
    "ScrWinClear",
    "ScrWinFontColor",
    "ScrWinFontSize",
    "ScrWinRubi",
    "ScrWinDisplay",
    "ScrWinType",
    "ScrMessageSpeed",
    "ScrWinFrameType",
    "ScrBgmPlay",
    "ScrBgmStop",
    "ScrSePlay",
    "ScrSeStop",
    "ScrExSePlay",
    "ScrExSeStop",
    "ScrMoviePlay",
    "ScrSystemIcon",
    "ScrTitleReturn",
    "ScrWaitIcon",
    "ScrWaitTime",
    "ScrWaitKey",
    "ScrMess",
    "ScrAchr",
    "ScrWaitA",
    "ScrLbg",
    "ScrLbgXy",
    "ScrLchr",
    "ScrDraw",
    "ScrDrawEx",
    "ScrEffectS",
    "ScrFlash",
    "ScrWaitKeyB",
    "ScrVoice",
};

static const unsigned char WORDS[] = {
    3, 4, 2, 2, 5, 6, 1, 2,
    4, 4, 3, 3, 2, 3, 2, 4,
    6, 2, 2, 1, 0, 2, 1, 4,
    3, 0, 1, 2, 2, 2, 3, 2,
    3, 2, 4, 3, 2, 1, 1, 2,
    2, 1, 0, 0, 1, 3, 5, 6,
    1, 5, 5, 1, 1, 2,
};

#define NAME_COUNT (sizeof(NAMES) / sizeof(NAMES[0]))

void onebin_extract_dir(const wchar_t *src_path, const wchar_t *out_dir);
void onebin_pack_dir(const wchar_t *in_dir, const wchar_t *out_path);
void onebin_extract_mem(const unsigned char *src, size_t src_size, const wchar_t *out_dir);
unsigned char *onebin_pack_mem(const wchar_t *in_dir, size_t *out_size);

#endif
