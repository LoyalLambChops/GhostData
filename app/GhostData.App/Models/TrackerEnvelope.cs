using System.Text.Json;
using System.Text.Json.Serialization;

namespace GhostData.App.Models;

public sealed class TrackerEnvelope
{
    [JsonPropertyName("sequence")] public long Sequence { get; set; }
    [JsonPropertyName("message_type")] public string MessageType { get; set; } = "";
    [JsonPropertyName("payload")] public Dictionary<string, JsonElement>? Payload { get; set; }

    public TrackerStateDto? TryGetTrackerState()
    {
        if (Payload is null || !Payload.TryGetValue("tracker", out var value))
            return null;
        try
        {
            return value.Deserialize<TrackerStateDto>(new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
            });
        }
        catch (JsonException)
        {
            return null;
        }
    }
}
