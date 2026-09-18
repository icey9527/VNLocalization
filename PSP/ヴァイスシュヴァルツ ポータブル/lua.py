import os, sys, re, subprocess

def solve(path):
    jar = "unluac.jar"
    for root, _, files in os.walk(path):
        for f in [x for x in files if x.lower().endswith(".lua")]:
            p = os.path.join(root, f)
            try:
                with open(p, 'rb') as fb: 
                    content = fb.read()
                
                # 1. 判定是否为字节码
                if content.startswith(b'\x1bLua'):
                    print(f"Decompiling: {p}")
                    # 获取反编译结果，直接按 latin-1 解码成“字节字符串”
                    raw = subprocess.check_output(["java", "-jar", jar, p]).decode('latin-1')
                    # 修正正则：只匹配1-3位数字，且过滤掉大于255的数值（防止 latin-1 报错）
                    def rep(m):
                        v = int(m.group(1))
                        return chr(v) if v < 256 else m.group(0)
                    # 还原转义序列并转回原始 bytes
                    content = re.sub(r'\\(\d{1,3})', rep, raw).encode('latin-1')

                # 2. 统一清理换行符并尝试解码 (UTF-8 -> CP932)
                clean_b = content.replace(b'\r', b'')
                try:
                    src = clean_b.decode('utf-8')
                except:
                    src = clean_b.decode('cp932', errors='ignore')

                # 3. 原样覆盖写入 UTF-8
                with open(p, 'w', encoding='utf-8', newline='\n') as fout:
                    fout.write(src)
                print(f"OK: {p}")
                
            except Exception as e:
                print(f"ERR: {p} | {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1: solve(sys.argv[1])