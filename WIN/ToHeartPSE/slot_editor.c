/* slot_editor.c - ToHeart PSE 存档槽编辑器 (仅 saveXXX.bmp)
 *
 * 界面: Win32 原生小窗口, 宋体, 支持拖拽 .bmp 打开。
 * 脚本号/代码偏移均按 4 位十六进制显示和输入 (如 0033 / 007B)。
 * v0-v199 数值变量表, 双击"数值"列直接改。
 * 保存时自动重算校验和, 直接覆盖原文件。
 *
 * 格式 (逆向确认):
 *   文件 220164 字节 = BMP头(54) + 标志(1) + 密钥(273) + 加密blob(0x32278) + 尾部
 *   blob 内: +0x0C 脚本号 | +0x14 代码偏移 | +0x32094 校验和(u32)
 *           +0x320E8 变量 v0-v199 (u16 x200)
 *           +0x321D8 章节(u16) +0x321DA 路线(u16)
 *           +0x32200 返回栈深度, +0x32204 起每4字节(脚本u16,偏移u16)
 *   加密: 按 i%5 的 加/减/取反 流, 密钥 = 文件[55..327]
 *   校验和 = sum(头328字节) + sum(blob且校验槽清零) + sum(尾部), 低32位
 *
 * 编译: gcc -O2 -static -mwindows -DUNICODE -D_UNICODE \
 *          -o ToHeartPSE存档编辑器.exe slot_editor.c -lcomctl32
 */
#ifndef SLOT_TEST
#include <windows.h>
#include <commctrl.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int  u32;

#define FILE_SIZE   220164
#define BLOB_OFF    328
#define BLOB_SIZE   0x32278
#define TAIL_OFF    (BLOB_OFF + BLOB_SIZE)
#define CHK_OFF     0x32094
#define VARS_OFF    0x320E8
#define NVARS       200
#define SCRIPT_OFF  0x0C
#define CODEOFF_OFF 0x14
#define CHAPTER_OFF 0x321D8
#define RETSTK_OFF  0x32200

/* ---------------- 存档数据 ---------------- */
static u8  g_raw[FILE_SIZE];        /* 原始文件 */
static u8  g_blob[BLOB_SIZE];       /* 解密后的 blob */
static int g_loaded = 0;
static int g_check_ok = 0;
static char g_path[600] = "";                /* 当前打开的存档路径 */
static u32 g_orig_script = 0xFFFFFFFF;       /* 打开时的脚本号, 用于检测"传送" */
static u32 g_orig_codeoff = 0;               /* 打开时的代码偏移 */

static u32 rd32(const u8 *p) { return p[0] | (p[1]<<8) | (p[2]<<16) | ((u32)p[3]<<24); }
static u16 rd16(const u8 *p) { return (u16)(p[0] | (p[1]<<8)); }
static void wr16(u8 *p, u16 v) { p[0] = v & 0xFF; p[1] = v >> 8; }
static void wr32(u8 *p, u32 v) { p[0]=v; p[1]=v>>8; p[2]=v>>16; p[3]=v>>24; }

static u32 get_script(void);        /* 前向声明 */
static void set_var(int i, u16 v);

/* 定位脚本 DAT: save 文件在 <游戏>\save\ 下, DAT 在 <游戏>\scn\ 下 */
#if 0                                           /* 已按需求移除外部校验, 保留备查 */
static int script_dat_path(u32 script, char *out, int n)
{
    char dir[600];
    strncpy(dir, g_path, 599); dir[599] = 0;
    char *a = strrchr(dir, '\\'), *b = strrchr(dir, '/');
    char *s = (b > a) ? b : a;
    if (!s) return -1;
    *s = 0;                                        /* ...\save */
    a = strrchr(dir, '\\'); b = strrchr(dir, '/');
    char *base = (b > a) ? b : a;
    if (base && _stricmp(base + 1, "save") == 0)
        *base = 0;                                 /* 去掉 save 一级 */
    _snprintf(out, n, "%s\\scn\\%04x.DAT", dir, script);
    return 0;
}
#endif

static void blob_decrypt(u8 *buf, const u8 *key)
{
    for (int i = 0; i < BLOB_SIZE; i++) {
        u8 k = key[i % 273], v = buf[i];
        switch (i % 5) {
        case 0: v = (u8)(v - k); break;
        case 1: v = (u8)(v + k); break;
        case 2: v = (u8)~v;      break;
        case 3: v = (u8)(~v - k); break;
        default: v = (u8)(v + k + 1); break;
        }
        buf[i] = v;
    }
}

