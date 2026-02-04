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
var mapping = Data.Sounds
    .Select((snd, index) => new { Index = index, Name = snd.Name.Content })
    .OrderBy(x => x.Index);

// === JSON Generation (Simplified) ===
// === JSON Generation (System.Text.Json) ===
var exportData = mapping.ToDictionary(x => x.Index.ToString(), x => x.Name);

var options = new JsonSerializerOptions {
    WriteIndented = true,
    Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping
};
string json = JsonSerializer.Serialize(exportData, options);

string outputPath = Path.Combine(outputFolder, "sound_index_map.json");
File.WriteAllText(outputPath, json);
ScriptMessage($"Exported sound map to:\n{outputPath}");
