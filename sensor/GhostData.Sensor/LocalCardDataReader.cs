using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using HackF5.UnitySpy;

namespace GhostData.Sensor
{
    // Reads public definitions, not collection ownership or hidden match entities.
    // No calls into the game, process writes, network requests or asset downloads.
    internal static class LocalCardDataReader
    {
        internal static string InstalledVersion(Process process)
        {
            if (process == null) return "";
            try
            {
                var root = Path.GetDirectoryName(process.MainModule.FileName);
                var path = Path.Combine(root, ".product.db");
                if (new FileInfo(path).Length > 1024 * 1024) return "";
                var versions = Regex.Matches(Encoding.ASCII.GetString(File.ReadAllBytes(path)),
                    @"(?<![0-9])\d{2}\.\d{1,2}\.\d{1,2}\.\d{5,7}(?![0-9])")
                    .Cast<Match>().Select(m => m.Value).Distinct().ToArray();
                return versions.Length == 1 ? versions[0] : "";
            }
            catch { return ""; }
        }

        internal static object Read(Process process)
        {
            if (process == null) throw new InvalidOperationException("Start Hearthstone and reach its main menu to read local card data.");
            var version = InstalledVersion(process);
            if (string.IsNullOrEmpty(version)) throw new InvalidOperationException("The installed game build could not be identified.");
            var build = int.Parse(version.Split('.').Last());
            var root = Path.GetDirectoryName(process.MainModule.FileName);
            var assemblyPath = Path.Combine(root, "Hearthstone_Data", "Managed", "Assembly-CSharp.dll");
            if (File.GetLastWriteTimeUtc(assemblyPath) > process.StartTime.ToUniversalTime().AddSeconds(2))
                throw new InvalidOperationException("Restart Hearthstone after its update before importing definitions.");
            var fingerprint = Fingerprint(assemblyPath);
            // Reflection-only reads constants from the installed client; it never executes its code.
            AppDomain.CurrentDomain.ReflectionOnlyAssemblyResolve += (_, args) =>
            {
                var dependency = Path.Combine(Path.GetDirectoryName(assemblyPath), new AssemblyName(args.Name).Name + ".dll");
                return File.Exists(dependency) ? Assembly.ReflectionOnlyLoadFrom(dependency) : Assembly.ReflectionOnlyLoad(args.Name);
            };
            var assembly = Assembly.ReflectionOnlyLoadFrom(assemblyPath);
            var logBuild = LogBuild(assembly);
            var tagNames = Constants(assembly, "GAME_TAG");
            var classes = Constants(assembly, "TAG_CLASS");
            var types = Constants(assembly, "TAG_CARDTYPE");
            var sets = Constants(assembly, "TAG_CARD_SET");
            var schools = Constants(assembly, "TAG_SPELL_SCHOOL");
            var tagIds = tagNames.ToDictionary(p => p.Value, p => p.Key, StringComparer.Ordinal);
            var required = new[] { "COST", "CLASS", "CARDTYPE", "CARD_SET", "COLLECTIBLE", "SPELL_SCHOOL" };
            foreach (var name in required) if (!tagIds.ContainsKey(name)) throw new InvalidOperationException("Missing client tag: " + name);
            var mechanical = new HashSet<string>(new[] { "SECRET", "QUEST", "QUESTLINE", "SIDE_QUEST", "DREDGE", "SIGIL", "PALADIN_AURA", "AURA", "OBJECTIVE" });
            var cards = new List<object>();
            var validUntil = DateTime.UtcNow.AddHours(24);
            using (var image = AssemblyImageFactory.Create(process.Id, _ => { }))
            {
                var events = ReadActiveEvents(image, ref validUntil);
                var currentSets = new Dictionary<int, int>();
                foreach (var row in Records(image, "CardSetTiming", 150000))
                {
                    var id = row.GetValue<int>("m_cardId");
                    if (!currentSets.ContainsKey(id) && events.Contains(row.GetValue<int>("m_eventTimingEvent")))
                        currentSets[id] = row.GetValue<int>("m_cardSetId");
                }
                var standardSets = new HashSet<int>(Records(image, "CardSet", 1000)
                    .Where(row => events.Contains(row.GetValue<int>("m_standardEvent")))
                    .Select(row => row.GetValue<int>("m_ID")));
                var tags = new Dictionary<int, Dictionary<int, int>>();
                var keywords = new Dictionary<int, HashSet<string>>();
                foreach (var row in Records(image, "CardTag", 1000000))
                {
                    if (row.GetValue<bool>("m_isReferenceTag")) continue;
                    var id = row.GetValue<int>("m_cardId");
                    var tag = row.GetValue<int>("m_tagId");
                    var value = row.GetValue<int>("m_tagValue");
                    var name = Lookup(tagNames, tag);
                    if (required.Contains(name))
                    {
                        if (!tags.TryGetValue(id, out var values)) tags[id] = values = new Dictionary<int, int>();
                        values[tag] = value;
                    }
                    if (value != 0 && name.Length > 0 && (mechanical.Contains(name) || row.GetValue<bool>("m_isPowerKeywordTag")))
                    {
                        if (!keywords.TryGetValue(id, out var values)) keywords[id] = values = new HashSet<string>();
                        values.Add(name);
                    }
                }
                foreach (var row in Records(image, "Card", 100000))
                {
                    var id = row.GetValue<int>("m_ID");
                    var cardId = row.GetValue<string>("m_noteMiniGuid");
                    if (string.IsNullOrWhiteSpace(cardId)) continue;
                    tags.TryGetValue(id, out var values);
                    int? Tag(string key) => values != null && values.TryGetValue(tagIds[key], out var v) ? (int?)v : null;
                    var cardSet = Tag("CARD_SET") ?? (currentSets.TryGetValue(id, out var setId) ? setId : 0);
                    cards.Add(new
                    {
                        id = cardId, dbfId = id, name = Localized(row, "m_name"), text = Localized(row, "m_textInHand"),
                        cardClass = Lookup(classes, Tag("CLASS")), type = Lookup(types, Tag("CARDTYPE")),
                        cost = Tag("COST"), collectible = Tag("COLLECTIBLE") == 1,
                        set = Lookup(sets, cardSet), spellSchool = Lookup(schools, Tag("SPELL_SCHOOL")),
                        standard = standardSets.Contains(cardSet),
                        mechanics = keywords.TryGetValue(id, out var words) ? words.OrderBy(x => x).ToArray() : new string[0],
                    });
                }
            }
            if (cards.Count < 1000) throw new InvalidOperationException("Card tables are not fully initialized; retry from the main menu.");
            if (process.HasExited || InstalledVersion(process) != version || Fingerprint(assemblyPath) != fingerprint)
                throw new InvalidOperationException("The game changed during import. Retry when its update finishes.");
            return new { status = "READY", schema_version = 1, source = "BLIZZARD_LOCAL_CLIENT", build,
                client_version = version, assembly_sha256 = fingerprint, imported_at = DateTime.UtcNow.ToString("O"),
                log_build = logBuild, valid_until = validUntil.ToString("O"), cards };
        }

