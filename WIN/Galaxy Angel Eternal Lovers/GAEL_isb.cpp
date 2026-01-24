#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <filesystem>
#include <fstream>
#include <algorithm>
#include <stdexcept>
#include <iostream>

using u8  = uint8_t;
using u16 = uint16_t;
using u32 = uint32_t;
using i32 = int32_t;

static constexpr u32 P_INT   = 0x40403;
static constexpr u32 P_FLOAT = 0x40402;
static constexpr u32 P_WSTR  = 0x40400;
static constexpr u32 P_STR   = 0x80002;
static constexpr u32 P_VAR   = 0x80001;
static constexpr u32 P_END   = 0x0401;

static constexpr u16 OP_CMD = 0x0000;
static constexpr u16 OP_RET = 0x0401;

static const std::string OPCODES_TXT = "opcode.txt";
static const std::string ELL = std::string("\x81\x63", 2);

static inline u32 ror3(u32 x){ return (x >> 3) | (x << 29); }
static inline u32 rol3(u32 x){ return (x << 3) | (x >> 29); }

static inline u32 rd_u32(const std::vector<u8>& b, size_t o){
    if(o + 4 > b.size()) throw std::runtime_error("rd_u32 oob");
    u32 v;
    std::memcpy(&v, b.data() + o, 4);
    return v;
}
static inline i32 rd_i32(const std::vector<u8>& b, size_t o){
    u32 v = rd_u32(b, o);
    i32 s;
    std::memcpy(&s, &v, 4);
    return s;
}
static inline float rd_f32(const std::vector<u8>& b, size_t o){
    u32 v = rd_u32(b, o);
    float f;
    std::memcpy(&f, &v, 4);
    return f;
}
static inline void wr_u32(std::vector<u8>& out, u32 v){
    out.push_back((u8)(v & 0xFF));
    out.push_back((u8)((v >> 8) & 0xFF));
    out.push_back((u8)((v >> 16) & 0xFF));
    out.push_back((u8)((v >> 24) & 0xFF));
}
static inline void set_u16_le(std::vector<u8>& out, size_t o, u16 v){
    if(o + 2 > out.size()) throw std::runtime_error("set_u16 oob");
    out[o] = (u8)(v & 0xFF);
    out[o + 1] = (u8)((v >> 8) & 0xFF);
}

static std::vector<u8> read_file(const std::filesystem::path& p){
    std::ifstream f(p, std::ios::binary);
    if(!f) throw std::runtime_error("open failed: " + p.string());
    f.seekg(0, std::ios::end);
    auto n = (size_t)f.tellg();
    f.seekg(0, std::ios::beg);
    std::vector<u8> buf(n);
    if(n && !f.read((char*)buf.data(), (std::streamsize)n)) throw std::runtime_error("read failed");
    return buf;
}
static void write_file(const std::filesystem::path& p, const std::vector<u8>& b){
    std::ofstream f(p, std::ios::binary);
    if(!f) throw std::runtime_error("open failed: " + p.string());
    if(!b.empty()) f.write((const char*)b.data(), (std::streamsize)b.size());
}

static inline bool is_space(u8 c){
    return c==' ' || c=='\t' || c=='\r' || c=='\n';
}
static std::string trim_copy(const std::string& s){
    size_t i=0, j=s.size();
    while(i<j && is_space((u8)s[i])) i++;
    while(j>i && is_space((u8)s[j-1])) j--;
    return s.substr(i, j-i);
}
static std::string to_lower_ascii(std::string s){
    for(char& c: s) if((unsigned char)c < 0x80 && c>='A' && c<='Z') c = char(c - 'A' + 'a');
    return s;
}
static std::string to_upper_ascii(std::string s){
    for(char& c: s) if((unsigned char)c < 0x80 && c>='a' && c<='z') c = char(c - 'a' + 'A');
    return s;
}

static u32 make_str_id_bytes(const std::string& bs){
    u32 v2=0, v3=0;
    for(u8 b: bs){
        v3 = (v3 + b) & 0xFFFFFFFFu;
        v2 = ((v2 << 8) + b) & 0xFFFFFFFFu;
        v2 %= 0xFFF9D7u;
    }
    return (((v3 & 0xFFu) << 24) | v2) & 0xFFFFFFFFu;
}
static u32 make_str_id_cp932_like(const std::string& s){
    return make_str_id_bytes(to_lower_ascii(s));
}

static u32 parse_hex_u32(std::string s){
    s = trim_copy(s);
    if(s.size() >= 2 && (s[0]=='0') && (s[1]=='x' || s[1]=='X')) s = s.substr(2);
    if(s.empty()) throw std::runtime_error("bad hex");
    u32 v = 0;
    for(char c: s){
        int d=-1;
        if(c>='0'&&c<='9') d=c-'0';
        else if(c>='a'&&c<='f') d=c-'a'+10;
        else if(c>='A'&&c<='F') d=c-'A'+10;
        else throw std::runtime_error("bad hex char");
        v = (v<<4) | (u32)d;
    }
    return v;
}
static u32 parse_var_u32(const std::string& t){
    if(t.empty() || t[0] != '@') throw std::runtime_error("bad var");
    return parse_hex_u32(t.substr(1));
}
static u32 parse_ptr_u32(const std::string& t){
    if(t.empty() || t[0] != '*') throw std::runtime_error("bad ptr");
    return parse_hex_u32(t.substr(1));
}
static u32 parse_lbl_u32(const std::string& t){
    if(t.empty() || !(t[0]=='L' || t[0]=='l')) throw std::runtime_error("bad lbl");
    return (u32)std::stoul(t.substr(1), nullptr, 10);
}
static u32 parse_sym_u32(const std::string& t){
    if(!t.empty() && t[0]=='#') return parse_hex_u32(t.substr(1));
    return make_str_id_cp932_like(t);
}

static std::string hex8(u32 v){
    static const char* h = "0123456789ABCDEF";
    std::string s(8, '0');
    for(int i=7;i>=0;i--){ s[i]=h[v&0xF]; v>>=4; }
    return s;
}

static std::pair<std::vector<u8>, size_t> dec_blob(const std::vector<u8>& buf, size_t pos, size_t n, u32 key){
    size_t a = (n + 3) & ~size_t(3);
    std::vector<u8> out(a);
    for(size_t i=0;i<a;i+=4){
        u32 w = rd_u32(buf, pos+i);
        u32 v = (ror3(w) ^ key) & 0xFFFFFFFFu;
        std::memcpy(out.data()+i, &v, 4);
    }
    out.resize(n);
    return {out, a};
}
static std::vector<u8> enc_blob(const std::vector<u8>& plain, u32 key, bool use_ellipsis){
    size_t n = plain.size();
    size_t a = (n + 3) & ~size_t(3);
    std::vector<u8> tmp(a, 0);
    if(n) std::memcpy(tmp.data(), plain.data(), n);

    std::vector<u8> out(a);
    for(size_t i=0;i<a;i+=4){
        u32 w;
        std::memcpy(&w, tmp.data()+i, 4);
        u32 v = rol3((w ^ key) & 0xFFFFFFFFu);
        std::memcpy(out.data()+i, &v, 4);
    }
    return out;
}

