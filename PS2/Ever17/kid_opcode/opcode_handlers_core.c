#include "opcode_handlers_core.h"

#include <stdio.h>
#include <string.h>

static int set_simple(DecodedInsn *out, const char *name, size_t consumed, const char *args) {
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

static const char *if_compare_name(uint8_t code) {
    switch (code) {
        case 0:
            return "==";
        case 1:
            return "!=";
        case 2:
            return "<=";
        case 3:
            return ">=";
        case 4:
            return "<";
        case 5:
            return ">";
        case 6:
            return "&";
        case 7:
            return "|";
        default:
            return "?";
    }
}

static const char *reg_calc_sub_name(uint8_t code) {
    switch (code) {
        case 0x00: return "mov";
        case 0x01: return "add";
        case 0x02: return "sub";
        case 0x03: return "mul";
        case 0x04: return "div";
        case 0x05: return "mod";
        case 0x06: return "and";
        case 0x07: return "or";
        case 0x08: return "load_u8";
        case 0x09: return "load_u16";
        case 0x0A: return "store_u8";
        case 0x0B: return "store_u16";
        case 0x0C: return "imm16";
        case 0x0D: return "add_raw";
        case 0x0E: return "jump_reg";
        case 0x0F: return "jump_table";
        case 0x10: return "rand_mod";
        case 0x11: return "flag_set";
        case 0x12: return "add_sat8";
        case 0x13: return "sub_sat8";
        case 0x14: return "inc_if";
        default:   return "unknown";
    }
}

static void format_reg_calc_operand(char *out, size_t out_size, uint16_t raw) {
    uint16_t kind = raw & 0xC000;
    uint16_t index = raw & 0x1FFF;

    if (kind == 0x4000) {
        snprintf(out, out_size, "%s[%u]", (raw & 0x2000) ? "sysvar" : "var", (unsigned)index);
        return;
    }
    if (kind == 0x8000) {
        snprintf(out, out_size, "%s[%u]", (raw & 0x2000) ? "sysflag" : "flag", (unsigned)index);
        return;
    }
    snprintf(out, out_size, "imm(%d)", (int)(int16_t)raw);
}

static int reg_calc_is_storage_ref(uint16_t raw) {
    uint16_t kind = raw & 0xC000;
    return kind == 0x4000 || kind == 0x8000;
}

static int reg_calc_is_immediate(uint16_t raw) {
    uint16_t kind = raw & 0xC000;
    return kind != 0x4000 && kind != 0x8000;
}

int decode_core_opcode(DecodeContext *ctx, DecodedInsn *out) {
    const uint8_t *p = ctx->data + ctx->cursor;
    size_t remain = ctx->size - ctx->cursor;

    switch (p[0]) {
        case 0x00:
            if (remain < 2) return 0;
            return set_simple(out, "nop", 2, "");
        case 0x01:
            if (remain < 2) return 0;
            return set_simple(out, "end", 2, "");
        case 0x02: {
            size_t pos = 4;
            size_t clause_index = 0;
            size_t cursor = 0;

            if (remain < 10) return 0;

            cursor += (size_t)snprintf(out->args + cursor, sizeof(out->args) - cursor, "mode=%u target=0x%04X", p[1], (unsigned)read_u16le(p, 2));
            while (pos + 6 <= remain) {
                uint16_t lhs = read_u16le(p, pos);
                uint16_t rhs = read_u16le(p, pos + 2);
                uint8_t cmp = p[pos + 4];
                uint8_t link = p[pos + 5];
                int written;

                written = snprintf(
                    out->args + cursor,
                    sizeof(out->args) - cursor,
                    "%s[%u]=0x%04X %s 0x%04X link=%u",
                    clause_index == 0 ? " " : ", ",
                    (unsigned)clause_index,
                    (unsigned)lhs,
                    if_compare_name(cmp),
                    (unsigned)rhs,
                    (unsigned)link);
                if (written < 0 || (size_t)written >= sizeof(out->args) - cursor) {
                    return 0;
                }
                cursor += (size_t)written;
                pos += 6;
                clause_index += 1;
                if (link == 0) {
                    snprintf(out->opcode_name, sizeof(out->opcode_name), "%s", "if");
                    out->consumed = pos;
                    out->known = 1;
                    out->has_text = 0;
                    out->text_count = 0;
                    return 1;
                }
            }
            return 0;
        }
        case 0x03:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "0x%04X", (unsigned)read_u16le(p, 2));
            return set_simple(out, "int_goto", 4, out->args);
        case 0x04:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "0x%04X", (unsigned)read_u16le(p, 2));
            return set_simple(out, "int_call", 4, out->args);
        case 0x05:
            if (remain < 2) return 0;
            return set_simple(out, "int_return", 2, "");
        case 0x06:
            if (remain < 2) return 0;
            return set_simple(out, "ext_goto", 2, "");
        case 0x07:
            if (remain < 2) return 0;
            return set_simple(out, "ext_call", 2, "");
        case 0x08:
            if (remain < 2) return 0;
            return set_simple(out, "ext_return", 2, "");
        case 0x09:
            if (remain < 6) return 0;
            {
                uint16_t a_raw = read_u16le(p, 2);
                uint16_t b_raw = read_u16le(p, 4);
                char a_buf[64];
                char b_buf[64];

                format_reg_calc_operand(a_buf, sizeof(a_buf), a_raw);
                format_reg_calc_operand(b_buf, sizeof(b_buf), b_raw);
                switch (p[1]) {
                    case 0x00:
                        snprintf(
                            out->args,
                            sizeof(out->args),
                            "sub=0x%02X(%s) dst=%s%s src=%s",
                            (unsigned)p[1],
                            reg_calc_sub_name(p[1]),
                            a_buf,
                            reg_calc_is_storage_ref(a_raw) ? "" : " <bad-dst>",
                            b_buf);
                        break;
                    case 0x01:
                        snprintf(
                            out->args,
                            sizeof(out->args),
                            "sub=0x%02X(%s) dst=%s%s rhs=%s",
                            (unsigned)p[1],
                            reg_calc_sub_name(p[1]),
                            a_buf,
                            reg_calc_is_storage_ref(a_raw) ? "" : " <bad-dst>",
                            b_buf);
                        break;
                    case 0x0F:
                    {
                        uint16_t table_off = a_raw;
                        uint16_t index_raw = b_raw;
                        uint16_t first_target = 0xFFFF;
                        uint16_t current_target = 0xFFFF;
                        if (reg_calc_is_immediate(a_raw) && (size_t)table_off + 1 < ctx->size) {
                            first_target = read_u16le(ctx->data, table_off);
                        }
                        if (first_target != 0xFFFF) {
                            out->data_end_address = first_target;
                        }
                        if (reg_calc_is_immediate(a_raw) && (size_t)table_off + 1 < ctx->size) {
                            size_t entry_off = (size_t)table_off + 2 * (size_t)(uint16_t)index_raw;
                            if (entry_off + 1 < ctx->size) {
                                current_target = read_u16le(ctx->data, entry_off);
                                if (reg_calc_is_immediate(b_raw)) {
                                    out->next_address = current_target;
                                }
                            }
                        }
                        if (out->next_address == 0 && first_target != 0xFFFF) {
                            out->next_address = first_target;
                        }
                        if (first_target != 0xFFFF) {
                            snprintf(
                                out->args,
                                sizeof(out->args),
                                "sub=0x%02X(%s) table=0x%04X index=%s",
                                (unsigned)p[1],
                                reg_calc_sub_name(p[1]),
                                (unsigned)table_off,
                                b_buf);
                        } else {
                            snprintf(
                                out->args,
                                sizeof(out->args),
                                "sub=0x%02X(%s) table=%s index=%s",
                                (unsigned)p[1],
                                reg_calc_sub_name(p[1]),
                                a_buf,
                                b_buf);
                        }
                        break;
                    }
                    default:
                        snprintf(out->args, sizeof(out->args), "sub=0x%02X(%s) a=%s b=%s", (unsigned)p[1], reg_calc_sub_name(p[1]), a_buf, b_buf);
                        break;
                }
            }
            return set_simple(out, "reg_calc", 6, out->args);
        case 0x0A:
            if (remain < 2) return 0;
            return set_simple(out, "count_clear", 2, "");
        case 0x0B:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "mode=%u value=0x%04X", p[1], (unsigned)read_u16le(p, 2));
            return set_simple(out, "count_wait", 4, out->args);
        case 0x0C:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "mode=%u value=0x%04X", p[1], (unsigned)read_u16le(p, 2));
            return set_simple(out, "time_wait", 4, out->args);
        case 0x0D:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "mode=%u value=0x%04X", p[1], (unsigned)read_u16le(p, 2));
            return set_simple(out, "pad_wait", 4, out->args);
        case 0x0E:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "dst=0x%04X", (unsigned)read_u16le(p, 2));
            return set_simple(out, "pad_get", 4, out->args);
        case 0x0F:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "type=%u id=0x%04X", p[1], (unsigned)read_u16le(p, 2));
            return set_simple(out, "file_read", 4, out->args);
        case 0x10:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u", (unsigned)p[1]);
            return set_simple(out, "file_wait", 2, out->args);
        case 0x26:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "unk=%u fade=%u step=%u", (unsigned)p[1], (unsigned)p[2], (unsigned)p[3]);
            return set_simple(out, "fade_start", 4, out->args);
        case 0x27:
            if (remain < 2) return 0;
            return set_simple(out, "fade_wait", 2, "");
        case 0x28:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u res=0x%04X", (unsigned)p[1], (unsigned)read_u16le(p, 2));
            return set_simple(out, "grap_set", 4, out->args);
        case 0x29:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u", (unsigned)p[1]);
            return set_simple(out, "grap_del", 2, out->args);
        case 0x2A:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "dst=%u src=%u unk=%u", (unsigned)p[1], (unsigned)p[2], (unsigned)p[3]);
            return set_simple(out, "grap_copy", 4, out->args);
        case 0x2B:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u mode=%u wait=%u", (unsigned)p[1], (unsigned)p[2], (unsigned)p[3]);
            return set_simple(out, "grap_view", 4, out->args);
        case 0x2C:
            if (remain < 6) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u x=%d y=%d", (unsigned)p[1], (int)read_s16le(p, 2), (int)read_s16le(p, 4));
            return set_simple(out, "grap_pos", 6, out->args);
        case 0x2D:
            if (remain < 8) return 0;
            snprintf(
                out->args,
                sizeof(out->args),
                "slot=%u x=%d y=%d mode=%d wait=%u",
                (unsigned)p[1],
                (int)read_s16le(p, 2),
                (int)read_s16le(p, 4),
                (int)((int8_t)p[6]),
                (unsigned)p[7]);
            return set_simple(out, "grap_move", 8, out->args);
        case 0x2E:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u prio=%u", (unsigned)p[1], (unsigned)read_u16le(p, 2));
            return set_simple(out, "grap_prio", 4, out->args);
        case 0x2F:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u anim=%u", (unsigned)p[1], (unsigned)read_u16le(p, 2));
            return set_simple(out, "grap_anim", 4, out->args);
        case 0x30:
            if (remain < 4) return 0;
            if (read_u16le(p, 2) == 0xFFFF) {
                snprintf(out->args, sizeof(out->args), "slot=%u pal=current", (unsigned)p[1]);
            } else {
                snprintf(out->args, sizeof(out->args), "slot=%u pal=0x%04X", (unsigned)p[1], (unsigned)read_u16le(p, 2));
            }
            return set_simple(out, "grap_pal", 4, out->args);
        case 0x31:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u layer=0x%04X", (unsigned)p[1], (unsigned)read_u16le(p, 2));
            return set_simple(out, "grap_lay", 4, out->args);
        case 0x32:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%d mode=%d", (int)((int8_t)p[1]), (int)((int8_t)p[2]));
            return set_simple(out, "grap_wait", 4, out->args);
        case 0x33:
        case 0x73: {
            size_t count;
            size_t consumed;

            if (remain < 2) return 0;
            count = p[1];
            consumed = 2 + count * 12;
            if (remain < consumed) return 0;
            snprintf(
                out->args,
                sizeof(out->args),
                "type=0x%02X count=%u item_size=12",
                (unsigned)p[0],
                (unsigned)count);
            return set_simple(out, p[0] == 0x73 ? "grap_disp2" : "grap_disp", consumed, out->args);
        }
        case 0x6A: {
            size_t count;
            size_t consumed;

            if (remain < 2) return 0;
            count = p[1];
            consumed = 2 + count * 20;
            if (remain < consumed) return 0;
            snprintf(
                out->args,
                sizeof(out->args),
                "type=0x%02X count=%u item_size=20",
                (unsigned)p[0],
                (unsigned)count);
            return set_simple(out, "grap_disp_ex", consumed, out->args);
        }
        case 0x34:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "type=%u a=%u b=%u", (unsigned)p[1], (unsigned)p[2], (unsigned)p[3]);
            return set_simple(out, "effect_start", 4, out->args);
        case 0x35:
            if (remain < 2) return 0;
            return set_simple(out, "effect_end", 2, "");
        case 0x36:
            if (remain < 2) return 0;
            return set_simple(out, "effect_wait", 2, "");
        case 0x37:
            if (remain < 2) return 0;
            return set_simple(out, "bgm_set", 2, "");
        case 0x38:
            if (remain < 2) return 0;
            return set_simple(out, "bgm_del", 2, "");
        case 0x39:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "mode=%u", (unsigned)p[1]);
            return set_simple(out, "bgm_req", 2, out->args);
        case 0x3A:
            if (remain < 2) return 0;
            return set_simple(out, "bgm_wait", 2, "");
        case 0x3B:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_simple(out, "bgm_speed", 2, out->args);
        case 0x3C:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_simple(out, "bgm_vol", 2, out->args);
        case 0x3D:
            if (remain < 2) return 0;
            return set_simple(out, "se_set", 2, "");
        case 0x3E:
            if (remain < 2) return 0;
            return set_simple(out, "se_del", 2, "");
        case 0x3F:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "mode=%u", (unsigned)p[1]);
            return set_simple(out, "se_req", 2, out->args);
        case 0x40:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "mode=%u", (unsigned)p[1]);
            return set_simple(out, "se_wait", 2, out->args);
        case 0x41:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_simple(out, "se_speed", 2, out->args);
        case 0x42:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_simple(out, "se_vol", 2, out->args);
        case 0x43:
            if (remain < 2) return 0;
            return set_simple(out, "voice_set", 2, "");
        case 0x44:
            if (remain < 2) return 0;
            return set_simple(out, "voice_del", 2, "");
        case 0x45:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "mode=%u", (unsigned)p[1]);
            return set_simple(out, "voice_req", 2, out->args);
        case 0x46:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "mode=%u", (unsigned)p[1]);
            return set_simple(out, "voice_wait", 2, out->args);
        case 0x47:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_simple(out, "voice_speed", 2, out->args);
        case 0x48:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_simple(out, "voice_vol", 2, out->args);
        case 0x49:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_simple(out, "menu_lock", 2, out->args);
        case 0x4A:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_simple(out, "save_lock", 2, out->args);
        case 0x4B:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "title=0x%04X", (unsigned)read_u16le(p, 2));
            return set_simple(out, "save_check", 4, out->args);
        case 0x4C:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "title=0x%04X", (unsigned)read_u16le(p, 2));
            return set_simple(out, "save_title", 4, out->args);
        case 0x4D:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "mode=%u title=0x%04X", (unsigned)p[1], (unsigned)read_u16le(p, 2));
            return set_simple(out, "save_disp", 4, out->args);
        case 0x4E:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "disk=%u arg=0x%04X", (unsigned)p[1], (unsigned)read_u16le(p, 2));
            return set_simple(out, "disk_change", 4, out->args);
        case 0x4F:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "count=0x%04X", (unsigned)read_u16le(p, 2));
            return set_simple(out, "skip_start", 4, out->args);
        case 0x50:
            if (remain < 2) return 0;
            return set_simple(out, "skip_end", 2, "");
        case 0x51:
            if (remain < 3) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u arg=%u", (unsigned)p[1], (unsigned)p[2]);
            return set_simple(out, "task_entry", 3, out->args);
        case 0x52:
            if (remain < 2) return 0;
            return set_simple(out, "task_del", 2, "");
        case 0x53:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "res=0x%04X", (unsigned)read_u16le(p, 2));
            return set_simple(out, "cal_disp", 4, out->args);
        case 0x54:
            if (remain < 2) return 0;
            return set_simple(out, "title_disp", 2, "");
        case 0x55:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "type=%u a=%u b=%u", (unsigned)p[1], (unsigned)p[2], (unsigned)p[3]);
            return set_simple(out, "vib_start", 4, out->args);
        case 0x56:
            if (remain < 2) return 0;
            return set_simple(out, "vib_end", 2, "");
        case 0x57:
            if (remain < 2) return 0;
            return set_simple(out, "vib_wait", 2, "");
        case 0x58:
            if (remain < 4) return 0;
            return set_simple(out, "map_view", 4, "");
        case 0x59:
            if (remain < 10) return 0;
            snprintf(out->args, sizeof(out->args), "entries=%u", (unsigned)p[1]);
            return set_simple(out, "map_entry", 10, out->args);
        case 0x5A:
            if (remain < 14 || remain < 14 + ((size_t)p[1] * 18)) return 0;
            snprintf(out->args, sizeof(out->args), "count=%u res=0x%04X", (unsigned)p[1], (unsigned)read_u16le(p, 4));
            return set_simple(out, "map_disp", 14 + ((size_t)p[1] * 18), out->args);
        case 0x5B:
            if (remain < 6) return 0;
            snprintf(
                out->args,
                sizeof(out->args),
                "mode_hi=%u mode_lo=%u x=%d y=%d",
                (unsigned)(p[1] >> 4),
                (unsigned)(p[1] & 0x0F),
                (int)read_s16le(p, 2),
                (int)read_s16le(p, 4));
            return set_simple(out, "edit_view", 6, out->args);
        case 0x5C:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "wait=%u text_off=0x%04X", (unsigned)p[1], (unsigned)read_u16le(p, 2));
            return set_simple(out, "chat_send", 4, out->args);
        case 0x5D:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "text_off=0x%04X", (unsigned)read_u16le(p, 2));
            return set_simple(out, "chat_msg", 4, out->args);
        case 0x5E:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u text_off=0x%04X", (unsigned)p[1], (unsigned)read_u16le(p, 2));
            return set_simple(out, "chat_entry", 4, out->args);
        case 0x5F:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u", (unsigned)p[1]);
            return set_simple(out, "chat_exit", 2, out->args);
        case 0x61:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "movie=%u", (unsigned)p[1]);
            return set_simple(out, "movie_play", 2, out->args);
        case 0x62:
            if (remain < 12) return 0;
            snprintf(
                out->args,
                sizeof(out->args),
                "slot=%u limit=%u x=0x%04X y=0x%04X target=0x%04X speed=0x%04X",
                (unsigned)p[1],
                (unsigned)read_u16le(p, 8),
                (unsigned)read_u16le(p, 2),
                (unsigned)read_u16le(p, 4),
                (unsigned)read_u16le(p, 6),
                (unsigned)read_u16le(p, 10));
            return set_simple(out, "grap_pos_auto", 12, out->args);
        case 0x63:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u", (unsigned)p[1]);
            return set_simple(out, "grap_pos_save", 2, out->args);
        case 0x64:
            if (remain < 16) return 0;
            snprintf(
                out->args,
                sizeof(out->args),
                "slot=%u limit=%u u0=0x%04X v0=0x%04X u1=0x%04X v1=0x%04X target=0x%04X speed=0x%04X",
                (unsigned)p[1],
                (unsigned)read_u16le(p, 12),
                (unsigned)read_u16le(p, 2),
                (unsigned)read_u16le(p, 4),
                (unsigned)read_u16le(p, 6),
                (unsigned)read_u16le(p, 8),
                (unsigned)read_u16le(p, 10),
                (unsigned)read_u16le(p, 14));
            return set_simple(out, "grap_uv_auto", 16, out->args);
        case 0x65:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u", (unsigned)p[1]);
            return set_simple(out, "grap_uv_save", 2, out->args);
        case 0x66:
            if (remain < 38) return 0;
            snprintf(
                out->args,
                sizeof(out->args),
                "slot=%u mode=%u arg0=0x%04X arg1=0x%04X arg2=0x%04X arg3=0x%04X",
                (unsigned)p[1],
                (unsigned)p[2],
                (unsigned)read_u16le(p, 4),
                (unsigned)read_u16le(p, 6),
                (unsigned)read_u16le(p, 8),
                (unsigned)read_u16le(p, 10));
            return set_simple(out, "effect_ex", 38, out->args);
        case 0x67:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "type=%u a=%u b=%u", (unsigned)p[1], (unsigned)p[2], (unsigned)p[3]);
            return set_simple(out, "fade_ex", 4, out->args);
        case 0x68:
            if (remain < 6) return 0;
            snprintf(
                out->args,
                sizeof(out->args),
                "type=%u a=%u b=%u c=%u d=%u",
                (unsigned)p[1],
                (unsigned)p[2],
                (unsigned)p[3],
                (unsigned)p[4],
                (unsigned)p[5]);
            return set_simple(out, "vib_ex", 6, out->args);
        case 0x69:
            if (remain < 6) return 0;
            snprintf(out->args, sizeof(out->args), "x=0x%04X y=0x%04X", (unsigned)read_u16le(p, 2), (unsigned)read_u16le(p, 4));
            return set_simple(out, "clock_disp", 6, out->args);
        case 0x6B:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "mode=%u", (unsigned)p[1]);
            return set_simple(out, "map_init_ex", 2, out->args);
        case 0x6C:
            if (remain < 8) return 0;
            if (p[2] == 0xFE) {
                snprintf(
                    out->args,
                    sizeof(out->args),
                    "slot=%u mode=0x%02X hidden",
                    (unsigned)p[1],
                    (unsigned)p[2]);
            } else {
                snprintf(
                    out->args,
                    sizeof(out->args),
                    "slot=%u mode=0x%02X arg=%u x=%d y=%d",
                    (unsigned)p[1],
                    (unsigned)p[2],
                    (unsigned)p[3],
                    (int)read_s16le(p, 4),
                    (int)read_s16le(p, 6));
            }
            return set_simple(out, "map_point_ex", 8, out->args);
        case 0x6D:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u off=0x%04X", (unsigned)p[1], (unsigned)read_u16le(p, 2));
            return set_simple(out, "map_route_ex", 4, out->args);
        case 0x6E:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_simple(out, "quick_save", 2, out->args);
        case 0x6F:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_simple(out, "trace_spc", 2, out->args);
        case 0x70:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "text_off=0x%04X", (unsigned)read_u16le(p, 2));
            return set_simple(out, "sys_msg", 4, out->args);
        case 0x71:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_simple(out, "skip_lock", 2, out->args);
        case 0x72:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_simple(out, "key_lock", 2, out->args);
        case 0x76:
            if (remain < 8) return 0;
            snprintf(
                out->args,
                sizeof(out->args),
                "year=0x%04X month=0x%04X day=0x%04X",
                (unsigned)read_u16le(p, 2),
                (unsigned)read_u16le(p, 4),
                (unsigned)read_u16le(p, 6));
            return set_simple(out, "date_disp", 8, out->args);
        case 0x77:
            if (remain < 2) return 0;
            return set_simple(out, "vr_disp", 2, "");
        case 0x78:
            if (remain < 2) return 0;
            return set_simple(out, "vr_select", 2, "");
        case 0x79:
            if (remain < 2) return 0;
            return set_simple(out, "vr_reg_calc", 2, "");
        case 0x7B:
            if (remain < 2) return 0;
            return set_simple(out, "map_select", 2, "");
        case 0x7C:
            if (remain < 2) return 0;
            return set_simple(out, "ecg_set", 2, "");
        case 0x7D:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "text_off=0x%04X", (unsigned)read_u16le(p, 2));
            return set_simple(out, "ev_init", 4, out->args);
        case 0x7E:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "slot=%u text_off=0x%04X", (unsigned)p[1], (unsigned)read_u16le(p, 2));
            return set_simple(out, "ev_disp", 4, out->args);
        case 0x7F:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "text_off=0x%04X", (unsigned)read_u16le(p, 2));
            return set_simple(out, "ev_anim", 4, out->args);
        case 0x80:
            if (remain < 2) return 0;
            snprintf(out->args, sizeof(out->args), "%u", (unsigned)p[1]);
            return set_simple(out, "eye_lock", 2, out->args);
        case 0x81:
            if (remain < 4) return 0;
            snprintf(out->args, sizeof(out->args), "arg=0x%04X", (unsigned)read_u16le(p, 2));
            return set_simple(out, "msg_log", 4, out->args);
        default:
            return 0;
    }
}
