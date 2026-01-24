#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <filesystem>
#include <regex>
#include <unordered_map>
#include <cstring>
#include <stdexcept>
#include <iomanip>

namespace fs = std::filesystem;

// CM格式解压函数
std::vector<uint8_t> decompress_cm(const std::vector<uint8_t>& data, size_t max_output = 0) {
    if (data.size() < 12) {
        throw std::runtime_error("数据太短，缺少头部");
    }
    
    // 检查魔数
    if (data[0] != 'C' || data[1] != 'M') {
        throw std::runtime_error("魔数不匹配，期望 'CM'");
    }
    
    // 读取头部（小端）
    uint32_t out_len_header = *reinterpret_cast<const uint32_t*>(&data[4]);
    uint32_t token_len = *reinterpret_cast<const uint32_t*>(&data[8]);
    
    // 目标输出长度
    size_t target_len = (max_output == 0 || max_output >= out_len_header) ? out_len_header : max_output;
    
    size_t token_pos = 12;  // token区起始
    size_t flags_base = 12 + token_len;  // 标志位区起始
    
    if (flags_base > data.size()) {
        throw std::runtime_error("数据长度不足：token区越界");
    }
    
    std::vector<uint8_t> out;
    out.reserve(target_len);
    
    size_t produced = 0;
    size_t bit_index = 0;  // 已消费标志位bit数
    
    while (produced < target_len) {
        // 取当前标志位（LSB-first）
        size_t flags_byte_idx = flags_base + (bit_index >> 3);
        if (flags_byte_idx >= data.size()) {
            throw std::runtime_error("标志位用尽/越界");
        }
        
        uint8_t flags_byte = data[flags_byte_idx];
        bool is_match = (flags_byte >> (bit_index & 7)) & 1;
        bit_index++;
        
        if (!is_match) {
            // 字面量
            if (token_pos >= flags_base) {
                throw std::runtime_error("token区用尽（需要字面量）");
            }
            out.push_back(data[token_pos]);
            token_pos++;
            produced++;
        } else {
            // 匹配项（2字节小端）
            if (token_pos + 2 > flags_base) {
                throw std::runtime_error("token区用尽（需要2字节匹配项）");
            }
            uint16_t u16 = data[token_pos] | (data[token_pos + 1] << 8);
            token_pos += 2;
            
            size_t length = (u16 >> 12) + 3;
            size_t distance = (u16 & 0x0FFF) + 1;
            
            if (distance > out.size()) {
                throw std::runtime_error("无效回溯距离：" + std::to_string(distance) + 
                                       " > 已输出 " + std::to_string(out.size()));
            }
            
            // 复制允许重叠
            size_t to_copy = std::min(length, target_len - produced);
            while (to_copy > 0) {
                size_t chunk = std::min(distance, to_copy);
                size_t src_start = out.size() - distance;
                for (size_t i = 0; i < chunk; i++) {
                    out.push_back(out[src_start + i]);
                }
                to_copy -= chunk;
                produced += chunk;
            }
        }
    }
    
    out.resize(target_len);
    return out;
}

// 解析头文件获取文件名映射
std::unordered_map<int, std::string> parse_header_file(const fs::path& h_file_path) {
    std::unordered_map<int, std::string> name_mapping;
    
    if (!fs::exists(h_file_path)) {
        std::cout << "警告: 头文件 " << h_file_path << " 不存在" << std::endl;
        return name_mapping;
    }
    
    std::ifstream file(h_file_path);
    if (!file.is_open()) {
        std::cout << "警告: 无法打开头文件 " << h_file_path << std::endl;
        return name_mapping;
    }
    
    std::string line;
    std::regex pattern(R"(#define\s+(\S+)\s+(\d+))");
    
    while (std::getline(file, line)) {
        std::smatch match;
        if (std::regex_search(line, match, pattern)) {
            std::string name = match[1];
            int file_id = std::stoi(match[2]);
            name_mapping[file_id] = name;
        }
    }
    
    return name_mapping;
}

// 读取文件到vector
std::vector<uint8_t> read_file(const fs::path& file_path) {
    std::ifstream file(file_path, std::ios::binary);
    if (!file.is_open()) {
        throw std::runtime_error("无法打开文件: " + file_path.string());
    }
    
    file.seekg(0, std::ios::end);
    size_t size = file.tellg();
    file.seekg(0, std::ios::beg);
    
    std::vector<uint8_t> data(size);
    file.read(reinterpret_cast<char*>(data.data()), size);
    
    return data;
}

// 写入vector到文件
void write_file(const fs::path& file_path, const std::vector<uint8_t>& data) {
    std::ofstream file(file_path, std::ios::binary);
    if (!file.is_open()) {
        throw std::runtime_error("无法创建文件: " + file_path.string());
    }
    
    file.write(reinterpret_cast<const char*>(data.data()), data.size());
}

