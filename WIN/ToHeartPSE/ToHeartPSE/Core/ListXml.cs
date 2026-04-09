using System.Xml.Linq;

namespace ToHeartPSE;

internal sealed class ListEntry
{
    readonly Dictionary<string, string> _values = new(StringComparer.OrdinalIgnoreCase);

    public string Section { get; }
    public string Name { get; }

    public ListEntry(string section, string name)
    {
        Section = section;
        Name = name;
    }

    public string? this[string key]
    {
        get => Get(key);
        set
        {
            if (value == null) _values.Remove(key);
            else _values[key] = value;
        }
    }

    public string? Get(string key) => _values.TryGetValue(key, out string? value) ? value : null;

    public int GetInt(string key)
    {
        string? value = Get(key);
        if (value == null || !int.TryParse(value, out int result))
            throw new InvalidOperationException($"list.xml entry {Name} is missing integer attribute {key}");
        return result;
    }

    public int GetIntOrDefault(string key, int defaultValue)
    {
        string? value = Get(key);
        return value != null && int.TryParse(value, out int result) ? result : defaultValue;
    }

    public XElement ToXml()
    {
        var node = new XElement("file", new XAttribute("name", Name));
        foreach ((string key, string value) in _values.OrderBy(static pair => pair.Key, StringComparer.Ordinal))
            node.SetAttributeValue(key, value);
        return node;
    }

    public static ListEntry FromXml(string section, XElement node)
    {
        string name = node.Attribute("name")?.Value ?? throw new InvalidOperationException("list.xml entry missing name");
        var entry = new ListEntry(section, name);
        foreach (XAttribute attr in node.Attributes())
        {
            if (attr.Name.LocalName == "name")
                continue;
            entry[attr.Name.LocalName] = attr.Value;
        }
        return entry;
    }
}

internal sealed class ListXml
{
    readonly List<ListEntry> _lff = new();
    readonly List<ListEntry> _lfb = new();
    readonly List<ListEntry> _lcf = new();

    public bool HasAny => _lff.Count != 0 || _lfb.Count != 0 || _lcf.Count != 0;
    public IEnumerable<ListEntry> AllEntries => _lff.Concat(_lfb).Concat(_lcf);

    public void Add(ListEntry entry)
    {
        switch (entry.Section)
        {
            case "lff": _lff.Add(entry); break;
            case "lfb": _lfb.Add(entry); break;
            case "lcf": _lcf.Add(entry); break;
            default: throw new InvalidOperationException($"unknown list.xml section: {entry.Section}");
        }
    }

    public void Save(string path)
    {
        var root = new XElement("thpse");
        AppendSection(root, "lff", _lff);
        AppendSection(root, "lfb", _lfb);
        AppendSection(root, "lcf", _lcf);
        new XDocument(new XDeclaration("1.0", "utf-8", null), root).Save(path);
    }

    public static ListXml Load(string path)
    {
        var doc = XDocument.Load(path);
        var list = new ListXml();
        XElement root = doc.Root ?? throw new InvalidOperationException("list.xml missing root");
        foreach (string section in new[] { "lff", "lfb", "lcf" })
        {
            XElement? group = root.Element(section);
            if (group == null)
                continue;
            foreach (XElement file in group.Elements("file"))
                list.Add(ListEntry.FromXml(section, file));
        }
        return list;
    }

    static void AppendSection(XElement root, string name, List<ListEntry> entries)
    {
        if (entries.Count == 0)
            return;
        var section = new XElement(name);
        foreach (ListEntry entry in entries.OrderBy(static e => e.Name, StringComparer.OrdinalIgnoreCase))
            section.Add(entry.ToXml());
        root.Add(section);
    }
}