        private static int LogBuild(Assembly assembly)
        {
            // Patch product builds can differ from the constant printed in Power.log.
            // Read that exact constant from metadata; never execute client code or guess an alias.
            var method = assembly.GetType("GameState", true).GetMethod("DebugPrintGame",
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static);
            var il = method?.GetMethodBody()?.GetILAsByteArray() ?? throw new InvalidOperationException("Client log build metadata is unavailable.");
            var codes = typeof(OpCodes).GetFields().Where(f => f.FieldType == typeof(OpCode))
                .Select(f => (OpCode)f.GetValue(null)).ToDictionary(op => (ushort)op.Value);
            var builds = new List<int>();
            var expectBuild = false;
            for (var i = 0; i < il.Length;)
            {
                ushort code = il[i++];
                if (code == 0xfe) code = (ushort)(0xfe00 | il[i++]);
                var op = codes[code];
                var size = op.OperandType == OperandType.InlineNone ? 0 :
                    op.OperandType == OperandType.ShortInlineBrTarget || op.OperandType == OperandType.ShortInlineI || op.OperandType == OperandType.ShortInlineVar ? 1 :
                    op.OperandType == OperandType.InlineVar ? 2 :
                    op.OperandType == OperandType.InlineI8 || op.OperandType == OperandType.InlineR ? 8 :
                    op.OperandType == OperandType.InlineSwitch ? checked(4 + 4 * BitConverter.ToInt32(il, i)) : 4;
                if (i + size > il.Length) throw new InvalidOperationException("Invalid log build metadata.");
                if (expectBuild && op == OpCodes.Ldc_I4) builds.Add(BitConverter.ToInt32(il, i));
                expectBuild = op == OpCodes.Ldstr && method.Module.ResolveString(BitConverter.ToInt32(il, i)) == "GameState.DebugPrintGame() - BuildNumber={0}";
                i += size;
            }
            if (builds.Count != 1 || builds[0] <= 0) throw new InvalidOperationException("Client log build could not be verified.");
            return builds[0];
        }