static void blob_encrypt(u8 *buf, const u8 *key)
{
    for (int i = 0; i < BLOB_SIZE; i++) {
        u8 k = key[i % 273], v = buf[i];
        switch (i % 5) {
        case 0: v = (u8)(v + k); break;
        case 1: v = (u8)(v - k); break;
        case 2: v = (u8)~v;      break;
        case 3: v = (u8)~(u8)(v + k); break;
        default: v = (u8)(v + (u8)~k); break;
        }
        buf[i] = v;
    }
}

static u32 compute_checksum(void)
{
    u32 s = 0;
    for (int i = 0; i < BLOB_OFF; i++) s += g_raw[i];
    for (int i = 0; i < BLOB_SIZE; i++)
        if (i < CHK_OFF || i >= CHK_OFF + 4) s += g_blob[i];
    for (int i = TAIL_OFF; i < FILE_SIZE; i++) s += g_raw[i];
    return s;
}

static int slot_load(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    size_t n = fread(g_raw, 1, FILE_SIZE, f);
    fclose(f);
    if (n != FILE_SIZE || g_raw[0] != 'B' || g_raw[1] != 'M') return -2;
    memcpy(g_blob, g_raw + BLOB_OFF, BLOB_SIZE);
    blob_decrypt(g_blob, g_raw + 55);
    u32 stored = rd32(g_blob + CHK_OFF);
    g_check_ok = (stored == compute_checksum());
    g_orig_script = get_script();
    g_orig_codeoff = rd32(g_blob + CODEOFF_OFF);
    g_loaded = 1;
    return 0;
}

static int slot_save(const char *path, const char *orig_path)
{
    (void)orig_path;
    if (!g_loaded) return -1;
    wr32(g_blob + CHK_OFF, compute_checksum());
    u8 enc[BLOB_SIZE];
    memcpy(enc, g_blob, BLOB_SIZE);
    blob_encrypt(enc, g_raw + 55);
    FILE *f = fopen(path, "wb");
    if (!f) return -3;
    fwrite(g_raw, 1, BLOB_OFF, f);
    fwrite(enc, 1, BLOB_SIZE, f);
    fwrite(g_raw + TAIL_OFF, 1, FILE_SIZE - TAIL_OFF, f);
    fclose(f);
    slot_load(path);
    return g_check_ok ? 0 : -4;
}

static u32  get_script(void)   { return rd32(g_blob + SCRIPT_OFF); }
static void set_script(u32 v)  { wr32(g_blob + SCRIPT_OFF, v); }

/* 传送清理: 脚本号被改后, 旧返回栈/镜像变量/场景快照全部失效, 必须重建,
 * 否则读档后 ret 弹垃圾栈或恢复无效场景 → 卡死。
 * 栈压 (E000@406) = 系统菜单, 是原生存档验证过的安全返回点。 */
static void teleport_cleanup(u32 script, u32 offset)
{
    u32 d = 0;
    wr32(g_blob + RETSTK_OFF, 1);
    wr16(g_blob + RETSTK_OFF + 4, 0xE000);
    wr16(g_blob + RETSTK_OFF + 6, 406);
    for (int i = 1; i < 16; i++) {          /* 清掉其余栈槽 */
        wr16(g_blob + RETSTK_OFF + 4 + 4 * i, 0);
        wr16(g_blob + RETSTK_OFF + 6 + 4 * i, 0);
    }
    set_var(126, (u16)script);              /* 镜像: 脚本号 x3 */
    set_var(146, (u16)script);
    set_var(140, 1);                        /* 镜像: 栈深/栈0 */
    set_var(142, 0xE000);
    set_var(143, 406);
    set_var(144, 0);
    set_var(145, 0);
    set_var(147, (u16)offset);              /* 镜像: 代码偏移 */
    wr32(g_blob + 0x320A0, 0);              /* 旧场景快照: bg/overlay/movie 清零 */
    wr32(g_blob + 0x320A4, 0);
    wr32(g_blob + 0x32098, 0);
    (void)d;
}

