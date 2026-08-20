"use client";

import { useState, useMemo, useCallback } from "react";
import { Layers, X, ChevronRight, SearchIcon } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import type { SBEvent, SBMarket, SBBookLine } from "@/lib/sbevent";
import { formatBookmakerName, buildBookmakerUniverse } from "@/lib/bookmakers";

const LEAGUES = ["MLB","NFL","NBA","NHL","NCAAF","NCAAB"] as const;
type League = typeof LEAGUES[number];
const BET_TYPES = ["moneyline","spread","total","player_prop","other"] as const;

interface Leg {
  id: string; eventName: string; market: string; selection: string;
  odds: number; bookmaker: string;
}

const EDT = "America/New_York";
const C = { card:"#0a0f24", border:"#1e293b", text:"#f0f6fc", muted:"#94a3b8", subtle:"#64748b", gold:"#c9a84c" };

function fmtOdds(v:number|null|undefined){ if(v==null)return"\u2014"; return v>0?"+"+v:""+v; }
function fmtSpread(v:number|null|undefined){ if(v==null)return"PK"; return v>0?"+"+v:""+v; }
function americanToDecimal(am:number){ return am>0?1+am/100:1+100/Math.abs(am); }

function todayEDT(){ return new Date().toLocaleDateString("en-US",{timeZone:EDT}); }
function tomorrowEDT(){ const d=new Date();d.setDate(d.getDate()+1);return d.toLocaleDateString("en-US",{timeZone:EDT}); }
function eventDateKey(iso:string|null):string {
  if(!iso)return"9999"; return new Date(iso).toLocaleDateString("en-US",{timeZone:EDT});
}
function dateLabel(iso:string|null):string {
  const dk=eventDateKey(iso); if(!dk||dk==="9999")return"Upcoming";
  const ts=iso||"";
  if(dk===todayEDT())return"TODAY \u2014 "+new Date(ts).toLocaleDateString("en-US",{timeZone:EDT,weekday:"long",month:"long",day:"numeric"}).toUpperCase();
  if(dk===tomorrowEDT())return"TOMORROW \u2014 "+new Date(ts).toLocaleDateString("en-US",{timeZone:EDT,weekday:"long",month:"long",day:"numeric"}).toUpperCase();
  return new Date(ts).toLocaleDateString("en-US",{timeZone:EDT,weekday:"long",month:"long",day:"numeric"}).toUpperCase();
}
function timeEDT(iso:string|null):string {
  if(!iso)return"TBD"; return new Date(iso).toLocaleTimeString("en-US",{timeZone:EDT,hour:"numeric",minute:"2-digit"})+" EDT";
}

function getBook(books:SBBookLine[],bookmaker:string):SBBookLine|undefined {
  if(!bookmaker)return undefined; return books.find(b=>b.bookmaker===bookmaker);
}


function SelectorBtn({label,odds,selected,disabled,onClick}:{label:string,odds:string,selected?:boolean,disabled?:boolean,onClick:()=>void}) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      padding:"8px 10px",borderRadius:8,width:"100%",cursor:disabled?"not-allowed":"pointer",
      background:selected?"rgba(201,168,76,0.12)":"rgba(255,255,255,0.02)",
      border:selected?"1px solid rgba(201,168,76,0.4)":"1px solid rgba(30,41,59,0.5)",
      opacity:disabled?0.4:1,textAlign:"left",display:"flex",justifyContent:"space-between",alignItems:"center",
      color:C.text,fontSize:12,fontWeight:600,transition:"all 0.1s",
    }}>
      <span>{label}</span>
      <span style={{color:selected?C.gold:C.gold,fontWeight:700}}>{odds}</span>
    </button>
  );
}

