"use client";

import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import {
  Flame, MessageCircle, List, Activity, ChevronRight, Zap, Sparkles, AlertCircle, BarChart3, Target,
} from "lucide-react";
import { useState, useMemo } from "react";
import { useLiveScores } from "@/lib/live-scores";
import type { SBEvent } from "@/lib/sbevent";
import { formatBookmakerName } from "@/lib/bookmakers";

const SPORTS = ["MLB","NFL","NBA","NHL","NCAAF","NCAAB","WNBA"] as const;
type Sport = typeof SPORTS[number];

const QUICK = [
  { icon: Flame, label: "Build Lineup", href: "/optimizer" },
  { icon: BarChart3, label: "Market Tools", href: "/market-tools" },
  { icon: MessageCircle, label: "Ask SB ME AI", href: "/ai" },
  { icon: List, label: "My Lineups", href: "/lineups" },
];

const CC = { card: "#0a0f24", border: "#1e293b", text: "#f0f6fc", muted: "#94a3b8", subtle: "#64748b", gold: "#c9a84c" };

function fmtOdds(v: number | null | undefined) { if(v==null) return "\u2014"; return v>0 ? "+"+v : ""+v; }
function isLive(s: string) { return (s||"").toUpperCase()==="LIVE"; }
function st(ev: SBEvent) {
  if (ev.status_display) return ev.status_display;
  if (isLive(ev.status)) return "LIVE";
  if ((ev.status||"").toUpperCase()==="FINAL") return "Final";
  if (!ev.start_time) return "TBD";
  return new Date(ev.start_time).toLocaleTimeString([],{hour:"numeric",minute:"2-digit",timeZoneName:"short"});
}

function GameStrip({event}:{event:SBEvent}) {
  const live = isLive(event.status);
  const showScore = live && (event.home_score!=null||event.away_score!=null);
  return (
    <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"10px 16px",borderRadius:12,background:live?"rgba(201,168,76,0.04)":CC.card,border:live?"1px solid rgba(201,168,76,0.15)":"1px solid "+CC.border,gap:10}}>
      <div style={{display:"flex",alignItems:"center",gap:10,minWidth:0}}>
        <span style={{padding:"2px 7px",borderRadius:5,fontSize:9,fontWeight:800,background:live?"rgba(239,68,68,0.15)":"rgba(100,116,139,0.1)",color:live?"#ef4444":CC.subtle,flexShrink:0,whiteSpace:"nowrap"}}>
          {live?"LIVE":st(event)}
        </span>
        <span style={{fontSize:13,fontWeight:700,color:CC.text,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>
          {event.away_team?.abbreviation||"AWY"} {"@"} {event.home_team?.abbreviation||"HOM"}
        </span>
      </div>
      {showScore&&(
        <span style={{fontSize:15,fontWeight:800,color:CC.gold,flexShrink:0}}>{event.away_score??0} {"–"} {event.home_score??0}</span>
      )}
    </div>
  );
}

function InsightTile({label,value,sub}:{label:string,value:string,sub:string}) {
  return (
    <div style={{padding:"10px 12px",borderRadius:10,background:"rgba(255,255,255,0.02)",border:"1px solid "+CC.border}}>
      <div style={{fontSize:10,color:CC.subtle,fontWeight:700,textTransform:"uppercase",marginBottom:1}}>{label}</div>
      <div style={{fontSize:14,fontWeight:800,color:CC.muted}}>{value}</div>
      <div style={{fontSize:9,color:CC.subtle}}>{sub}</div>
    </div>
  );
}

function MLStat({label,value,book}:{label:string,value:string,book:string}) {
  return (
    <div style={{padding:"9px 10px",borderRadius:10,background:"rgba(201,168,76,0.04)",textAlign:"center"}}>
      <div style={{fontSize:9,color:CC.subtle,textTransform:"uppercase"}}>{label}</div>
      <div style={{fontSize:17,fontWeight:800,color:CC.gold,lineHeight:1.3}}>{value}</div>
      <div style={{fontSize:9,color:CC.subtle}}>{book}</div>
    </div>
  );
}