/* 常规保存时同步镜像, 保持引擎不变量 */
static void sync_mirrors(u32 script, u32 offset)
{
    set_var(126, (u16)script);
    set_var(146, (u16)script);
    set_var(147, (u16)offset);
}
static u32  get_codeoff(void)  { return rd32(g_blob + CODEOFF_OFF); }
static void set_codeoff(u32 v) { wr32(g_blob + CODEOFF_OFF, v); }
static u16  get_chapter(void)  { return rd16(g_blob + CHAPTER_OFF); }
static void set_chapter(u16 v) { wr16(g_blob + CHAPTER_OFF, v); }
static u16  get_route(void)    { return rd16(g_blob + CHAPTER_OFF + 2); }
static void set_route(u16 v)   { wr16(g_blob + CHAPTER_OFF + 2, v); }
static u16  get_var(int i)     { return rd16(g_blob + VARS_OFF + 2 * i); }
static void set_var(int i, u16 v) { wr16(g_blob + VARS_OFF + 2 * i, v); }

static const wchar_t *var_note(int i)
{
    if (i < 110)  return L"脚本计数/临时值";
    if (i < 118)  return L"引擎状态 (脚本未引用)";
    if (i <= 122) return L"图像临时变量";
    if (i == 126 || i == 142 || i == 146) return L"当前脚本号镜像";
    if (i == 144) return L"返回栈顶·脚本镜像";
    if (i == 145) return L"返回栈顶·偏移镜像";
    if (i == 147) return L"代码偏移镜像";
    return L"引擎内部";
}

#ifndef SLOT_TEST
/* ================= Win32 界面 ================= */

static HWND hMain, hList, hEditScript, hEditOff, hEditChap, hEditRoute,
           hStStatus, hStRet, hCellEdit;
static int  g_cell_item = -1;
static int  g_filling = 0;                   /* 程序填充字段时抑制自动对齐 */
static HFONT hFont;
static WNDPROC g_cell_orig_proc = NULL;      /* 单元格编辑框原子类过程 */
static LRESULT CALLBACK cell_edit_proc(HWND h, UINT m, WPARAM w, LPARAM l);

#define IDC_OPEN   100
#define IDC_SAVE   101
#define IDC_ZEROOFF 102
#define IDC_EDITSCRIPT 103

static void status(const wchar_t *msg)
{
    wchar_t buf[280];
    if (g_loaded && g_path[0]) {
        char base[MAX_PATH]; const char *p = strrchr(g_path, '\\');
        strncpy(base, p ? p + 1 : g_path, MAX_PATH - 1);
        wchar_t wbase[MAX_PATH];
        MultiByteToWideChar(CP_ACP, 0, base, -1, wbase, MAX_PATH);
        _snwprintf(buf, 280, L"%s  |  %s", wbase, msg);
    } else
        _snwprintf(buf, 280, L"%s", msg);
    SetWindowTextW(hStStatus, buf);
}

static void fill_fields(void)
{
    wchar_t buf[64];
    g_filling = 1;
    _snwprintf(buf, 64, L"%04X", get_script());
    SetWindowTextW(hEditScript, buf);
    _snwprintf(buf, 64, L"%04X", get_codeoff());      /* 偏移也用16进制 */
    SetWindowTextW(hEditOff, buf);
    _snwprintf(buf, 64, L"%u", get_chapter());
    SetWindowTextW(hEditChap, buf);
    _snwprintf(buf, 64, L"%u", get_route());
    SetWindowTextW(hEditRoute, buf);
    g_filling = 0;
    u32 d = rd32(g_blob + RETSTK_OFF);
    (void)d;                                                 /* 返回栈已不显示, 保留读取以备将来 */
}

static void fill_list(void)
{
    ListView_DeleteAllItems(hList);
    LVITEMW lvi = {0};
    wchar_t buf[2][32];
    for (int i = 0; i < NVARS; i++) {
        u16 v = get_var(i);
        _snwprintf(buf[0], 32, L"v%d%s", i, v ? L" ★" : L"");
        _snwprintf(buf[1], 32, L"%d", v);
        lvi.mask = LVIF_TEXT;
        lvi.iItem = i;
        lvi.pszText = buf[0];
        ListView_InsertItem(hList, &lvi);
        ListView_SetItemText(hList, i, 1, (LPWSTR)var_note(i));
        ListView_SetItemText(hList, i, 2, buf[1]);
    }
}