function MarketLegs({betType,markets,event,bookmaker,onAdd,propFilter,legs}:{
  betType:string;markets:SBMarket[];event:SBEvent;bookmaker:string;
  onAdd:(market:string,selection:string,odds:number)=>void;propFilter:string;legs:Leg[];
}) {
  if(!markets.length) return <p style={{color:C.subtle,fontSize:11,textAlign:"center",padding:10}}>No {betType} markets.</p>;

  if(betType==="moneyline") {
    const home=markets.find(m=>m.side?.toLowerCase()==="home");
    const away=markets.find(m=>m.side?.toLowerCase()==="away");
    const hb=home?getBook(home.books,bookmaker):undefined;
    const ab=away?getBook(away.books,bookmaker):undefined;
    const awName=event.away_team?.abbreviation||"Away";
    const hmName=event.home_team?.abbreviation||"Home";
    const awAdded=legs.some(l=>l.eventName.includes(awName)&&l.market==="Moneyline");
    const hmAdded=legs.some(l=>l.eventName.includes(hmName)&&l.market==="Moneyline");
    return (
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
        <SelectorBtn label={awName} odds={fmtOdds(ab?.moneyline)} selected={awAdded} disabled={!ab} onClick={()=>{if(ab)onAdd("Moneyline",awName,ab.moneyline??-110);}}/>
        <SelectorBtn label={hmName} odds={fmtOdds(hb?.moneyline)} selected={hmAdded} disabled={!hb} onClick={()=>{if(hb)onAdd("Moneyline",hmName,hb.moneyline??-110);}}/>
      </div>
    );
  }

  if(betType==="spread") {
    const home=markets.find(m=>m.side?.toLowerCase()==="home");
    const away=markets.find(m=>m.side?.toLowerCase()==="away");
    const hb=home?getBook(home.books,bookmaker):undefined;
    const ab=away?getBook(away.books,bookmaker):undefined;
    const awName=event.away_team?.abbreviation||"Away";
    const hmName=event.home_team?.abbreviation||"Home";
    return (
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
        <SelectorBtn label={awName+" "+fmtSpread(ab?.spread)} odds={fmtOdds(ab?.moneyline)} disabled={!ab} onClick={()=>{if(ab)onAdd("Spread",awName+" "+fmtSpread(ab.spread),ab.moneyline??-110);}}/>
        <SelectorBtn label={hmName+" "+fmtSpread(hb?.spread)} odds={fmtOdds(hb?.moneyline)} disabled={!hb} onClick={()=>{if(hb)onAdd("Spread",hmName+" "+fmtSpread(hb.spread),hb.moneyline??-110);}}/>
      </div>
    );
  }

  if(betType==="total") {
    const over=markets.find(m=>m.side?.toLowerCase()==="over");
    const under=markets.find(m=>m.side?.toLowerCase()==="under");
    const ob=over?getBook(over.books,bookmaker):undefined;
    const ub=under?getBook(under.books,bookmaker):undefined;
    const line=ob?.over_under??ub?.over_under??null;
    return (
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
        <SelectorBtn label={"Over "+(line??"?")} odds={fmtOdds(ob?.moneyline)} disabled={!ob} onClick={()=>{if(ob)onAdd("Total","Over "+(line??"?"),ob.moneyline??-110);}}/>
        <SelectorBtn label={"Under "+(line??"?")} odds={fmtOdds(ub?.moneyline)} disabled={!ub} onClick={()=>{if(ub)onAdd("Total","Under "+(line??"?"),ub.moneyline??-110);}}/>
      </div>
    );
  }

  // player_prop + other — render with optional filter
  const filtered = propFilter ? markets.filter(m=>m.player_name?.toLowerCase().includes(propFilter.toLowerCase())||m.market_name?.toLowerCase().includes(propFilter.toLowerCase())) : markets.slice(0,30);
  return (
    <div style={{display:"flex",flexDirection:"column",gap:6}}>
      {filtered.map((m,i)=>{
        const bk=getBook(m.books,bookmaker);
        if(!bk||!bk.available)return null;
        const label=(m.player_name||"")+" "+(m.market_name||"")+" "+(bk.over_under??"");
        return (
          <SelectorBtn key={i} label={label} odds={fmtOdds(bk.moneyline)} selected={false}
            onClick={()=>onAdd(m.market_name||betType,label,bk.moneyline??-100)}/>
        );
      })}
      {filtered.length===0&&<p style={{color:C.subtle,fontSize:11,textAlign:"center",padding:6}}>No matching props</p>}
    </div>
  );
}