        private static IEnumerable<IManagedObjectInstance> Records(IAssemblyImage image, string table, int maximum)
        {
            IManagedObjectInstance records = image["GameDbf"][table]["m_records"];
            var count = records.GetValue<int>("_size");
            if (count <= 0 || count > maximum) throw new InvalidOperationException("Invalid local table size: " + table);
            var items = records.GetValue<object[]>("_items");
            if (items == null || items.Length < count) throw new InvalidOperationException("Incomplete local table: " + table);
            for (var i = 0; i < count; i++)
                yield return items[i] as IManagedObjectInstance ?? throw new InvalidOperationException("Invalid local record: " + table);
        }

        private static HashSet<int> ReadActiveEvents(IAssemblyImage image, ref DateTime validUntil)
        {
            dynamic services = image["Hearthstone.HearthstoneJobs"]["s_dependencyBuilder"]["_items"][0]["m_serviceLocator"]["m_services"];
            IManagedObjectInstance manager = null;
            foreach (dynamic entry in services["_entries"])
            {
                if (entry == null || entry["value"] == null) continue;
                if ((string)entry["value"]["<ServiceTypeName>k__BackingField"] == "EventTimingManager")
                { manager = entry["value"]["<Service>k__BackingField"]; break; }
            }
            if (manager == null || !manager.GetValue<bool>("<HasReceivedEventTimingsFromServer>k__BackingField"))
                throw new InvalidOperationException("Game rotation dates are not initialized. Retry from the main menu.");
            // Developer overrides would invalidate normal Standard legality. Do not guess.
            if (manager.GetValue<IManagedObjectInstance>("m_forcedActiveEvents") != null
                || manager.GetValue<IManagedObjectInstance>("m_forcedInactiveEvents") != null
                || Convert.ToDouble(manager.GetValue<object>("<DevTimeOffsetSeconds>k__BackingField")) != 0)
                throw new InvalidOperationException("Nonstandard game event overrides are active.");
            var timings = manager.GetValue<IManagedObjectInstance>("m_eventTimings");
            var count = timings.GetValue<int>("_count");
            var entries = timings.GetValue<object[]>("_entries");
            if (count < 1 || count > 100000 || entries.Length < count) throw new InvalidOperationException("Invalid event table.");
            var now = DateTime.UtcNow.Ticks;
            // The client defines these sentinels independently of date windows.
            var result = new HashSet<int> { 203 };
            for (var i = 0; i < count; i++)
            {
                var entry = (IManagedObjectInstance)entries[i];
                var value = entry.GetValue<IManagedObjectInstance>("value");
                if (value == null) continue;
                var key = entry.GetValue<int>("key");
                if (key == 203 || key == 164) continue;
                var start = DateTicks(value.GetValue<IManagedObjectInstance>("<StartTimeUtc>k__BackingField"));
                var end = DateTicks(value.GetValue<IManagedObjectInstance>("<EndTimeUtc>k__BackingField"));
                foreach (var boundary in new[] { start, end })
                    if (boundary.HasValue && boundary.Value > now && boundary.Value < validUntil.Ticks)
                        validUntil = new DateTime(boundary.Value, DateTimeKind.Utc);
                if ((!start.HasValue || now >= start.Value) && (!end.HasValue || now < end.Value)) result.Add(key);
            }
            return result;
        }

        private static long? DateTicks(IManagedObjectInstance nullable)
        {
            if (nullable == null || !nullable.GetValue<bool>("hasValue")) return null;
            var date = nullable.GetValue<IManagedObjectInstance>("value");
            return (long)(date.GetValue<ulong>("_dateData") & 0x3fffffffffffffffUL);
        }

        private static Dictionary<int, string> Constants(Assembly assembly, string name)
        {
            var type = assembly.GetType(name, true);
            return type.GetFields(BindingFlags.Public | BindingFlags.Static).Where(f => f.IsLiteral)
                .Select(f => new { Id = Convert.ToInt32(f.GetRawConstantValue()), f.Name })
                .GroupBy(f => f.Id).ToDictionary(g => g.Key, g => g.First().Name);
        }
        private static string Lookup(Dictionary<int, string> names, int? value) => value.HasValue && names.TryGetValue(value.Value, out var name) ? name : "";
        private static string Localized(IManagedObjectInstance record, string field) =>
            record.GetValue<IManagedObjectInstance>(field)?.GetValue<string>("m_currentLocaleValue") ?? "";
        private static string Fingerprint(string path)
        {
            using (var sha = SHA256.Create()) using (var file = File.OpenRead(path))
                return BitConverter.ToString(sha.ComputeHash(file)).Replace("-", "").ToLowerInvariant();
        }
    }
}
