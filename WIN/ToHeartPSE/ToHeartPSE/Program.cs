using System.Text;

namespace ToHeartPSE;

internal static class Program
{
    static int Main(string[] args)
    {
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);

        try
        {
            if (args.Length < 2 || HasHelp(args))
            {
                PrintHelp();
                return args.Length < 2 ? 1 : 0;
            }

            if (HasList(args))
            {
                PrintTransformers();
                return 0;
            }

            string a0 = args[0];
            string a1 = args[1];

            if (!TryGetXformSpec(args, out string spec, out string err))
            {
                Console.WriteLine(err);
                PrintHelp();
                return 1;
            }

            if (!Transformers.TryConfigure(spec, out string cfgErr))
            {
                Console.WriteLine(cfgErr);
                PrintHelp();
                return 1;
            }

            bool a0IsPak = string.Equals(Path.GetExtension(a0), ".pak", StringComparison.OrdinalIgnoreCase);
            bool a1IsPak = string.Equals(Path.GetExtension(a1), ".pak", StringComparison.OrdinalIgnoreCase);

            if (a0IsPak && !a1IsPak)
            {
                string pakPath = Path.GetFullPath(a0);
                string outDir = Path.GetFullPath(a1);
                Directory.CreateDirectory(outDir);
                App.Unpack(pakPath, outDir);
                return 0;
            }

            if (!a0IsPak && a1IsPak)
            {
                string inDir = Path.GetFullPath(a0);
                string pakPath = Path.GetFullPath(a1);
                if (!Directory.Exists(inDir))
                {
                    Console.WriteLine("input directory does not exist: " + inDir);
                    return 1;
                }
                App.Pack(inDir, pakPath);
                return 0;
            }

            Console.WriteLine("arguments are ambiguous:");
            Console.WriteLine("  if the first argument is .pak and the second is a directory = unpack");
            Console.WriteLine("  if the first argument is a directory and the second is .pak = pack");
            PrintHelp();
            return 1;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("error: " + ex.Message);
            return 1;
        }
    }

    static bool HasHelp(string[] args)
    {
        foreach (string a in args)
            if (a is "-h" or "--help" or "/?" or "help")
                return true;
        return false;
    }

    static bool HasList(string[] args)
    {
        foreach (string a in args)
            if (a is "--list-xform" or "--list-transform" or "--list")
                return true;
        return false;
    }

    static bool TryGetXformSpec(string[] args, out string spec, out string error)
    {
        spec = "all";
        error = "";

        for (int i = 2; i < args.Length; i++)
        {
            string a = args[i];

            if (a.StartsWith("--xform=", StringComparison.OrdinalIgnoreCase) ||
                a.StartsWith("--transform=", StringComparison.OrdinalIgnoreCase))
            {
                spec = a[(a.IndexOf('=') + 1)..];
                continue;
            }

            if (a.Equals("--xform", StringComparison.OrdinalIgnoreCase) ||
                a.Equals("--transform", StringComparison.OrdinalIgnoreCase) ||
                a.Equals("-x", StringComparison.OrdinalIgnoreCase))
            {
                if (i + 1 >= args.Length)
                {
                    error = $"missing value for argument: {a}";
                    return false;
                }
                spec = args[++i];
                continue;
            }

            if (a is "--list-xform" or "--list-transform" or "--list" or "-h" or "--help" or "/?" or "help")
                continue;

            error = $"unknown argument: {a}";
            return false;
        }

        return true;
    }

    static void PrintTransformers()
    {
        Console.WriteLine("available transformers:");
        foreach (string n in Transformers.Available)
            Console.WriteLine("  " + n);
    }

    static void PrintHelp()
    {
        Console.WriteLine("usage:");
        Console.WriteLine("  ToHeartPSE <xxx.pak> <directory>");
        Console.WriteLine("  ToHeartPSE <directory> <xxx.pak>");
        Console.WriteLine();
        Console.WriteLine("options:");
        Console.WriteLine("  --xform=<spec>");
        Console.WriteLine("  --xform <spec>");
        Console.WriteLine("  -x <spec>");
        Console.WriteLine();
        Console.WriteLine("<spec> rules:");
        Console.WriteLine("  all              enable all transformers (default)");
        Console.WriteLine("  none             disable all transformers");
        Console.WriteLine("  LFF,LFB,LCF      enable only these transformers");
        Console.WriteLine("  all,-LCF         start from all, then exclude");
        Console.WriteLine("  -LCF             same as all,-LCF");
        Console.WriteLine();
        Console.WriteLine("examples:");
        Console.WriteLine("  ToHeartPSE game.pak out --xform=none");
        Console.WriteLine("  ToHeartPSE out game.pak --xform=LFF,LFB");
        Console.WriteLine("  ToHeartPSE out game.pak --xform=all,-LCF");
        PrintTransformers();
    }
}
