#include "opcode_handlers_text.h"

#include "cp932.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int set_textless(DecodedInsn *out, const char *name, size_t consumed, const char *args) {
    snprintf(out->opcode_name, sizeof(out->opcode_name), "%s", name);
    out->consumed = consumed;
    out->known = 1;
    out->has_text = 0;
    out->text_count = 0;
    if (args) {
        snprintf(out->args, sizeof(out->args), "%s", args);
    } else {
        out->args[0] = '\0';
    }
    return 1;
}

static uint16_t read_u16le(const uint8_t *data, size_t off) {
    return (uint16_t)(data[off] | (data[off + 1] << 8));
}

static int16_t read_s16le(const uint8_t *data, size_t off) {
    return (int16_t)read_u16le(data, off);
}

static int append_text(DecodedInsn *out, const char *text) {
    if (out->text_count >= 256) {
        return 0;
    }
    snprintf(out->texts[out->text_count], sizeof(out->texts[out->text_count]), "%s", text);
    out->text_count += 1;
    out->has_text = 1;
    return 1;
}

static int read_script_text_utf8(DecodeContext *ctx, uint16_t offset, char *out_text, size_t out_size) {
    const uint8_t *base;
    size_t pos;
    size_t start;
    char *utf8 = NULL;

    if (offset == 0xFFFF) {
        snprintf(out_text, out_size, "<null>");
        return 1;
    }
    if (ctx->size < 2) {
        return 0;
    }
    base = ctx->data;
    start = (size_t)offset;
    if (start >= ctx->size) {
        snprintf(out_text, out_size, "<bad:0x%04X>", (unsigned)offset);
        return 1;
    }
    pos = start;
    while (pos < ctx->size && base[pos] != 0) {
        pos += 1;
    }
    if (pos > ctx->size) {
        return 0;
    }
    if (!cp932_bytes_to_utf8(base + start, pos - start, &utf8)) {
        snprintf(out_text, out_size, "<cp932:0x%04X>", (unsigned)offset);
        return 1;
    }
    snprintf(out_text, out_size, "%s", utf8);
    free(utf8);
    return 1;
}

