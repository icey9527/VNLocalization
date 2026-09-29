// UI/MainForm.cs — GUI 主窗体。项目模型照搬 GalaxyAngel2Localization：
//   顶部"当前项目"下拉框（多工作区切换）；工作区 = exe 同级\<项目名>\。
//   "新建项目"页：选 ISO（只用这一次）→ 按文件名生成同名工作区 → 切记录原始字节进 original\。
//   此后提取 / 重建前任务 / 打包 一律只读写工作区，不再碰 ISO（GA2 同款自包含模型）。
//
// 工作区固定四目录：original\（原始字节 + scr 组备份 + ACCESSDB 备份）、
// extract\（PNG）、modified\（只放改过的）、packed\（回包产物）。

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace kita.UI
{
    internal sealed class MainForm : Form
    {
        readonly AppConfig cfg;

        /// <summary>exe 所在目录（GA2 的 AppRoot 同款）：所有工作区 <项目名>\ 都在这下面。</summary>
        static string AppRoot =>
            System.IO.Path.GetDirectoryName(Environment.ProcessPath ?? AppContext.BaseDirectory)
            ?? AppContext.BaseDirectory;

        readonly ComboBox cmbProjects = new() { Dock = DockStyle.Fill, DropDownStyle = ComboBoxStyle.DropDownList };
        readonly TextBox txtIso = new() { Dock = DockStyle.Fill };
        readonly CheckedListBox clbNew = new() { Dock = DockStyle.Fill, CheckOnClick = true, IntegralHeight = false };
        readonly CheckedListBox clbExtract = new() { Dock = DockStyle.Fill, CheckOnClick = true, IntegralHeight = false };
        readonly TextBox txtLog = new()
        {
            Dock = DockStyle.Fill, Multiline = true, ScrollBars = ScrollBars.Vertical,
            ReadOnly = true, BackColor = System.Drawing.SystemColors.Window,
            Font = new System.Drawing.Font("Consolas", 9F),
        };
        readonly ListBox lstWorkStats = new()
        {
            Dock = DockStyle.Fill, IntegralHeight = false, ScrollAlwaysVisible = true,
            BorderStyle = BorderStyle.None, Font = new System.Drawing.Font("Consolas", 9F),
        };
        readonly TextBox txtPrePack = new()
        {
            Dock = DockStyle.Fill, Multiline = true, ScrollBars = ScrollBars.Vertical,
            Font = new System.Drawing.Font("Consolas", 9F), AcceptsTab = false,
        };
        readonly ToolStripStatusLabel lblStatus = new() { Text = "就绪" };

        readonly Button btnCreate = new() { Text = "创建工作区", AutoSize = true };
        readonly Button btnExtract = new() { Text = "提取图片 → extract\\", AutoSize = true };
        readonly Button btnPack = new() { Text = "开始打包 → packed\\", AutoSize = true };

        List<ArchiveBin> isoArchives = new();     // 新建项目页：ISO 里发现的档案
        List<WsArchive> wsArchives = new();       // 当前工作区发现的档案
        string Workspace => System.IO.Path.Combine(AppRoot, cmbProjects.SelectedItem as string ?? "");

        public MainForm()
        {
            cfg = AppConfig.Load(System.IO.Path.Combine(AppContext.BaseDirectory, "kita.ini"));

            Text = "kita — 北へ。资源工具（新建项目 / 提取 / 差分打包）";
            Font = new System.Drawing.Font("Microsoft YaHei UI", 9F);
            StartPosition = FormStartPosition.CenterScreen;
            MinimumSize = new System.Drawing.Size(820, 600);
            Size = new System.Drawing.Size(920, 680);

            // ---------- 顶部：当前项目 ----------
            var grpTop = new GroupBox { Dock = DockStyle.Top, Height = 60, Text = "当前项目", Padding = new Padding(12, 4, 12, 8) };
            var grid = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 3 };
            grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            grid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 96));
            grid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 110));
            grid.Controls.Add(cmbProjects, 0, 0);
            var btnRefresh = new Button { Text = "刷新", Dock = DockStyle.Fill };
            btnRefresh.Click += (s, e) => LoadProjects();
            grid.Controls.Add(btnRefresh, 1, 0);
            var btnOpen = new Button { Text = "打开工作区", Dock = DockStyle.Fill };
            btnOpen.Click += (s, e) => OpenWorkspace();
            grid.Controls.Add(btnOpen, 2, 0);
            grpTop.Controls.Add(grid);

            // ---------- 中部：页签 ----------
            var tabs = new TabControl { Dock = DockStyle.Fill };
            tabs.TabPages.Add(BuildNewProjectTab());
            tabs.TabPages.Add(BuildExtractTab());
            tabs.TabPages.Add(BuildPrePackTab());
            tabs.TabPages.Add(BuildPackTab());

            // ---------- 底部：日志 + 状态栏 ----------
            var split = new SplitContainer
            {
                Dock = DockStyle.Fill, Orientation = Orientation.Horizontal,
                FixedPanel = FixedPanel.Panel2, SplitterDistance = 220,
            };
            var logGroup = new GroupBox { Dock = DockStyle.Fill, Text = "日志", Padding = new Padding(10, 4, 10, 10) };
            logGroup.Controls.Add(txtLog);
            split.Panel1.Controls.Add(logGroup);
            var status = new StatusStrip { Dock = DockStyle.Fill };
            status.Items.Add(lblStatus);
            split.Panel2.Controls.Add(status);

            var center = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 2, ColumnCount = 1 };
            center.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            center.RowStyles.Add(new RowStyle(SizeType.Absolute, 260));
            center.Controls.Add(tabs, 0, 0);
            center.Controls.Add(split, 0, 1);

            Controls.Add(center);
            Controls.Add(grpTop);

            // ---------- 事件 ----------
            cmbProjects.SelectedIndexChanged += (s, e) => OnProjectChanged();
            clbNew.ItemCheck += (s, e) =>
            {
                if (IsHandleCreated) BeginInvoke((MethodInvoker)ScheduleSave);
                else ScheduleSave();
            };
            FormClosing += (s, e) => SaveConfig();
            saveTimer.Tick += (s, e) => { saveTimer.Stop(); SaveConfig(); };
            btnCreate.Click += async (s, e) => await CreateProjectAsync();
            btnExtract.Click += async (s, e) => await RunExtractAsync();
            btnPack.Click += async (s, e) => await RunPackAsync();

            LoadProjects();
        }

        // ---------------- 项目管理 ----------------

        /// <summary>项目列表 = ini 记忆 + 现场扫描（exe 同级含 original\ 的文件夹自动纳入）。</summary>
        void LoadProjects()
        {
            // 现场扫描：老工作区（如 work）不用手动登记
            foreach (string dir in Directory.GetDirectories(AppRoot))
                if (Directory.Exists(System.IO.Path.Combine(dir, "original")))
                    RegisterProject(System.IO.Path.GetFileName(dir), select: false);

            cmbProjects.Items.Clear();
            foreach (string name in cfg.Projects)
                if (Directory.Exists(System.IO.Path.Combine(AppRoot, name)))
                    cmbProjects.Items.Add(name);
            if (cmbProjects.Items.Count == 0)
            {
                SetStatus("没有工作区——到\"新建项目\"选 ISO 创建");
                return;
            }
            int idx = cmbProjects.Items.IndexOf(cfg.CurrentProject);
            cmbProjects.SelectedIndex = idx >= 0 ? idx : 0;
        }

        void RegisterProject(string name, bool select)
        {
            if (!cfg.Projects.Contains(name, StringComparer.OrdinalIgnoreCase))
                cfg.Projects.Add(name);
            if (select)
            {
                int idx = cmbProjects.Items.IndexOf(name);
                if (idx < 0) idx = cmbProjects.Items.Add(name);
                cmbProjects.SelectedIndex = idx;
            }
        }

        void OnProjectChanged()
        {
            cfg.CurrentProject = cmbProjects.SelectedItem as string ?? "";
            RefreshWorkspace();
            ScheduleSave();
        }

        void RefreshWorkspace()
        {
            wsArchives = Directory.Exists(Workspace)
                ? Engine.DiscoverWorkspace(Workspace)
                : new();
            FillExtractList();
            LoadPrePackToUi();
            RefreshWorkStats();
            SetStatus($"当前项目：{cfg.CurrentProject}（{wsArchives.Count} 个档案就绪）");
        }

        void OpenWorkspace()
        {
            if (!Directory.Exists(Workspace)) { MessageBox.Show("先选择一个项目。", "提示"); return; }
            try { System.Diagnostics.Process.Start("explorer.exe", Workspace); }
            catch (Exception ex) { Log("打开失败: " + ex.Message); }
        }

        // ---------------- 新建项目页 ----------------

        TabPage BuildNewProjectTab()
        {
            var page = new TabPage("新建项目");
            var layout = NewLayout();
            layout.Controls.Add(HintLabel(
                "选择 ISO → 勾选要处理的档案 → 创建。工作区 = 本程序同级\\<ISO 文件名>\\，\n"
                + "原始字节（未解码未重压）切进 original\\。ISO 只用这一次，之后一切都在工作区里。"), 0, 0);

            var rowIso = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 3, Height = 32 };
            rowIso.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 90));
            rowIso.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            rowIso.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 96));
            rowIso.Controls.Add(new Label { Text = "ISO 文件：", Dock = DockStyle.Fill, TextAlign = System.Drawing.ContentAlignment.MiddleLeft }, 0, 0);
            rowIso.Controls.Add(txtIso, 1, 0);
            var btnIso = new Button { Text = "选择 ISO…", Dock = DockStyle.Fill };
            btnIso.Click += (s, e) => BrowseIso();
            rowIso.Controls.Add(btnIso, 2, 0);

            var middle = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 2, ColumnCount = 1 };
            middle.RowStyles.Add(new RowStyle(SizeType.Absolute, 36));
            middle.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            middle.Controls.Add(rowIso, 0, 0);
            middle.Controls.Add(clbNew, 0, 1);
            layout.Controls.Add(middle, 0, 1);

            var buttons = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 3 };
            buttons.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            buttons.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            buttons.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            var btnAll = new Button { Text = "全选", AutoSize = true };
            var btnNone = new Button { Text = "全不选", AutoSize = true };
            btnAll.Click += (s, e) => SetAllChecks(clbNew, true);
            btnNone.Click += (s, e) => SetAllChecks(clbNew, false);
            buttons.Controls.Add(btnAll, 0, 0);
            buttons.Controls.Add(btnNone, 1, 0);
            buttons.Controls.Add(btnCreate, 2, 0);
            layout.Controls.Add(buttons, 0, 2);

            page.Controls.Add(layout);
            return page;
        }

        void BrowseIso()
        {
            using var dlg = new OpenFileDialog
            {
                Filter = "ISO 镜像 (*.iso)|*.iso|所有文件 (*.*)|*.*",
                Title = "选择 ISO 镜像",
            };
            string cur = txtIso.Text.Trim();
            if (cur.Length > 0 && File.Exists(cur))
                dlg.InitialDirectory = System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(cur));
            if (dlg.ShowDialog(this) == DialogResult.OK)
                txtIso.Text = dlg.FileName;
            LoadIsoArchives();
        }

        void LoadIsoArchives()
        {
            clbNew.Items.Clear();
            isoArchives = new();
            string iso = txtIso.Text.Trim();
            if (iso.Length == 0 || !File.Exists(iso)) return;
            try
            {
                var src = GameSource.Open(iso);
                isoArchives = Engine.Discover(src);
                foreach (ArchiveBin bin in isoArchives)
                {
                    long mb = bin.Size >> 20;
                    clbNew.Items.Add($"{bin.BinName,-12} {mb,4} MB  [{bin.Kind.Name}]", false);
                }
                foreach (int i in Enumerable.Range(0, isoArchives.Count)
                             .Where(i => cfg.LastPicked.Contains(isoArchives[i].BinName)))
                    clbNew.SetItemChecked(i, true);
                SetStatus($"ISO 共 {src.FileCount} 个文件，{isoArchives.Count} 个档案可选");
            }
            catch (Exception ex)
            {
                Log("解析 ISO 失败: " + ex.Message);
                SetStatus("解析 ISO 失败");
            }
        }

        async Task CreateProjectAsync()
        {
            string iso = txtIso.Text.Trim();
            var picked = clbNew.CheckedIndices.Cast<int>().Select(i => isoArchives[i]).ToList();
            if (iso.Length == 0 || !File.Exists(iso)) { MessageBox.Show("先选择 ISO。", "提示"); return; }
            if (picked.Count == 0) { MessageBox.Show("先勾选至少一个档案。", "提示"); return; }

            // GA2 同款：工作区 = exe 同级\<ISO 文件名去扩展名>
            string name = System.IO.Path.GetFileNameWithoutExtension(iso);
            string workspace = System.IO.Path.Combine(AppRoot, name);

            btnCreate.Enabled = false;
            SetStatus("创建工作区…");
            try
            {
                await Task.Run(() =>
                {
                    var src = GameSource.Open(iso);
                    var db = AccessDb.Load(src);
                    Directory.CreateDirectory(System.IO.Path.Combine(workspace, Engine.OriginalDir));
                    // 索引表参考备份：此后提取/打包的基准都是这份（不再碰 ISO）
                    src.CopyTo("DATA/ACCESSDB.BIN",
                        System.IO.Path.Combine(workspace, Engine.OriginalDir, "ACCESSDB.BIN"));
                    // 独立图像文件的原始基准（本作才有；缺哪个跳哪个，不互相牵连）。
                    // CopyTo 流式直拷——CBD 单文件最大 70MB，不在内存里攒整份。
                    // mvepic 只取 DATA 根目录那份（etc\ 拷贝游戏未引用）。
                    foreach (string rel in new[] { "etc/tit_bg.p2x", "mvepic.bin", "sysdat.bin" }
                                 .Concat(Enumerable.Range(0, 9).Select(i => $"cbd/cbd{i}00.bin")))
                    {
                        try
                        {
                            src.CopyTo("DATA/" + rel,
                                System.IO.Path.Combine(workspace, Engine.OriginalDir, System.IO.Path.GetFileName(rel)));
                        }
                        catch { /* 该 ISO 没有这个文件 —— 对应功能自动不可用 */ }
                    }
                    var bg = picked.Where(b => b.Kind.Name == "bg").ToList();
                    var scr = picked.Where(b => b.Kind.Name == "scr").ToList();
                    if (bg.Count > 0) BgFormat.UnpackOriginal(bg, db, workspace, Log);
                    if (scr.Count > 0) ScrFormat.UnpackOriginal(scr, db, workspace, Log);
                });
                SaveConfig();
                RegisterProject(name, select: true);
                Log($"工作区创建完成 -> {workspace}");
                SetStatus($"工作区创建完成：{name}");
                MessageBox.Show(this,
                    $"创建完成 ->\n{workspace}\n\n下一步：到\"提取\"页把要改的 BG 转成 PNG；\n脚本块用 scn.py d/e 处理（original\\scr ↔ modified\\scr）。",
                    "完成", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                SetStatus("创建失败");
                Log("error: " + ex);
                MessageBox.Show(this, "创建失败：\n" + ex.Message, "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally { btnCreate.Enabled = true; }
        }

        // ---------------- 提取页 ----------------

        TabPage BuildExtractTab()
        {
            var page = new TabPage("提取");
            var layout = NewLayout();
            layout.Controls.Add(HintLabel(
                "全部按文件勾选（BG 同款），目录结构也与 BG 平行：\n"
                + "extract\\BGxxx\\ / extract\\cbdNNN\\ / extract\\sysdat\\ / extract\\mvepic\\ / extract\\tit_bg\\…\n"
                + "改哪个文件就把它的 PNG 复制到 modified\\同名文件夹\\；没复制的视为未改动，回包用原始字节。"), 0, 0);
            layout.Controls.Add(clbExtract, 0, 1);

            var buttons = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 4 };
            buttons.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            buttons.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            buttons.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            buttons.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            var btnAll = new Button { Text = "全选", AutoSize = true };
            var btnNone = new Button { Text = "全不选", AutoSize = true };
            btnAll.Click += (s, e) => SetAllChecks(clbExtract, true);
            btnNone.Click += (s, e) => SetAllChecks(clbExtract, false);
            buttons.Controls.Add(btnAll, 0, 0);
            buttons.Controls.Add(btnNone, 1, 0);
            buttons.Controls.Add(new Label(), 2, 0);
            buttons.Controls.Add(btnExtract, 3, 0);
            layout.Controls.Add(buttons, 0, 2);

            page.Controls.Add(layout);
            return page;
        }

        /// <summary>sysdat 一律走工作区：original\ 是原始基准（新建项目从 ISO 切入），
        /// packed\ 是重建前任务的文本版（有则作为图像补丁的 base）。</summary>
        string SysdatOriginal => System.IO.Path.Combine(Workspace, Engine.OriginalDir, "sysdat.bin");
        string SysdatPacked => System.IO.Path.Combine(Workspace, Engine.PackedDir, "sysdat.bin");

        // ---------------- 独立图像文件（不在 ACCESSDB；扫描/回写与 sysdat 同一套代码） ----------------
        // mvepic：游戏只引用盘上 DATA 根目录那份（etc\ 里的拷贝无引用），解包打包都用根目录版。
        internal readonly record struct StandaloneImage(string Key, string Label,
            (string Orig, string Packed)[] Files);
        static readonly StandaloneImage[] Standalones =
        {
            new("mvepic", "mvepic.bin  旅行照片（明文块）", new (string, string)[]
            {
                ("mvepic.bin", "mvepic.bin"),
            }),
            new("tit_bg", "tit_bg.p2x  标题背景（压缩流）", new (string, string)[]
            {
                ("tit_bg.p2x", "etc\\tit_bg.p2x"),
            }),
        };
        string StandaloneOriginal(string origName) =>
            System.IO.Path.Combine(Workspace, Engine.OriginalDir, origName);

        // ---------------- CBD 立绘（9 个独立文件，各自扫描/回写；记录式布局 + RLE 部件） ----------------
        // 提取 -> extract\cbd\cbdNNN\<地址>.png（按文件勾选）；修改 -> modified\cbd\cbdNNN\<地址>.png；
        // 回包 -> packed\CBD\CBDNN0.BIN（路径镜像盘上 DATA\CBD\，改哪个文件回哪个）。
        static readonly string[] CbdFiles = Enumerable.Range(0, 9).Select(i => $"cbd{i}00.bin").ToArray();
        string CbdOriginal(string fileName) => System.IO.Path.Combine(Workspace, Engine.OriginalDir, fileName);
        static string CbdBase(string fileName) => System.IO.Path.GetFileNameWithoutExtension(fileName);

        // ---------------- 提取列表：统一按文件勾选（BG 同款），typed 项避免字符串匹配 ----------------
        internal sealed record ExtractPick(string Display, string Kind, object? Tag);
        readonly List<ExtractPick> extractPicks = new();

        void FillExtractList()
        {
            extractPicks.Clear();
            clbExtract.Items.Clear();
            foreach (WsArchive bin in wsArchives.Where(b => b.Kind.Name == "bg"))
            {
                extractPicks.Add(new ExtractPick(bin.BinName, "bg", bin));
                clbExtract.Items.Add(bin.BinName, false);
            }
            if (File.Exists(SysdatOriginal))
            {
                extractPicks.Add(new ExtractPick("sysdat.bin", "sysdat", null));
                clbExtract.Items.Add("sysdat.bin", false);
            }
            foreach (var st in Standalones)
                if (File.Exists(StandaloneOriginal(st.Files[0].Orig)))
                {
                    extractPicks.Add(new ExtractPick(st.Files[0].Orig, "standalone", st));
                    clbExtract.Items.Add(st.Files[0].Orig, false);
                }
            foreach (string f in CbdFiles)
                if (File.Exists(CbdOriginal(f)))
                {
                    extractPicks.Add(new ExtractPick(f, "cbd", f));
                    clbExtract.Items.Add(f, false);
                }
        }

        async Task RunExtractAsync()
        {
            var bgPicked = new List<WsArchive>();
            var stPicked = new List<StandaloneImage>();
            var cbdPicked = new List<string>();
            bool doSysdat = false;
            foreach (int i in clbExtract.CheckedIndices.Cast<int>())
            {
                if (i >= extractPicks.Count) continue;
                var pick = extractPicks[i];
                switch (pick.Kind)
                {
                    case "bg": bgPicked.Add((WsArchive)pick.Tag!); break;
                    case "sysdat": doSysdat = true; break;
                    case "standalone": stPicked.Add((StandaloneImage)pick.Tag!); break;
                    case "cbd": cbdPicked.Add((string)pick.Tag!); break;
                }
            }
            if (bgPicked.Count == 0 && !doSysdat && stPicked.Count == 0 && cbdPicked.Count == 0)
            { MessageBox.Show("先勾选要提取的内容。", "提示"); return; }
            string workspace = Workspace;
            string accessBackup = System.IO.Path.Combine(workspace, Engine.OriginalDir, "ACCESSDB.BIN");
            if (bgPicked.Count > 0 && !File.Exists(accessBackup))
            { MessageBox.Show("工作区里没有 original\\ACCESSDB.BIN——请先在\"新建项目\"处理。", "提示"); return; }
            if (doSysdat && !File.Exists(SysdatOriginal))
            { MessageBox.Show("工作区里没有 original\\sysdat.bin——请先在\"新建项目\"重新处理。", "提示"); return; }

            btnExtract.Enabled = false;
            SetStatus("提取中…");
            try
            {
                await Task.Run(() =>
                {
                    if (bgPicked.Count > 0)
                    {
                        var db = AccessDb.Load(accessBackup);
                        BgFormat.Extract(bgPicked, db, workspace, Log);
                    }
                    if (doSysdat)
                        SysdatFormat.Extract(SysdatOriginal,
                            System.IO.Path.Combine(workspace, Engine.ExtractDir, "sysdat"), Log);
                    foreach (var st in stPicked)
                        SysdatFormat.Extract(StandaloneOriginal(st.Files[0].Orig),
                            System.IO.Path.Combine(workspace, Engine.ExtractDir, st.Key), Log);
                    foreach (string f in cbdPicked)
                        CbdFormat.Extract(CbdOriginal(f),
                            System.IO.Path.Combine(workspace, Engine.ExtractDir, CbdBase(f)), Log);
                });
                SaveConfig();
                SetStatus("提取完成");
                Log($"提取完成 -> {System.IO.Path.Combine(workspace, Engine.ExtractDir)}");
                MessageBox.Show(this,
                    $"提取完成 ->\n{workspace}\\{Engine.ExtractDir}\n\n把要改的 PNG 复制到 modified\\ 同名子目录去改；\n"
                    + "sysdat 系统图是地址命名（如 0119080.png），文件名就是回写位置；\n脚本块由 scn.py 产出到 modified\\scr\\。",
                    "完成", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                SetStatus("提取失败");
                Log("error: " + ex);
                MessageBox.Show(this, "提取失败：\n" + ex.Message, "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally { btnExtract.Enabled = true; }
        }

        // ---------------- 重建前任务页 ----------------

        TabPage BuildPrePackTab()
        {
            var page = new TabPage("重建前任务");
            var layout = NewLayout();
            layout.Controls.Add(HintLabel(
                "每项目一份，每行一条命令。点击\"开始打包\"后先按顺序执行（工作目录 = 当前工作区），\n"
                + "全部成功才开始回包；任一失败即中止。"), 0, 0);
            layout.Controls.Add(txtPrePack, 0, 1);

            var btnSave = new Button { Text = "保存", Dock = DockStyle.Fill, Height = 30 };
            btnSave.Click += (s, e) => { SavePrePack(); MessageBox.Show(this, "已保存到 kita.ini。", "提示"); };
            layout.Controls.Add(btnSave, 0, 2);

            txtPrePack.TextChanged += (s, e) => SavePrePack(); // 输入即存
            page.Controls.Add(layout);
            return page;
        }

        void LoadPrePackToUi()
        {
            txtPrePack.TextChanged -= OnPrePackEdited;
            txtPrePack.Text = string.Join(Environment.NewLine, cfg.PrePackOf(cfg.CurrentProject));
            txtPrePack.TextChanged += OnPrePackEdited;
        }

        void OnPrePackEdited(object sender, EventArgs e) => SavePrePack();

        void SavePrePack()
        {
            if (cfg.CurrentProject.Length == 0) return;
            cfg.SetPrePack(cfg.CurrentProject, txtPrePack.Lines
                .Select(l => l.Trim())
                .Where(l => l.Length > 0)
                .ToList());
            ScheduleSave();
        }

        /// <summary>按顺序执行重建前命令（cwd=工作区，cmd.exe /C，捕获输出）。任一失败返回 false。</summary>
        (bool Ok, string Log) RunPrePackCommands(string workDir)
        {
            var sb = new System.Text.StringBuilder();
            foreach (string cmd in cfg.PrePackOf(cfg.CurrentProject))
            {
                sb.AppendLine($"[TASK] {cmd}");
                var psi = new System.Diagnostics.ProcessStartInfo
                {
                    FileName = "cmd.exe",
                    Arguments = "/C " + cmd,
                    WorkingDirectory = workDir,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                    StandardOutputEncoding = System.Text.Encoding.UTF8,
                    StandardErrorEncoding = System.Text.Encoding.UTF8,
                };
                try
                {
                    using var p = System.Diagnostics.Process.Start(psi);
                    if (p == null)
                    {
                        sb.AppendLine("[ERROR] 无法启动进程");
                        return (false, sb.ToString().TrimEnd());
                    }
                    string stdout = p.StandardOutput.ReadToEnd();
                    string stderr = p.StandardError.ReadToEnd();
                    p.WaitForExit();
                    if (stdout.Length > 0) sb.AppendLine(stdout.TrimEnd());
                    if (stderr.Length > 0) sb.AppendLine(stderr.TrimEnd());
                    if (p.ExitCode != 0)
                    {
                        sb.AppendLine($"[ERROR] 退出代码 {p.ExitCode}，已中止（未开始回包）");
                        return (false, sb.ToString().TrimEnd());
                    }
                }
                catch (Exception ex)
                {
                    sb.AppendLine("[EXCEPTION] " + ex.Message);
                    return (false, sb.ToString().TrimEnd());
                }
            }
            return (true, sb.ToString().TrimEnd());
        }

        // ---------------- 打包页 ----------------

        TabPage BuildPackTab()
        {
            var page = new TabPage("打包");
            var layout = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 4, Padding = new Padding(10), ColumnCount = 1 };
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));

            layout.Controls.Add(HintLabel(
                "差分打包：modified\\ 里有什么 = 改什么；没有的记录用 original\\ 原始字节（未重压，差分最小）。\n"
                + "输出到 <工作区>\\packed\\（BG\\ SCR\\ sysdat.bin CBD\\ ACCESSDB.BIN），之后点 生成ISO.bat 覆盖回数据目录并出 ISO。\n"
                + "sysdat 图像补丁的 base：有 packed\\sysdat.bin（重建前任务的文本写回）就用它，否则用 original\\ 原始版。"), 0, 0);

            var grpStats = new GroupBox { Dock = DockStyle.Fill, Text = "将要修改的内容（modified\\ 现状）", Padding = new Padding(12, 4, 12, 8) };
            grpStats.Controls.Add(lstWorkStats);
            layout.Controls.Add(grpStats, 0, 1);

            var buttons = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 3 };
            buttons.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            buttons.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            buttons.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            var btnStats = new Button { Text = "刷新统计", AutoSize = true };
            btnStats.Click += (s, e) => { RefreshWorkStats(); SaveConfig(); };
            buttons.Controls.Add(btnStats, 0, 0);
            buttons.Controls.Add(new Label(), 1, 0);
            buttons.Controls.Add(btnPack, 2, 0);
            layout.Controls.Add(buttons, 0, 2);

            page.Controls.Add(layout);
            return page;
        }

        void RefreshWorkStats()
        {
            var items = new List<string>();
            string work = Workspace;
            if (work.Length == 0 || !Directory.Exists(work))
                items.Add("（没有选中的工作区）");
            else
            {
                string modRoot = System.IO.Path.Combine(work, Engine.ModifiedDir);
                var pngRegex = new Regex(@"^\d{4}\.\d+\.png$", RegexOptions.IgnoreCase);
                if (Directory.Exists(modRoot))
                {
                    foreach (string dir in Directory.GetDirectories(modRoot).OrderBy(d => d))
                    {
                        var pngs = Directory.GetFiles(dir, "*.png")
                            .Where(f => pngRegex.IsMatch(System.IO.Path.GetFileName(f)))
                            .OrderBy(f => f).ToList();
                        if (pngs.Count == 0) continue;
                        items.Add($"BG  {System.IO.Path.GetFileName(dir)}：{pngs.Count} 张图");
                        foreach (string f in pngs.Take(3))
                            items.Add($"      {System.IO.Path.GetFileName(f)}");
                        if (pngs.Count > 3) items.Add("      …");
                    }
                    string modScr = System.IO.Path.Combine(modRoot, "scr");
                    if (Directory.Exists(modScr))
                    {
                        var blocks = Directory.GetFiles(modScr, "ev*.bin");
                        if (blocks.Length > 0)
                        {
                            items.Add($"SCR scr：{blocks.Length} 个脚本块");
                            foreach (string f in blocks.OrderBy(f => f).Take(3))
                                items.Add($"      {System.IO.Path.GetFileName(f)}");
                            if (blocks.Length > 3) items.Add("      …");
                        }
                    }
                    string modSys = System.IO.Path.Combine(modRoot, "sysdat");
                    if (Directory.Exists(modSys))
                    {
                        var spngs = Directory.GetFiles(modSys, "*.png", SearchOption.AllDirectories);
                        if (spngs.Length > 0)
                        {
                            items.Add($"SYSDAT sysdat：{spngs.Length} 张系统图（地址命名，存在才改）");
                            foreach (string f in spngs.OrderBy(f => f).Take(3))
                                items.Add($"      {System.IO.Path.GetFileName(f)}");
                            if (spngs.Length > 3) items.Add("      …");
                        }
                    }
                    foreach (var st in Standalones)
                    {
                        string modSt = System.IO.Path.Combine(modRoot, st.Key);
                        if (!Directory.Exists(modSt)) continue;
                        var pngs = Directory.GetFiles(modSt, "*.png", SearchOption.AllDirectories);
                        if (pngs.Length == 0) continue;
                        items.Add($"IMG {st.Key}：{pngs.Length} 张（地址命名）");
                        foreach (string f in pngs.OrderBy(f => f).Take(3))
                            items.Add($"      {System.IO.Path.GetFileName(f)}");
                        if (pngs.Length > 3) items.Add("      …");
                    }
                    foreach (string f in CbdFiles)
                    {
                        string modCbd = System.IO.Path.Combine(modRoot, CbdBase(f));
                        if (!Directory.Exists(modCbd)) continue;
                        var pngs = Directory.GetFiles(modCbd, "*.png", SearchOption.AllDirectories);
                        if (pngs.Length == 0) continue;
                        items.Add($"CBD {CbdBase(f)}：{pngs.Length} 张（地址命名）");
                        foreach (string f2 in pngs.OrderBy(x => x).Take(3))
                            items.Add($"      {System.IO.Path.GetFileName(f2)}");
                        if (pngs.Length > 3) items.Add("      …");
                    }
                }
                if (items.Count == 0)
                    items.Add("（modified\\ 里没有内容——把要改的文件放进去才会被回包）");
            }

            lstWorkStats.BeginUpdate();
            lstWorkStats.Items.Clear();
            foreach (string it in items) lstWorkStats.Items.Add(it);
            lstWorkStats.EndUpdate();
        }

        async Task RunPackAsync()
        {
            string workspace = Workspace;
            string outDir = System.IO.Path.Combine(workspace, Engine.PackedDir);
            string accessBackup = System.IO.Path.Combine(workspace, Engine.OriginalDir, "ACCESSDB.BIN");
            if (workspace.Length == 0 || !Directory.Exists(workspace)) { MessageBox.Show("先选择项目。", "提示"); return; }
            if (!File.Exists(accessBackup))
            { MessageBox.Show("工作区里没有 original\\ACCESSDB.BIN——请先在\"新建项目\"处理。", "提示"); return; }

            btnPack.Enabled = false;
            SetStatus("打包中…");
            try
            {
                // 重建前任务：全部成功才开始回包（命令为空则直接跳过）
                var preCmds = cfg.PrePackOf(cfg.CurrentProject);
                if (preCmds.Count > 0)
                {
                    SetStatus("执行重建前任务…");
                    var pre = await Task.Run(() => RunPrePackCommands(workspace));
                    if (pre.Log.Length > 0) Log(pre.Log);
                    if (!pre.Ok)
                    {
                        SetStatus("重建前任务失败，已中止");
                        MessageBox.Show(this, "重建前任务失败，未开始回包。\n详见日志。", "中止",
                            MessageBoxButtons.OK, MessageBoxIcon.Warning);
                        return;
                    }
                }

                bool any = false;
                await Task.Run(() =>
                {
                    var bins = Engine.DiscoverWorkspace(workspace);
                    if (bins.Count == 0) throw new DirectoryNotFoundException("工作区里没有档案（original\\ 为空？）");
                    var db = AccessDb.Load(accessBackup);
                    var updater = db.BeginUpdate(bins.Select(b => b.Kind.FirstSection + b.SlotIndex));
                    any = BgFormat.Pack(bins.Where(b => b.Kind.Name == "bg").ToList(), db, updater, workspace, outDir, Log)
                        | ScrFormat.Pack(bins.Where(b => b.Kind.Name == "scr").ToList(), db, updater, workspace, outDir, Log);
                    // sysdat 系统图像补丁：base = 重建前任务的文本版（packed\sysdat.bin，
                    // 有则用——顺序天然正确，prepack 刚跑完），否则退回 original\ 原始版；
                    // 存在才改，输出整份文件回 packed\sysdat.bin（生成ISO.bat 统一送回）
                    string sysdatMod = System.IO.Path.Combine(workspace, Engine.ModifiedDir, "sysdat");
                    if (Directory.Exists(sysdatMod) &&
                        Directory.GetFiles(sysdatMod, "*.png", SearchOption.AllDirectories).Length > 0)
                    {
                        string sysBase = File.Exists(SysdatPacked) ? SysdatPacked : SysdatOriginal;
                        if (!File.Exists(sysBase))
                            throw new FileNotFoundException(
                                "original\\sysdat.bin 缺失——请先在\"新建项目\"处理该工作区");
                        Log(sysBase == SysdatPacked
                            ? "sysdat：base = packed\\sysdat.bin（含重建前任务的文本写回）"
                            : "sysdat：base = original\\sysdat.bin（没有文本版，直接用原始版）");
                        SysdatFormat.Pack(sysBase, sysdatMod, SysdatPacked, Log);
                        any = true;
                    }
                    // 独立图像文件：同一批修改分别打到各自的基准上（mvepic 两份拷贝内容不同）
                    foreach (var st in Standalones)
                    {
                        string mod = System.IO.Path.Combine(workspace, Engine.ModifiedDir, st.Key);
                        if (!Directory.Exists(mod) ||
                            Directory.GetFiles(mod, "*.png", SearchOption.AllDirectories).Length == 0)
                            continue;
                        foreach (var (origName, packedRel) in st.Files)
                        {
                            string orig = StandaloneOriginal(origName);
                            if (!File.Exists(orig))
                                throw new FileNotFoundException(
                                    $"original\\{origName} 缺失——请先在\"新建项目\"处理该工作区");
                            string outFile = System.IO.Path.Combine(outDir, packedRel);
                            SysdatFormat.Pack(orig, mod, outFile, Log);
                        }
                        any = true;
                    }
                    // CBD 立绘：每个文件的修改各自回自己的基准（modified\cbdNNN\地址.png，与 BG 平行）
                    foreach (string f in CbdFiles)
                    {
                        string mod = System.IO.Path.Combine(workspace, Engine.ModifiedDir, CbdBase(f));
                        if (!Directory.Exists(mod) ||
                            Directory.GetFiles(mod, "*.png", SearchOption.AllDirectories).Length == 0)
                            continue;
                        string orig = CbdOriginal(f);
                        if (!File.Exists(orig))
                            throw new FileNotFoundException(
                                $"original\\{f} 缺失——请先在\"新建项目\"处理该工作区");
                        string outFile = System.IO.Path.Combine(outDir, "CBD", f.ToUpperInvariant());
                        CbdFormat.Pack(orig, mod, outFile, Log);
                        any = true;
                    }
                    Directory.CreateDirectory(outDir);
                    if (any)
                        updater.Save(System.IO.Path.Combine(outDir, "ACCESSDB.BIN")); // 落盘前自检
                });
                SaveConfig();
                SetStatus(any ? "打包完成" : "没有改动");
                Log(any ? $"打包完成 -> {outDir}" : "没有任何改动，未写出 ACCESSDB.BIN");
                MessageBox.Show(this, any ? $"打包完成 ->\n{outDir}" : "modified\\ 里没有需要回包的改动。",
                    "完成", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                SetStatus("打包失败");
                Log("error: " + ex);
                MessageBox.Show(this, "打包失败：\n" + ex.Message, "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally { btnPack.Enabled = true; }
        }

        // ---------------- 小工具 ----------------

        void ScheduleSave()
        {
            saveTimer.Stop();
            saveTimer.Start();
        }
        readonly System.Windows.Forms.Timer saveTimer = new() { Interval = 600 };

        void SaveConfig()
        {
            cfg.LastPicked = clbNew.CheckedIndices.Cast<int>()
                .Where(i => i < isoArchives.Count)
                .Select(i => isoArchives[i].BinName)
                .ToList();
            cfg.CurrentProject = cmbProjects.SelectedItem as string ?? cfg.CurrentProject;
            cfg.Save();
        }

        void Log(string msg)
        {
            string line = $"[{DateTime.Now:HH:mm:ss}] {msg}";
            if (InvokeRequired)
            {
                BeginInvoke(() => txtLog.AppendText(line + Environment.NewLine));
                return;
            }
            txtLog.AppendText(line + Environment.NewLine);
        }

        void SetStatus(string text)
        {
            if (InvokeRequired)
            {
                BeginInvoke(() => lblStatus.Text = text);
                return;
            }
            lblStatus.Text = text;
        }

        void SetAllChecks(CheckedListBox list, bool state)
        {
            for (int i = 0; i < list.Items.Count; i++)
                list.SetItemChecked(i, state);
        }

        static TableLayoutPanel NewLayout()
        {
            var layout = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 3, Padding = new Padding(10), ColumnCount = 1 };
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));
            return layout;
        }

        static Label HintLabel(string text) => new()
        {
            Dock = DockStyle.Fill, TextAlign = System.Drawing.ContentAlignment.MiddleLeft, AutoSize = true,
            Text = text, ForeColor = System.Drawing.SystemColors.GrayText,
        };
    }
}
