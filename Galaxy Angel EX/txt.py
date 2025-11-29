import os
import csv
import re
import argparse

def extract_file(input_path, output_path):
    """提取模式：从txt提取文本到csv"""
    current_speaker = ""
    
    # 用cp932读取文件
    try:
        with open(input_path, 'r', encoding='cp932') as f:
            lines = f.readlines()
    except:
        print(f"编码错误，跳过: {input_path}")
        return False
    
    if not lines:
        return False
    
    full_text = ''.join(lines)
    
    # 建立字符位置到说话人的映射
    pos = 0
    speaker_at_pos = {}
    
    for line in lines:
        # 检测说话人 - 冒号必须不在括号内
        if '：' in line:
            colon_pos = line.find('：')
            before_colon = line[:colon_pos]
            # 检查冒号前面是否有未闭合的括号
            open_brackets = 0
            for ch in before_colon:
                if ch in '[［「':
                    open_brackets += 1
                elif ch in ']］」':
                    open_brackets -= 1
            
            # 只有冒号不在括号内才识别说话人
            if open_brackets == 0:
                potential_speaker = before_colon.rstrip('\n')
                potential_speaker = potential_speaker.lstrip('/').lstrip('*').rstrip('\n')
                if potential_speaker and not potential_speaker.startswith(('<', '「')):
                    current_speaker = potential_speaker
        
        for i in range(len(line)):
            speaker_at_pos[pos + i] = current_speaker
        pos += len(line)
    
    # 收集所有匹配项
    all_matches = []
    
    # 提取//注释内容
    for match in re.finditer(r'^//(.+)$', full_text, re.MULTILINE):
        content = match.group(1).rstrip('\n')
        if content and not content.startswith('<'):
            all_matches.append({
                'pos': match.start(),
                'type': '//',
                'content': content,
                'full_match': match.group(0),
                'speaker': speaker_at_pos.get(match.start(), "")
            })
    
    # 提取「」内容 - 支持无结束」的情况
    # 匹配到」结束，或者遇到<结束，或者文件结束
    for match in re.finditer(r'「(.*?)(?:」|(?=<)|$)', full_text, re.DOTALL):
        all_matches.append({
            'pos': match.start(),
            'type': '「」',
            'content': match.group(1),
            'full_match': match.group(0),
            'speaker': speaker_at_pos.get(match.start(), "")
        })
    
    # 提取［］内容（全角）
    for match in re.finditer(r'［([^］]*)］', full_text, re.DOTALL):
        all_matches.append({
            'pos': match.start(),
            'type': '［］',
            'content': match.group(1),
            'full_match': match.group(0),
            'speaker': speaker_at_pos.get(match.start(), "")
        })
    
    # 提取[]内容（半角）
    for match in re.finditer(r'\[([^\]]*)\]', full_text, re.DOTALL):
        all_matches.append({
            'pos': match.start(),
            'type': '[]',
            'content': match.group(1),
            'full_match': match.group(0),
            'speaker': speaker_at_pos.get(match.start(), "")
        })
    
    # 按位置排序
    all_matches.sort(key=lambda x: x['pos'])
    
    # 生成结果
    results = []
    type_counts = {'//': 0, '「」': 0, '［］': 0, '[]': 0}
    for item in all_matches:
        type_counts[item['type']] += 1
        key = f"{item['type']}{type_counts[item['type']]}"
        content_escaped = item['content'].replace('\r\n', '\\n').replace('\n', '\\n')
        # 只有「」才输出说话人
        speaker = item['speaker'] if item['type'] == '「」' else ""
        results.append([key, content_escaped, "", speaker])
    
    if results:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerows(results)
        print(f"提取完成: {input_path} -> {output_path}")
        return True
    return False


