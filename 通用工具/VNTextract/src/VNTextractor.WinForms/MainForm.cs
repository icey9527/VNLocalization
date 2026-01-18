using System.Diagnostics;
using System.Text;
using VNTextractor.Core.Extraction;
using VNTextractor.Core.Export;
using VNTextractor.Core.WriteBack;
using VNTextractor.WinForms.Ini;

namespace VNTextractor.WinForms;

public sealed class MainForm : Form
{
    private readonly TabControl _tabs = new() { Dock = DockStyle.Fill };
    private readonly TextBox _log = new()
    {
        Multiline = true,
        ReadOnly = true,
        ScrollBars = ScrollBars.Both,
        WordWrap = false,
        Dock = DockStyle.Fill
    };

    // Export tab controls
    private readonly TextBox _expInputDir = new() { Anchor = AnchorStyles.Left | AnchorStyles.Right };
    private readonly Button _expBrowseInput = new() { Text = "浏览", Width = 72, Height = 28 };

    private readonly CheckBox _expMerge = new() { Text = "合并(输出=文件)", AutoSize = true };
    private readonly TextBox _expOutput = new() { Anchor = AnchorStyles.Left | AnchorStyles.Right };
    private readonly Button _expBrowseOutput = new() { Text = "浏览", Width = 72, Height = 28 };

    private readonly ComboBox _expEncoding = new() { DropDownStyle = ComboBoxStyle.DropDownList };
    private readonly ComboBox _expFormat = new() { DropDownStyle = ComboBoxStyle.DropDownList };

    private readonly CheckBox _expSkipSemicolon = new() { Text = "跳过注释 ;", AutoSize = true };
    private readonly CheckBox _expSkipSlash = new() { Text = "跳过注释 // (含行内)", AutoSize = true };

    private readonly Button _expRun = new() { Text = "导出", Width = 96, Height = 32, Anchor = AnchorStyles.Right };

    // Import tab controls
    private readonly TextBox _impSourceDir = new() { Anchor = AnchorStyles.Left | AnchorStyles.Right };
    private readonly Button _impBrowseSource = new() { Text = "浏览", Width = 72, Height = 28 };

    private readonly CheckBox _impMerge = new() { Text = "合并(输入=文件)", AutoSize = true };
    private readonly TextBox _impInput = new() { Anchor = AnchorStyles.Left | AnchorStyles.Right };
    private readonly Button _impBrowseInput = new() { Text = "浏览", Width = 72, Height = 28 };
    private readonly ComboBox _impFormat = new() { DropDownStyle = ComboBoxStyle.DropDownList };

    private readonly TextBox _impOutputDir = new() { Anchor = AnchorStyles.Left | AnchorStyles.Right };
    private readonly Button _impBrowseOutput = new() { Text = "浏览", Width = 72, Height = 28 };

    private readonly ComboBox _impSourceEncoding = new() { DropDownStyle = ComboBoxStyle.DropDownList };
    private readonly ComboBox _impOutputEncoding = new() { DropDownStyle = ComboBoxStyle.DropDownList };

    private readonly Button _impRun = new() { Text = "写回", Width = 96, Height = 32, Anchor = AnchorStyles.Right };

    private readonly StatusStrip _status = new();
    private readonly ToolStripStatusLabel _statusLabel = new() { Text = "Ready" };

    private sealed record EncodingChoice(string Label, Encoding Encoding);
    private sealed record FormatChoice(string Label, ExportFormat Format);

    private enum ExportFormat
    {
        AllTxt,
        DlTxt,
        ParatranzJson
    }

    private readonly string _iniPath;
    private IniFile _ini = new();
    private bool _loading = true; // prevent config overwrite during WinForms binding

