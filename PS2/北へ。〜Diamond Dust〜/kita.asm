; ============================================================================
; kita.asm — 剧情文本渲染补丁合集（北へ。〜Diamond Dust〜 SLPM-654.04）
;   ① 半角支持（分派重写）  ② 半角渲染洞（CameraMatrix 尸体）
;   ③ 全局打字速度 TEXT_SPEED  ④ 翻页等待点击（R 溢出/P 清屏 hook）
;
; 原理（IDA 验证，详见 plans/04-font-hankaku.md）：
;   剧情渲染任务 s_strput24w_task（0x11E0D0）的字节分派只对双字节引导
;   （0x80..0x9F / ≥0xE0）渲染并推进指针；ASCII（<0x80）与半角假名
;   （0xA0..0xDF）两条分支只做每帧配额计数，既不渲染也不推进 → 对话卡死。
;   菜单版 s_strput24 的半角配方是现成的：s_font_expand_2(code, buf, 1)。
;
; 改动（四节，均不触碰任何在用函数的语义）：
;   ① 0x11E6DC..0x11E714（15 条）分派重写——半角两分支直接 bne/beq 分支到
;      代码洞（距离 113KB，在 ±128KB 分支范围内，无需 lui/jr 中转）；
;      双字节路径原语义重建（含 0x818F 全角空格特判）。
;   ② 代码洞 = sceVu0CameraMatrix @ 0x102A28（Sony SDK 死函数，全零引用）
;      ——先前的方案放在 0x400000 零区，但那片是零初始化全局变量区
;      （有 1054 处引用，zyusin_ani 等），会互相践踏，已废弃。
;   ④ 代码洞2 = sceVu0NormalLightMatrix 尸体 @ 0x102AE0 起（三通道零引用；
;      上方 8 字节让给 ② 的 184 字节尾巴）。
;
; ⚠ 字节序（2026-09-21 定论，曾搞反过一次）：本作 PS2 ELF 是【小端】
;   （EE 默认小端；原版文件字节按小端读才是合法 MIPS——例：0x11DF9C
;   字节 40 00 05 24 = addiu a1,zero,64）。armips 的 .ps2 正确，勿改
;   .n64（大端，会把指令整字写反）。验证脚本必须用 struct "<I" 小端解码。
;   另一陷阱：IDA 反汇编注释里的 "dword_A-B" 是差值显示（A-B 才是目标地址），
;   抄 jal 目标必须交叉验证两个调用点。
;
; 用法（在本目录执行，armips.exe 就在项目根）：
;   armips kita.asm
;   → 产出 kita\SLPM_654.04（已打补丁，替换回 ISO 的 SLPM_654.04 即可）
;   调试（可选）：armips kita.asm -sym2 kita.sym
;   → HK_CAVE / CHK81 等标签进符号表，PCSX2 / NO$PSX 里可直接断点
;   （armips 无 .globl 指令——那是 GAS 语法；不带 @@ 的标签默认全局，
;     -sym2 即导出）
; ============================================================================

.ps2

; 段基：文件偏移 0x80 ↔ vaddr 0x100000 → headersize = 0xFFF80（从程序头算，勿猜）
.open "font\SLPM_65", "font\SLPM_654", 0xFFF80