static int collect_fields(wchar_t *err, int errlen)
{
    wchar_t buf[64]; wchar_t *end;
    GetWindowTextW(hEditScript, buf, 64);
    u32 v = (u32)wcstoul(buf, &end, 16);               /* 脚本号: 16进制 */
    if (*end || !buf[0]) { _snwprintf(err, errlen, L"脚本号无效: %s (请用16进制)", buf); return -1; }
    set_script(v);
    GetWindowTextW(hEditOff, buf, 64);
    u32 o = (u32)wcstoul(buf, &end, 16);               /* 偏移: 16进制 */
    if (*end || !buf[0]) { _snwprintf(err, errlen, L"代码偏移无效: %s (请用16进制)", buf); return -1; }
    set_codeoff(o);
    GetWindowTextW(hEditChap, buf, 64);
    u32 c = (u32)wcstoul(buf, &end, 10);
    if (*end || !buf[0]) { _snwprintf(err, errlen, L"章节无效"); return 1; }
    set_chapter((u16)c);
    GetWindowTextW(hEditRoute, buf, 64);
    u32 r = (u32)wcstoul(buf, &end, 10);
    if (*end || !buf[0]) { _snwprintf(err, errlen, L"路线无效"); return 1; }
    set_route((u16)r);
    return 0;
}

static void do_open(const wchar_t *wpath)
{
    char path[MAX_PATH];
    WideCharToMultiByte(CP_ACP, 0, wpath, -1, path, MAX_PATH, NULL, NULL);
    if (slot_load(path) != 0) {
        MessageBoxW(hMain, L"打开失败:\n不是有效的存档槽文件 (saveXXX.bmp, 220164 字节)",
                    L"错误", MB_ICONERROR);
        return;
    }
    strncpy(g_path, path, MAX_PATH - 1);
    fill_fields();
    fill_list();
    status(g_check_ok ? L"校验和 ✓" : L"⚠ 校验和不一致 (仍可编辑)");
}

static void do_open_dialog(void)
{
    OPENFILENAMEW ofn = {0};
    wchar_t file[MAX_PATH] = L"";
    ofn.lStructSize = sizeof ofn;
    ofn.hwndOwner = hMain;
    ofn.lpstrFilter = L"存档槽 (save*.bmp)\0*.bmp\0所有文件\0*.*\0";
    ofn.lpstrFile = file;
    ofn.nMaxFile = MAX_PATH;
    ofn.Flags = OFN_FILEMUSTEXIST | OFN_HIDEREADONLY;
    if (GetOpenFileNameW(&ofn))
        do_open(file);
}

static void do_save(void)
{
    wchar_t err[128];
    if (!g_loaded) {
        MessageBoxW(hMain, L"请先打开一个存档槽文件 (saveXXX.bmp)", L"提示", MB_ICONINFORMATION);
        return;
    }
    if (collect_fields(err, 128)) {
        MessageBoxW(hMain, err, L"输入有误", MB_ICONWARNING);
        return;
    }
    u32 sc = get_script(), of = get_codeoff();
    if (sc != g_orig_script)
        teleport_cleanup(sc, of);          /* 脚本号变了: 清理旧状态防卡死 */
    else
        sync_mirrors(sc, of);
    if (slot_save(g_path, g_path) == 0) {
        fill_fields();
        status(L"已保存 ✓");
    } else {
        MessageBoxW(hMain, L"保存失败 (无法写文件)", L"错误", MB_ICONERROR);
    }
}

/* 日期主脚本表 (12入口, 逆向 E000 主控状态机得出: 推进时 call(v126, 4..10),
 * 只有这些脚本有入口4-10; 跳到子脚本会被 call 出口越界报"事件编号错误") */
static int is_main_script(u32 sc)
{
    return (sc >= 0x33 && sc <= 0x48) || (sc >= 0x57 && sc <= 0x6F);
}

/* 脚本号一变就把偏移自动置 0000 (入口0, 安全位置); 改回原脚本则恢复原偏移 */
static void on_script_changed(void)
{
    wchar_t buf[64]; wchar_t *end;
    GetWindowTextW(hEditScript, buf, 64);
    if (!buf[0]) return;
    u32 sc = (u32)wcstoul(buf, &end, 16);
    if (*end) return;
    wchar_t off[64];
    if (sc == g_orig_script) {                     /* 改回原脚本: 恢复原偏移 */
        _snwprintf(off, 64, L"%04X", g_orig_codeoff);
        SetWindowTextW(hEditOff, off);
        status(L"");
    } else {
        SetWindowTextW(hEditOff, L"0000");
        status(is_main_script(sc) ? L"日期主脚本 ✓ 偏移已置 0000"
                                  : L"⚠ 此脚本号可能会报错");
    }
}

