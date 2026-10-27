using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using HackF5.UnitySpy.HearthstoneLib;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace GhostData.Sensor
{
    internal static class Program
    {
        private const string SensorVersion = "1.3.7";
        private const string Provider = "ghostdata_sensor_unityspy";

        private static int Main(string[] args)
        {
            Console.OutputEncoding = new System.Text.UTF8Encoding(false);
            var command = (args.FirstOrDefault() ?? "health").ToLowerInvariant();
            try
            {
                switch (command)
                {
                    case "hand-stream":
                        RunHandStream(args);
                        return 0;
                    case "health":
                        Emit(HealthPayload());
                        return 0;
                    case "selected-deck":
                        Emit(ReadSelectedDeck(args));
                        return 0;
                    case "card-data":
                        Emit(LocalCardDataReader.Read(HearthstoneProcess()));
                        return 0;
                    default:
                        Emit(new
                        {
                            status = "ERROR",
                            provider = Provider,
                            sensor_version = SensorVersion,
                            reason = "unknown command: " + command,
                            source_revision = ReadSourceRevision(),
                        });
                        return 2;
                }
            }
            catch (Exception ex)
            {
                if (args.Contains("--diagnostics")) Console.Error.WriteLine(ex);
                // The sensor is an enrichment boundary. It returns structured failure
                // data so the local recorder can continue without deck metadata.
                Emit(new
                {
                    status = "ERROR",
                    provider = Provider,
                    sensor_version = SensorVersion,
                    hearthstone_running = HearthstoneProcess() != null,
                    reason = ex.GetType().Name + ": " + ex.Message,
                    source_revision = ReadSourceRevision(),
                });
                return 1;
            }
        }

        private static string TryProcessPath(Process process)
        {
            try { return process?.MainModule?.FileName ?? ""; }
            catch { return ""; }
        }

        private static object HealthPayload()
        {
            var process = HearthstoneProcess();
            return new
            {
                status = "READY",
                provider = Provider,
                hearthstone_running = process != null,
                hearthstone_pid = process?.Id ?? 0,
                sensor_version = SensorVersion,
                reader = "unityspy-selected-deck",
                source_revision = ReadSourceRevision(),
                hearthstone_build = TryFileVersion(process),
                hearthstone_path = TryProcessPath(process),
            };
        }

        private static void RunHandStream(string[] args)
        {
            HandReader reader=null;
            Process game=null;
            Process parent=null;
            var parentIndex=Array.IndexOf(args,"--parent-pid");
            if(parentIndex>=0)
            {
                if(parentIndex+1>=args.Length || !int.TryParse(args[parentIndex+1],out var pid))return;
                try{parent=Process.GetProcessById(pid);}catch{return;}
            }
            int tick=0;
            try
            {
                while(parent==null || !parent.HasExited)
                {
                    try
                    {
                        if(game==null || game.HasExited)
                        {
                            reader?.Dispose();reader=null;game?.Dispose();game=HearthstoneProcess();
                            if(game!=null)reader=new HandReader(game.Id);
                        }
                        Emit(reader==null ? (object)new {status="WAITING",hover=(object)null,hand=new object[0]} : reader.Read(tick++%10==0));
                        System.Threading.Thread.Sleep(reader==null ? 1000 : 100);
                    }
                    catch(System.IO.IOException){return;} // owner closed the pipe
                    catch
                    {
                        reader?.Dispose();reader=null;game?.Dispose();game=null;
                        Emit(new {status="UNAVAILABLE",hover=(object)null,hand=new object[0]});
                        System.Threading.Thread.Sleep(3000);
                    }
                }
            }
            finally {reader?.Dispose();game?.Dispose();parent?.Dispose();}
        }

        private static object ReadSelectedDeck(string[] args)
        {
            var process = HearthstoneProcess();
            if (process == null)
            {
                return Failure("UNAVAILABLE", false, "Hearthstone is not running.", "");
            }

            try
            {
                using (var reader = new CurrentDeckReader(process.Id))
                {
                    var deck = reader.Read();
                    if (deck == null)
                        return Failure("UNAVAILABLE", true, "The current client deck could not be verified.", TryFileVersion(process));
                    long? deckId = deck.DeckId != 0 ? (long?)deck.DeckId : null;
                    var cardRows = GroupCardIds(deck.DeckList);
                    // GetActiveDeck is intentionally typed as IDeck. Constructed decks
                    // currently materialize as the concrete Deck type, which carries
                    // sideboard metadata that is not part of the IDeck contract.
                    var concreteDeck = deck as HackF5.UnitySpy.HearthstoneLib.Detail.Deck.Deck;
                    var sideboardRows = GroupSideboards(concreteDeck?.Sideboards);
                    var mainCount = cardRows.Sum(x => x.count);
                    var format = deck.FormatType == 2 ? "STANDARD" : "FORMAT_" + deck.FormatType;
                    var hero = (deck.HeroCardId ?? "").Trim();

                    if (format != "STANDARD")
                    {
                        return new
                        {
                            status = "NON_STANDARD",
                            provider = Provider,
                            sensor_version = SensorVersion,
                            hearthstone_running = true,
                            reason = "GhostData records Constructed Standard deck metadata only.",
                            selected_deck_id = deckId.HasValue ? deckId.Value.ToString() : "",
                            deck_name = deck.Name ?? "",
                            format = format,
                            class_id = "",
                            hero_card_ids = string.IsNullOrWhiteSpace(hero) ? new string[0] : new[] { hero },
                            cards = cardRows,
                            sideboards = sideboardRows,
                            hearthstone_build = TryFileVersion(process),
                hearthstone_path = TryProcessPath(process),
                            unity_version = "",
                            source_revision = ReadSourceRevision(),
                        };
                    }

                    if ((mainCount != 20 && mainCount != 30) || string.IsNullOrWhiteSpace(hero))
                    {
                        return new
                        {
                            status = "PARTIAL",
                            provider = Provider,
                            sensor_version = SensorVersion,
                            hearthstone_running = true,
                            reason = "Client deck was readable but did not resolve to a complete 30-card Standard deck with a hero.",
                            selected_deck_id = deckId.HasValue ? deckId.Value.ToString() : "",
                            deck_name = deck.Name ?? "",
                            format = format,
                            class_id = "",
                            hero_card_ids = string.IsNullOrWhiteSpace(hero) ? new string[0] : new[] { hero },
                            cards = cardRows,
                            sideboards = sideboardRows,
                            hearthstone_build = TryFileVersion(process),
                hearthstone_path = TryProcessPath(process),
                            unity_version = "",
                            source_revision = ReadSourceRevision(),
                        };
                    }

                    return new
                    {
                        status = "EXACT",
                        provider = Provider,
                        sensor_version = SensorVersion,
                        hearthstone_running = true,
                        reason = "",
                        selected_deck_id = deckId.HasValue ? deckId.Value.ToString() : "",
                        deck_name = deck.Name ?? "",
                        format = "STANDARD",
                        class_id = "",
                        hero_card_ids = new[] { hero },
                        cards = cardRows,
                        sideboards = sideboardRows,
                        hearthstone_build = TryFileVersion(process),
                hearthstone_path = TryProcessPath(process),
                        unity_version = "",
                        source_revision = ReadSourceRevision(),
                    };
                }
            }
            catch (Exception ex)
            {
                // Memory layout changes are expected over the lifetime of the game.
                // Report them explicitly as incompatibility rather than guessing.
                return Failure(
                    "INCOMPATIBLE",
                    true,
                    ex.GetType().Name + ": " + ex.Message,
                    TryFileVersion(process)
                );
            }
        }

        private sealed class CardRow
        {
            public string card_id { get; set; }
            public int count { get; set; }
        }

        private sealed class SideboardRow
        {
            public string card_id { get; set; }
            public int count { get; set; }
            public string owner_card_id { get; set; }
        }

        private static List<CardRow> GroupCardIds(IEnumerable<string> cards)
        {
            return (cards ?? Enumerable.Empty<string>())
                .Where(x => !string.IsNullOrWhiteSpace(x))
                .GroupBy(x => x.Trim(), StringComparer.Ordinal)
                .OrderBy(x => x.Key, StringComparer.Ordinal)
                .Select(x => new CardRow { card_id = x.Key, count = x.Count() })
                .ToList();
        }

        private static List<SideboardRow> GroupSideboards(IEnumerable<HackF5.UnitySpy.HearthstoneLib.Detail.Deck.DeckSideboard> sideboards)
        {
            var rows = new List<SideboardRow>();
            foreach (var sideboard in sideboards ?? Enumerable.Empty<HackF5.UnitySpy.HearthstoneLib.Detail.Deck.DeckSideboard>())
            {
                var owner = (sideboard.KeyCardId ?? "").Trim();
                foreach (var group in (sideboard.Cards ?? new List<string>())
                    .Where(x => !string.IsNullOrWhiteSpace(x))
                    .GroupBy(x => x.Trim(), StringComparer.Ordinal)
                    .OrderBy(x => x.Key, StringComparer.Ordinal))
                {
                    rows.Add(new SideboardRow { card_id = group.Key, count = group.Count(), owner_card_id = owner });
                }
            }
            return rows;
        }

        private static object Failure(string status, bool running, string reason, string build, long? deckId = null)
        {
            return new
            {
                status = status,
                provider = Provider,
                sensor_version = SensorVersion,
                hearthstone_running = running,
                reason = reason,
                selected_deck_id = deckId.HasValue ? deckId.Value.ToString() : "",
                deck_name = "",
                format = "",
                class_id = "",
                hero_card_ids = new string[0],
                cards = new object[0],
                sideboards = new object[0],
                hearthstone_build = build ?? "",
                unity_version = "",
                source_revision = ReadSourceRevision(),
            };
        }

        private static Process HearthstoneProcess()
        {
            return Process.GetProcessesByName("Hearthstone").FirstOrDefault();
        }

        private static string TryFileVersion(Process process)
        {
            if (process == null) return "";
            try
            {
                return LocalCardDataReader.InstalledVersion(process);
            }
            catch
            {
                return "";
            }
        }

        private static bool TryArgumentLong(string[] args, string name, out long value)
        {
            value = 0;
            for (var i = 0; i + 1 < args.Length; i++)
            {
                if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase))
                {
                    return long.TryParse(args[i + 1], out value);
                }
            }
            return false;
        }

        private static string ReadSourceRevision()
        {
            try
            {
                var path = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "unityspy-manifest.json");
                if (!File.Exists(path)) return "unknown";
                var payload = JObject.Parse(File.ReadAllText(path));
                return (string)payload["commit"] ?? "unknown";
            }
            catch
            {
                return "unknown";
            }
        }

        private static void Emit(object payload)
        {
            Console.WriteLine(JsonConvert.SerializeObject(payload, Formatting.None));
        }
    }
}