static std::vector<std::string> split_lines_bytes(const std::vector<u8>& b){
    std::vector<std::string> out;
    size_t i=0, n=b.size();
    while(i<n){
        size_t j=i;
        while(j<n && b[j]!='\n') j++;
        size_t end=j;
        if(end>i && b[end-1]=='\r') end--;
        out.emplace_back((const char*)b.data()+i, end-i);
        i = (j<n)? j+1 : j;
    }
    if(!n) out.clear();
    return out;
}

static std::vector<std::string> split_csv_quoted(const std::string& s, bool keep_empty){
    std::vector<std::string> out;
    std::string cur;
    bool inq=false;
    for(u8 c: s){
        if(c=='"'){ inq = !inq; cur.push_back((char)c); continue; }
        if(c==',' && !inq){
            auto t = trim_copy(cur);
            if(keep_empty || !t.empty()) out.push_back(t);
            cur.clear();
            continue;
        }
        cur.push_back((char)c);
    }
    auto t = trim_copy(cur);
    if(keep_empty || !t.empty()) out.push_back(t);
    return out;
}

static bool is_block_cmd(const std::string& cmd){
    return cmd=="text" || cmd=="select";
}
static bool is_ellipsis_cmd(const std::string& cmd){
    return cmd=="text" || cmd=="select";
}
static bool is_noquote_cmd(const std::string& cmd){
    return cmd=="voice" || cmd=="savelabel" || cmd=="timeadd" || cmd=="timeset" || cmd=="timecheck";
}

static std::unordered_map<u32, std::string> load_cmd_map(const std::filesystem::path& base){
    std::unordered_map<u32, std::string> m;
    auto p = base / OPCODES_TXT;
    if(!std::filesystem::exists(p)) return m;
    auto b = read_file(p);
    std::string txt((const char*)b.data(), b.size());
    size_t i=0;
    while(i<txt.size()){
        size_t j = txt.find('\n', i);
        if(j==std::string::npos) j = txt.size();
        std::string ln = txt.substr(i, j-i);
        if(!ln.empty() && ln.back()=='\r') ln.pop_back();
        ln = trim_copy(ln);
        if(!ln.empty()){
            auto low = to_lower_ascii(ln);
            m.emplace(make_str_id_cp932_like(low), ln);
        }
        i = (j<txt.size()? j+1 : j);
    }
    return m;
}

struct TableInfo{
    u32 blocks=0;
    size_t tbl_start=0;
    std::vector<u32> addrs;
};

static bool read_table(const std::vector<u8>& buf, TableInfo& ti){
    if(buf.size() < 8) return false;
    u32 total = rd_u32(buf, buf.size()-4);
    u32 blocks = total & 0x3FFFFFFFu;
    size_t tbl = buf.size()-4 - (size_t)blocks*4;
    if(blocks==0 || (int64_t)tbl < 0) return false;
    if(tbl > buf.size()) return false;
    ti.blocks = blocks;
    ti.tbl_start = tbl;
    ti.addrs.resize(blocks);
    for(u32 i=0;i<blocks;i++) ti.addrs[i] = rd_u32(buf, tbl + (size_t)i*4);
    return true;
}

static const std::unordered_map<u16, std::string> OP_NAME = {
    {0x0001,"MOV"},{0x0002,"MOV"},{0x0003,"PUSH"},{0x0004,"PUSH"},{0x0005,"POP"},
    {0x0100,"INC"},{0x0101,"DEC"},{0x0102,"ADD"},{0x0103,"ADD"},{0x0104,"SUB"},{0x0105,"SUB"},
    {0x0106,"MUL"},{0x0107,"MUL"},{0x0108,"DIV"},{0x0109,"DIV"},
    {0x0200,"NOT"},{0x0201,"AND"},{0x0202,"AND"},{0x0203,"OR"},{0x0204,"OR"},
    {0x0300,"SETE"},{0x0301,"SETE"},{0x0302,"SETNE"},{0x0303,"SETNE"},{0x0304,"SETG"},{0x0305,"SETG"},
    {0x0306,"SETGE"},{0x0307,"SETGE"},{0x0308,"SETL"},{0x0309,"SETL"},{0x030A,"SETLE"},{0x030B,"SETLE"},
    {0x0400,"CALL"},{0x0401,"RET"},{0x0402,"JMP"},{0x0403,"JMP"},
    {0x0500,"JZ"},{0x0501,"JNZ"},{0x0502,"JE"},{0x0503,"JE"},{0x0504,"JNE"},{0x0505,"JNE"},
    {0x0506,"JG"},{0x0507,"JG"},{0x0508,"JGE"},{0x0509,"JGE"},{0x050A,"JL"},{0x050B,"JL"},
    {0x050C,"JLE"},{0x050D,"JLE"}
};

static const std::unordered_map<u16, std::string> OP_FMT = {
    {0x0401,""},
    {0x0001,"vv"},{0x0002,"vi"},{0x0003,"v"},{0x0004,"p"},{0x0005,"v"},
    {0x0100,"v"},{0x0101,"v"},{0x0102,"vv"},{0x0103,"vi"},{0x0104,"vv"},{0x0105,"vi"},
    {0x0106,"vv"},{0x0107,"vi"},{0x0108,"vv"},{0x0109,"vi"},
    {0x0200,"v"},{0x0201,"vv"},{0x0202,"vi"},{0x0203,"vv"},{0x0204,"vi"},
    {0x0300,"vv"},{0x0301,"vi"},{0x0302,"vv"},{0x0303,"vi"},{0x0304,"vv"},{0x0305,"vi"},
    {0x0306,"vv"},{0x0307,"vi"},{0x0308,"vv"},{0x0309,"vi"},{0x030A,"vv"},{0x030B,"vi"},
    {0x0400,"s"},{0x0402,"s"},{0x0403,"l"},
    {0x0500,"vl"},{0x0501,"vl"},
    {0x0502,"vvl"},{0x0503,"vil"},{0x0504,"vvl"},{0x0505,"vil"},
    {0x0506,"vvl"},{0x0507,"vil"},{0x0508,"vvl"},{0x0509,"vil"},
    {0x050A,"vvl"},{0x050B,"vil"},{0x050C,"vvl"},{0x050D,"vil"}
};