/* ---- ListView 单元格编辑 ---- */
static void start_cell_edit(NMHDR *nm)
{
    NMLISTVIEW *pn = (NMLISTVIEW *)nm;
    if (pn->iSubItem != 2 || pn->iItem < 0) return;
    RECT rc;
    ListView_GetSubItemRect(hList, pn->iItem, 2, LVIR_LABEL, &rc);
    MapWindowPoints(hList, hMain, (POINT *)&rc, 2);
    if (hCellEdit) DestroyWindow(hCellEdit);
    wchar_t cur[32];
    ListView_GetItemText(hList, pn->iItem, 2, cur, 32);
    hCellEdit = CreateWindowW(L"EDIT", cur, WS_CHILD | WS_VISIBLE | WS_BORDER |
                              ES_CENTER | ES_AUTOHSCROLL,
                              rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top,
                              hMain, NULL, GetModuleHandle(NULL), NULL);
    g_cell_orig_proc = (WNDPROC)SetWindowLongPtrW(hCellEdit, GWLP_WNDPROC,
                                                  (LONG_PTR)cell_edit_proc);
    SendMessageW(hCellEdit, WM_SETFONT, (WPARAM)hFont, TRUE);
    SendMessageW(hCellEdit, EM_SETSEL, 0, -1);
    SetFocus(hCellEdit);
    g_cell_item = pn->iItem;
}

static void commit_cell_edit(void)
{
    if (!hCellEdit || g_cell_item < 0) return;
    HWND h = hCellEdit;
    hCellEdit = NULL;                        /* 先清防重入 */
    wchar_t buf[32];
    GetWindowTextW(h, buf, 32);
    wchar_t *end;
    unsigned long v = wcstoul(buf, &end, 10);
    if (*end == 0 && buf[0] && v <= 65535) {
        set_var(g_cell_item, (u16)v);
        _snwprintf(buf, 32, L"%lu", v);
        ListView_SetItemText(hList, g_cell_item, 2, buf);
        wchar_t name[32];
        _snwprintf(name, 32, L"v%d%s", g_cell_item, v ? L" ★" : L"");
        ListView_SetItemText(hList, g_cell_item, 0, name);
        status(L"已修改 (尚未保存)");
    }
    DestroyWindow(h);
    g_cell_item = -1;
}

/* 单元格编辑框钩子: 回车提交, Esc 取消, 失焦提交 */
static LRESULT CALLBACK cell_edit_proc(HWND h, UINT m, WPARAM w, LPARAM l)
{
    if (m == WM_KEYDOWN && w == VK_RETURN) { commit_cell_edit(); return 0; }
    if (m == WM_KEYDOWN && w == VK_ESCAPE) {
        hCellEdit = NULL;
        DestroyWindow(h);
        g_cell_item = -1;
        return 0;
    }
    if (m == WM_KILLFOCUS) { commit_cell_edit(); return 0; }
    return CallWindowProcW(g_cell_orig_proc, h, m, w, l);
}

static BOOL CALLBACK set_font_proc(HWND h, LPARAM lp)
{
    SendMessageW(h, WM_SETFONT, (WPARAM)hFont, TRUE);
    return TRUE;
}

