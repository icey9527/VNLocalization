import os
import re
import argparse
import yaml

def extract_speakers(input_folder, output_yaml):
    """提取所有说话人到YAML"""
    speakers = {}
    
    for root, dirs, files in os.walk(input_folder):
        for file in files:
            if not file.lower().endswith('.txt'):
                continue
            
            input_path = os.path.join(root, file)
            
            try:
                with open(input_path, 'r', encoding='cp932') as f:
                    lines = f.readlines()
            except:
                continue
            
            for line in lines:
                if '：' not in line:
                    continue
                
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
                    # 去掉注释符号
                    potential_speaker = potential_speaker.lstrip('/').lstrip('*').rstrip('\n')
                    if potential_speaker and not potential_speaker.startswith(('<', '「')):
                        # 添加到字典，初始译文为空
                        if potential_speaker not in speakers:
                            speakers[potential_speaker] = ""
    
    # 排序并写入YAML
    sorted_speakers = dict(sorted(speakers.items()))
    
    with open(output_yaml, 'w', encoding='utf-8') as f:
        yaml.dump(sorted_speakers, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    print(f"提取完成！共找到 {len(sorted_speakers)} 个说话人")
    print(f"已保存到: {output_yaml}")
    print("\n请编辑 YAML 文件，在冒号后填写译文，例如：")
    print("タクト: 塔克特")


def replace_speakers(input_folder, output_folder, yaml_path):
    """根据YAML替换说话人"""
    # 读取YAML
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            speaker_map = yaml.safe_load(f)
    except Exception as e:
        print(f"无法读取YAML文件: {e}")
        return
    
    if not speaker_map:
        print("YAML文件为空")
        return
    
    # 过滤出有译文的映射
    valid_map = {k: v for k, v in speaker_map.items() if v and v.rstrip('\n')}
    
    if not valid_map:
        print("没有找到任何译文，请先编辑YAML文件")
        return
    
    print(f"将替换 {len(valid_map)} 个说话人")
    
    for root, dirs, files in os.walk(input_folder):
        for file in files:
            if not file.lower().endswith('.txt'):
                continue
            
            input_path = os.path.join(root, file)
            
            try:
                with open(input_path, 'r', encoding='cp936',errors='ignore') as f:
                    content = f.read()
            except:
                print(f"无法读取: {input_path}")
                continue
            
            # 替换说话人
            modified = False
            for original, translation in valid_map.items():
                # 匹配 "说话人：" 格式，确保冒号后面有内容或标签
                pattern = re.escape(original) + r'：'
                if re.search(pattern, content):
                    content = re.sub(pattern, translation + '：', content)
                    modified = True
            
            if modified:
                # 保存到输出文件夹
                rel_path = os.path.relpath(root, input_folder)
                if rel_path == '.':
                    output_dir = output_folder
                else:
                    output_dir = os.path.join(output_folder, rel_path)
                
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, file)
                
                try:
                    with open(output_path, 'w', encoding='cp936',errors='ignore') as f:
                        f.write(content)
                    print(f"已处理: {output_path}")
                except Exception as e:
                    print(f"写入失败 {output_path}: {e}")


def main():
    parser = argparse.ArgumentParser(description='说话人提取/替换工具')
    parser.add_argument('mode', choices=['e', 'w'], help='e=提取说话人, w=替换说话人')
    parser.add_argument('input_folder', help='输入txt文件夹')
    parser.add_argument('--output', '-o', help='w模式：输出文件夹；e模式：输出yaml文件路径', default='speakers.yaml')
    parser.add_argument('--yaml', '-y', help='w模式：使用的yaml文件路径', default='speakers.yaml')
    
    args = parser.parse_args()
    
    if args.mode == 'e':
        # 提取模式
        output_yaml = args.output if args.output != 'speakers.yaml' else 'speakers.yaml'
        extract_speakers(args.input_folder, output_yaml)
    else:
        # 替换模式
        if not args.output or args.output == 'speakers.yaml':
            print("错误：w模式必须指定输出文件夹 --output")
            return
        yaml_path = args.yaml
        replace_speakers(args.input_folder, args.output, yaml_path)
        print("\n全部处理完成！")


if __name__ == '__main__':
    main()