static inline bool is_var_tok(const std::string& t){ return !t.empty() && t[0]=='@'; }
static inline bool is_lbl_tok(const std::string& t){ return !t.empty() && (t[0]=='L' || t[0]=='l'); }

static u16 resolve_opcode(const std::string& mnem, const std::vector<std::string>& ops){
    std::string u = to_upper_ascii(trim_copy(mnem));
    if(u=="CALL") return 0x0400;
    if(u=="RET") return 0x0401;
    if(u=="JZ") return 0x0500;
    if(u=="JNZ") return 0x0501;
    if(u=="JMP") return is_lbl_tok(ops.at(0)) ? 0x0403 : 0x0402;
    if(u=="PUSH") return (!ops.empty() && !ops[0].empty() && ops[0][0]=='*') ? 0x0004 : 0x0003;
    if(u=="POP") return 0x0005;
    if(u=="INC") return 0x0100;
    if(u=="DEC") return 0x0101;
    if(u=="NOT") return 0x0200;
    if(u=="MOV") return is_var_tok(ops.at(1)) ? 0x0001 : 0x0002;
    if(u=="ADD") return is_var_tok(ops.at(1)) ? 0x0102 : 0x0103;
    if(u=="SUB") return is_var_tok(ops.at(1)) ? 0x0104 : 0x0105;
    if(u=="MUL") return is_var_tok(ops.at(1)) ? 0x0106 : 0x0107;
    if(u=="DIV") return is_var_tok(ops.at(1)) ? 0x0108 : 0x0109;
    if(u=="AND") return is_var_tok(ops.at(1)) ? 0x0201 : 0x0202;
    if(u=="OR")  return is_var_tok(ops.at(1)) ? 0x0203 : 0x0204;
    if(u=="SETE")  return is_var_tok(ops.at(1)) ? 0x0300 : 0x0301;
    if(u=="SETNE") return is_var_tok(ops.at(1)) ? 0x0302 : 0x0303;
    if(u=="SETG")  return is_var_tok(ops.at(1)) ? 0x0304 : 0x0305;
    if(u=="SETGE") return is_var_tok(ops.at(1)) ? 0x0306 : 0x0307;
    if(u=="SETL")  return is_var_tok(ops.at(1)) ? 0x0308 : 0x0309;
    if(u=="SETLE") return is_var_tok(ops.at(1)) ? 0x030A : 0x030B;
    if(u=="JE")  return is_var_tok(ops.at(1)) ? 0x0502 : 0x0503;
    if(u=="JNE") return is_var_tok(ops.at(1)) ? 0x0504 : 0x0505;
    if(u=="JG")  return is_var_tok(ops.at(1)) ? 0x0506 : 0x0507;
    if(u=="JGE") return is_var_tok(ops.at(1)) ? 0x0508 : 0x0509;
    if(u=="JL")  return is_var_tok(ops.at(1)) ? 0x050A : 0x050B;
    if(u=="JLE") return is_var_tok(ops.at(1)) ? 0x050C : 0x050D;
    throw std::runtime_error("unknown mnem: " + mnem);
}

static std::vector<u8> pack_ins_line(const std::string& line){
    auto s = trim_copy(line);
    if(s.empty()) return {};
    auto up = to_upper_ascii(s);
    if(up=="RET" || up=="RETURN"){
        std::vector<u8> blk(4, 0);
        set_u16_le(blk, 0, OP_RET);
        set_u16_le(blk, 2, 0);
        return blk;
    }
    auto sp = s.find(' ');
    std::string mnem = (sp==std::string::npos) ? s : trim_copy(s.substr(0, sp));
    std::vector<std::string> ops;
    if(sp!=std::string::npos){
        std::string tail = trim_copy(s.substr(sp+1));
        if(!tail.empty()){
            size_t i=0;
            while(i<tail.size()){
                size_t j = tail.find(',', i);
                if(j==std::string::npos) j = tail.size();
                auto t = trim_copy(tail.substr(i, j-i));
                if(!t.empty()) ops.push_back(t);
                i = (j<tail.size()? j+1 : j);
            }
        }
    }
    u16 op = resolve_opcode(mnem, ops);
    auto itf = OP_FMT.find(op);
    if(itf==OP_FMT.end()) throw std::runtime_error("missing fmt");
    const std::string& fmt = itf->second;

    std::vector<u8> blk(4, 0);
    auto w_u32 = [&](u32 v){ wr_u32(blk, v); };
    auto w_i32 = [&](i32 v){ u32 u; std::memcpy(&u, &v, 4); wr_u32(blk, u); };

    for(size_t k=0;k<fmt.size();k++){
        char c = fmt[k];
        const auto& t = ops.at(k);
        if(c=='v') w_u32(parse_var_u32(t));
        else if(c=='p') w_u32(parse_ptr_u32(t));
        else if(c=='i') w_i32((i32)std::stol(t, nullptr, 10));
        else if(c=='l') w_u32(parse_lbl_u32(t));
        else if(c=='s') w_u32(parse_sym_u32(t));
    }
    set_u16_le(blk, 0, op);
    set_u16_le(blk, 2, (u16)(blk.size() - 4));
    return blk;
}

static std::string parse_ins(const std::vector<u8>& buf, size_t start){
    u16 op = (u16)(rd_u32(buf, start) & 0xFFFFu);
    if(op==OP_CMD) return {};
    if(op==OP_RET) return "RET";
    auto itf = OP_FMT.find(op);
    if(itf==OP_FMT.end()) return "unk_" + hex8(op);
    const std::string& fmt = itf->second;
    size_t pos = start + 4;
    std::vector<std::string> args;
    for(char c: fmt){
        if(c=='v') args.push_back("@"+hex8(rd_u32(buf, pos)));
        else if(c=='p') args.push_back("*"+hex8(rd_u32(buf, pos)));
        else if(c=='i') args.push_back(std::to_string(rd_i32(buf, pos)));
        else if(c=='l') args.push_back("L"+std::to_string(rd_u32(buf, pos)));
        else if(c=='s') args.push_back("#"+hex8(rd_u32(buf, pos)));
        pos += 4;
    }
    auto itn = OP_NAME.find(op);
    std::string name = (itn==OP_NAME.end()) ? ("op_"+hex8(op)) : itn->second;
    if(args.empty()) return name;
    std::string out = name + " ";
    for(size_t i=0;i<args.size();i++){
        if(i) out += ", ";
        out += args[i];
    }
    return out;
}

