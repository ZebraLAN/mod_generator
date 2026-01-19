using System.IO;
using System.Text.Json;

// Simplified path configuration
// Reads paths.json from project root
public static string GetMetaOutput(string scriptPath)
{
    string scriptDir = Path.GetDirectoryName(scriptPath);
    string rootDir = Path.GetFullPath(Path.Combine(scriptDir, ".."));
    string configPath = Path.Combine(rootDir, "paths.json");

    if (!File.Exists(configPath))
    {
        throw new FileNotFoundException($"Configuration file not found: {configPath}. Please copy paths.json.example to paths.json and configure it.");
    }

    string outputFolder = null;
    using (JsonDocument doc = JsonDocument.Parse(File.ReadAllText(configPath)))
    {
        // Direct access: throws KeyNotFoundException if missing
        JsonElement val = doc.RootElement.GetProperty("data_meta");

        string path = val.GetString();
        if (!string.IsNullOrEmpty(path))
        {
            if (!Path.IsPathRooted(path))
                path = Path.GetFullPath(Path.Combine(rootDir, path));
            outputFolder = path;
        }
    }

    if (outputFolder == null)
    {
        throw new Exception("Missing 'data_meta' key in paths.json");
    }

    if (!Directory.Exists(outputFolder))
        Directory.CreateDirectory(outputFolder);

    return outputFolder;
}
