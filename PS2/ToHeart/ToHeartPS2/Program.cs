using System.Text;

namespace ToHeartPS2;

internal static class Program
{
    static int Main(string[] args)
    {
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);

        try
        {
            if (args.Length < 3 || HasHelp(args))
            {
                PrintHelp();
                return args.Length < 3 ? 1 : 0;
            }

            if (HasList(args))
            {
                PrintTransformers();
                return 0;
            }

            if (!TryParseArguments(args, out string elf, out string input, out string output, out string? outputElf, out string spec, out string error))
            {
                Console.WriteLine(error);
                PrintHelp();
                return 1;
            }

            if (!Transformers.TryConfigure(spec, out string cfgError))
            {
                Console.WriteLine(cfgError);
                PrintHelp();
                return 1;
            }

            string elfPath = Path.GetFullPath(elf);
            if (!File.Exists(elfPath))
            {
                Console.WriteLine("elf file does not exist: " + elfPath);
                return 1;
            }

            bool inputIsSfs = string.Equals(Path.GetExtension(input), ".sfs", StringComparison.OrdinalIgnoreCase);
            bool outputIsSfs = string.Equals(Path.GetExtension(output), ".sfs", StringComparison.OrdinalIgnoreCase);

            if (inputIsSfs && !outputIsSfs)
            {
                if (!string.IsNullOrWhiteSpace(outputElf))
                {
                    Console.WriteLine("unpack mode does not accept a fourth positional argument");
                    return 1;
                }
                App.Unpack(elfPath, Path.GetFullPath(input), Path.GetFullPath(output));
                return 0;
            }

            if (!inputIsSfs && outputIsSfs)
            {
                if (string.IsNullOrWhiteSpace(outputElf))
                {
                    Console.WriteLine("pack mode requires a fourth positional argument for output elf path");
                    return 1;
                }

                string inDir = Path.GetFullPath(input);
                if (!Directory.Exists(inDir))
                {
                    Console.WriteLine("input directory does not exist: " + inDir);
                    return 1;
                }

                App.Pack(elfPath, inDir, Path.GetFullPath(output), outputElf);
                return 0;
            }

            Console.WriteLine("arguments are ambiguous:");
            Console.WriteLine("  <elf> <xxx.sfs> <directory> = unpack");
            Console.WriteLine("  <elf> <directory> <xxx.sfs> = pack");
            PrintHelp();
            return 1;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("error: " + ex.Message);
            return 1;
        }
    }

    static bool HasHelp(string[] args) => args.Any(static a => a is "-h" or "--help" or "/?" or "help");

    static bool HasList(string[] args) => args.Any(static a => a is "--list-xform" or "--list-transform" or "--list");

    static bool TryParseArguments(string[] args, out string elf, out string input, out string output, out string? outputElf, out string spec, out string error)
    {
        elf = "";
        input = "";
        output = "";
        outputElf = null;
        spec = "all";
        error = "";

        var positional = new List<string>();
        for (int i = 0; i < args.Length; i++)
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

            if (a.Length != 0 && a[0] == '-')
            {
                error = "unknown argument: " + a;
                return false;
            }

            positional.Add(a);
        }

        if (positional.Count is < 3 or > 4)
        {
            error = "expected three positional arguments for unpack, or four for pack";
            return false;
        }

        elf = positional[0];
        input = positional[1];
        output = positional[2];
        if (positional.Count == 4)
            outputElf = positional[3];
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
        Console.WriteLine("  ToHeartPS2 <elf> <xxx.sfs> <directory>");
        Console.WriteLine("  ToHeartPS2 <elf> <directory> <xxx.sfs> <output-elf>");
        Console.WriteLine();
        Console.WriteLine("options:");
        Console.WriteLine("  --xform=<spec>");
        Console.WriteLine("  --xform <spec>");
        Console.WriteLine("  -x <spec>");
        Console.WriteLine();
        Console.WriteLine("<spec> rules:");
        Console.WriteLine("  all              enable all implemented transformers (default)");
        Console.WriteLine("  none             disable all transformers");
        Console.WriteLine("  TPP              enable only TPP");
        Console.WriteLine();
        PrintTransformers();
    }
}
