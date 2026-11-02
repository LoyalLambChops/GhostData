using System;
using System.Collections.Generic;
using System.Linq;
using HackF5.UnitySpy;
using HackF5.UnitySpy.HearthstoneLib.Detail;
using HackF5.UnitySpy.HearthstoneLib.Detail.Deck;
using HackF5.UnitySpy.HearthstoneLib.Detail.SceneMode;

namespace HackF5.UnitySpy.HearthstoneLib
{
    // GhostData extension: collection composition selected by current client context.
    // Never substitute an ID retained on disk, and never read hidden match cards.
    public sealed class CurrentDeckReader : IDisposable
    {
        private readonly HearthstoneImage image;
        public CurrentDeckReader(int processId)
        {
            ActiveDeckReader.InvalidateDeckCardDbfCache();
            image = new HearthstoneImage(AssemblyImageFactory.Create(processId, _ => { }));
        }

        private long? ContextDeckId(SceneModeEnum? scene)
        {
            if (scene != SceneModeEnum.GAMEPLAY)
                return ActiveDeckReader.GetSelectedDeckId(image);
            if (image["GameState"]?["s_instance"]?["m_gameEntity"] == null)
                return null;
            IManagedObjectInstance value = image.GetService("GameMgr")?["m_lastDeckId"];
            return value != null && value.GetValue<bool>("hasValue")
                ? (long?)value.GetValue<long>("value") : null;
        }

        public bool GameContext { get; private set; }

        public IDeck Read()
        {
            var scene = SceneModeReader.ReadSceneMode(image);
            var id = ContextDeckId(scene);
            if (!id.HasValue || id.Value == 0) return null;
            var deck = ActiveDeckReader.ReadActiveDeck(image, id);
            // A picker/match transition during a read must not seed another game.
            if (SceneModeReader.ReadSceneMode(image) != scene || ContextDeckId(scene) != id)
                return null;
            if (deck == null || (id.Value > 0 && deck.DeckId != id.Value)) return null;
            GameContext = scene == SceneModeEnum.GAMEPLAY;
            return deck;
        }

        public IReadOnlyList<IDeck> ReadCollection()
        {
            var scene = SceneModeReader.ReadSceneMode(image);
            dynamic memory = image["CollectionManager"]?["s_instance"]?["m_decks"];
            if (memory == null) return null;
            var values = (object[])memory["valueSlots"];
            if (values == null || values.Length > 512) return null;
            var decks = new List<IDeck>();
            foreach (var value in values)
            {
                if (value == null) continue;
                try
                {
                    var first = ActiveDeckReader.GetDynamicDeck(value);
                    var second = ActiveDeckReader.GetDynamicDeck(value);
                    if (first == null || second == null || first.DeckId <= 0 || first.DeckId != second.DeckId
                        || first.Name != second.Name || first.FormatType != second.FormatType
                        || first.HeroCardId != second.HeroCardId
                        || !first.DeckList.OrderBy(x=>x).SequenceEqual(second.DeckList.OrderBy(x=>x))) continue;
                    string Side(Deck deck) => string.Join("|", deck.Sideboards.SelectMany(b => b.Cards.Select(c=>b.KeyCardId+":"+c)).OrderBy(x=>x));
                    if (Side(first) != Side(second)) continue;
                    decks.Add(second);
                }
                catch { /* A deck being edited may not be a coherent snapshot. */ }
            }
            return SceneModeReader.ReadSceneMode(image) == scene ? decks : null;
        }

        public void Dispose() => image.Dispose();
    }
}
