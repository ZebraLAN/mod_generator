using System.Text;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Encodings.Web;

EnsureDataLoaded();

if (Data.IsYYC())
{
    ScriptError("The opened game uses YYC: no code is available.");
    return;
}

// === Path Configuration (Unified config.json) ===
// === Path Configuration ===
#load "Paths.csx"

string outputFolder = GetMetaOutput(ScriptPath);

// === Logic ===
var inheritanceDict = Data.GameObjects
    .Where(o => o.ParentId is not null)
    .GroupBy(o => o.ParentId.Name.Content)
    .ToDictionary(g => g.Key, g => g.Select(o => o.Name.Content).OrderBy(n => n).ToList());

// === JSON Generation (System.Text.Json) ===
// Use SortedDictionary to ensure keys are alphabetical, matching original behavior
var sortedDict = new SortedDictionary<string, List<string>>(inheritanceDict);

var options = new JsonSerializerOptions {
    WriteIndented = true,
    Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping
};
string json = JsonSerializer.Serialize(sortedDict, options);

string outputPath = Path.Combine(outputFolder, "object_tree.json");
File.WriteAllText(outputPath, json);
ScriptMessage($"Exported object tree to:\n{outputPath}");
