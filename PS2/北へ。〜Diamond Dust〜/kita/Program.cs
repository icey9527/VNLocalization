// Program.cs — kita 入口：纯 GUI（照 GA2，双击即用，无命令行模式）。
// 构建脚本（汉化构建.bat）继续用 KitaAccess.exe，两者互不影响。

using System;
using System.Windows.Forms;

namespace kita
{
    internal static class Program
    {
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new UI.MainForm());
        }
    }
}
