"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import {
  Flame, MessageCircle, List, Activity, ChevronRight, Sparkles, BarChart3, Upload, Swords,
} from "lucide-react";
import { useState, useMemo } from "react";
import { useLiveScores } from "@/lib/live-scores";
import type { SBEvent } from "@/lib/sbevent";
import { formatBookmakerName } from "@/lib/bookmakers";

const SPORTS = ["MLB","NFL","NBA","NHL","NCAAF","NCAAB","WNBA"] as const;
type Sport = typeof SPORTS[number];

const QUICK = [
  { icon: Flame, label: "Build Lineup", href: "/optimizer" },
  { icon: Swords, label: "Parlay Builder", href: "/market-tools/parlay" },
  { icon: BarChart3, label: "Market Tools", href: "/market-tools" },
  { icon: MessageCircle, label: "Ask SB ME AI", href: "/ai" },
  { icon: List, label: "My Lineups", href: "/lineups" },
];

const C = { card: "#0a0f24", border: "#1e293b", text: "#f0f6fc", muted: "#94a3b8", subtle: "#64748b", gold: "#c9a84c" };

function fmtOdds(v: number|null|undefined) { if(v==null) return "\u2014"; return v>0?"+"+v:""+v; }
function isLive(s: string) { return(s||"").toUpperCase()==="LIVE"; }

// ── Date helpers (EDT) ──
const EDT = "America/New_York";
function todayEDT(): string { return new Date().toLocaleDateString("en-US",{timeZone:EDT}); }
function tomorrowEDT(): string { const d=new Date();d.setDate(d.getDate()+1); return d.toLocaleDateString("en-US",{timeZone:EDT}); }
function eventDateET(iso: string|null): string {
  if(!iso)return""; return new Date(iso).toLocaleDateString("en-US",{timeZone:EDT,weekday:"short",month:"short",day:"numeric"});
}
function eventDateKey(iso: string|null): string {
  if(!iso)return"9999"; return new Date(iso).toLocaleDateString("en-US",{timeZone:EDT});
}
function isNow(iso: string|null): boolean { return eventDateKey(iso)===todayEDT(); }
function isNext(iso: string|null): boolean { return eventDateKey(iso)===tomorrowEDT(); }
function dateLabel(iso: string|null): string {
  const dk=eventDateKey(iso); if(!dk||dk==="9999")return"Upcoming";
  const ts = iso || "";
  if(dk===todayEDT())return "TODAY \u2014 "+new Date(ts).toLocaleDateString("en-US",{timeZone:EDT,weekday:"long",month:"long",day:"numeric"}).toUpperCase();
  if(dk===tomorrowEDT())return "TOMORROW \u2014 "+new Date(ts).toLocaleDateString("en-US",{timeZone:EDT,weekday:"long",month:"long",day:"numeric"}).toUpperCase();
  return new Date(ts).toLocaleDateString("en-US",{timeZone:EDT,weekday:"long",month:"long",day:"numeric"}).toUpperCase();
}
function timeEDT(iso: string|null): string {
  if(!iso)return""; return new Date(iso).toLocaleTimeString("en-US",{timeZone:EDT,hour:"numeric",minute:"2-digit"})+" EDT";
}
function dayCtx(iso: string|null): string {
  if(!iso)return"";
  if(isNow(iso))return"Today \u00b7 ";
  if(isNext(iso))return"Tomorrow \u00b7 ";
  return eventDateET(iso)+" \u00b7 ";
}

function GameStrip({event}:{event:SBEvent}) {
  const live = isLive(event.status);
  const t = timeEDT(event.start_time);
  const ctx = dayCtx(event.start_time);
  return (
    <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"8px 14px",borderRadius:10,background:live?"rgba(201,168,76,0.03)":"rgba(255,255,255,0.01)",border:live?"1px solid rgba(201,168,76,0.12)":"1px solid rgba(30,41,59,0.5)",gap:8}}>
      <div style={{display:"flex",alignItems:"center",gap:8,minWidth:0}}>
        <span style={{padding:"2px 6px",borderRadius:4,fontSize:8,fontWeight:800,background:live?"rgba(239,68,68,0.15)":"rgba(100,116,139,0.08)",color:live?"#ef4444":C.subtle,flexShrink:0,whiteSpace:"nowrap"}}>
          {live?"LIVE":ctx+t}
        </span>
        <span style={{fontSize:13,fontWeight:600,color:C.text,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>
          {event.away_team?.abbreviation||"AWY"} {"@"} {event.home_team?.abbreviation||"HOM"}
        </span>
      </div>
      {live&&(event.home_score!=null||event.away_score!=null)&&(
        <span style={{fontSize:14,fontWeight:800,color:C.gold,flexShrink:0}}>{event.away_score??0}{"\u2013"}{event.home_score??0}</span>
      )}
    </div>
  );
}