int decode_text_opcode(DecodeContext *ctx, DecodedInsn *out) {
    const uint8_t *p = ctx->data + ctx->cursor;
    size_t remain = ctx->size - ctx->cursor;

    switch (p[0]) {
        case 0x11:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_textless(out, "msg_wind", 2, out->args);
        case 0x12:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_textless(out, "msg_view", 2, out->args);
        case 0x13:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_textless(out, "msg_mode", 2, out->args);
        case 0x14:
            if (remain < 6) return 0;
            snprintf(out->args, sizeof(out->args), "%d %d", (int)read_s16le(p, 2), (int)read_s16le(p, 4));
            return set_textless(out, "msg_pos", 6, out->args);
        case 0x15:
            if (remain < 6) return 0;
            snprintf(out->args, sizeof(out->args), "%d %d", (int)read_s16le(p, 2), (int)read_s16le(p, 4));
            return set_textless(out, "msg_size", 6, out->args);
        case 0x16:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_textless(out, "msg_type", 2, out->args);
        case 0x17:
            if (remain < 6) return 0;
            snprintf(out->args, sizeof(out->args), "%d %d", (int)read_s16le(p, 2), (int)read_s16le(p, 4));
            return set_textless(out, "msg_cursor", 6, out->args);
        case 0x18:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "0x%04X", (unsigned)read_u16le(p, 2));
            return set_textless(out, "msg_set", 4, out->args);
        case 0x19:
            if (remain < 2) return 0;
            return set_textless(out, "msg_wait", 2, "");
        case 0x1A:
            if (remain < 2) return 0;
            return set_textless(out, "msg_clear", 2, "");
        case 0x1B:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "0x%04X", (unsigned)read_u16le(p, 2));
            return set_textless(out, "msg_line", 4, out->args);
        case 0x1C:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "0x%04X", (unsigned)read_u16le(p, 2));
            return set_textless(out, "msg_speed", 4, out->args);
        case 0x1D:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "0x%04X", (unsigned)read_u16le(p, 2));
            return set_textless(out, "msg_color", 4, out->args);
        case 0x1E:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "0x%04X", (unsigned)read_u16le(p, 2));
            return set_textless(out, "msg_anim", 4, out->args);
        case 0x1F:
        case 0x7A: {
            char text_buf[512];
            uint16_t text_off;
            if (remain < 8) return 0;
            text_off = read_u16le(p, 2);
            if (!read_script_text_utf8(ctx, text_off, text_buf, sizeof(text_buf))) return 0;
            snprintf(out->args, sizeof(out->args), "mode=0x%02X text_off=0x%04X voice=0x%04X wait=0x%04X", p[1], (unsigned)text_off, (unsigned)read_u16le(p, 4), (unsigned)read_u16le(p, 6));
            if (!set_textless(out, p[0] == 0x7A ? "vr_msg_disp" : "msg_disp", 8, out->args)) return 0;
            return append_text(out, text_buf);
        }
        case 0x20:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "0x%04X", (unsigned)read_u16le(p, 2));
            return set_textless(out, "sel_set", 4, out->args);
        case 0x21:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "0x%04X", (unsigned)read_u16le(p, 2));
            return set_textless(out, "sel_entry", 4, out->args);
        case 0x22:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "0x%04X", (unsigned)read_u16le(p, 2));
            return set_textless(out, "sel_view", 4, out->args);
        case 0x23:
            if (remain < 2) return 0;
            return set_textless(out, "sel_wait", 2, "");
        case 0x24:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "0x%04X", (unsigned)read_u16le(p, 2));
            return set_textless(out, "sel_style", 4, out->args);
        case 0x25:
        case 0x75: {
            size_t count;
            size_t entry_base;
            size_t consumed;
            size_t i;

            if (remain < 4) return 0;
            count = p[1];
            entry_base = (p[0] == 0x25) ? 4 : 6;
            consumed = entry_base + count * 8;
            if (remain < consumed) return 0;
            snprintf(out->args, sizeof(out->args), "count=%u base=0x%04X", (unsigned)count, (unsigned)read_u16le(p, 2));
            if (!set_textless(out, p[0] == 0x25 ? "sel_disp" : "sel_disp2", consumed, out->args)) return 0;
            for (i = 0; i < count; ++i) {
                uint16_t text_off = read_u16le(p, entry_base + i * 8);
                char text_buf[512];
                if (!read_script_text_utf8(ctx, text_off, text_buf, sizeof(text_buf))) return 0;
                if (!append_text(out, text_buf)) return 0;
            }
            return 1;
        }
        case 0x74: {
            char text_buf[512];
            uint16_t text_off;
            if (remain < 10) return 0;
            text_off = read_u16le(p, 4);
            if (!read_script_text_utf8(ctx, text_off, text_buf, sizeof(text_buf))) return 0;
            snprintf(out->args, sizeof(out->args), "mode=0x%02X voice=0x%04X wait=0x%04X extra=0x%04X", p[1], (unsigned)read_u16le(p, 2), (unsigned)read_u16le(p, 6), (unsigned)read_u16le(p, 8));
            if (!set_textless(out, "msg_disp2", 10, out->args)) return 0;
            return append_text(out, text_buf);
        }
        case 0x5C:
        case 0x5D:
        case 0x5E:
        case 0x70:
        case 0x7D:
        case 0x7E:
        case 0x7F: {
            char text_buf[512];
            uint16_t text_off;
            const char *name;

            if (remain < 4) return 0;
            text_off = read_u16le(p, 2);
            if (!read_script_text_utf8(ctx, text_off, text_buf, sizeof(text_buf))) return 0;
            switch (p[0]) {
                case 0x5C:
                    name = "chat_send";
                    snprintf(out->args, sizeof(out->args), "wait=%u", (unsigned)p[1]);
                    break;
                case 0x5D:
                    name = "chat_msg";
                    out->args[0] = '\0';
                    break;
                case 0x5E:
                    name = "chat_entry";
                    snprintf(out->args, sizeof(out->args), "slot=%u", (unsigned)p[1]);
                    break;
                case 0x70:
                    name = "sys_msg";
                    out->args[0] = '\0';
                    break;
                case 0x7D:
                    name = "ev_init";
                    out->args[0] = '\0';
                    break;
                case 0x7E:
                    name = "ev_disp";
                    snprintf(out->args, sizeof(out->args), "slot=%u", (unsigned)p[1]);
                    break;
                default:
                    name = "ev_anim";
                    out->args[0] = '\0';
                    break;
            }
            if (!set_textless(out, name, 4, out->args)) return 0;
            return append_text(out, text_buf);
        }
        default:
            return 0;
    }
}
