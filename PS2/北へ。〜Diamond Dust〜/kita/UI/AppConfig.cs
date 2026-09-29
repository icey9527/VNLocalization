// UI/AppConfig.cs — GUI 配置记忆（exe 旁 kita.ini）。照 GA2 的项目模型：
//   [projects] names = 工作区文件夹名列表（工作区都在 exe 同级）；current = 当前项目
//   [prepack.<项目名>] 每项目一份重建前命令（1 = ..., 2 = ...）
// ISO 路径不落配置——只在"新建项目"时用一次，生成同名工作区后一切读写都在工作区里。

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace kita.UI
{
    internal sealed class AppConfig
    {
        public List<string> Projects = new();
        public string CurrentProject = "";
        public List<string> LastPicked = new();
        public Dictionary<string, List<string>> PrePackPerProject = new(StringComparer.OrdinalIgnoreCase);

        public string Path = "";

        public List<string> PrePackOf(string project) =>
            PrePackPerProject.TryGetValue(project, out var list) ? list : new List<string>();

        public void SetPrePack(string project, List<string> commands) => PrePackPerProject[project] = commands;

        public static AppConfig Load(string iniPath)
        {
            var cfg = new AppConfig { Path = iniPath };
            if (!File.Exists(iniPath)) return cfg;

            string section = null;
            foreach (string raw in File.ReadAllLines(iniPath))
            {
                string line = raw.Trim();
                if (line.Length == 0 || line.StartsWith("#") || line.StartsWith(";")) continue;
                if (line.StartsWith("[") && line.EndsWith("]"))
                {
                    section = line[1..^1].Trim();
                    continue;
                }
                int eq = line.IndexOf('=');
                if (eq <= 0 || section == null) continue;
                string key = line[..eq].Trim();
                string value = line[(eq + 1)..].Trim();

                if (section.Equals("projects", StringComparison.OrdinalIgnoreCase))
                {
                    if (key.Equals("names", StringComparison.OrdinalIgnoreCase))
                        cfg.Projects = value
                            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                            .ToList();
                    else if (key.Equals("current", StringComparison.OrdinalIgnoreCase))
                        cfg.CurrentProject = value;
                }
                else if (section.Equals("ui", StringComparison.OrdinalIgnoreCase))
                {
                    if (key.Equals("last_picked", StringComparison.OrdinalIgnoreCase))
                        cfg.LastPicked = value
                            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                            .ToList();
                }
                else if (section.StartsWith("prepack.", StringComparison.OrdinalIgnoreCase))
                {
                    string proj = section["prepack.".Length..].Trim();
                    if (proj.Length == 0) continue;
                    if (int.TryParse(key, out int order) && value.Length > 0)
                    {
                        if (!cfg.PrePackPerProject.TryGetValue(proj, out var list))
                            cfg.PrePackPerProject[proj] = list = new List<string>();
                        list.Add(value); // ini 按序号顺序写，按文件顺序读回即有序
                    }
                }
            }
            // 序号键按文件顺序天然有序；上面边读边 Add 保持了顺序
            return cfg;
        }

        public void Save()
        {
            var lines = new List<string>
            {
                "; kita GUI 配置（自动生成）：项目列表与勾选记忆",
                "; 工作区 = exe 同级\\<项目名>\\，内含 original\\ extract\\ modified\\ packed\\",
                "[projects]",
                $"names = {string.Join(",", Projects)}",
                $"current = {CurrentProject}",
                "",
                "[ui]",
                $"last_picked = {string.Join(",", LastPicked)}",
            };
            foreach (string proj in PrePackPerProject.Keys)
            {
                lines.Add("");
                lines.Add($"[prepack.{proj}]");
                var cmds = PrePackPerProject[proj];
                for (int i = 0; i < cmds.Count; i++)
                    lines.Add($"{i + 1} = {cmds[i]}");
            }

            try { File.WriteAllText(System.IO.Path.Combine(System.IO.Path.GetTempPath(), "kita_ini_debug.log"),
                $"{DateTime.Now:HH:mm:ss} save -> {Path}  projects={Projects.Count} current={CurrentProject}{Environment.NewLine}"); }
            catch { /* ignore */ }
            try { File.WriteAllLines(Path, lines); }
            catch { /* 配置写不进去不致命，别让主流程炸 */ }
        }
    }
}