interface PropItem { player:string; matchup:string; market:string; line:number|null; odds:number|null; book:string; key:string }
function PropRow({p}:{p:PropItem}) {
  return (
    <div style={{padding:"7px 12px",borderRadius:8,border:"1px solid rgba(30,41,59,0.5)",background:"rgba(255,255,255,0.01)",display:"flex",alignItems:"center",justifyContent:"space-between",gap:8}}>
      <div style={{minWidth:0}}>
        <div style={{fontSize:12,fontWeight:700,color:C.text}}>{p.player}</div>
        <div style={{fontSize:9,color:C.subtle}}>{p.market} {"\u00b7"} {p.matchup}</div>
      </div>
      <div style={{display:"flex",alignItems:"center",gap:10,flexShrink:0}}>
        <span style={{fontSize:13,fontWeight:800,color:C.gold}}>{p.line??"\u2014"}</span>
        <span style={{fontSize:12,fontWeight:600,color:C.muted,minWidth:48,textAlign:"right"}}>{fmtOdds(p.odds)}</span>
        <span style={{fontSize:9,color:C.subtle,minWidth:60,textAlign:"right"}}>{p.book}</span>
      </div>
    </div>
  );
}

function MLRow({book,home,away}:{book:string,home:number|null,away:number|null}) {
  return (
    <div style={{display:"grid",gridTemplateColumns:"1fr 70px 70px",gap:4,padding:"3px 0",borderBottom:"1px solid rgba(30,41,59,0.3)",alignItems:"center"}}>
      <span style={{fontSize:10,color:C.subtle}}>{book}</span>
      <span style={{fontSize:12,fontWeight:home!=null?700:400,color:home!=null?C.text:C.muted,textAlign:"center"}}>{fmtOdds(home)}</span>
      <span style={{fontSize:12,fontWeight:away!=null?700:400,color:away!=null?C.text:C.muted,textAlign:"center"}}>{fmtOdds(away)}</span>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [activeSport, setActiveSport] = useState<Sport>("MLB");
  const { events: rawEvents, loading, error } = useLiveScores(activeSport);

  const events = useMemo(() => {
    const seen = new Set<string>();
    return rawEvents.filter((e) => { if(seen.has(e.id))return false;seen.add(e.id);return true; });
  }, [rawEvents]);

  // Group events by date (EDT), sort chronologically
  const dateGroups = useMemo(() => {
    const groups: Record<string,SBEvent[]> = {};
    for(const ev of events){
      const dk = eventDateKey(ev.start_time) || "0000";
      if(!groups[dk])groups[dk]=[];
      groups[dk].push(ev);
    }
    const sorted = Object.entries(groups).sort(([a],[b])=>{
      if(a==="9999")return 1;if(b==="9999")return -1;
      return new Date(a).getTime()-new Date(b).getTime();
    });
    for(const [,list] of sorted){ list.sort((a,b)=>new Date(a.start_time||0).getTime()-new Date(b.start_time||0).getTime()); }
    return sorted;
  }, [events]);

  // For display: today first, then next 1-2 groups, up to 8 games
  const displayGroups = useMemo(() => {
    const td = todayEDT();
    const result: {label:string,events:SBEvent[]}[] = [];
    let count = 0;
    for(const [dk,list] of dateGroups){
      if(dk===td){ result.push({label:dateLabel(list[0].start_time),events:list}); count+=list.length; break; }
    }
    for(const [dk,list] of dateGroups){
      if(dk===td)continue;
      if(count>=8)break;
      result.push({label:dateLabel(list[0].start_time),events:list.slice(0,8-count)});
      count+=Math.min(list.length,8-count);
    }
    return result;
  }, [dateGroups]);

  const mlBooks = useMemo(() => {
    const map:Record<string,{home:number|null,away:number|null}> = {};
    for(const ev of events){for(const m of ev.markets){if(m.bet_type!=="moneyline")continue;for(const b of m.books){if(!b.available||b.moneyline==null)continue;const nm=formatBookmakerName(b.bookmaker);if(!map[nm])map[nm]={home:null,away:null};if(m.side==="home")map[nm].home=b.moneyline;if(m.side==="away")map[nm].away=b.moneyline;}}}
    const entries = Object.entries(map).filter(([,v])=>v.home!=null||v.away!=null);
    const teams = events.length>0?events[0].away_team?.abbreviation+" @ "+events[0].home_team?.abbreviation:"";
    let bestH=-Infinity,bestA=-Infinity,bkH="",bkA="";
    for(const [bk,v] of entries){if(v.home!=null&&v.home>bestH){bestH=v.home;bkH=bk;}if(v.away!=null&&v.away>bestA){bestA=v.away;bkA=bk;}}
    return {entries,teams,bestH,bestA,bkH,bkA};
  }, [events]);

  const allProps = useMemo(():PropItem[]=>{
    const seen = new Set<string>();
    const items:PropItem[]=[];
    for(const ev of events){for(const m of ev.markets){if(m.bet_type!=="player_prop"||!m.player_name)continue;for(const b of m.books){if(!b.available||b.over_under==null)continue;const book=formatBookmakerName(b.bookmaker);const key=[m.player_name,m.market_name,String(b.over_under),book].join("|");if(seen.has(key))continue;seen.add(key);items.push({player:m.player_name,matchup:ev.away_team?.abbreviation+" @ "+ev.home_team?.abbreviation,market:m.market_name,line:b.over_under,odds:b.moneyline,book,key});}}}
    items.sort((a,b)=>(b.odds??-Infinity)-(a.odds??-Infinity));
    return items.slice(0,5);
  }, [events]);

  const now = new Date();
  const dateStr = now.toLocaleDateString("en-US",{weekday:"long",month:"short",day:"numeric",timeZone:EDT});
  const sec:React.CSSProperties={fontSize:11,fontWeight:700,color:C.subtle,textTransform:"uppercase",letterSpacing:1,margin:0};

  return (
    <div style={{maxWidth:1280,margin:"0 auto",padding:"16px 24px 56px",color:C.text}}>

      {/* HEADER */}
      <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",marginBottom:16,flexWrap:"wrap",gap:8}}>
        <div>
          <h1 style={{fontSize:22,fontWeight:800,margin:0,lineHeight:1.15,letterSpacing:-0.5}}>SB ME DFS AI</h1>
          <p style={{fontSize:13,color:C.gold,margin:0,fontWeight:600}}>Today&apos;s Command Center</p>
          <p style={{fontSize:10,color:C.subtle,margin:"3px 0 0"}}>{dateStr} {"\u00b7"} Live Data</p>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:8}}>
          <span style={{padding:"3px 10px",borderRadius:6,fontSize:10,fontWeight:700,background:"rgba(34,197,94,0.1)",border:"1px solid rgba(34,197,94,0.2)",color:"#22c55e",display:"flex",alignItems:"center",gap:5}}>
            <span style={{width:5,height:5,borderRadius:"50%",background:"#22c55e",display:"inline-block"}}/> LIVE DATA
          </span>
          {user&&<span style={{padding:"3px 10px",borderRadius:6,fontSize:10,fontWeight:600,background:"rgba(201,168,76,0.08)",border:"1px solid rgba(201,168,76,0.25)",color:C.gold}}>{user.plan||"Free"} Plan</span>}
        </div>
      </div>

      {/* QUICK ACTIONS */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:8,marginBottom:14}}>
        {QUICK.map((a,i)=>{const Icon=a.icon;return(
          <Link key={i} href={a.href} style={{background:C.card,borderRadius:12,border:"1px solid "+C.border,padding:"11px 6px",textAlign:"center",textDecoration:"none",display:"flex",flexDirection:"column",alignItems:"center",gap:5}}>
            <Icon size={20} color={C.gold}/><span style={{fontSize:10,fontWeight:600,color:C.text,whiteSpace:"nowrap"}}>{a.label}</span>
          </Link>
        );})}
      </div>

      {/* BUILD YOUR PARLAY — COMPACT PROMO */}
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:12,padding:"10px 14px",borderRadius:10,background:"rgba(201,168,76,0.06)",border:"1px solid rgba(201,168,76,0.15)",marginBottom:14,flexWrap:"wrap"}}>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <div style={{width:32,height:32,borderRadius:8,background:"rgba(201,168,76,0.15)",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>
            <Swords size={16} color={C.gold}/>
          </div>
          <div>
            <div style={{fontSize:12,fontWeight:800,color:C.text,letterSpacing:-0.3}}>BUILD YOUR PARLAY</div>
            <div style={{fontSize:10,color:C.subtle}}>Moneylines · Spreads · Totals · Player Props</div>
            <div style={{fontSize:9,color:C.muted}}>55+ Supported Sportsbooks & Platforms · Availability varies by sport and event.</div>
          </div>
        </div>
        <div style={{display:"flex",gap:6,flexShrink:0}}>
          <Link href="/market-tools/parlay" style={{textDecoration:"none",padding:"7px 14px",borderRadius:6,background:"rgba(201,168,76,0.15)",border:"1px solid rgba(201,168,76,0.3)",color:C.gold,fontSize:11,fontWeight:700,whiteSpace:"nowrap"}}>OPEN PARLAY BUILDER →</Link>
          <Link href="/ai" style={{textDecoration:"none",padding:"7px 12px",borderRadius:6,background:"transparent",border:"1px solid rgba(30,41,59,0.5)",color:C.muted,fontSize:11,fontWeight:600,whiteSpace:"nowrap"}}>ASK SB ME AI →</Link>
        </div>
      </div>

      {/* SPORT TABS */}
      <div style={{display:"flex",gap:4,marginBottom:14,flexWrap:"wrap"}}>
        {SPORTS.map(s=>(
          <button key={s} onClick={()=>setActiveSport(s)} style={{padding:"4px 12px",borderRadius:6,fontSize:11,fontWeight:700,background:activeSport===s?"rgba(201,168,76,0.1)":C.card,border:activeSport===s?"1px solid "+C.gold:"1px solid "+C.border,color:activeSport===s?C.gold:C.muted,cursor:"pointer"}}>{s}</button>
        ))}
      </div>

      {/* TWO-COLUMN: GAMES + INSIGHTS */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 310px",gap:14,marginBottom:14}}>
        <div style={{background:C.card,borderRadius:14,border:"1px solid "+C.border,padding:14}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:10}}>
            <h2 style={sec}>{activeSport} {"\u2014"} Today&apos;s Games</h2>
            <Link href="/data-hub" style={{fontSize:10,color:C.gold,textDecoration:"none",display:"flex",alignItems:"center",gap:2}}>View All <ChevronRight size={10}/></Link>
          </div>
          {loading ? (
            <div style={{textAlign:"center",padding:36,color:C.muted,fontSize:12}}><Activity size={16} style={{marginBottom:4,opacity:0.3}}/><p style={{margin:0}}>Loading {activeSport} games...</p></div>
          ) : error ? (
            <div style={{textAlign:"center",padding:36,color:"#ef4444",fontSize:12}}>Unable to load {activeSport} games</div>
          ) : displayGroups.length===0 ? (
            <div style={{textAlign:"center",padding:36,color:C.subtle,fontSize:12}}>No {activeSport} games scheduled.</div>
          ) : (
            displayGroups.map((grp,gi)=>(
              <div key={gi} style={{marginBottom:gi<displayGroups.length-1?14:0}}>
                <div style={{fontSize:10,fontWeight:700,color:C.gold,textTransform:"uppercase",letterSpacing:1,marginBottom:6}}>{grp.label}</div>
                <div style={{display:"grid",gap:5}}>{grp.events.map(evt=><GameStrip key={evt.id} event={evt}/>)}</div>
              </div>
            ))
          )}
        </div>

        <div style={{background:C.card,borderRadius:14,border:"1px solid "+C.border,padding:14}}>
          <h2 style={{...sec,marginBottom:10}}>Insights</h2>
          <div style={{display:"flex",flexDirection:"column",gap:8}}>
            <div style={{padding:"9px 12px",borderRadius:8,background:"rgba(255,255,255,0.02)",border:"1px solid rgba(30,41,59,0.5)"}}>
              <div style={{fontSize:10,color:C.subtle,fontWeight:700,textTransform:"uppercase",marginBottom:1}}>Top Projection</div>
              <div style={{fontSize:14,fontWeight:800,color:C.muted}}>{"\u2014"}</div>
              <div style={{fontSize:9,color:C.subtle}}>Slate not published</div>
            </div>
            <div style={{padding:"9px 12px",borderRadius:8,background:"rgba(255,255,255,0.02)",border:"1px solid rgba(30,41,59,0.5)"}}>
              <div style={{fontSize:10,color:C.subtle,fontWeight:700,textTransform:"uppercase",marginBottom:1}}>Best Value</div>
              <div style={{fontSize:14,fontWeight:800,color:C.muted}}>{"\u2014"}</div>
              <div style={{fontSize:9,color:C.subtle}}>No DFS salary data</div>
            </div>
            <Link href="/ai" style={{textDecoration:"none"}}>
              <div style={{padding:"9px 12px",borderRadius:8,background:"rgba(201,168,76,0.06)",border:"1px solid rgba(201,168,76,0.15)",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
                <div style={{display:"flex",alignItems:"center",gap:8}}>
                  <Sparkles size={15} color={C.gold}/><div><div style={{fontSize:12,fontWeight:700,color:C.text}}>Ask SB ME AI</div><div style={{fontSize:10,color:C.subtle}}>Get analysis & picks</div></div>
                </div><ChevronRight size={12} color={C.gold}/>
              </div></Link>
          </div>
        </div>
      </div>
{/* THREE-COLUMN MARKET DATA */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:14}}>
        {/* BEST AVAILABLE ODDS */}
        <div style={{background:C.card,borderRadius:14,border:"1px solid "+C.border,padding:14}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8}}>
            <h3 style={sec}>Best Available Odds</h3>
            <Link href="/market-tools" style={{fontSize:10,color:C.gold,textDecoration:"none"}}>Compare {"\u2192"}</Link>
          </div>
          {mlBooks.entries.length>0?<div>
            <div style={{fontSize:10,color:C.subtle,marginBottom:6,fontWeight:600}}>{mlBooks.teams||activeSport+" Moneyline"}</div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 70px 70px",gap:4,padding:"2px 0 4px",borderBottom:"1px solid rgba(201,168,76,0.3)",alignItems:"center"}}>
              <span style={{fontSize:9,color:C.gold,fontWeight:700,textTransform:"uppercase"}}>Book</span>
              <span style={{fontSize:9,color:C.gold,fontWeight:700,textAlign:"center"}}>Home</span>
              <span style={{fontSize:9,color:C.gold,fontWeight:700,textAlign:"center"}}>Away</span>
            </div>
            {mlBooks.entries.slice(0,6).map(([bk,v],i)=><MLRow key={i} book={bk} home={v.home} away={v.away}/>)}
          </div>:<div style={{textAlign:"center",padding:20,color:C.subtle,fontSize:11}}>No odds available for {activeSport}</div>}
        </div>

        {/* FEATURED PLAYER PROPS */}
        <div style={{background:C.card,borderRadius:14,border:"1px solid "+C.border,padding:14}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8}}>
            <h3 style={sec}>Featured Player Props</h3>
            <Link href="/market-tools" style={{fontSize:10,color:C.gold,textDecoration:"none"}}>View All {"\u2192"}</Link>
          </div>
          {allProps.length>0?<div style={{display:"flex",flexDirection:"column",gap:6}}>
            {allProps.map((p,i)=><PropRow key={i} p={p}/>)}
          </div>:<div style={{textAlign:"center",padding:20,color:C.subtle,fontSize:11}}>No props available for {activeSport}</div>}
        </div>

        {/* TOP DFS VALUES */}
        <div style={{background:C.card,borderRadius:14,border:"1px solid "+C.border,padding:14}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8}}>
            <h3 style={sec}>Top DFS Values</h3>
            <Link href="/data-hub" style={{fontSize:10,color:C.gold,textDecoration:"none"}}>Open Data Hub {"\u2192"}</Link>
          </div>
          <div style={{textAlign:"center",padding:"20px 16px"}}>
            <div style={{fontSize:24,marginBottom:6,opacity:0.3}}>{"\u231b"}</div>
            <div style={{fontSize:11,fontWeight:700,color:C.subtle,marginBottom:4}}>No current DFS salary slate</div>
            <div style={{fontSize:10,color:C.muted,marginBottom:12}}>Upload a DraftKings or FanDuel slate to calculate today&apos;s DFS values.</div>
            <Link href="/data-hub" style={{textDecoration:"none",display:"inline-flex",alignItems:"center",gap:6,padding:"7px 18px",borderRadius:8,background:"rgba(201,168,76,0.1)",border:"1px solid rgba(201,168,76,0.25)",color:C.gold,fontSize:11,fontWeight:700}}>
              <Upload size={13}/> Upload Slate
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