def write_back_file(csv_path, original_txt_path, output_path):
    """写回模式：从csv读取译文写回txt"""
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            translations = {}
            for row in reader:
                if len(row) >= 3 and row[2]:
                    translations[row[0].lstrip('\ufeff')] = row[2].replace('\\n', '\n')
    except Exception as e:
        print(f"无法读取CSV {csv_path}: {e}")
        return False
    
    if not translations:
        print(f"没有译文，跳过: {csv_path}")
        return False
    
    try:
        with open(original_txt_path, 'r', encoding='cp932') as f:
            content = f.read()
    except:
        print(f"无法读取原文件: {original_txt_path}")
        return False
    
    # 替换//注释
    comment_count = 0
    def replace_comment(match):
        nonlocal comment_count
        comment_count += 1
        key = f"//{comment_count}"
        if key in translations:
            return f"//{translations[key]}"
        return match.group(0)
    content = re.sub(r'^//(.+)$', replace_comment, content, flags=re.MULTILINE)
    
    # 替换「」- 需要处理无结束」的情况
    kakko_count = 0
    def replace_kakko(match):
        nonlocal kakko_count
        kakko_count += 1
        key = f"「」{kakko_count}"
        if key in translations:
            full_match = match.group(0)
            # 检查原文是否有结束的」
            if full_match.endswith('」'):
                return f"「{translations[key]}」"
            else:
                # 无」结束，保持原样（可能遇到<或文件结束）
                return f"「{translations[key]}"
        return match.group(0)
    content = re.sub(r'「(.*?)(?:」|(?=<)|$)', replace_kakko, content, flags=re.DOTALL)
    
    # 替换［］（全角）
    bracket_count = 0
    def replace_bracket(match):
        nonlocal bracket_count
        bracket_count += 1
        key = f"［］{bracket_count}"
        if key in translations:
            return f"［{translations[key]}］"
        return match.group(0)
    content = re.sub(r'［([^］]*)］', replace_bracket, content, flags=re.DOTALL)
    
    # 替换[]（半角）
    half_bracket_count = 0
    def replace_half_bracket(match):
        nonlocal half_bracket_count
        half_bracket_count += 1
        key = f"[]{half_bracket_count}"
        if key in translations:
            return f"[{translations[key]}]"
        return match.group(0)
    content = re.sub(r'\[([^\]]*)\]', replace_half_bracket, content, flags=re.DOTALL)
    
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    try:
        with open(output_path, 'w', encoding='cp936',errors='ignore') as f:
            f.write(content)
        print(f"写回完成: {output_path}")
        return True
    except Exception as e:
        print(f"写回失败 {output_path}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='文本提取/写回工具')
    parser.add_argument('mode', choices=['e', 'w'], help='e=提取, w=写回')
    parser.add_argument('input_folder', help='输入文件夹')
    parser.add_argument('output_folder', help='输出文件夹')
    parser.add_argument('--original', '-o', help='写回模式时原始txt文件夹')
    
    args = parser.parse_args()
    os.makedirs(args.output_folder, exist_ok=True)
    
    if args.mode == 'e':
        for root, dirs, files in os.walk(args.input_folder):
            for file in files:
                if not file.lower().endswith('.txt'):
                    continue
                input_path = os.path.join(root, file)
                rel_path = os.path.relpath(root, args.input_folder)
                output_dir = args.output_folder if rel_path == '.' else os.path.join(args.output_folder, rel_path)
                output_path = os.path.join(output_dir, os.path.splitext(file)[0] + '.csv')
                extract_file(input_path, output_path)
    else:
        original_folder = args.original if args.original else args.input_folder
        for root, dirs, files in os.walk(args.input_folder):
            for file in files:
                if not file.lower().endswith('.csv'):
                    continue
                csv_path = os.path.join(root, file)
                rel_path = os.path.relpath(root, args.input_folder)
                txt_filename = os.path.splitext(file)[0] + '.txt'
                if rel_path == '.':
                    original_txt_path = os.path.join(original_folder, txt_filename)
                    output_dir = args.output_folder
                else:
                    original_txt_path = os.path.join(original_folder, rel_path, txt_filename)
                    output_dir = os.path.join(args.output_folder, rel_path)
                write_back_file(csv_path, original_txt_path, os.path.join(output_dir, txt_filename))
    
    print("\n全部处理完成！")

if __name__ == '__main__':
    main()