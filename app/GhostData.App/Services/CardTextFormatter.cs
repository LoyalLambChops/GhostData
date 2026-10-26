using System.Net;
using System.Text.RegularExpressions;
namespace GhostData.App.Services;

public static class CardTextFormatter
{
    public static string Format(string? raw)
    {
        var text=WebUtility.HtmlDecode((raw ?? "").Replace("&amp;","\uE000")).Replace("\\n","\n").Replace("\r\n","\n");
        text=Regex.Replace(text,@"<br\s*/?>", "\n",RegexOptions.IgnoreCase);
        text=Regex.Replace(text,@"<[^>]*>|\[x\]", "");
        text=Regex.Replace(text,@"~[A-Z][A-Z0-9_]*", "");
        text=Regex.Replace(text,@"[$#](?=[+-]?\d)", "");
        text=text.Replace("_"," ").Replace("&"," ").Replace("\uE000","&").Replace("\u00ad","");
        // Raw DB strings contain alternative descriptions and runtime arguments.
        // Use the client's rendered text when available; never print templates
        // or manufacture a number that could change how a card is understood.
        if(text.Contains('@'))
        {
            var variants=text.Split('@');
            var baseText=variants.FirstOrDefault(v=>!Regex.IsMatch(v,@"\{\d+\}|\|4\(") && Regex.IsMatch(v.Trim(),@"[.!?]$"));
            if(baseText is not null)text=baseText;
        }
        if(Regex.IsMatch(text,@"@|\{\d+\}|\|4\("))
            return "Live card wording is available when the game displays this card.";
        text=Regex.Replace(text,@"[ \t]+", " ");
        return string.Join("\n",text.Split('\n').Select(line=>line.Trim())).Trim();
    }
}