// 解包单个DAT文件
void extract_dat_file(const fs::path& dat_file_path, const fs::path& output_dir) {
    std::cout << "处理文件: " << dat_file_path << std::endl;
    
    std::vector<uint8_t> data = read_file(dat_file_path);
    
    if (data.size() < 12) {
        std::cout << "错误: " << dat_file_path << " 文件太小" << std::endl;
        return;
    }
    
    // 读取索引表头部
    uint32_t file_count = *reinterpret_cast<const uint32_t*>(&data[0]);
    uint32_t data_start_value = *reinterpret_cast<const uint32_t*>(&data[4]);
    
    // 计算实际的数据起始地址
    uint32_t data_start_address = data_start_value * 32;
    
    std::cout << "文件数量: " << file_count << std::endl;
    std::cout << "数据起始地址: 0x" << std::hex << std::setw(8) << std::setfill('0') 
              << data_start_address << " (值: " << std::dec << data_start_value << ")" << std::endl;
    
    if (file_count == 0 || file_count > 1000) {
        std::cout << "错误: 文件数量异常 (" << file_count << ")" << std::endl;
        return;
    }
    
    // 查找对应的.h文件
    fs::path base_name = dat_file_path.stem();
    fs::path h_file_path = dat_file_path.parent_path() / (base_name.string() + ".h");
    auto name_mapping = parse_header_file(h_file_path);
    
    // 创建输出文件夹
    fs::path output_folder = output_dir / base_name.filename();
    fs::create_directories(output_folder);
    
    // 读取文件结束位置索引表
    std::vector<uint32_t> end_positions;
    for (uint32_t i = 0; i < file_count; i++) {
        size_t offset = 8 + i * 4;
        if (offset + 4 <= data.size()) {
            uint32_t end_value = *reinterpret_cast<const uint32_t*>(&data[offset]);
            uint32_t end_position = end_value * 32;  // 乘以32得到实际地址
            end_positions.push_back(end_position);
        } else {
            std::cout << "错误: 索引表数据不足" << std::endl;
            return;
        }
    }
    
    // 显示前10个结束位置值
    std::cout << "结束位置值: ";
    for (size_t i = 0; i < std::min(size_t(10), end_positions.size()); i++) {
        std::cout << end_positions[i] / 32 << " ";
    }
    if (end_positions.size() > 10) std::cout << "...";
    std::cout << std::endl;
    
    // 提取文件
    int extracted_count = 0;
    uint32_t current_start = data_start_address;
    
    for (uint32_t i = 0; i < file_count; i++) {
        uint32_t file_start = current_start;
        uint32_t file_end = end_positions[i];
        int32_t file_size = file_end - file_start;
        
        if (file_start >= data.size() || file_size <= 0) {
            std::cout << "跳过无效文件 " << i << ": 起始位置 0x" << std::hex << file_start 
                      << ", 结束位置 0x" << file_end << ", 大小 " << std::dec << file_size << std::endl;
            current_start = file_end;
            continue;
        }
        
        if (file_end > data.size()) {
            std::cout << "警告: 文件 " << i << " 超出数据范围，截断到文件末尾" << std::endl;
            file_end = data.size();
            file_size = file_end - file_start;
        }
        
        // 提取文件数据
        std::vector<uint8_t> file_data(data.begin() + file_start, data.begin() + file_end);
        
        // 确定文件名
        std::string filename = std::to_string(i);
        auto it = name_mapping.find(i);
        if (it != name_mapping.end()) {
            filename += "." + it->second;
        }
        
        // 保存文件（解压后）
        fs::path output_path = output_folder / filename;
        try {
            std::vector<uint8_t> decompressed_data = decompress_cm(file_data);
            write_file(output_path, decompressed_data);
            std::cout << "  文件 " << std::setw(3) << i << ": " 
                      << std::left << std::setw(25) << filename 
                      << " (0x" << std::hex << std::setw(8) << std::setfill('0') << file_start 
                      << " - 0x" << std::setw(8) << std::setfill('0') << file_end 
                      << ", " << std::dec << std::setw(6) << file_size << " 字节)" << std::endl;
        } catch (const std::exception& e) {
            std::cout << "  文件 " << std::setw(3) << i << ": 解压失败 - " << e.what() << std::endl;
        }
        
        extracted_count++;
        current_start = file_end;
    }
    
    std::cout << "完成! 提取了 " << extracted_count << " 个文件到 " << output_folder << std::endl;
    std::cout << std::string(70, '-') << std::endl;
}

// 处理所有DAT文件
void process_all_dat_files(const fs::path& input_dir, const fs::path& output_dir) {
    if (!fs::exists(input_dir)) {
        std::cout << "错误: 输入文件夹 " << input_dir << " 不存在" << std::endl;
        return;
    }
    
    std::vector<fs::path> dat_files;
    for (const auto& entry : fs::directory_iterator(input_dir)) {
        if (entry.path().extension() == ".dat") {
            dat_files.push_back(entry.path());
        }
    }
    
    if (dat_files.empty()) {
        std::cout << "在 " << input_dir << " 中没有找到.dat文件" << std::endl;
        return;
    }
    
    std::cout << "找到 " << dat_files.size() << " 个.dat文件" << std::endl;
    fs::create_directories(output_dir);
    
    for (const auto& dat_file : dat_files) {
        try {
            extract_dat_file(dat_file, output_dir);
        } catch (const std::exception& e) {
            std::cout << "处理 " << dat_file << " 时出错: " << e.what() << std::endl;
            continue;
        }
    }
}

int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cout << "用法: " << argv[0] << " <输入文件夹> <输出文件夹>" << std::endl;
        return 1;
    }
    
    fs::path input_directory = argv[1];
    fs::path output_directory = argv[2];
    
    std::cout << "DAT文件解包工具 (C++版本)" << std::endl;
    std::cout << std::string(70, '=') << std::endl;
    
    process_all_dat_files(input_directory, output_directory);
    std::cout << "\n解包完成!" << std::endl;
    
    return 0;
}