export default function ParlayBuilderPage() {
  const [activeLeague,setActiveLeague]=useState<League>("MLB");
  const [legs,setLegs]=useState<Leg[]>([]);
  const [stake,setStake]=useState("10");
  const [selectedGameId,setSelectedGameId]=useState<string|null>(null);
  const [selectedBetType,setSelectedBetType]=useState<string>("moneyline");
  const [selectedBook,setSelectedBook]=useState<string>("");
  const [propFilter,setPropFilter]=useState("");

  const { events:rawEvents, loading } = useEvents(activeLeague);
  const events = useMemo(()=>{
    const seen=new Set<string>();
    return rawEvents.filter(e=>{if(seen.has(e.id))return false;seen.add(e.id);return true;});
  },[rawEvents]);

  const dateGroups = useMemo(()=>{
    const groups:Record<string,SBEvent[]>={};
    for(const ev of events){const dk=eventDateKey(ev.start_time)||"0000";if(!groups[dk])groups[dk]=[];groups[dk].push(ev);}
    return Object.entries(groups).sort(([a],[b])=>{
      if(a==="9999")return 1;if(b==="9999")return -1;
      return new Date(a).getTime()-new Date(b).getTime();
    }).map(([dk,list])=>({date:dk,label:dateLabel(list[0].start_time),events:list.sort((a,b)=>new Date(a.start_time||0).getTime()-new Date(b.start_time||0).getTime())}));
  },[events]);

  const availableBooks = useMemo(()=>buildBookmakerUniverse(events.map(e=>e.bookmakers)),[events]);
  useMemo(()=>{if(selectedBook&&!availableBooks.includes(selectedBook))setSelectedBook("");},[availableBooks,selectedBook]);

  const selectedGame = useMemo(()=>events.find(e=>e.id===selectedGameId)||null,[events,selectedGameId]);
  const expandedMarkets = useMemo(()=>{
    if(!selectedGame)return {};
    const groups:Record<string,SBMarket[]>={};
    for(const m of selectedGame.markets||[]){const k=m.bet_type;if(!groups[k])groups[k]=[];groups[k].push(m);}
    return groups;
  },[selectedGame]);

  const addLeg = useCallback((event:SBEvent,market:string,selection:string,odds:number)=>{
    const evName = event.away_team?.abbreviation+" @ "+event.home_team?.abbreviation;
    setLegs(prev=>[...prev,{id:Date.now()+"-"+Math.random().toString(36).slice(2,6),eventName:evName,market,selection,odds,bookmaker:selectedBook}]);
  },[selectedBook]);

  const removeLeg = useCallback((id:string)=>setLegs(prev=>prev.filter(l=>l.id!==id)),[]);

  const result = useMemo(()=>{
    if(legs.length===0)return{odds:0,payout:0,profit:0};
    let dec=1;for(const l of legs)dec*=americanToDecimal(l.odds||0);
    const st=parseFloat(stake)||0,payout=dec*st,profit=payout-st;
    const am=dec>=2?Math.round((dec-1)*100):Math.round(-100/(dec-1));
    return{odds:am,payout,profit};
  },[legs,stake]);

  const allSameEvent = legs.length>=2&&legs.every(l=>l.eventName===legs[0]?.eventName);


  return (
    <div style={{maxWidth:"100%",margin:"0 auto",padding:"10px 16px 40px",color:C.text,minHeight:"100vh",display:"flex",flexDirection:"column"}}>
      {/* HEADER ROW */}
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:10,flexWrap:"wrap",gap:8}}>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <Layers size={22} color={C.gold}/>
          <h1 style={{fontSize:18,fontWeight:800,margin:0}}>Parlay Builder</h1>
        </div>
        <select value={selectedBook} onChange={e=>{setSelectedBook(e.target.value);setLegs([]);}} style={{
          padding:"6px 12px",borderRadius:8,fontSize:12,fontWeight:700,background:C.card,border:"1px solid "+C.border,color:C.gold,cursor:"pointer",minWidth:200,
        }}>
          <option value="" disabled>{loading?"Loading books…":"Select sportsbook ("+availableBooks.length+" available)"}</option>
          {availableBooks.map(b=><option key={b} value={b}>{formatBookmakerName(b)}</option>)}
        </select>
      </div>

      {/* LEAGUE TABS */}
      <div style={{display:"flex",gap:4,marginBottom:10,flexWrap:"wrap"}}>
        {LEAGUES.map(lg=>(
          <button key={lg} onClick={()=>{setActiveLeague(lg);setSelectedGameId(null);setSelectedBook("");setLegs([]);}}
            style={{padding:"4px 12px",borderRadius:6,fontSize:11,fontWeight:700,
              background:activeLeague===lg?"rgba(201,168,76,0.1)":C.card,
              border:activeLeague===lg?"1px solid "+C.gold:"1px solid "+C.border,
              color:activeLeague===lg?C.gold:C.muted,cursor:"pointer"}}>{lg}</button>
        ))}
      </div>

      {/* THREE-PANEL */}
      <div style={{display:"grid",gridTemplateColumns:"260px 280px 1fr",gap:10,flex:1,minHeight:0}}>

        {/* LEFT: My Parlay */}
        <div style={{background:C.card,borderRadius:14,border:"1px solid rgba(201,168,76,0.15)",padding:14,display:"flex",flexDirection:"column",overflow:"hidden"}}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:8}}>
            <span style={{fontSize:12,fontWeight:800,color:C.gold}}>My Parlay ({legs.length})</span>
            {legs.length>0&&<button onClick={()=>setLegs([])} style={{background:"none",border:"none",color:C.subtle,fontSize:10,cursor:"pointer"}}>Clear</button>}
          </div>
          {selectedBook&&<div style={{fontSize:9,color:C.subtle,marginBottom:6,padding:"3px 8px",borderRadius:4,background:"rgba(255,255,255,0.03)",textAlign:"center"}}>{formatBookmakerName(selectedBook)}</div>}
          {allSameEvent&&<div style={{fontSize:9,fontWeight:800,color:"#f97316",marginBottom:6,padding:"3px 8px",borderRadius:4,background:"rgba(249,115,22,0.15)",textAlign:"center"}}>SAME GAME PARLAY</div>}
          <div style={{flex:1,overflowY:"auto",minHeight:0}}>
            {legs.length===0?<p style={{color:C.subtle,fontSize:11,textAlign:"center",padding:20}}>Pick a sportsbook, then select games to add legs.</p>
            :legs.map(l=>(<div key={l.id} style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"6px 0",borderBottom:"1px solid rgba(30,41,59,0.5)",fontSize:11}}>
              <div style={{minWidth:0}}><div style={{fontWeight:600,color:C.text,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{l.eventName}</div><div style={{color:C.subtle,fontSize:9}}>{l.market} — {l.selection} @ {fmtOdds(l.odds)}</div></div>
              <button onClick={()=>removeLeg(l.id)} style={{background:"none",border:"none",cursor:"pointer",flexShrink:0}}><X size={14} color="#ef4444"/></button>
            </div>))}
          </div>
          {legs.length>=2&&(<div style={{borderTop:"1px solid "+C.border,paddingTop:10,marginTop:6}}>
            <div style={{display:"flex",justifyContent:"space-between",fontSize:11,marginBottom:4}}><span style={{color:C.subtle}}>Parlay Odds</span><span style={{fontWeight:800,color:C.gold}}>{fmtOdds(result.odds)}</span></div>
            <input type="text" value={stake} onChange={e=>setStake(e.target.value)} placeholder="Stake" style={{width:"100%",padding:"6px 10px",borderRadius:8,background:"#1a1f33",border:"1px solid "+C.border,color:C.text,fontSize:12,fontWeight:600,outline:"none",boxSizing:"border-box"}}/>
            <div style={{display:"flex",justifyContent:"space-between",fontSize:11,marginTop:6}}><span style={{color:C.subtle}}>Payout</span><span style={{fontWeight:800,color:C.gold}}>${result.payout.toFixed(2)}</span></div>
            <div style={{display:"flex",justifyContent:"space-between",fontSize:11}}><span style={{color:C.subtle}}>Profit</span><span style={{fontWeight:800,color:C.gold}}>${result.profit.toFixed(2)}</span></div>
          </div>)}
        </div>

        {/* CENTER: Games list */}
        <div style={{background:C.card,borderRadius:14,border:"1px solid "+C.border,padding:12,overflowY:"auto",display:"flex",flexDirection:"column"}}>
          <div style={{fontSize:10,fontWeight:700,color:C.subtle,textTransform:"uppercase",letterSpacing:1,marginBottom:8}}>{activeLeague} Games</div>
          {loading?<p style={{color:C.muted,fontSize:11,textAlign:"center",padding:20}}>Loading...</p>
          :events.length===0?<p style={{color:C.subtle,fontSize:11,textAlign:"center",padding:20}}>No {activeLeague} games.</p>
          :dateGroups.map((grp,gi)=>(
            <div key={gi} style={{marginBottom:gi<dateGroups.length-1?10:0}}>
              <div style={{fontSize:9,fontWeight:700,color:C.gold,textTransform:"uppercase",letterSpacing:1,marginBottom:4}}>{grp.label}</div>
              {grp.events.map(ev=>{
                const sel = selectedGameId===ev.id;
                return (<button key={ev.id} onClick={()=>setSelectedGameId(ev.id)} style={{
                  display:"flex",alignItems:"center",justifyContent:"space-between",width:"100%",padding:"7px 10px",borderRadius:8,marginBottom:2,fontSize:12,fontWeight:600,
                  background:sel?"rgba(201,168,76,0.08)":"rgba(255,255,255,0.01)",border:sel?"1px solid rgba(201,168,76,0.3)":"1px solid transparent",color:sel?C.gold:C.text,cursor:"pointer",textAlign:"left"
                }}>
                  <span style={{whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis",minWidth:0}}>{ev.away_team?.abbreviation||"AWY"} @ {ev.home_team?.abbreviation||"HOM"}</span>
                  <span style={{fontSize:9,color:C.subtle,flexShrink:0,marginLeft:4}}>{timeEDT(ev.start_time)}</span>
                </button>);
              })}
            </div>))}
        </div>

        {/* RIGHT: Markets */}
        <div style={{background:C.card,borderRadius:14,border:"1px solid "+C.border,padding:14,overflowY:"auto",display:"flex",flexDirection:"column"}}>
          {!selectedGame?(
            <div style={{flex:1,display:"flex",alignItems:"center",justifyContent:"center"}}><p style={{color:C.subtle,fontSize:12}}>Select a game to view markets</p></div>
          ):!selectedBook?(
            <div style={{flex:1,display:"flex",alignItems:"center",justifyContent:"center"}}><p style={{color:C.subtle,fontSize:12}}>Select a sportsbook</p></div>
          ):(
            <>
              <div style={{fontSize:12,fontWeight:700,color:C.text,marginBottom:2}}>{selectedGame.away_team?.abbreviation||"AWY"} @ {selectedGame.home_team?.abbreviation||"HOM"}</div>
              <div style={{fontSize:9,color:C.subtle,marginBottom:10}}>{formatBookmakerName(selectedBook)}</div>
              <div style={{display:"flex",gap:4,marginBottom:10,flexWrap:"wrap"}}>
                {BET_TYPES.map(bt=>{
                  const count=(expandedMarkets[bt]||[]).length;
                  return (<button key={bt} onClick={()=>setSelectedBetType(bt)} style={{
                    padding:"4px 10px",borderRadius:6,fontSize:10,fontWeight:600,
                    background:selectedBetType===bt?"rgba(201,168,76,0.1)":C.card,
                    border:selectedBetType===bt?"1px solid "+C.gold:"1px solid "+C.border,
                    color:selectedBetType===bt?C.gold:C.muted,cursor:"pointer"
                  }}>{bt==="moneyline"?"ML":bt==="spread"?"Spread":bt==="total"?"Total":bt==="player_prop"?"Props":"Other"} {count>0?count:""}</button>);
                })}
              </div>
              {(selectedBetType==="player_prop"||selectedBetType==="other")&&(
                <div style={{marginBottom:8,display:"flex",alignItems:"center",gap:6}}>
                  <SearchIcon size={12} color={C.subtle}/>
                  <input type="text" value={propFilter} onChange={e=>setPropFilter(e.target.value)} placeholder="Filter by player or market..." style={{
                    flex:1,padding:"5px 8px",borderRadius:6,background:"#1a1f33",border:"1px solid "+C.border,color:C.text,fontSize:11,outline:"none"
                  }}/>
                  {propFilter&&<button onClick={()=>setPropFilter("")} style={{background:"none",border:"none",color:C.subtle,cursor:"pointer",fontSize:10}}>Clear</button>}
                </div>
              )}
              <MarketLegs betType={selectedBetType} markets={expandedMarkets[selectedBetType]||[]} event={selectedGame} bookmaker={selectedBook}
                onAdd={(market,selection,odds)=>addLeg(selectedGame,market,selection,odds)} propFilter={propFilter} legs={legs}/>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