function PropCard({p}:{p:{name:string,event:string,markets:string[],line:number|null,odds:number|null,book:string}}) {
  return (
    <div style={{padding:"10px 12px",borderRadius:10,border:"1px solid "+CC.border,background:"rgba(255,255,255,0.02)"}}>
      <div style={{fontSize:13,fontWeight:700,color:CC.text,marginBottom:2}}>{p.name}</div>
      <div style={{fontSize:10,color:CC.subtle,marginBottom:2}}>{p.event}</div>
      <div style={{fontSize:10,color:CC.muted}}>{p.markets.join(", ")}</div>
      <div style={{display:"flex",alignItems:"center",gap:12,marginTop:6}}>
        <span style={{fontSize:14,fontWeight:800,color:CC.gold}}>{p.line}</span>
        <span style={{fontSize:13,fontWeight:600,color:CC.muted}}>{fmtOdds(p.odds)}</span>
        <span style={{fontSize:10,color:CC.subtle,marginLeft:"auto"}}>{p.book}</span>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [activeSport, setActiveSport] = useState<Sport>("MLB");
  const { events: rawEvents, loading, error } = useLiveScores(activeSport);

  const events = useMemo(() => {
    const seen = new Set<string>();
    return rawEvents.filter((e) => { if (seen.has(e.id)) return false; seen.add(e.id); return true; });
  }, [rawEvents]);

  const displayGames = useMemo(() => {
    const live = events.filter((e) => isLive(e.status));
    const up = events.filter((e) => !isLive(e.status) && (e.status||"").toUpperCase()!=="FINAL");
    return [...live, ...up].slice(0, 8);
  }, [events]);

  const bestML = useMemo(() => {
    let bestH=-Infinity,bestA=-Infinity,bkH="",bkA="",teams="";
    for(const ev of events){for(const m of ev.markets){if(m.bet_type!=="moneyline")continue;if(!teams)teams=ev.away_team?.abbreviation+" @ "+ev.home_team?.abbreviation;for(const b of m.books){if(!b.available)continue;const nm=formatBookmakerName(b.bookmaker);if(m.side==="home"&&b.moneyline!=null&&b.moneyline>bestH){bestH=b.moneyline;bkH=nm;}if(m.side==="away"&&b.moneyline!=null&&b.moneyline>bestA){bestA=b.moneyline;bkA=nm;}}}}
    return {bestH,bestA,bkH,bkA,teams};
  }, [events]);

  const featuredProps = useMemo(() => {
    const map:Record<string,{name:string,event:string,markets:string[],line:number|null,odds:number|null,book:string}> = {};
    for(const ev of events){for(const m of ev.markets){if(m.bet_type!=="player_prop"||!m.player_name)continue;const k=m.player_name.toLowerCase();if(!map[k])map[k]={name:m.player_name,event:(ev.away_team?.abbreviation||"AWY")+" @ "+(ev.home_team?.abbreviation||"HOM"),markets:[],line:null,odds:null,book:""};for(const b of m.books){if(!b.available||b.over_under==null)continue;if(map[k].line==null||(b.moneyline!=null&&b.moneyline>(map[k].odds??-Infinity))){map[k].line=b.over_under;map[k].odds=b.moneyline;map[k].book=formatBookmakerName(b.bookmaker);}}if(!map[k].markets.includes(m.market_name))map[k].markets.push(m.market_name);}}
    return Object.values(map).filter((p:any)=>p.line!=null).slice(0,3);
  }, [events]);

  const now = new Date();
  const dateStr = now.toLocaleDateString("en-US",{weekday:"long",month:"short",day:"numeric"});

  return (
    <div style={{maxWidth:1280,margin:"0 auto",padding:"20px 24px 64px",color:CC.text}}>
      {/* HEADER */}
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:18,flexWrap:"wrap",gap:10}}>
        <div>
          <div style={{display:"flex",alignItems:"center",gap:10}}>
            <Image src="/logo.png" alt="SB ME" width={30} height={16} priority style={{flexShrink:0}}/>
            <div>
              <h1 style={{fontSize:19,fontWeight:800,margin:0,lineHeight:1.2}}>SB ME DFS AI</h1>
              <p style={{fontSize:11,color:CC.gold,margin:0,fontWeight:600}}>Today&apos;s Command Center</p>
            </div>
          </div>
          <p style={{fontSize:10,color:CC.subtle,margin:"2px 0 0 40px"}}>{dateStr} &middot; Live Data</p>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:8}}>
          <span style={{padding:"3px 10px",borderRadius:7,fontSize:10,fontWeight:700,background:"rgba(34,197,94,0.1)",border:"1px solid rgba(34,197,94,0.2)",color:"#22c55e",display:"flex",alignItems:"center",gap:5}}>
            <span style={{width:5,height:5,borderRadius:"50%",background:"#22c55e",display:"inline-block"}}/> LIVE DATA
          </span>
          {user&&<span style={{padding:"3px 10px",borderRadius:7,fontSize:10,fontWeight:600,background:"rgba(201,168,76,0.08)",border:"1px solid rgba(201,168,76,0.25)",color:CC.gold}}>{user.plan||"Free"} Plan</span>}
        </div>
      </div>

      {/* QUICK ACTIONS */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:10,marginBottom:18}}>
        {QUICK.map((a,i)=>{const Icon=a.icon;return(<Link key={i} href={a.href} style={{background:CC.card,borderRadius:14,border:"1px solid "+CC.border,padding:"13px 10px",textAlign:"center",textDecoration:"none",display:"flex",flexDirection:"column",alignItems:"center",gap:7}}>
          <Icon size={22} color={CC.gold}/><span style={{fontSize:11,fontWeight:600,color:CC.text}}>{a.label}</span></Link>);})}
      </div>

      {/* SPORT TABS */}
      <div style={{display:"flex",gap:4,marginBottom:18,flexWrap:"wrap"}}>
        {SPORTS.map(s=>(<button key={s} onClick={()=>setActiveSport(s)} style={{padding:"5px 13px",borderRadius:7,fontSize:11,fontWeight:700,background:activeSport===s?"rgba(201,168,76,0.1)":CC.card,border:activeSport===s?"1px solid "+CC.gold:"1px solid "+CC.border,color:activeSport===s?CC.gold:CC.muted,cursor:"pointer"}}>{s}</button>))}
      </div>

      {/* TWO-COLUMN: GAMES + INSIGHTS */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 310px",gap:18,marginBottom:24}}>
        <div style={{background:CC.card,borderRadius:16,border:"1px solid "+CC.border,padding:18}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:12}}>
            <h2 style={{fontSize:12,fontWeight:700,color:CC.subtle,textTransform:"uppercase",letterSpacing:1,margin:0}}>{activeSport} {"—"} Today&apos;s Games</h2>
            <Link href="/data-hub" style={{fontSize:10,color:CC.gold,textDecoration:"none",display:"flex",alignItems:"center",gap:3}}>View All <ChevronRight size={11}/></Link>
          </div>
          {loading?<div style={{textAlign:"center",padding:44,color:CC.muted,fontSize:13}}><Activity size={18} style={{marginBottom:6,opacity:0.3}}/><p style={{margin:0}}>Loading games...</p></div>
          :error?<div style={{textAlign:"center",padding:44,color:"#ef4444",fontSize:13}}>Unable to load games</div>
          :displayGames.length===0?<div style={{textAlign:"center",padding:44,color:CC.subtle,fontSize:13}}>No {activeSport} games scheduled.</div>
          :<div style={{display:"grid",gap:5}}>{displayGames.map(evt=><GameStrip key={evt.id} event={evt}/>)}</div>}
        </div>

        <div style={{background:CC.card,borderRadius:16,border:"1px solid "+CC.border,padding:18}}>
          <h2 style={{fontSize:12,fontWeight:700,color:CC.subtle,textTransform:"uppercase",letterSpacing:1,margin:"0 0 12px"}}>Insights</h2>
          <div style={{display:"flex",flexDirection:"column",gap:8}}>
            <InsightTile label="Top Projection" value={"—"} sub="Slate not published"/>
            <InsightTile label="Best Value" value={"—"} sub="No DFS salary data"/>
            <Link href="/ai" style={{textDecoration:"none"}}>
              <div style={{padding:"10px 12px",borderRadius:10,background:"rgba(201,168,76,0.06)",border:"1px solid rgba(201,168,76,0.15)",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
                <div style={{display:"flex",alignItems:"center",gap:8}}>
                  <Sparkles size={15} color={CC.gold}/><div><div style={{fontSize:12,fontWeight:700,color:CC.text}}>Ask SB ME AI</div><div style={{fontSize:10,color:CC.subtle}}>Get analysis & picks</div></div>
                </div><ChevronRight size={12} color={CC.gold}/>
              </div></Link>
          </div>
        </div>
      </div>

      {/* THREE-COLUMN MARKET DATA */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:18}}>
        {/* Best Available Odds */}
        <div style={{background:CC.card,borderRadius:16,border:"1px solid "+CC.border,padding:18}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:10}}>
            <h3 style={{fontSize:11,fontWeight:700,color:CC.subtle,textTransform:"uppercase",letterSpacing:1,margin:0}}>Best Available Odds</h3>
            <Link href="/market-tools" style={{fontSize:10,color:CC.gold,textDecoration:"none"}}>Compare &rarr;</Link>
          </div>
          {bestML.teams?<div>
            <div style={{fontSize:10,color:CC.subtle,marginBottom:8}}>{bestML.teams}</div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
              <MLStat label="Best Home ML" value={fmtOdds(bestML.bestH)} book={bestML.bkH}/>
              <MLStat label="Best Away ML" value={fmtOdds(bestML.bestA)} book={bestML.bkA}/>
            </div>
          </div>:<div style={{textAlign:"center",padding:24,color:CC.subtle,fontSize:12}}>No odds available for {activeSport}</div>}
        </div>

        {/* Featured Player Props */}
        <div style={{background:CC.card,borderRadius:16,border:"1px solid "+CC.border,padding:18}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:10}}>
            <h3 style={{fontSize:11,fontWeight:700,color:CC.subtle,textTransform:"uppercase",letterSpacing:1,margin:0}}>Featured Player Props</h3>
            <Link href="/market-tools" style={{fontSize:10,color:CC.gold,textDecoration:"none"}}>View All &rarr;</Link>
          </div>
          {featuredProps.length>0?<div style={{display:"flex",flexDirection:"column",gap:10}}>
            {(featuredProps as any[]).map((p:any,i:number)=><PropCard key={i} p={p}/>)}
          </div>:<div style={{textAlign:"center",padding:24,color:CC.subtle,fontSize:12}}>No props available for {activeSport}</div>}
        </div>

        {/* Top DFS Values */}
        <div style={{background:CC.card,borderRadius:16,border:"1px solid "+CC.border,padding:18}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:10}}>
            <h3 style={{fontSize:11,fontWeight:700,color:CC.subtle,textTransform:"uppercase",letterSpacing:1,margin:0}}>Top DFS Values</h3>
            <Link href="/data-hub" style={{fontSize:10,color:CC.gold,textDecoration:"none"}}>Open Data Hub &rarr;</Link>
          </div>
          <div style={{textAlign:"center",padding:24,color:CC.subtle,fontSize:12}}>
            Upload a current DraftKings or FanDuel slate to populate values.
          </div>
        </div>
      </div>
    </div>
  );
}