static std::string parse_cmd(const std::vector<u8>& buf, size_t start, size_t end, u32 key,
                             const std::unordered_map<u32, std::string>& cmd_map){
    size_t pos = start + 4;
    u32 h = rd_u32(buf, pos); pos += 4;
    auto it = cmd_map.find(h);
    std::string name = to_lower_ascii(it!=cmd_map.end() ? it->second : ("0x"+hex8(h)));
    std::string cmd = name;

    std::vector<std::string> args;
    std::vector<std::string> lines;

    while(pos + 4 <= end){
        u32 t = rd_u32(buf, pos); pos += 4;
        if(t == P_END) break;
        if(t == P_INT){
            args.push_back(std::to_string(rd_i32(buf, pos)));
            pos += 4;
            continue;
        }
        if(t == P_FLOAT){
            float f = rd_f32(buf, pos);
            std::string s = std::to_string(f);
            while(!s.empty() && s.back()=='0') s.pop_back();
            if(!s.empty() && s.back()=='.') s.pop_back();
            s += "f";
            args.push_back(s);
            pos += 4;
            continue;
        }
        if(t == P_VAR){
            args.push_back("@"+hex8(rd_u32(buf, pos)));
            pos += 4;
            continue;
        }
        if(t == P_STR || t == P_WSTR){
            u32 n = rd_u32(buf, pos); pos += 4;
            size_t adv = (n + 3) & ~size_t(3);
            if(pos + adv > end) break;
            auto dec = dec_blob(buf, pos, n, key);
            pos += adv;

            std::string raw((const char*)dec.first.data(), dec.first.size());
            if(is_block_cmd(cmd)){
                lines.push_back(raw);
            }else if(is_noquote_cmd(cmd)){
                args.push_back(raw);
            }else{
                args.push_back("\"" + raw + "\"");
            }
            continue;
        }
        args.push_back("0x"+hex8(t));
        break;
    }

    if(is_block_cmd(cmd)){
        std::string head = cmd + "(";
        for(size_t i=0;i<args.size();i++){
            if(i) head += ", ";
            head += args[i];
        }
        std::string out = head + "\n";
        for(const auto& ln: lines) out += ln + "\n";
        out += cmd + ")";
        return out;
    }else{
        std::string out = cmd + "(";
        for(size_t i=0;i<args.size();i++){
            if(i) out += ", ";
            out += args[i];
        }
        out += ")";
        return out;
    }
}

static std::vector<u8> decode_isb_slices(const std::filesystem::path& isb,
                                        const std::vector<std::tuple<std::string, u32, u32>>& slices,
                                        const std::unordered_map<u32, std::string>& cmd_map){
    auto buf = read_file(isb);
    TableInfo ti;
    if(!read_table(buf, ti)) return {};
    std::string out;

    for(const auto& s: slices){
        const std::string& hid = std::get<0>(s);
        u32 entry = std::get<1>(s);
        u32 end_excl = std::get<2>(s);
        if(entry >= ti.blocks) continue;
        if(entry == 0) continue;
        u32 key_head = entry - 1;

        size_t ks = ti.addrs[key_head];
        size_t ke = (key_head + 1 < ti.blocks) ? ti.addrs[key_head + 1] : ti.tbl_start;
        if(ke > ti.tbl_start) ke = ti.tbl_start;
        if(ks + 8 > ke) continue;

        u32 key = rd_u32(buf, ks);
        u32 msgs = rd_u32(buf, ks + 4);

        out += hid + ":" + hex8(key) + ":" + std::to_string(msgs) + " {\n";
        u32 stop = std::min<u32>(end_excl, ti.blocks);
        for(u32 b = entry; b < stop; b++){
            size_t st = ti.addrs[b];
            size_t en = (b + 1 < ti.blocks) ? ti.addrs[b + 1] : ti.tbl_start;
            if(en > ti.tbl_start) en = ti.tbl_start;
            if(en <= st) continue;
            u16 op = (u16)(rd_u32(buf, st) & 0xFFFFu);
            if(op == OP_CMD){
                out += parse_cmd(buf, st, en, key, cmd_map) + "\n";
            }else{
                auto ln = parse_ins(buf, st);
                if(!ln.empty()) out += ln + "\n";
            }
        }
        out += "}\n\n";
    }

    if(!out.empty()){
        while(!out.empty() && (out.back()=='\n' || out.back()=='\r')) out.pop_back();
        out.push_back('\n');
    }
    return std::vector<u8>(out.begin(), out.end());
}

struct IdTbl{
    std::vector<std::string> lines;
    std::unordered_map<std::string, std::string> files;
    std::unordered_map<std::string, std::string> offs;
};

static IdTbl read_id_tbl(const std::filesystem::path& p){
    auto b = read_file(p);
    std::string txt((const char*)b.data(), b.size());

    IdTbl t;
    t.lines = {};
    t.files.clear();
    t.offs.clear();

    std::string cur;
    size_t i=0;
    while(i<txt.size()){
        size_t j = txt.find('\n', i);
        if(j==std::string::npos) j = txt.size();
        std::string ln = txt.substr(i, j-i);
        if(!ln.empty() && ln.back()=='\r') ln.pop_back();
        t.lines.push_back(ln + "\n");

        auto tr = trim_copy(ln);
        if(tr.size()>=2 && tr.front()=='[' && tr.back()==']'){
            cur = to_upper_ascii(trim_copy(tr.substr(1, tr.size()-2)));
        }else{
            auto s = tr;
            if(!s.empty() && s[0]=='#'){
                auto eq = s.find('=');
                if(eq!=std::string::npos){
                    std::string k = trim_copy(s.substr(1, eq-1));
                    std::string v = trim_copy(s.substr(eq+1));
                    if(k.size()>=2 && k[0]=='0' && (k[1]=='x' || k[1]=='X')) k = k.substr(2);
                    k = to_upper_ascii(k);
                    if(cur=="FILE") t.files[k]=v;
                    if(cur=="OFFSET") t.offs[k]=v;
                }
            }
        }
        i = (j<txt.size()? j+1 : j);
    }
    return t;
}

static u32 base36_parse(const std::string& s){
    std::string t = to_lower_ascii(trim_copy(s));
    if(t.empty()) throw std::runtime_error("bad base36");
    u32 v=0;
    for(char c: t){
        int d=-1;
        if(c>='0'&&c<='9') d=c-'0';
        else if(c>='a'&&c<='z') d=c-'a'+10;
        else throw std::runtime_error("bad base36 char");
        v = v*36u + (u32)d;
    }
    return v;
}
static std::string base36_fmt(u32 n){
    static const char* d="0123456789abcdefghijklmnopqrstuvwxyz";
    if(n==0) return "0";
    std::string out;
    while(n){
        u32 r = n%36u;
        out.push_back(d[r]);
        n/=36u;
    }
    std::reverse(out.begin(), out.end());
    return out;
}

