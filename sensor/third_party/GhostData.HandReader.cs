using System;
using System.Collections.Generic;
using HackF5.UnitySpy;
using HackF5.UnitySpy.HearthstoneLib.Detail;

namespace HackF5.UnitySpy.HearthstoneLib
{
    // Reads only the visible friendly hand and cursor focus. No method calls,
    // input injection, opponent cards, deck contents or process writes.
    public sealed class HandReader : IDisposable
    {
        private readonly HearthstoneImage image;
        public HandReader(int pid) { image=new HearthstoneImage(AssemblyImageFactory.Create(pid,_=>{})); }
        private static object ReadCard(dynamic card)
        {
            dynamic zone=card?["m_zone"];
            if(zone==null || (int)zone["m_Side"]!=1 || (int)zone["m_ServerTag"]!=3) return null;
            dynamic entity=card["m_entity"];
            if(entity==null)return null;
            int id=0;
            dynamic tags=entity["m_tags"]?["m_values"];
            if(tags==null)return null;
            int count=(int)tags["_count"];
            if(count<0 || count>2048)return null;
            for(int i=0;i<count;i++)
            {
                dynamic entry=tags["_entries"][i];
                if((int)entry["key"]==53){id=(int)entry["value"];break;}
            }
            if(id<=0)return null;
            string cid=(string)entity["m_cardIdInternal"];
            string text="";
            try { text=(string)card["m_actor"]?["m_powersTextMesh"]?["m_Text"] ?? ""; } catch { }
            if(text.Length>8192)text="";
            return new {entity_id=id,card_id=cid,text};
        }
        public object Read(bool includeHand)
        {
            dynamic hovered=image["InputManager"]?["s_instance"]?["m_mousedOverCard"];
            var focus=ReadCard(hovered);
            List<object> hand=null;
            if(includeHand)
            {
                hand=new List<object>();
                dynamic zones=image["ZoneMgr"]?["s_instance"]?["m_zones"];
                if(zones!=null)
                {
                    int count=(int)zones["_size"];
                    if(count<0 || count>128)throw new InvalidOperationException("Unexpected zone count");
                    for(int i=0;i<count;i++)
                    {
                        dynamic zone=zones["_items"][i];
                        if(zone==null || (int)zone["m_Side"]!=1 || (int)zone["m_ServerTag"]!=3)continue;
                        dynamic cards=zone["m_cards"];
                        int size=(int)cards["_size"];
                        if(size<0 || size>32)throw new InvalidOperationException("Unexpected hand size");
                        for(int j=0;j<size;j++) {var row=ReadCard(cards["_items"][j]);if(row!=null)hand.Add(row);}
                    }
                }
            }
            return new {status="READY",hover=focus,hand};
        }
        public void Dispose()=>image.Dispose();
    }
}