    public MainForm()
    {
        Text = "VNTextractor";
        MinimumSize = new Size(860, 520);
        StartPosition = FormStartPosition.CenterScreen;

        _iniPath = Path.Combine(AppContext.BaseDirectory, $"{GetExeBaseName()}.ini");

        _status.Items.Add(_statusLabel);
        _status.SizingGrip = false;

        BuildExportTab();
        BuildImportTab();

        var split = new SplitContainer
        {
            Dock = DockStyle.Fill,
            Orientation = Orientation.Horizontal,
            SplitterDistance = 340,
            Panel2MinSize = 120
        };
        split.Panel1.Controls.Add(_tabs);
        split.Panel2.Controls.Add(_log);

        Controls.Add(split);
        Controls.Add(_status);

        // WinForms ComboBox with DataSource may reset selection during handle creation.
        // Load/Apply INI after the form is shown so selections stick.
        Shown += delegate
        {
            LoadConfig();
            UpdateExportOutputUi(force: true);
            BeginInvoke(delegate
            {
                // Second pass: some bindings finalize right after Shown.
                LoadConfig();
                UpdateExportOutputUi(force: false);
            });
        };
    }

    private static string GetExeBaseName()
    {
        try
        {
            var p = Process.GetCurrentProcess().ProcessName;
            return string.IsNullOrWhiteSpace(p) ? "VNTextractor" : p;
        }
        catch
        {
            return "VNTextractor";
        }
    }