static void write_id_tbl(const std::filesystem::path& dst,
                         const IdTbl& src,
                         const std::unordered_map<std::string, u32>& new_off){
    std::string cur;
    std::string out;
    out.reserve(1<<20);

    for(const auto& ln0: src.lines){
        std::string ln = ln0;
        std::string raw = ln;
        if(!raw.empty() && raw.back()=='\n') raw.pop_back();
        if(!raw.empty() && raw.back()=='\r') raw.pop_back();
        auto tr = trim_copy(raw);

        if(tr.size()>=2 && tr.front()=='[' && tr.back()==']'){
            cur = to_upper_ascii(trim_copy(tr.substr(1, tr.size()-2)));
            out += ln;
            continue;
        }

        if(cur=="OFFSET"){
            auto s = tr;
            if(!s.empty() && s[0]=='#'){
                auto eq = s.find('=');
                if(eq!=std::string::npos){
                    std::string k = trim_copy(s.substr(1, eq-1));
                    std::string tail = raw.substr(eq+1);
                    (void)tail;
                    if(k.size()>=2 && k[0]=='0' && (k[1]=='x' || k[1]=='X')) k = k.substr(2);
                    k = to_upper_ascii(k);
                    auto it = new_off.find(k);
                    if(it != new_off.end()){
                        out += "#" + k + "=" + base36_fmt(it->second) + "\n";
                        continue;
                    }
                }
            }
        }
        out += ln;
    }

    std::vector<u8> b(out.begin(), out.end());
    write_file(dst, b);
}

static void decode_dir(const std::filesystem::path& in_dir, const std::filesystem::path& out_dir,
                       const std::filesystem::path& base){
    std::filesystem::create_directories(out_dir);
    auto cmd_map = load_cmd_map(base);

    auto tbl_path = out_dir / "id.tbl";
    auto tbl = read_id_tbl(tbl_path);

    std::unordered_map<std::string, std::vector<std::pair<std::string, u32>>> by_file;
    for(const auto& kv: tbl.files){
        const std::string& hid = kv.first;
        const std::string& fname = kv.second;
        auto it = tbl.offs.find(hid);
        if(it==tbl.offs.end()) continue;
        auto v = trim_copy(it->second);
        if(v.empty()) continue;
        u32 e = base36_parse(v);
        by_file[fname].push_back({hid, e});
    }

    for(auto& kv: by_file){
        const std::string& fname = kv.first;
        auto ents = kv.second;
        std::sort(ents.begin(), ents.end(), [](auto& a, auto& b){ return a.second < b.second; });

        std::vector<std::tuple<std::string, u32, u32>> slices;
        for(size_t j=0;j<ents.size();j++){
            u32 e = ents[j].second;
            u32 next_e = (j+1<ents.size()) ? ents[j+1].second : 1000000000u;
            u32 end_excl = std::max<u32>(e, next_e - 1);
            slices.push_back({ents[j].first, e, end_excl});
        }

        auto isb = in_dir / fname;
        if(!std::filesystem::exists(isb)) continue;
        auto stem = std::filesystem::path(fname).stem().string();
        auto scn = out_dir / (stem + ".scn");
        auto outb = decode_isb_slices(isb, slices, cmd_map);
        write_file(scn, outb);
    }
}

static std::vector<u8> pack_cmd_hash(u32 cmd_hash, const std::vector<std::string>& args, u32 key, const std::string& cmd_name){
    bool use_ell = is_ellipsis_cmd(cmd_name);
    std::vector<u8> blk(4, 0);
    wr_u32(blk, cmd_hash);

    auto add_blob = [&](u32 ptype, const std::vector<u8>& raw, bool ell){
        wr_u32(blk, ptype);
        wr_u32(blk, (u32)raw.size());
        auto enc = enc_blob(raw, key, ell);
        blk.insert(blk.end(), enc.begin(), enc.end());
    };

    for(auto tok0: args){
        std::string tok = tok0;
        if(tok.empty()){
            if(is_noquote_cmd(cmd_name)){
                add_blob(P_STR, {}, false);
            }
            continue;
        }
        if(tok[0]=='@'){
            wr_u32(blk, P_VAR);
            wr_u32(blk, parse_var_u32(tok));
            continue;
        }
        if(tok.size()>=2 && tok.back()=='f'){
            auto num = tok.substr(0, tok.size()-1);
            char* endp=nullptr;
            float fv = std::strtof(num.c_str(), &endp);
            if(endp && *endp=='\0'){
                u32 bits;
                std::memcpy(&bits, &fv, 4);
                wr_u32(blk, P_FLOAT);
                wr_u32(blk, bits);
                continue;
            }
        }
        {
            char* endp=nullptr;
            long v = std::strtol(tok.c_str(), &endp, 10);
            if(endp && *endp=='\0'){
                wr_u32(blk, P_INT);
                wr_u32(blk, (u32)(i32)v);
                continue;
            }
        }
        if(tok.size()>=2 && tok.front()=='"' && tok.back()=='"'){
            std::string inner = tok.substr(1, tok.size()-2);
            std::vector<u8> raw(inner.begin(), inner.end());
            add_blob(P_STR, raw, use_ell);
            continue;
        }
        if(tok.size()>=3 && (tok[0]=='L' || tok[0]=='l') && tok[1]=='"' && tok.back()=='"'){
            std::string inner = tok.substr(2, tok.size()-3);
            std::vector<u8> raw(inner.begin(), inner.end());
            add_blob(P_STR, raw, use_ell);
            continue;
        }
        if(is_noquote_cmd(cmd_name)){
            std::vector<u8> raw(tok.begin(), tok.end());
            add_blob(P_STR, raw, false);
            continue;
        }
        std::vector<u8> raw(tok.begin(), tok.end());
        add_blob(P_STR, raw, use_ell);
    }

    wr_u32(blk, P_END);
    set_u16_le(blk, 0, OP_CMD);
    set_u16_le(blk, 2, (u16)(blk.size() - 8));
    return blk;
}

static bool parse_scn_head(const std::string& line, std::string& hid, u32& key, u32& msgs){
    auto s = trim_copy(line);
    if(s.empty()) return false;
    auto p1 = s.find(':');
    if(p1==std::string::npos) return false;
    auto p2 = s.find(':', p1+1);
    if(p2==std::string::npos) return false;
    auto p3 = s.find('{', p2+1);
    if(p3==std::string::npos) return false;

    hid = trim_copy(s.substr(0, p1));
    std::string key_s = trim_copy(s.substr(p1+1, p2-(p1+1)));
    std::string msgs_s = trim_copy(s.substr(p2+1, p3-(p2+1)));

    if(hid.empty() || key_s.size()!=8) return false;
    key = parse_hex_u32(key_s);
    msgs = (u32)std::stoul(msgs_s, nullptr, 10);
    hid = to_upper_ascii(hid);
    return true;
}