static LRESULT CALLBACK WndProc(HWND hw, UINT msg, WPARAM wp, LPARAM lp)
{
    switch (msg) {
    case WM_CREATE: {
        INITCOMMONCONTROLSEX icc = { sizeof icc, ICC_LISTVIEW_CLASSES };
        InitCommonControlsEx(&icc);
        /* 宋体 12px, 小巧清晰 */
        hFont = CreateFontW(-12, 0, 0, 0, FW_NORMAL, 0, 0, 0,
                            DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY,
                            DEFAULT_PITCH | FF_DONTCARE, L"SimSun");

        int y = 8;
        CreateWindowW(L"BUTTON", L"打开…",
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 8, y, 56, 22, hw, (HMENU)IDC_OPEN, NULL, NULL);
        CreateWindowW(L"BUTTON", L"保存",
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 68, y, 46, 22, hw, (HMENU)IDC_SAVE, NULL, NULL);
        hStStatus = CreateWindowW(L"STATIC", L"未打开 — 点【打开…】或把 saveXXX.bmp 拖进窗口",
            WS_CHILD | WS_VISIBLE | SS_CENTERIMAGE, 122, y + 1, 380, 20, hw, NULL, NULL, NULL);

        y = 38;                                             /* 存档位置行 */
        #define LBL(t, x, w) CreateWindowW(L"STATIC", t, WS_CHILD | WS_VISIBLE | \
            SS_RIGHT | SS_CENTERIMAGE, x, y + 2, w, 18, hw, NULL, NULL, NULL)
        #define EDT(x, w) CreateWindowW(L"EDIT", L"", WS_CHILD | WS_VISIBLE | WS_BORDER | \
            ES_CENTER, x, y, w, 21, hw, NULL, NULL, NULL)
        LBL(L"脚本(16)",   0, 52);
        hEditScript = CreateWindowW(L"COMBOBOX", L"",
            WS_CHILD | WS_VISIBLE | CBS_DROPDOWN | CBS_AUTOHSCROLL | WS_VSCROLL,
            56, y, 60, 220, hw, (HMENU)IDC_EDITSCRIPT, NULL, NULL);
        for (u32 s = 0x33; s <= 0x48; s++) {         /* 日期主脚本白名单(内置) */
            wchar_t item[8];
            _snwprintf(item, 8, L"%04X", s);
            SendMessageW(hEditScript, CB_ADDSTRING, 0, (LPARAM)item);
        }
        for (u32 s = 0x57; s <= 0x6F; s++) {
            wchar_t item[8];
            _snwprintf(item, 8, L"%04X", s);
            SendMessageW(hEditScript, CB_ADDSTRING, 0, (LPARAM)item);
        }
        LBL(L"偏移(16)", 122, 52);  hEditOff    = EDT(178, 44);
        CreateWindowW(L"BUTTON", L"清零", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                      226, y, 36, 21, hw, (HMENU)IDC_ZEROOFF, NULL, NULL);
        LBL(L"章节",     270, 32);  hEditChap   = EDT(306, 36);
        LBL(L"路线",     348, 32);  hEditRoute  = EDT(384, 32);
        y += 26;                                             /* 分割线 */
        CreateWindowW(L"STATIC", L"", WS_CHILD | WS_VISIBLE | SS_ETCHEDHORZ,
                      6, y, 494, 2, hw, NULL, NULL, NULL);
        y += 4;
        CreateWindowW(L"STATIC", L"数值变量 v0–v199  (双击【数值】修改, ★ = 非零)",
            WS_CHILD | WS_VISIBLE, 8, y, 400, 18, hw, NULL, NULL, NULL);
        y += 20;
        hList = CreateWindowW(WC_LISTVIEWW, L"",
            WS_CHILD | WS_VISIBLE | LVS_REPORT | LVS_SHOWSELALWAYS | WS_BORDER | LVS_SINGLESEL,
            6, y, 494, 380, hw, NULL, NULL, NULL);
        ListView_SetExtendedListViewStyle(hList, LVS_EX_FULLROWSELECT | LVS_EX_GRIDLINES);
        LVCOLUMNW col;
        memset(&col, 0, sizeof col);
        col.mask = LVCF_TEXT | LVCF_WIDTH;
        col.pszText = (LPWSTR)L"变量";  col.cx = 56;  ListView_InsertColumn(hList, 0, &col);
        col.pszText = (LPWSTR)L"说明";  col.cx = 280; ListView_InsertColumn(hList, 1, &col);
        col.pszText = (LPWSTR)L"数值";  col.cx = 56;  ListView_InsertColumn(hList, 2, &col);

        EnumChildWindows(hw, set_font_proc, 0);             /* 全部子控件统一宋体 */
        DragAcceptFiles(hw, TRUE);
        return 0;
    }
    case WM_COMMAND:
        if (LOWORD(wp) == IDC_OPEN) do_open_dialog();
        else if (LOWORD(wp) == IDC_SAVE) do_save();
        else if (LOWORD(wp) == IDC_ZEROOFF) {
            SetWindowTextW(hEditOff, L"0000");
            status(L"已修改 (尚未保存)");
        }
        else if (LOWORD(wp) == IDC_EDITSCRIPT && !g_filling &&
                 (HIWORD(wp) == CBN_EDITCHANGE || HIWORD(wp) == CBN_SELCHANGE))
            on_script_changed();
        return 0;
    case WM_DROPFILES: {
        wchar_t path[MAX_PATH];
        if (DragQueryFileW((HDROP)wp, 0, path, MAX_PATH))
            do_open(path);
        DragFinish((HDROP)wp);
        return 0;
    }
    case WM_NOTIFY:
        if (lp && ((NMHDR *)lp)->hwndFrom == hList) {
            NMHDR *nm = (NMHDR *)lp;
            if (nm->code == NM_DBLCLK)
                start_cell_edit(nm);
        }
        return 0;
    default:
        if (hCellEdit && (msg == WM_LBUTTONDOWN || msg == WM_NCLBUTTONDOWN))
            commit_cell_edit();
        break;
    }
    return DefWindowProcW(hw, msg, wp, lp);
}

