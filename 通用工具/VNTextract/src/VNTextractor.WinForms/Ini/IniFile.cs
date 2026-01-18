using System.Text;

namespace VNTextractor.WinForms.Ini;

// Tiny INI helper (UTF-8). Enough for storing UI settings.
public sealed class IniFile
{
    private readonly Dictionary<string, Dictionary<string, string>> _data = new(StringComparer.OrdinalIgnoreCase);

    public static IniFile Load(string path)
    {
        var ini = new IniFile();
        if (!File.Exists(path))
            return ini;

        string currentSection = "main";
        foreach (var raw in File.ReadAllLines(path, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false)))
        {
            var line = raw.Trim();
            if (line.Length == 0)
                continue;
            if (line.StartsWith(';') || line.StartsWith('#'))
                continue;

            if (line.StartsWith('[') && line.EndsWith(']'))
            {
                currentSection = line[1..^1].Trim();
                if (currentSection.Length == 0)
                    currentSection = "main";
                continue;
            }

            var idx = line.IndexOf('=');
            if (idx <= 0)
                continue;

            var key = line[..idx].Trim();
            var value = line[(idx + 1)..].Trim();
            ini.Set(currentSection, key, value);
        }

        return ini;
    }

    public string? Get(string section, string key)
    {
        if (_data.TryGetValue(section, out var sec) && sec.TryGetValue(key, out var v))
            return v;
        return null;
    }

    public bool GetBool(string section, string key, bool fallback)
    {
        var v = Get(section, key);
        if (v is null) return fallback;
        return v.Equals("1", StringComparison.OrdinalIgnoreCase)
            || v.Equals("true", StringComparison.OrdinalIgnoreCase)
            || v.Equals("yes", StringComparison.OrdinalIgnoreCase);
    }

    public int GetInt(string section, string key, int fallback)
    {
        var v = Get(section, key);
        return int.TryParse(v, out var i) ? i : fallback;
    }

    public void Set(string section, string key, string value)
    {
        if (!_data.TryGetValue(section, out var sec))
        {
            sec = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            _data[section] = sec;
        }
        sec[key] = value;
    }

    public void Save(string path)
    {
        var utf8NoBom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
        using var sw = new StreamWriter(path, append: false, encoding: utf8NoBom);

        foreach (var (section, sec) in _data.OrderBy(kv => kv.Key, StringComparer.OrdinalIgnoreCase))
        {
            sw.Write('[');
            sw.Write(section);
            sw.WriteLine(']');

            foreach (var (k, v) in sec.OrderBy(kv => kv.Key, StringComparer.OrdinalIgnoreCase))
            {
                sw.Write(k);
                sw.Write('=');
                sw.WriteLine(v);
            }

            sw.WriteLine();
        }
    }
}

