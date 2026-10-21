using System;
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
            return deck;
        }

        public void Dispose() => image.Dispose();
    }
}