int WINAPI WinMain(HINSTANCE hInst, HINSTANCE hPrev, LPSTR cmd, int show)
{
    (void)hPrev; (void)cmd;
    WNDCLASSW wc = {0};
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInst;
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wc.lpszClassName = L"THPSESlotEditor";
    RegisterClassW(&wc);
    hMain = CreateWindowExW(0, wc.lpszClassName,
        L"ToHeart PSE 存档编辑器",
        WS_OVERLAPPEDWINDOW & ~WS_MAXIMIZEBOX & ~WS_THICKFRAME,
        CW_USEDEFAULT, CW_USEDEFAULT, 516, 516, NULL, NULL, hInst, NULL);
    ShowWindow(hMain, show);
    UpdateWindow(hMain);
    if (__argc >= 2) {
        wchar_t wpath[MAX_PATH];
        MultiByteToWideChar(CP_ACP, 0, __argv[1], -1, wpath, MAX_PATH);
        do_open(wpath);
    }
    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    return (int)msg.wParam;
}

#else /* SLOT_TEST: 控制台 roundtrip 测试 */
int main(int argc, char **argv)
{
    if (argc < 2) { printf("usage: slot_editor --test <saveXXX.bmp>\n"); return 1; }
    if (slot_load(argv[1]) != 0) { printf("load failed\n"); return 1; }
    printf("script=%04X codeoff=%04X chapter=%u route=%u check=%s\n",
           get_script(), get_codeoff(), get_chapter(), get_route(),
           g_check_ok ? "OK" : "BAD");
    printf("nonzero vars:");
    for (int i = 0; i < NVARS; i++)
        if (get_var(i)) printf(" v%d=%u", i, get_var(i));
    printf("\n");
    char out[600];
    snprintf(out, sizeof out, "%s.rt", argv[1]);
    int rc = slot_save(out, NULL);
    FILE *a = fopen(argv[1], "rb"), *b = fopen(out, "rb");
    int same = 1;
    for (int i = 0; i < FILE_SIZE; i++)
        if (fgetc(a) != fgetc(b)) { same = 0; break; }
    fclose(a); fclose(b); remove(out);
    printf("roundtrip identical: %s  save rc=%d reload check=%s\n",
           same ? "YES" : "NO", rc, g_check_ok ? "OK" : "BAD");
    set_script(52); set_var(35, 77); set_chapter(9);
    rc = slot_save(out, NULL);
    slot_load(out);
    printf("edited: script=%04X v35=%u chapter=%u check=%s rc=%d\n",
           get_script(), get_var(35), get_chapter(), g_check_ok ? "OK" : "BAD", rc);
    remove(out);
    /* 传送清理验证: 模拟把 0033 的位置改到 0035 */
    set_script(0x35); set_codeoff(0);
    teleport_cleanup(0x35, 0);
    rc = slot_save(out, NULL);
    slot_load(out);
    printf("teleport: script=%04X v126=%u v146=%u v147=%u depth=%u "
           "stack0=%04X@%u bg=%u check=%s rc=%d\n",
           get_script(), get_var(126), get_var(146), get_var(147),
           rd32(g_blob + RETSTK_OFF),
           rd16(g_blob + RETSTK_OFF + 4), rd16(g_blob + RETSTK_OFF + 6),
           rd32(g_blob + 0x320A0), g_check_ok ? "OK" : "BAD", rc);
    remove(out);
    return 0;
}
#endif