static bool parse_block_open(const std::string& line, std::string& cmd, std::string& arg_text){
    auto s = trim_copy(line);
    auto p = s.find('(');
    if(p==std::string::npos) return false;
    cmd = to_lower_ascii(trim_copy(s.substr(0, p)));
    if(!is_block_cmd(cmd)) return false;
    arg_text = s.substr(p+1);
    return true;
}
static bool parse_block_close(const std::string& line, const std::string& cmd){
    auto s = to_lower_ascii(trim_copy(line));
    return s == (cmd + ")");
}
static bool parse_call_hash(const std::string& line, u32& h, std::string& arg_text){
    auto s = trim_copy(line);
    if(s.size() < 3 || s[0] != '0' || (s[1] != 'x' && s[1] != 'X')) return false;
    auto p = s.find('(');
    auto q = s.rfind(')');
    if(p==std::string::npos || q==std::string::npos || q<p) return false;
    h = parse_hex_u32(s.substr(2, p-2));
    arg_text = s.substr(p+1, q-(p+1));
    return true;
}
static bool parse_call_named(const std::string& line, std::string& cmd, std::string& arg_text){
    auto s = trim_copy(line);
    auto p = s.find('(');
    auto q = s.rfind(')');
    if(p==std::string::npos || q==std::string::npos || q<p) return false;
    cmd = to_lower_ascii(trim_copy(s.substr(0, p)));
    if(cmd.empty()) return false;
    auto c0 = (unsigned char)cmd[0];
    if(!((c0>='a'&&c0<='z') || (c0>='A'&&c0<='Z') || c0=='_')) return false;
    for(char c: cmd){
        unsigned char uc = (unsigned char)c;
        if(!((uc>='a'&&uc<='z') || (uc>='A'&&uc<='Z') || (uc>='0'&&uc<='9') || uc=='_')) return false;
    }
    arg_text = s.substr(p+1, q-(p+1));
    return true;
}

static std::pair<std::vector<u8>, std::unordered_map<std::string, u32>>
pack_scn_to_isb(const std::filesystem::path& scn_path, const std::unordered_set<std::string>& allowed_ids){
    auto bytes = read_file(scn_path);
    auto lines = split_lines_bytes(bytes);

    std::vector<u8> out;
    std::vector<u32> addrs;
    std::unordered_map<std::string, u32> new_off;

    u32 cur_key=0;
    bool in_sc=false;

    for(size_t i=0;i<lines.size();){
        std::string raw = lines[i++];
        auto s = trim_copy(raw);
        if(s.empty()) continue;

        std::string hid;
        u32 key=0, msgs=0;
        if(parse_scn_head(s, hid, key, msgs)){
            cur_key = key;
            if(allowed_ids.find(hid) != allowed_ids.end()){
                new_off[hid] = (u32)addrs.size() + 1;
            }
            addrs.push_back((u32)out.size());
            wr_u32(out, cur_key);
            wr_u32(out, msgs);
            in_sc = true;
            continue;
        }

        if(s == "}"){ in_sc=false; continue; }
        if(!in_sc) continue;

        std::string bcmd, barg;
        if(parse_block_open(raw, bcmd, barg)){
            bool keep_empty = is_noquote_cmd(bcmd) && barg.find(',') != std::string::npos;
            auto head_args = split_csv_quoted(barg, keep_empty);
            std::vector<std::string> body;
            while(i < lines.size()){
                std::string ln = lines[i++];
                if(parse_block_close(ln, bcmd)) break;
                body.push_back("\"" + ln + "\"");
            }
            std::vector<std::string> args = head_args;
            args.insert(args.end(), body.begin(), body.end());
            addrs.push_back((u32)out.size());
            auto blk = pack_cmd_hash(make_str_id_cp932_like(bcmd), args, cur_key, bcmd);
            out.insert(out.end(), blk.begin(), blk.end());
            continue;
        }

        u32 hh=0;
        std::string arg_text;
        if(parse_call_hash(raw, hh, arg_text)){
            auto args = split_csv_quoted(arg_text, false);
            addrs.push_back((u32)out.size());
            auto blk = pack_cmd_hash(hh, args, cur_key, "");
            out.insert(out.end(), blk.begin(), blk.end());
            continue;
        }

        std::string cmd;
        if(parse_call_named(raw, cmd, arg_text)){
            bool keep_empty = is_noquote_cmd(cmd) && arg_text.find(',') != std::string::npos;
            auto args = split_csv_quoted(arg_text, keep_empty);
            addrs.push_back((u32)out.size());
            auto blk = pack_cmd_hash(make_str_id_cp932_like(cmd), args, cur_key, cmd);
            out.insert(out.end(), blk.begin(), blk.end());
            continue;
        }

        addrs.push_back((u32)out.size());
        auto blk = pack_ins_line(raw);
        out.insert(out.end(), blk.begin(), blk.end());
    }

    for(u32 a: addrs) wr_u32(out, a);
    wr_u32(out, (u32)addrs.size());
    return {out, new_off};
}

static void pack_dir(const std::filesystem::path& in_dir, const std::filesystem::path& out_dir){
    std::filesystem::create_directories(out_dir);
    auto tbl_path = in_dir / "id.tbl";
    auto tbl = read_id_tbl(tbl_path);

    std::unordered_set<std::string> allowed_ids;
    for(const auto& kv: tbl.files) allowed_ids.insert(kv.first);

    std::unordered_map<std::string, std::filesystem::path> file_to_scn;
    for(const auto& kv: tbl.files){
        const std::string& fname = kv.second;
        if(file_to_scn.find(fname) == file_to_scn.end()){
            auto stem = std::filesystem::path(fname).stem().string();
            file_to_scn[fname] = in_dir / (stem + ".scn");
        }
    }

    std::unordered_map<std::string, u32> new_off_all;

    for(const auto& kv: file_to_scn){
        const std::string& fname = kv.first;
        const auto& scn = kv.second;
        if(!std::filesystem::exists(scn)) continue;
        auto packed = pack_scn_to_isb(scn, allowed_ids);
        write_file(out_dir / fname, packed.first);
        for(const auto& it: packed.second) new_off_all[it.first] = it.second;
    }

    write_id_tbl(out_dir / "id.tbl", tbl, new_off_all);
}

// ===== IDXC (.tbl/.idx) helpers =====