    private void BuildExportTab()
    {
        var tab = new TabPage("导出");

        _expBrowseInput.Click += (_, _) => BrowseFolder(_expInputDir);
        _expBrowseOutput.Click += (_, _) => BrowseExportOutput();
        _expRun.Click += async (_, _) => await ExportAsync();

        _expMerge.CheckedChanged += (_, _) =>
        {
            if (_loading) return;
            UpdateExportOutputUi(force: true);
            SaveConfig();
        };
        _expFormat.SelectedIndexChanged += (_, _) =>
        {
            if (_loading) return;
            UpdateExportOutputUi(force: true);
            SaveConfig();
        };
        _expEncoding.SelectedIndexChanged += (_, _) => SaveConfig();
        _expSkipSemicolon.CheckedChanged += (_, _) => SaveConfig();
        _expSkipSlash.CheckedChanged += (_, _) => SaveConfig();
        _expInputDir.TextChanged += (_, _) => SaveConfig();
        _expOutput.TextChanged += (_, _) => SaveConfig(); // SaveConfig will store to outputDir/outputFile depending on merge

        var encChoices = new[]
        {
            new EncodingChoice("cp932 (Shift-JIS)", Encoding.GetEncoding(932)),
            new EncodingChoice("cp936 (GBK)", Encoding.GetEncoding(936)),
            new EncodingChoice("UTF-8", new UTF8Encoding(encoderShouldEmitUTF8Identifier: false)),
            new EncodingChoice("UTF-16 (LE)", Encoding.Unicode),
            new EncodingChoice("UTF-16 (BE)", Encoding.BigEndianUnicode),
        };
        _expEncoding.DisplayMember = nameof(EncodingChoice.Label);
        _expEncoding.DataSource = encChoices;
        if (_expEncoding.Items.Count > 0) _expEncoding.SelectedIndex = 0;

        var formats = new[]
        {
            new FormatChoice("alltxt (+ lines.txt)", ExportFormat.AllTxt),
            new FormatChoice("dltxt (双行)", ExportFormat.DlTxt),
            new FormatChoice("Paratranz JSON", ExportFormat.ParatranzJson),
        };
        _expFormat.DisplayMember = nameof(FormatChoice.Label);
        _expFormat.DataSource = formats;
        if (_expFormat.Items.Count > 0) _expFormat.SelectedIndex = 0;

        var root = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 3,
            RowCount = 6,
            Padding = new Padding(10),
        };
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 110));
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 78));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 30));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));

        root.Controls.Add(new Label { Text = "输入文件夹", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill }, 0, 0);
        root.Controls.Add(_expInputDir, 1, 0);
        root.Controls.Add(_expBrowseInput, 2, 0);

        root.Controls.Add(new Label { Text = "输出", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill }, 0, 2);
        root.Controls.Add(_expOutput, 1, 2);
        root.Controls.Add(_expBrowseOutput, 2, 2);

        root.Controls.Add(new Label { Text = "合并", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill }, 0, 1);
        root.Controls.Add(_expMerge, 1, 1);
        root.SetColumnSpan(_expMerge, 2);

        root.Controls.Add(new Label { Text = "输入编码", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill }, 0, 3);
        root.Controls.Add(_expEncoding, 1, 3);
        root.SetColumnSpan(_expEncoding, 2);

        root.Controls.Add(new Label { Text = "导出格式", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill }, 0, 4);
        root.Controls.Add(_expFormat, 1, 4);
        root.SetColumnSpan(_expFormat, 2);

        var opts = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, WrapContents = false };
        opts.Controls.Add(_expSkipSemicolon);
        opts.Controls.Add(_expSkipSlash);
        root.Controls.Add(new Label { Text = "", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill }, 0, 5);
        root.Controls.Add(opts, 1, 5);
        root.Controls.Add(_expRun, 2, 5);

        tab.Controls.Add(root);
        _tabs.TabPages.Add(tab);
    }

    private void BuildImportTab()
    {
        var tab = new TabPage("导入(写回)");

        _impBrowseSource.Click += (_, _) => BrowseFolder(_impSourceDir);
        _impMerge.CheckedChanged += (_, _) =>
        {
            if (_loading) return;
            UpdateImportInputUi(force: true);
            SaveConfig();
        };
        _impBrowseInput.Click += (_, _) => BrowseImportInput();
        _impBrowseOutput.Click += (_, _) => BrowseFolder(_impOutputDir);
        _impRun.Click += async (_, _) => await ImportAsync();

        _impSourceDir.TextChanged += (_, _) => SaveConfig();
        _impInput.TextChanged += (_, _) => SaveConfig(); // SaveConfig will store to inputDir/inputFile depending on merge
        _impOutputDir.TextChanged += (_, _) => SaveConfig();
        _impSourceEncoding.SelectedIndexChanged += (_, _) => SaveConfig();
        _impOutputEncoding.SelectedIndexChanged += (_, _) => SaveConfig();
        // Don't reset user-chosen path when switching format; only adjust if needed.
        _impFormat.SelectedIndexChanged += (_, _) =>
        {
            if (_loading) return;
            UpdateImportInputUi(force: false);
            SaveConfig();
        };

        var encChoices = new[]
        {
            new EncodingChoice("cp932 (Shift-JIS)", Encoding.GetEncoding(932)),
            new EncodingChoice("cp936 (GBK)", Encoding.GetEncoding(936)),
            new EncodingChoice("UTF-8", new UTF8Encoding(encoderShouldEmitUTF8Identifier: false)),
            new EncodingChoice("UTF-16 (LE)", Encoding.Unicode),
            new EncodingChoice("UTF-16 (BE)", Encoding.BigEndianUnicode),
        };

        _impSourceEncoding.DisplayMember = nameof(EncodingChoice.Label);
        _impSourceEncoding.DataSource = encChoices;
        if (_impSourceEncoding.Items.Count > 0) _impSourceEncoding.SelectedIndex = 0;

        var outEncChoices = new[]
        {
            new EncodingChoice("UTF-16 (LE)", Encoding.Unicode),
            new EncodingChoice("UTF-16 (BE)", Encoding.BigEndianUnicode),
            new EncodingChoice("UTF-8", new UTF8Encoding(encoderShouldEmitUTF8Identifier: false)),
        };
        _impOutputEncoding.DisplayMember = nameof(EncodingChoice.Label);
        _impOutputEncoding.DataSource = outEncChoices;
        if (_impOutputEncoding.Items.Count > 0) _impOutputEncoding.SelectedIndex = 0;

        var formats = new[]
        {
            new FormatChoice("alltxt (+ lines.txt)", ExportFormat.AllTxt),
            new FormatChoice("dltxt (双行)", ExportFormat.DlTxt),
            new FormatChoice("Paratranz JSON", ExportFormat.ParatranzJson),
        };
        _impFormat.DisplayMember = nameof(FormatChoice.Label);
        _impFormat.DataSource = formats;
        if (_impFormat.Items.Count > 0) _impFormat.SelectedIndex = 0;

        var root = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 3,
            RowCount = 6,
            Padding = new Padding(10),
        };
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 110));
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 78));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));

        root.Controls.Add(new Label { Text = "源文件夹", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill }, 0, 0);
        root.Controls.Add(_impSourceDir, 1, 0);
        root.Controls.Add(_impBrowseSource, 2, 0);

        root.Controls.Add(new Label { Text = "导入格式", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill }, 0, 1);
        root.Controls.Add(_impFormat, 1, 1);
        root.SetColumnSpan(_impFormat, 2);

        root.Controls.Add(new Label { Text = "合并", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill }, 0, 2);
        root.Controls.Add(_impMerge, 1, 2);
        root.SetColumnSpan(_impMerge, 2);

        root.Controls.Add(new Label { Text = "输入", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill }, 0, 3);
        root.Controls.Add(_impInput, 1, 3);
        root.Controls.Add(_impBrowseInput, 2, 3);

        root.Controls.Add(new Label { Text = "输出文件夹", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill }, 0, 4);
        root.Controls.Add(_impOutputDir, 1, 4);
        root.Controls.Add(_impBrowseOutput, 2, 4);

        var encPanel = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, WrapContents = false };
        encPanel.Controls.Add(new Label { Text = "源编码", AutoSize = true, TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(0, 6, 6, 0) });
        encPanel.Controls.Add(_impSourceEncoding);
        encPanel.Controls.Add(new Label { Text = "输出编码", AutoSize = true, TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(12, 6, 6, 0) });
        encPanel.Controls.Add(_impOutputEncoding);

        root.Controls.Add(new Label { Text = "", TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill }, 0, 5);
        root.Controls.Add(encPanel, 1, 5);
        root.Controls.Add(_impRun, 2, 5);

        tab.Controls.Add(root);
        _tabs.TabPages.Add(tab);
    }

    private void BrowseFolder(TextBox target)
    {
        using var dlg = new FolderBrowserDialog { SelectedPath = target.Text };
        if (dlg.ShowDialog(this) == DialogResult.OK)
            target.Text = dlg.SelectedPath;
    }

    private void BrowseImportInput()
    {
        if (_impMerge.Checked)
        {
            var fmt = ((FormatChoice)_impFormat.SelectedItem!).Format;
            var filter = fmt == ExportFormat.ParatranzJson ? "JSON|*.json|All files|*.*" : "Text|*.txt|All files|*.*";
            using var dlg = new OpenFileDialog { Filter = filter };
            if (File.Exists(_impInput.Text))
                dlg.InitialDirectory = Path.GetDirectoryName(_impInput.Text);
            if (dlg.ShowDialog(this) == DialogResult.OK)
                _impInput.Text = dlg.FileName;
        }
        else
        {
            BrowseFolder(_impInput);
        }
    }

    private void BrowseExportOutput()
    {
        if (_expMerge.Checked)
        {
            var (defName, filter) = GetMergedOutputSuggestion();
            using var dlg = new SaveFileDialog
            {
                Filter = filter,
                FileName = defName,
            };
            if (File.Exists(_expOutput.Text))
                dlg.InitialDirectory = Path.GetDirectoryName(_expOutput.Text);
            if (Directory.Exists(_expOutput.Text))
                dlg.InitialDirectory = _expOutput.Text;

            if (dlg.ShowDialog(this) == DialogResult.OK)
                _expOutput.Text = dlg.FileName;
        }
        else
        {
            BrowseFolder(_expOutput);
        }
    }

    private (string FileName, string Filter) GetMergedOutputSuggestion()
    {
        if (_expFormat.SelectedItem is not FormatChoice fmtChoice)
            return ("all.txt", "Text|*.txt|All files|*.*");
        var fmt = fmtChoice.Format;
        return fmt switch
        {
            ExportFormat.ParatranzJson => ("all.json", "JSON|*.json|All files|*.*"),
            _ => ("all.txt", "Text|*.txt|All files|*.*"),
        };
    }

    private void UpdateExportOutputUi(bool force)
    {
        if (_expMerge.Checked)
        {
            var (defName, _) = GetMergedOutputSuggestion();
            var cur = _expOutput.Text.Trim();

            // If switching to merged mode, always make it a file path unless user already set a file.
            if (force || string.IsNullOrWhiteSpace(cur) || Directory.Exists(cur) || !Path.HasExtension(cur))
            {
                // Prefer last saved merged output file from INI.
                var saved = _ini.Get("export", "outputFile");
                _expOutput.Text = !string.IsNullOrWhiteSpace(saved) ? saved : Path.Combine(Environment.CurrentDirectory, defName);
            }
            else
                _expOutput.Text = Path.ChangeExtension(cur, Path.GetExtension(defName));
        }
        else
        {
            var cur = _expOutput.Text.Trim();
            if (force || string.IsNullOrWhiteSpace(cur) || File.Exists(cur) || Path.HasExtension(cur))
            {
                // Prefer last saved split output directory from INI.
                var saved = _ini.Get("export", "outputDir");
                _expOutput.Text = !string.IsNullOrWhiteSpace(saved) ? saved : Path.Combine(Environment.CurrentDirectory, "out");
            }
        }
    }

    private void UpdateImportInputUi(bool force)
    {
        if (_impFormat.SelectedItem is not FormatChoice fmtChoice)
            return;
        var fmt = fmtChoice.Format;
        if (_impMerge.Checked)
        {
            var defName = fmt == ExportFormat.ParatranzJson ? "all.json" : "all.txt";
            var cur = _impInput.Text.Trim();
            if (force || string.IsNullOrWhiteSpace(cur) || Directory.Exists(cur) || !Path.HasExtension(cur))
            {
                var saved = _ini.Get("import", "inputFile");
                _impInput.Text = !string.IsNullOrWhiteSpace(saved) ? saved : Path.Combine(Environment.CurrentDirectory, defName);
                return;
            }

            // Keep the user's chosen path; only normalize extension if needed.
            var expectedExt = Path.GetExtension(defName);
            if (!cur.EndsWith(expectedExt, StringComparison.OrdinalIgnoreCase))
                _impInput.Text = Path.ChangeExtension(cur, expectedExt);
        }
        else
        {
            var cur = _impInput.Text.Trim();
            if (force || string.IsNullOrWhiteSpace(cur))
            {
                var saved = _ini.Get("import", "inputDir");
                _impInput.Text = !string.IsNullOrWhiteSpace(saved) ? saved : Path.Combine(Environment.CurrentDirectory, "in");
            }
        }
    }

    private async Task ExportAsync()
    {
        _log.Clear();
        var inputDir = _expInputDir.Text;
        if (!Directory.Exists(inputDir))
        {
            MessageBox.Show(this, "输入文件夹不存在。", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }

        var outValue = _expOutput.Text;
        if (string.IsNullOrWhiteSpace(outValue))
        {
            MessageBox.Show(this, "输出不能为空。", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }

        var encoding = ((EncodingChoice)_expEncoding.SelectedItem!).Encoding;
        var fmt = ((FormatChoice)_expFormat.SelectedItem!).Format;
        var merge = _expMerge.Checked;

        // Avoid creating a directory named "all.txt" / "all.json" in split mode.
        if (!merge && Path.HasExtension(outValue))
        {
            MessageBox.Show(this, "分开导出时，“输出”必须是文件夹路径（不要填 all.txt/all.json）。", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        if (merge && Directory.Exists(outValue))
        {
            MessageBox.Show(this, "合并导出时，“输出”必须是文件路径（例如 all.txt / all.json）。", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }

        SetStatus("Working...");
        SetUiEnabled(false);

        try
        {
            var total = 0;
            var totalFiles = 0;
            await Task.Run(() =>
            {
                var extractor = new TextDirectoryExtractor();

                var skipDir = merge
                    ? Path.GetDirectoryName(Path.GetFullPath(outValue))
                    : outValue;

                Log($"[Export] InputDir={Path.GetFullPath(inputDir)}");
                Log($"[Export] Output={(merge ? Path.GetFullPath(outValue) : Path.GetFullPath(outValue))}");
                Log($"[Export] Merge={merge} Format={fmt} Encoding={GetEncodingKey(encoding)} (codepage={encoding.CodePage}, webName={encoding.WebName})");

                var extractOptions = new ExtractOptions
                {
                    InputEncoding = encoding,
                    SkipSemicolonComments = _expSkipSemicolon.Checked,
                    SkipDoubleSlashComments = _expSkipSlash.Checked,
                };

                var result = extractor.Extract(inputDir, skipDir, extractOptions);
                total = result.TotalItemCount;
                totalFiles = result.ItemsByFile.Count;
                Log($"[Export] ScannedFiles={totalFiles} ExtractedLines={total}");

                if (merge)
                {
                    var outFile = Path.GetFullPath(outValue);
                    switch (fmt)
                    {
                        case ExportFormat.AllTxt:
                            new AllTxtExporter().ExportMergedToFile(outFile, result);
                            break;
                        case ExportFormat.DlTxt:
                            new DlTxtExporter().ExportMergedToFile(outFile, result);
                            break;
                        case ExportFormat.ParatranzJson:
                            new ParatranzJsonExporter().ExportMergedToFile(outFile, result);
                            break;
                    }
                    Log($"[Export] WroteFile={outFile}");
                }
                else
                {
                    Directory.CreateDirectory(outValue);
                    var exportOptions = new ExportOptions { MergeOutput = false };

                    switch (fmt)
                    {
                        case ExportFormat.AllTxt:
                            new AllTxtExporter().Export(outValue, result, exportOptions);
                            break;
                        case ExportFormat.DlTxt:
                            new DlTxtExporter().Export(outValue, result, exportOptions);
                            break;
                        case ExportFormat.ParatranzJson:
                            new ParatranzJsonExporter().Export(outValue, result, exportOptions);
                            break;
                    }
                    Log($"[Export] WroteDir={Path.GetFullPath(outValue)}");
                }
            });

            SetStatus("Done.");
            if (total == 0)
                MessageBox.Show(this, "提取完成，但没有匹配到任何文本。\n常见原因：输入编码选错 / 全是注释 / 文件不含日文字符。", "提示", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (FileNotFoundException ex)
        {
            MessageBox.Show(this, ex.Message, "缺少文件/模式不匹配", MessageBoxButtons.OK, MessageBoxIcon.Error);
            SetStatus("Error.");
        }
        catch (InvalidDataException ex)
        {
            MessageBox.Show(this, ex.Message, "格式错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            SetStatus("Error.");
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, ex.ToString(), "异常", MessageBoxButtons.OK, MessageBoxIcon.Error);
            SetStatus("Error.");
        }
        finally
        {
            SetUiEnabled(true);
        }
    }

    private async Task ImportAsync()
    {
        _log.Clear();
        var sourceDir = _impSourceDir.Text;
        if (!Directory.Exists(sourceDir))
        {
            MessageBox.Show(this, "源文件夹不存在。", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }

        var fmt = ((FormatChoice)_impFormat.SelectedItem!).Format;
        var input = _impInput.Text;
        if (_impMerge.Checked)
        {
            if (!File.Exists(input))
            {
                MessageBox.Show(this, "导入文件不存在。", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
        }
        else
        {
            if (!Directory.Exists(input))
            {
                MessageBox.Show(this, "导入文件夹不存在。", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
        }

        var outputDir = _impOutputDir.Text;
        if (string.IsNullOrWhiteSpace(outputDir))
        {
            MessageBox.Show(this, "输出文件夹不能为空。", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }

        var srcEnc = ((EncodingChoice)_impSourceEncoding.SelectedItem!).Encoding;
        var outEnc = ((EncodingChoice)_impOutputEncoding.SelectedItem!).Encoding;

        SetStatus("Working...");
        SetUiEnabled(false);

        try
        {
            await Task.Run(() =>
            {
                Log($"[Import] SourceDir={Path.GetFullPath(sourceDir)}");
                Log($"[Import] Input={Path.GetFullPath(input)} Merge={_impMerge.Checked} Format={fmt}");
                Log($"[Import] SourceEnc={srcEnc.WebName} OutputEnc={outEnc.WebName}");

                switch (fmt)
                {
                    case ExportFormat.AllTxt:
                    {
                        string linesTxtPath;
                        if (_impMerge.Checked)
                        {
                            var dir = Path.GetDirectoryName(Path.GetFullPath(input))!;
                            linesTxtPath = Path.Combine(dir, "lines.txt");
                        }
                        else
                        {
                            linesTxtPath = Path.Combine(Path.GetFullPath(input), "lines.txt");
                        }

                        if (!File.Exists(linesTxtPath))
                            throw new FileNotFoundException($"lines.txt not found: {linesTxtPath}\n(你可能选错了导入格式：如果是 dltxt/json，请把“导入格式”切换过去)");

                        TextWriteBack.WriteBackAllTxt(
                            sourceDir,
                            linesTxtPath,
                            outputDir,
                            new TextWriteBack.WriteBackOptions { SourceEncoding = srcEnc, OutputEncoding = outEnc }
                        );
                        Log($"[Import] alltxt lines.txt = {linesTxtPath}");
                        break;
                    }
                    case ExportFormat.DlTxt:
                    {
                        int applied;
                        if (_impMerge.Checked)
                            applied = DlTxtWriteBack.WriteBackMerged(sourceDir, input, outputDir, srcEnc, outEnc, Log);
                        else
                            applied = DlTxtWriteBack.WriteBackSplit(sourceDir, input, outputDir, srcEnc, outEnc, Log);

                        if (applied == 0)
                            throw new InvalidDataException("未找到可写回的 dltxt 文件。\n提示：dltxt 分开导出文件必须是包含 '#行号/◇/◆' 结构的 .txt；如果目录里是 alltxt 的纯文本，会被跳过。\n建议：导出 dltxt 到一个单独的输出目录，再用该目录写回。");

                        Log($"[Import] dltxt writeback finished. FilesApplied={applied}");
                        break;
                    }
                    case ExportFormat.ParatranzJson:
                    {
                        int applied;
                        if (_impMerge.Checked)
                            applied = ParatranzWriteBack.WriteBackMerged(sourceDir, input, outputDir, srcEnc, outEnc, Log);
                        else
                            applied = ParatranzWriteBack.WriteBackSplit(sourceDir, input, outputDir, srcEnc, outEnc, Log);

                        if (applied == 0)
                            throw new InvalidDataException("未找到可写回的 Paratranz JSON。\n提示：JSON 写回按 stage 决定替换内容：stage=1 用 translation，否则用 original。\n请确认输入目录/文件是本工具导出的 paratranz JSON。");

                        Log($"[Import] json writeback finished. FilesApplied={applied}");
                        break;
                    }
                }
            });

            SetStatus("Done.");
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, ex.ToString(), "异常", MessageBoxButtons.OK, MessageBoxIcon.Error);
            SetStatus("Error.");
        }
        finally
        {
            SetUiEnabled(true);
        }
    }

    private void SetUiEnabled(bool enabled)
    {
        _tabs.Enabled = enabled;
    }

    private void SetStatus(string s)
    {
        if (IsDisposed) return;
        BeginInvoke(() => _statusLabel.Text = s);
    }

    private void Log(string s)
    {
        if (IsDisposed) return;
        BeginInvoke(() =>
        {
            _log.AppendText(s);
            _log.AppendText(Environment.NewLine);
        });
    }

    private void LoadConfig()
    {
        _loading = true;
        try
        {
            _ini = IniFile.Load(_iniPath);

            _expInputDir.Text = _ini.Get("export", "inputDir") ?? Environment.CurrentDirectory;
            _expMerge.Checked = _ini.GetBool("export", "merge", false);
            // Separate persisted paths for merge/split; keep backward compatibility with old "output".
            var legacyExportOutput = _ini.Get("export", "output");
            var exportDir = _ini.Get("export", "outputDir") ?? legacyExportOutput;
            var exportFile = _ini.Get("export", "outputFile") ?? legacyExportOutput;
            _expOutput.Text = _expMerge.Checked
                ? (exportFile ?? Path.Combine(Environment.CurrentDirectory, "all.txt"))
                : (exportDir ?? Path.Combine(Environment.CurrentDirectory, "out"));
            _expSkipSemicolon.Checked = _ini.GetBool("export", "skipSemicolon", false);
            _expSkipSlash.Checked = _ini.GetBool("export", "skipSlash", false);

            var expEnc = _ini.Get("export", "encoding") ?? "cp932";
            SelectEncoding(_expEncoding, expEnc);

            var fmt = _ini.GetInt("export", "format", 0);
            if (fmt >= 0 && fmt < _expFormat.Items.Count)
                _expFormat.SelectedIndex = fmt;

            _impSourceDir.Text = _ini.Get("import", "sourceDir") ?? Environment.CurrentDirectory;
            _impOutputDir.Text = _ini.Get("import", "outputDir") ?? Path.Combine(Environment.CurrentDirectory, "out_writeback");
            _impMerge.Checked = _ini.GetBool("import", "merge", false);
            // Separate persisted paths for merge/split; keep backward compatibility with old "input".
            var legacyImportInput = _ini.Get("import", "input");
            var inputDir = _ini.Get("import", "inputDir") ?? legacyImportInput;
            var inputFile = _ini.Get("import", "inputFile") ?? legacyImportInput;
            _impInput.Text = _impMerge.Checked ? (inputFile ?? "") : (inputDir ?? "");

            var impFmt = _ini.GetInt("import", "format", 0);
            if (impFmt >= 0 && impFmt < _impFormat.Items.Count)
                _impFormat.SelectedIndex = impFmt;

            var impSrcEnc = _ini.Get("import", "sourceEncoding") ?? "cp932";
            SelectEncoding(_impSourceEncoding, impSrcEnc);

            var impOutEnc = _ini.Get("import", "outputEncoding") ?? "utf-16";
            SelectEncoding(_impOutputEncoding, impOutEnc);
        }
        finally
        {
            _loading = false;
            UpdateImportInputUi(force: false);
            UpdateExportOutputUi(force: false);
        }
    }

    private void SaveConfig()
    {
        if (_loading)
            return;

        try
        {
            _ini.Set("export", "inputDir", _expInputDir.Text);
            // Store merge/split outputs separately so toggling merge restores last value.
            if (_expMerge.Checked)
                _ini.Set("export", "outputFile", _expOutput.Text);
            else
                _ini.Set("export", "outputDir", _expOutput.Text);
            _ini.Set("export", "merge", _expMerge.Checked ? "1" : "0");
            _ini.Set("export", "skipSemicolon", _expSkipSemicolon.Checked ? "1" : "0");
            _ini.Set("export", "skipSlash", _expSkipSlash.Checked ? "1" : "0");
            _ini.Set("export", "encoding", GetEncodingKey(((EncodingChoice)_expEncoding.SelectedItem!).Encoding));
            _ini.Set("export", "format", _expFormat.SelectedIndex.ToString());

            _ini.Set("import", "sourceDir", _impSourceDir.Text);
            if (_impMerge.Checked)
                _ini.Set("import", "inputFile", _impInput.Text);
            else
                _ini.Set("import", "inputDir", _impInput.Text);
            _ini.Set("import", "outputDir", _impOutputDir.Text);
            _ini.Set("import", "merge", _impMerge.Checked ? "1" : "0");
            _ini.Set("import", "format", _impFormat.SelectedIndex.ToString());
            _ini.Set("import", "sourceEncoding", GetEncodingKey(((EncodingChoice)_impSourceEncoding.SelectedItem!).Encoding));
            _ini.Set("import", "outputEncoding", GetEncodingKey(((EncodingChoice)_impOutputEncoding.SelectedItem!).Encoding));

            _ini.Save(_iniPath);
        }
        catch
        {
            // Don't break the UI if config can't be written.
        }
    }

    private static void SelectEncoding(ComboBox combo, string key)
    {
        key = key.Trim().ToLowerInvariant();
        for (var i = 0; i < combo.Items.Count; i++)
        {
            var enc = ((EncodingChoice)combo.Items[i]!).Encoding;
            if (GetEncodingKey(enc) == key)
            {
                combo.SelectedIndex = i;
                return;
            }
        }
    }

    private static string GetEncodingKey(Encoding enc)
    {
        if (enc.CodePage == 932) return "cp932";
        if (enc.CodePage == 936) return "cp936";
        if (enc is UTF8Encoding) return "utf-8";
        if (enc.CodePage == Encoding.Unicode.CodePage) return "utf-16";
        if (enc.CodePage == Encoding.BigEndianUnicode.CodePage) return "utf-16be";
        return enc.WebName;
    }
}