; ---- 打字机速度（全角/半角统一，改完重新 armips 即可）----
; 模型：计时器每帧 -16。汉字（码≥0x88）等待 ×2 → 每字 speed/8 帧；
; 假名/半角 ×1 → speed/16 帧。中文全汉字，右列为实际体感（60fps）：
;   64 = 原版 ≈7.5字/秒        32 ≈15字/秒（当前，偏慢）
;   24 ≈20字/秒                20 ≈24字/秒
;   16 ≈30字/秒（推荐"一口气"） 12 ≈40字/秒（快）
;    8 = 60字/秒（每帧1字）     4 = 120字/秒（每帧2字）    1 = 瞬出（特殊分支）
; 标点（、。！？等）另乘 ×2/×4/×8，节奏感保留。{S###} 逐行覆盖仍可用。
TEXT_SPEED equ 30

; ---------------- ① 分派改写（s_strput24w_task 内） ----------------
; 入口条件与原版一致：a1 = 当前字节（<0xE0；≥0xE0 已在上游 0x11E6D4 跳出），
; s2 = 字符串指针，控制码（<0x20 与 '{'）已在上游处理。
.org 0x11E6DC
    slti  at, a1, 0x80          ; ASCII（0x20..0x7F）？
    bne   at, zero, HK_CAVE     ; → 代码洞（113KB 内，直接分支）
    nop
    slti  at, a1, 0xA0          ; 0x80..0x9F = 双字节引导？
    beq   at, zero, HK_CAVE     ; 否（0xA0..0xDF 半角假名）→ 同一洞
    nop
    nop                         ; （释放出的原跳转构造位，填 nop）
    nop
    nop                         ; ≥0xE0 路径（0x11E6D4 跳入）的落点
CHK81:                          ; —— 重建原版 0x81/0x8F 检查 ——
    addiu v1, zero, 0x81
    bne   a1, v1, 0x11E718      ; 非 0x81 → 原双字节渲染
    nop
    lbu   a0, 1(s2)             ; 0x81xx：查次字节
    addiu v1, zero, 0x8F
    beq   a0, v1, 0x11E788      ; 0x818F 全角空格 → 原跳过路径
    ; 注意：不写延迟槽——beq 的延迟落在 0x11E718，保留原版 lw v0,-0x7ccc(gp)
    ; （s_mode 载入，双字节主路径必需；对 0x818F 路径无副作用）

; ---------------- ② 半角渲染代码洞（sceVu0CameraMatrix 尸体） ----------------
; 输入：a1 = 半角码，s0 = x 累积（步进单位 = 半像素），s1 = y 行，
;       s2 = 字符串指针，s4 = palabuf 项，s5 = 每帧配额计数。
; 寄存器纪律：只写 at/v0/v1/a0-a3/t0/t1（调用者保存）与 s0/s2/s5 的
; 业务递进；s 寄存器其余只读；ra 存 v69 空闲尾（半角字形输出恰止于 sp+0x1B0）。
.org 0x102A28
HK_CAVE:
    sw    ra, 0x1B0(sp)         ; 保护任务体返回地址（内部 jal 会毁 ra）
    sra   v0, s0, 1             ; x = 累积/2（负数向下取整与原版一致）
    bgez  s0, @@xy
    nop
    addiu v0, s0, 1
    sra   v0, v0, 1
@@xy:
    lw    a0, 0x20(s4)          ; 基准 x
    addiu a3, zero, 0x18        ; 高 24
    addu  a0, v0, a0
    sh    a0, 0x1B8(sp)         ; quad.x
    lh    a0, 0x24(s4)          ; 基准 y
    addu  a0, s1, a0
    sh    a0, 0x1BA(sp)         ; quad.y
    sh    a3, 0x1BE(sp)         ; quad.h
    or    a0, a1, zero          ; 半角码原样传（search 自己减 0x20/0x40）
    addiu a1, sp, 0x90          ; v69 字形缓冲
    addiu a2, zero, 1           ; sheet=1 → 半角表（0x192B30，12×24 2bpp）
    jal   0x11ECA0              ; s_font_expand_2 —— 与菜单版 s_strput24 半角路径逐字相同
    nop
    addiu t0, zero, 3
    sh    t0, 0x1BC(sp)         ; quad.w = 3（半宽；全角为 6）
    addiu a1, sp, 0x90
    addiu a0, sp, 0x1B8
    jal   0x11D3E0              ; s_str_load（上传字形）
    addiu s0, s0, 6             ; delay: x 累积 += 6（半宽步进；全角为 12）
    lw    t0, 0x2C(s4)          ; 每字延时基值（palabuf[11]）
    lui   at, 0x36
    addiu t1, zero, 1
    sw    t0, -0x5018(at)       ; s_str_syncflg[0]
    sw    t1, -0x5014(at)       ; [1] = 1
    sw    t1, -0x5010(at)       ; [2] = 1
    ; —— 以下逐条照抄全角路径收尾（0x11EA08..0x11EA3C），保证半角节奏=假名 ——
    lw    t0, 0x2C(s4)          ; speed
    addiu t1, zero, 1
    bne   t0, t1, @@reload      ; speed != 1 → 正常重载
    nop
    sw    zero, -0x5018(at)     ; speed == 1 → 瞬出：sync 全清（0x11EA18..2C 原样）
    sw    zero, -0x5014(at)
    addiu t2, zero, -2
    j     @@done
    sw    t2, -0x5010(at)       ; delay: sync[2] = -2
@@reload:
    addiu t0, zero, 1           ; r3 = 1（半角按假名节奏；汉字为 2）
    sw    t0, 0x28(s4)          ; v10[10] = r3 —— 每字计时器重载（此前漏掉 → 半角瞬出）
@@done:
    addiu s5, s5, 1             ; 每帧配额 +1
    lw    ra, 0x1B0(sp)
    j     0x11EA44              ; 回共享配额检查（0x11EA40 的 S5++ 已做，跳过）
    addiu s2, s2, 1             ; delay: 字符串指针推进 ★（原版缺陷点）

; ---------------- ③ 全局打字速度（全角/半角统一） ----------------
; 0x11DF9C：s_strput24w 初始化——palabuf[11]=64 且预置 sync[0]=64（同一常量）
.org 0x11DF9C
    addiu r5, zero, TEXT_SPEED
; 0x11E39C：{SD} 命令恢复默认速度（保持与全局默认一致）
.org 0x11E39C
    addiu r3, zero, TEXT_SPEED

; ---------------- ④ 翻页等待点击（hook R 溢出清屏 / P 清屏） ----------------
; 窗口 4 行：第 5 行的 {R;} 与 {P;} 原本到达即清屏（原版代码 0x11E428..64：
; S1+=28 超过 88 即 s_strclr——按行位置触发，与速度无关），快速度下读者
; 没读完就翻页。hook 后：R/P 是块首命令且未按确认键 → 指针回退到块首、
; 行计数回退，跳 0x11EA50 存回 palabuf 退出本帧 → 下一帧重解析同一块；
; 按下确认键才执行原清屏序列继续。
;   确认键 = on_key[0] bit 0x20（选择窗确认键，读取照抄 0x121948-50；
;   手感与对话推进键不符时只改 PW_CHK 里的 andi 常量重汇编）。
;   【数据零改动】R/P 不是块首命令（V/TRG 排前面的 18 处原版写法）→
;   不等待，直接原版立即清屏——等待会令块首伴生命令每帧重跑
;   （语音重放/s_str_trg 爆刷），故这 18 句保持原版行为。
;   向后扫描假定块内无嵌套 '{'（全库已验证零嵌套；超 16 步未找到按点击兜底）。
; 洞 = sceVu0NormalLightMatrix 尸体（0x102AD8 起 192B；xrefs/lui+ori/裸指针
; 三通道零引用）。起点 0x102AE0：避开上方 HK_CAVE 的 184 字节占用。
.org 0x11E434
    b     PW_R
    addiu a0, sp, 0x1B8      ; delay：即原 0x11E438（洞内 s_strclr 需要 a0）
.org 0x11E4BC
    b     PW_P
    addiu a0, sp, 0x1B8      ; delay：即原 0x11E4C0
.org 0x102AE0
PW_R:
    addiu s1, s1, -28        ; 撤销行推进（点击/兜底路径随后清零）
    addiu t3, zero, 0x52     ; 'R'
    b     PW_CHK
    nop
PW_P:
    addiu t3, zero, 0x50     ; 'P'
PW_CHK:
    lui   at, 0x30
    lhu   v0, -0x11F0(at)    ; on_key[0]
    andi  v0, v0, 0x20       ; 确认键
    bnez  v0, PW_GO
    nop
    addiu t0, zero, 16       ; 未点击：向后扫描块首（安全上限 16 步）
PW_SCAN:
    addiu s2, s2, -1
    lbu   t1, 0(s2)
    addiu t2, zero, 0x7B     ; '{'
    beq   t1, t2, PW_FOUND
    addiu t0, t0, -1         ; delay（两路都要计数）
    bne   t0, zero, PW_SCAN
    nop
    b     PW_GO              ; 上限耗尽未找到（不应发生）→ 按点击兜底清屏
    nop
PW_FOUND:
    lbu   t1, 1(s2)          ; 块首命令字母
    bne   t1, t3, PW_GO      ; 非 R/P 块首（V/TRG 在前）→ 原版立即清屏
    nop
    b     0x11EA50           ; 挂起：存 v10[12]/[3]/[4] 退出本帧
    nop
PW_GO:                       ; 已点击/兜底：照抄原清屏序列（0x11E434..0x11E464）
    lh    v0, 0x20(s4)
    sh    v0, 0x1B8(sp)
    lh    v0, 0x24(s4)
    sh    v0, 0x1BA(sp)
    lh    v0, 4(s4)
    sh    v0, 0x1BC(sp)
    lh    v0, 8(s4)
    jal   0x11D520           ; s_strclr（0x11E454/0x123994 两处原版调用交叉验证；
    sh    v0, 0x1BE(sp)      ;  ⚠ IDA 注释 dword_23A9B4-0x11D494 是差值显示，勿当地址）
    or    s1, zero, zero     ; S1 = 0（原 paddub，armips 表缺 MMI，or 等价）
    b     0x11E660           ; 回命令循环顶（s2 停在 '}' 上，由循环正常吃掉）
    or    s0, zero, zero     ; S0 = 0（delay）

.close