struct IdxcEntry { u32 hash=0, name_ptr=0, start=0, end=0; };
struct IdxcTriple { u32 k=0; i32 key_ptr=0; i32 val_ptr=0; };
struct IdxcFile {
    std::vector<IdxcEntry> entries;
    std::vector<IdxcTriple> triples;
    std::vector<u8> pool;
};

static inline bool has_ext_tbl_idx(const std::filesystem::path& p){
    auto e = to_lower_ascii(p.extension().string());
    return e == ".tbl" || e == ".idx";
}

static inline bool is_idxc_bytes(const std::vector<u8>& b){
    return b.size() >= 8 && std::memcmp(b.data(), "IDXC", 4) == 0;
}

// 纯 bytes 的 C 字符串：ptr 是 pool 内 byte offset；-1 表示无
static std::string pool_cstr(const std::vector<u8>& pool, i32 ptr){
    if(ptr < 0) return {};
    size_t off = (size_t)ptr;
    if(off >= pool.size()) return {};
    size_t end = off;
    while(end < pool.size() && pool[end] != 0) end++;
    return std::string((const char*)pool.data() + off, end - off);
}

static IdxcFile parse_idxc(const std::vector<u8>& data){
    if(data.size() < 8) throw std::runtime_error("IDXC truncated");
    if(std::memcmp(data.data(), "IDXC", 4) != 0) throw std::runtime_error("bad IDXC magic");

    size_t off = 8;
    u32 n_entries = rd_u32(data, 4);
    if(off + (size_t)n_entries * 16 > data.size()) throw std::runtime_error("IDXC entries truncated");

    IdxcFile x;
    x.entries.resize(n_entries);
    for(u32 i=0;i<n_entries;i++){
        size_t o = off + (size_t)i * 16;
        x.entries[i].hash     = rd_u32(data, o + 0);
        x.entries[i].name_ptr = rd_u32(data, o + 4);
        x.entries[i].start    = rd_u32(data, o + 8);
        x.entries[i].end      = rd_u32(data, o + 12);
    }
    off += (size_t)n_entries * 16;

    if(off + 4 > data.size()) throw std::runtime_error("IDXC no triple count");
    u32 n_triples = rd_u32(data, off); off += 4;
    if(off + (size_t)n_triples * 12 > data.size()) throw std::runtime_error("IDXC triples truncated");

    x.triples.resize(n_triples);
    for(u32 i=0;i<n_triples;i++){
        size_t o = off + (size_t)i * 12;
        x.triples[i].k       = rd_u32(data, o + 0);
        x.triples[i].key_ptr = rd_i32(data, o + 4);
        x.triples[i].val_ptr = rd_i32(data, o + 8);
    }
    off += (size_t)n_triples * 12;

    if(off + 4 > data.size()) throw std::runtime_error("IDXC no pool len");
    u32 pool_len = rd_u32(data, off); off += 4;
    if(off + (size_t)pool_len > data.size()) throw std::runtime_error("IDXC pool truncated");

    x.pool.assign(data.begin() + off, data.begin() + off + pool_len);
    return x;
}

static bool is_text_like_tbl(const std::vector<u8>& data){
    if(data.empty()) return false;
    // 很简单的判定：前 2KB 内不应有 0，并且包含 [ 和 =
    size_t n = std::min<size_t>(data.size(), 2048);
    for(size_t i=0;i<n;i++){
        if(data[i] == 0) return false;
    }
    auto s = std::string((const char*)data.data(), n);
    return s.find('[') != std::string::npos && s.find('=') != std::string::npos;
}

static std::string strip_comment_and_trim(const std::string& raw){
    std::string s = raw;
    auto p1 = s.find("//");
    auto p2 = s.find(';');
    size_t cut = std::string::npos;
    if(p1 != std::string::npos) cut = p1;
    if(p2 != std::string::npos) cut = (cut == std::string::npos) ? p2 : std::min(cut, p2);
    if(cut != std::string::npos) s = s.substr(0, cut);
    return trim_copy(s);
}

static u32 parse_hex_u32_maybe0x(std::string s){
    s = trim_copy(s);
    if(s.size() >= 2 && s[0]=='0' && (s[1]=='x' || s[1]=='X')) s = s.substr(2);
    if(s.empty()) throw std::runtime_error("bad hex");
    u32 v = 0;
    for(char c: s){
        int d=-1;
        if(c>='0'&&c<='9') d=c-'0';
        else if(c>='a'&&c<='f') d=c-'a'+10;
        else if(c>='A'&&c<='F') d=c-'A'+10;
        else throw std::runtime_error("bad hex char");
        v = (v<<4) | (u32)d;
    }
    return v;
}

static std::string hex_upper(u32 v){
    static const char* h = "0123456789ABCDEF";
    std::string s;
    do{
        s.push_back(h[v & 0xF]);
        v >>= 4;
    }while(v);
    std::reverse(s.begin(), s.end());
    return s;
}

struct TblSectionItem {
    bool is_num=false;
    u32 num=0;
    std::string key;   // alpha key
    std::string val;
};
struct TblSection {
    std::string name;
    std::vector<TblSectionItem> items; // 保持文本出现顺序（不排序）
};

struct StringPoolBuilder {
    std::vector<u8> buf;
    std::unordered_map<std::string, u32> cache;

    StringPoolBuilder(){
        cache.emplace(std::string(), 0);
        buf.push_back(0);
    }
    u32 add(const std::string& s){
        auto it = cache.find(s);
        if(it != cache.end()) return it->second;
        u32 ptr = (u32)buf.size();
        buf.insert(buf.end(), s.begin(), s.end());
        buf.push_back(0);
        cache.emplace(s, ptr);
        return ptr;
    }
};

static std::string idxc_to_text(const IdxcFile& x){
    std::string out;
    for(size_t si=0; si<x.entries.size(); si++){
        const auto& e = x.entries[si];
        std::string sec = pool_cstr(x.pool, (i32)e.name_ptr);
        sec = trim_copy(sec);
        if(sec.empty()){
            // 兜底
            sec = "SECTION_" + std::to_string(si);
        }
        out += "[" + sec + "]\n";

        // triples 区间
        u32 st = e.start;
        u32 en = e.end;
        if(st > en || en > x.triples.size()) { out += "\n"; continue; }

        for(u32 i=st; i<en; i++){
            const auto& t = x.triples[i];
            std::string v = pool_cstr(x.pool, t.val_ptr);
            if(t.key_ptr != -1){
                std::string k = pool_cstr(x.pool, t.key_ptr);
                k = trim_copy(k);
                out += k + "=" + v + "\n";
            }else{
                // 数字 key 默认 16进制，不加 0x
                out += "#" + hex_upper(t.k) + "=" + v + "\n";
            }
        }
        out += "\n";
    }
    return out;
}

