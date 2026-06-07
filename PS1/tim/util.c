#include "util.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char *utf8_from_wide(const wchar_t *w) {
    int n = WideCharToMultiByte(CP_UTF8, 0, w, -1, NULL, 0, NULL, NULL);
    char *s = (char *)malloc((size_t)n);
    if (!s) return NULL;
    WideCharToMultiByte(CP_UTF8, 0, w, -1, s, n, NULL, NULL);
    return s;
}

wchar_t *wide_from_utf8(const char *s) {
    int n = MultiByteToWideChar(CP_UTF8, 0, s, -1, NULL, 0);
    wchar_t *w = (wchar_t *)malloc((size_t)n * sizeof(wchar_t));
    if (!w) return NULL;
    MultiByteToWideChar(CP_UTF8, 0, s, -1, w, n);
    return w;
}

int path_join_w(wchar_t *out, size_t cap, const wchar_t *dir, const wchar_t *name) {
    (void)cap;
    return swprintf(out, L"%ls\\%ls", dir, name) < 0 ? -1 : 0;
}

int path_change_ext_w(wchar_t *out, size_t cap, const wchar_t *path, const wchar_t *ext) {
    const wchar_t *slash1 = wcsrchr(path, L'\\');
    const wchar_t *slash2 = wcsrchr(path, L'/');
    const wchar_t *name = path;
    const wchar_t *dot;
    size_t prefix_len;
    if (slash1 && (!slash2 || slash1 > slash2)) name = slash1 + 1;
    else if (slash2) name = slash2 + 1;
    dot = wcsrchr(name, L'.');
    prefix_len = dot ? (size_t)(dot - path) : wcslen(path);
    if (prefix_len + wcslen(ext) + 1 > cap) return -1;
    wmemcpy(out, path, prefix_len);
    wcscpy(out + prefix_len, ext);
    return 0;
}

int path_stem_w(wchar_t *out, size_t cap, const wchar_t *path) {
    const wchar_t *base = wcsrchr(path, L'\\');
    const wchar_t *base2 = wcsrchr(path, L'/');
    const wchar_t *name = base;
    if (!name || (base2 && base2 > name)) name = base2;
    name = name ? name + 1 : path;
    const wchar_t *dot = wcsrchr(name, L'.');
    size_t len = dot ? (size_t)(dot - name) : wcslen(name);
    if (len + 1 > cap) return -1;
    wmemcpy(out, name, len);
    out[len] = 0;
    return 0;
}

int path_make_relative_no_ext_w(wchar_t *out, size_t cap, const wchar_t *base_dir, const wchar_t *full_path) {
    size_t base_len = wcslen(base_dir);
    const wchar_t *p = full_path;
    if (_wcsnicmp(base_dir, full_path, base_len) == 0) {
        p = full_path + base_len;
        if (*p == L'\\' || *p == L'/') p++;
    }
    if (wcslen(p) + 1 > cap) return -1;
    wcscpy(out, p);
    {
        wchar_t *dot = wcsrchr(out, L'.');
        if (dot) *dot = 0;
    }
    return 0;
}

int path_join_stem_ext_w(wchar_t *out, size_t cap, const wchar_t *base_dir, const wchar_t *stem, const wchar_t *ext) {
    wchar_t tmp[MAX_PATH * 4];
    if (swprintf(tmp, L"%ls\\%ls", base_dir, stem) < 0) return -1;
    return path_change_ext_w(out, cap, tmp, ext);
}

int ensure_parent_dir_w(const wchar_t *path) {
    wchar_t tmp[MAX_PATH * 4];
    wchar_t *slash;
    size_t len = wcslen(path);
    if (len >= (sizeof(tmp) / sizeof(tmp[0]))) return -1;
    wcscpy(tmp, path);
    slash = wcsrchr(tmp, L'\\');
    if (!slash) slash = wcsrchr(tmp, L'/');
    if (!slash) return 0;
    *slash = 0;
    return ensure_dir_w(tmp);
}

static int mkdir_one(const wchar_t *path) {
    if (CreateDirectoryW(path, NULL)) return 0;
    if (GetLastError() == ERROR_ALREADY_EXISTS) return 0;
    return -1;
}

int ensure_dir_w(const wchar_t *path) {
    wchar_t tmp[MAX_PATH * 4];
    size_t len = wcslen(path);
    if (len >= (sizeof(tmp) / sizeof(tmp[0]))) return -1;
    wcscpy(tmp, path);
    for (wchar_t *p = tmp + 1; *p; ++p) {
        if (*p == L'\\' || *p == L'/') {
            wchar_t hold = *p;
            *p = 0;
            mkdir_one(tmp);
            *p = hold;
        }
    }
    return mkdir_one(tmp);
}

int read_file_w(const wchar_t *path, uint8_t **data, size_t *size) {
    FILE *f = _wfopen(path, L"rb");
    long len;
    uint8_t *buf;
    if (!f) return -1;
    if (fseek(f, 0, SEEK_END) != 0) {
        fclose(f);
        return -1;
    }
    len = ftell(f);
    if (len < 0) {
        fclose(f);
        return -1;
    }
    if (fseek(f, 0, SEEK_SET) != 0) {
        fclose(f);
        return -1;
    }
    buf = (uint8_t *)malloc((size_t)len ? (size_t)len : 1);
    if (!buf) {
        fclose(f);
        return -1;
    }
    if (fread(buf, 1, (size_t)len, f) != (size_t)len) {
        free(buf);
        fclose(f);
        return -1;
    }
    fclose(f);
    *data = buf;
    *size = (size_t)len;
    return 0;
}

int write_file_w(const wchar_t *path, const uint8_t *data, size_t size) {
    FILE *f = _wfopen(path, L"wb");
    if (!f) return -1;
    if (size && fwrite(data, 1, size, f) != size) {
        fclose(f);
        return -1;
    }
    fclose(f);
    return 0;
}