static std::vector<u8> text_to_idxc(const std::string& text){
    // 解析文本
    std::vector<TblSection> secs;
    TblSection cur;
    bool has_cur=false;

    auto flush = [&](){
        if(has_cur){
            secs.push_back(cur);
            cur = TblSection{};
            has_cur=false;
        }
    };

    size_t i=0;
    while(i < text.size()){
        size_t j = text.find('\n', i);
        if(j == std::string::npos) j = text.size();
        std::string raw = text.substr(i, j-i);
        if(!raw.empty() && raw.back()=='\r') raw.pop_back();
        i = (j<text.size()? j+1 : j);

        std::string line = strip_comment_and_trim(raw);
        if(line.empty()) continue;

        if(line.size()>=2 && line.front()=='[' && line.back()==']'){
            flush();
            cur.name = trim_copy(line.substr(1, line.size()-2));
            cur.items.clear();
            has_cur=true;
            continue;
        }

        if(!has_cur) continue;
        auto eq = line.find('=');
        if(eq == std::string::npos) continue;

        std::string k = trim_copy(line.substr(0, eq));
        std::string v = trim_copy(line.substr(eq+1));

        TblSectionItem it;
        it.val = v;

        if(!k.empty() && k[0]=='#'){
            it.is_num=true;
            it.num = parse_hex_u32_maybe0x(k.substr(1));
        }else{
            it.is_num=false;
            it.key = k;
        }
        cur.items.push_back(std::move(it));
    }
    flush();

    // 构建二进制
    StringPoolBuilder pool;
    std::vector<IdxcEntry> entries;
    std::vector<IdxcTriple> triples;

    entries.reserve(secs.size());

    for(const auto& sec: secs){
        u32 start = (u32)triples.size();

        // 不排序：按文本出现顺序写
        for(const auto& it: sec.items){
            if(it.is_num){
                IdxcTriple t;
                t.k = it.num;
                t.key_ptr = -1;
                t.val_ptr = (i32)pool.add(it.val);
                triples.push_back(t);
            }else{
                IdxcTriple t;
                t.k = make_str_id_bytes(it.key);            // 复用你现有算法
                t.key_ptr = (i32)pool.add(it.key);
                t.val_ptr = (i32)pool.add(it.val);
                triples.push_back(t);
            }
        }

        IdxcEntry e;
        e.hash = make_str_id_bytes(sec.name);             // 复用你现有算法
        e.name_ptr = pool.add(sec.name);
        e.start = start;
        e.end = (u32)triples.size();
        entries.push_back(e);
    }

    // 写出
    std::vector<u8> out;
    out.insert(out.end(), {'I','D','X','C'});
    wr_u32(out, (u32)entries.size());
    for(const auto& e: entries){
        wr_u32(out, e.hash);
        wr_u32(out, e.name_ptr);
        wr_u32(out, e.start);
        wr_u32(out, e.end);
    }
    wr_u32(out, (u32)triples.size());
    for(const auto& t: triples){
        wr_u32(out, t.k);
        // 写 i32 little endian
        u32 u;
        std::memcpy(&u, &t.key_ptr, 4); wr_u32(out, u);
        std::memcpy(&u, &t.val_ptr, 4); wr_u32(out, u);
    }
    wr_u32(out, (u32)pool.buf.size());
    out.insert(out.end(), pool.buf.begin(), pool.buf.end());
    return out;
}

// 把 in_dir 内的 .tbl/.idx（若是 IDXC）转文本写到 out_dir
static void decode_tbl_dir(const std::filesystem::path& in_dir, const std::filesystem::path& out_dir){
    for(auto it = std::filesystem::recursive_directory_iterator(in_dir);
        it != std::filesystem::recursive_directory_iterator(); ++it)
    {
        if(!it->is_regular_file()) continue;
        auto p = it->path();
        if(!has_ext_tbl_idx(p)) continue;

        auto data = read_file(p);
        if(!is_idxc_bytes(data)) continue;

        auto obj = parse_idxc(data);
        auto txt = idxc_to_text(obj);

        auto rel = std::filesystem::relative(p, in_dir);
        auto dst = out_dir / rel;
        std::filesystem::create_directories(dst.parent_path());

        std::vector<u8> b(txt.begin(), txt.end());
        write_file(dst, b);
    }
}

// 把 in_dir 内的 .tbl/.idx（若是文本）转 IDXC 二进制写到 out_dir
static void encode_tbl_dir(const std::filesystem::path& in_dir, const std::filesystem::path& out_dir){
    for(auto it = std::filesystem::recursive_directory_iterator(in_dir);
        it != std::filesystem::recursive_directory_iterator(); ++it)
    {
        if(!it->is_regular_file()) continue;
        auto p = it->path();
        if(!has_ext_tbl_idx(p)) continue;

        auto data = read_file(p);
        if(!is_text_like_tbl(data)) continue;

        std::string txt((const char*)data.data(), data.size());
        auto bin = text_to_idxc(txt);

        auto rel = std::filesystem::relative(p, in_dir);
        auto dst = out_dir / rel;
        std::filesystem::create_directories(dst.parent_path());
        write_file(dst, bin);
    }
}

int main(int argc, char** argv){
    auto print_usage = [&](){
        // Keep it simple and English
        std::cerr
            << "Usage:\n"
            << "  tool d <in_dir> <out_dir>   Decode: IDXC(.tbl/.idx)->text, then ISB->SCN\n"
            << "  tool e <in_dir> <out_dir>   Encode: SCN->ISB, then text(.tbl/.idx)->IDXC\n"
            << "\n"
            << "Notes:\n"
            << "  - 'd' writes decoded .scn files and converts .tbl/.idx (IDXC) into text.\n"
            << "  - 'e' packs .scn back into .isb and converts text .tbl/.idx back into IDXC.\n";
    };

    if(argc != 4){
        print_usage();
        return 2;
    }

    std::string cmd = argv[1];
    auto in_dir  = std::filesystem::path(argv[2]);
    auto out_dir = std::filesystem::path(argv[3]);

    std::filesystem::path base = std::filesystem::path(argv[0]).parent_path();
    if(base.empty()) base = std::filesystem::current_path();

    try{
        if(cmd == "d"){
            // 1) IDXC (.tbl/.idx) -> text
            decode_tbl_dir(in_dir, out_dir);
            // 2) ISB -> SCN
            decode_dir(in_dir, out_dir, base);
        }else if(cmd == "e"){
            // 1) SCN -> ISB
            pack_dir(in_dir, out_dir);
            // 2) text (.tbl/.idx) -> IDXC
            encode_tbl_dir(in_dir, out_dir);
        }else{
            print_usage();
            return 2;
        }
    }catch(...){
        return 1;
    }

    return 0;
}