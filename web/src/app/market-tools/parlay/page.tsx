"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import { Layers, X, ChevronRight, SearchIcon, ChevronDown } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import type { SBEvent, SBMarket, SBBookLine } from "@/lib/sbevent";
import { formatBookmakerName, buildBookmakerUniverse } from "@/lib/bookmakers";

const LEAGUES = ["MLB","NFL","NBA","NHL","NCAAF","NCAAB"] as const;
type League = typeof LEAGUES[number];
const BET_TYPES = ["moneyline","spread","total","player_prop","other"] as const;
const INITIAL_VISIBLE_BOOKS = 12;  // number of sportsbook tiles shown before "Show More"

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
function shortDate(iso:string|null):string {
  if(!iso)return"?"; return new Date(iso||"").toLocaleDateString("en-US",{timeZone:EDT,weekday:"short",month:"short",day:"numeric"});
}
function timeEDT(iso:string|null):string {
  if(!iso)return"TBD"; return new Date(iso).toLocaleTimeString("en-US",{timeZone:EDT,hour:"numeric",minute:"2-digit"})+" EDT";
}

/** Build an array of {dateKey,label,short} for all distinct dates in the cache. */
function buildDateList(events:SBEvent[]):{date:string,label:string,sh:string}[] {
  const seen=new Set<string>(); const out:{date:string,label:string,sh:string}[]=[];
  for(const ev of events){const dk=eventDateKey(ev.start_time);if(!dk||dk==="9999")continue;if(seen.has(dk))continue;seen.add(dk);
    out.push({date:dk,label:dateLabel(ev.start_time),sh:shortDate(ev.start_time)});}
  return out.sort((a,b)=>new Date(a.date).getTime()-new Date(b.date).getTime());
}

/** Check if a leg for the given event+market+selection already exists. */
function isLegAdded(legs:Leg[],eventName:string,market:string,selection:string):boolean {
  return legs.some(l=>l.eventName===eventName&&l.market===market&&l.selection===selection);
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
    const evName=awName+" @ "+hmName;
    const awAdded=isLegAdded(legs,evName,"Moneyline",awName);
    const hmAdded=isLegAdded(legs,evName,"Moneyline",hmName);
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
    const evName=awName+" @ "+hmName;
    const awSel=awName+" "+fmtSpread(ab?.spread);
    const hmSel=hmName+" "+fmtSpread(hb?.spread);
    return (
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
        <SelectorBtn label={awSel} odds={fmtOdds(ab?.moneyline)} selected={isLegAdded(legs,evName,"Spread",awSel)} disabled={!ab} onClick={()=>{if(ab)onAdd("Spread",awSel,ab.moneyline??-110);}}/>
        <SelectorBtn label={hmSel} odds={fmtOdds(hb?.moneyline)} selected={isLegAdded(legs,evName,"Spread",hmSel)} disabled={!hb} onClick={()=>{if(hb)onAdd("Spread",hmSel,hb.moneyline??-110);}}/>
      </div>
    );
  }

  if(betType==="total") {
    const over=markets.find(m=>m.side?.toLowerCase()==="over");
    const under=markets.find(m=>m.side?.toLowerCase()==="under");
    const ob=over?getBook(over.books,bookmaker):undefined;
    const ub=under?getBook(under.books,bookmaker):undefined;
    const line=ob?.over_under??ub?.over_under??null;
    const awName=event.away_team?.abbreviation||"Away";
    const hmName=event.home_team?.abbreviation||"Home";
    const evName=awName+" @ "+hmName;
    const ovSel="Over "+(line??"?");
    const unSel="Under "+(line??"?");
    return (
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
        <SelectorBtn label={ovSel} odds={fmtOdds(ob?.moneyline)} selected={isLegAdded(legs,evName,"Total",ovSel)} disabled={!ob} onClick={()=>{if(ob)onAdd("Total",ovSel,ob.moneyline??-110);}}/>
        <SelectorBtn label={unSel} odds={fmtOdds(ub?.moneyline)} selected={isLegAdded(legs,evName,"Total",unSel)} disabled={!ub} onClick={()=>{if(ub)onAdd("Total",unSel,ub.moneyline??-110);}}/>
      </div>
    );
  }

  // player_prop + other — render with optional filter
  const filtered = propFilter ? markets.filter(m=>m.player_name?.toLowerCase().includes(propFilter.toLowerCase())||m.market_name?.toLowerCase().includes(propFilter.toLowerCase())) : markets.slice(0,30);
  const awName=event.away_team?.abbreviation||"Away";
  const hmName=event.home_team?.abbreviation||"Home";
  const evName=awName+" @ "+hmName;
  return (
    <div style={{display:"flex",flexDirection:"column",gap:6}}>
      {filtered.map((m,i)=>{
        const bk=getBook(m.books,bookmaker);
        if(!bk||!bk.available)return null;
        const label=(m.player_name||"")+" "+(m.market_name||"").trim()+" "+(bk.over_under??"").toString().trim();
        const sel=label.trim();
        const added=isLegAdded(legs,evName,m.market_name||betType,sel);
        return (
          <SelectorBtn key={i} label={sel||"?"} odds={fmtOdds(bk.moneyline)} selected={added}
            onClick={()=>onAdd(m.market_name||betType,sel,bk.moneyline??-100)}/>
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
  const [stakeFocused,setStakeFocused]=useState(false);
  const [selectedGameId,setSelectedGameId]=useState<string|null>(null);
  const [selectedBetType,setSelectedBetType]=useState<string>("moneyline");
  const [selectedBook,setSelectedBook]=useState<string>("");
  const [propFilter,setPropFilter]=useState("");
  const [selectedDateIdx,setSelectedDateIdx]=useState(0);
  const [showAllBooks,setShowAllBooks]=useState(false);
  const [pendingBook,setPendingBook]=useState<string|null>(null);  // target book when confirmation dialog is open

  const { events:rawEvents, loading } = useEvents(activeLeague);
  const events = useMemo(()=>{
    const seen=new Set<string>();
    return rawEvents.filter(e=>{if(seen.has(e.id))return false;seen.add(e.id);return true;});
  },[rawEvents]);

  const availableBooks = useMemo(()=>buildBookmakerUniverse(events.map(e=>e.bookmakers)),[events]);
  useMemo(()=>{if(selectedBook&&!availableBooks.includes(selectedBook))setSelectedBook("");},[availableBooks,selectedBook]);

  // build list of available dates for navigation
  const dateNav = useMemo(()=>buildDateList(events),[events]);
  const selectedDate = useMemo(()=>dateNav[selectedDateIdx]||null,[dateNav,selectedDateIdx]);
  const selectedDateGames = useMemo(()=>{
    if(!selectedDate)return[];
    return events.filter(e=>eventDateKey(e.start_time)===selectedDate.date).sort((a,b)=>new Date(a.start_time||0).getTime()-new Date(b.start_time||0).getTime());
  },[events,selectedDate]);

  // Reset date idx + selected game on league switch
  const goLeague = useCallback((lg:League)=>{
    setActiveLeague(lg);setSelectedGameId(null);setSelectedBook("");setLegs([]);
    // date idx resets to 0; useEffect below snaps to today when events load
  },[]);

  // When events (re)load, snap to today if available, else first date
  useEffect(()=>{
    if(loading||dateNav.length===0)return;
    const td=todayEDT(); const idx=dateNav.findIndex(d=>d.date===td);
    setSelectedDateIdx(idx>=0?idx:0);
  },[loading,dateNav]);

  const selectedGame = useMemo(()=>events.find(e=>e.id===selectedGameId)||null,[events,selectedGameId]);
  const expandedMarkets = useMemo(()=>{
    if(!selectedGame)return {};
    const groups:Record<string,SBMarket[]>={};
    for(const m of selectedGame.markets||[]){const k=m.bet_type;if(!groups[k])groups[k]=[];groups[k].push(m);}
    return groups;
  },[selectedGame]);

  const addLeg = useCallback((event:SBEvent,market:string,selection:string,odds:number)=>{
    const evName = event.away_team?.abbreviation+" @ "+event.home_team?.abbreviation;
    // Prevent identical duplicate legs
    const dup = legs.find(l=>l.eventName===evName&&l.market===market&&l.selection===selection);
    if(dup)return;
    // Prevent conflicting sides (both sides of same market in same game)
    const conf = legs.find(l=>l.eventName===evName&&l.market===market&&l.selection!==selection);
    if(conf && (market==="Moneyline"||market.includes("Spread")||market.includes("Total")))return;
    setLegs(prev=>[...prev,{id:Date.now()+"-"+Math.random().toString(36).slice(2,6),eventName:evName,market,selection,odds,bookmaker:selectedBook}]);
  },[selectedBook,legs]);

  const removeLeg = useCallback((id:string)=>setLegs(prev=>prev.filter(l=>l.id!==id)),[]);

  const result = useMemo(()=>{
    if(legs.length===0)return{odds:0,payout:0,profit:0};
    let dec=1;for(const l of legs)dec*=americanToDecimal(l.odds||0);
    const st=parseFloat(stake)||0,payout=dec*st,profit=payout-st;
    const am=dec>=2?Math.round((dec-1)*100):Math.round(-100/(dec-1));
    return{odds:am,payout,profit};
  },[legs,stake]);

  const allSameEvent = legs.length>=2&&legs.every(l=>l.eventName===legs[0]?.eventName);

  // Sorted sportsbooks: popular/available first, then alphabetical
  const sortedBooks = useMemo(()=>{
    const popular = ["draftkings","fanduel","betmgm","caesars","espnbet","bovada","pinnacle","bet365","pointsbet","barstool"];
    const seen = new Set<string>(); const out: string[]=[];
    for(const b of popular){if(availableBooks.includes(b)&&!seen.has(b)){out.push(b);seen.add(b);}}
    for(const b of availableBooks.sort()){if(!seen.has(b))out.push(b);}
    return out;
  },[availableBooks]);

  const visibleBooks = showAllBooks ? sortedBooks : sortedBooks.slice(0,INITIAL_VISIBLE_BOOKS);
  const hiddenCount = sortedBooks.length - INITIAL_VISIBLE_BOOKS;

  // Sportsbook switch — confirm if legs exist, otherwise switch immediately
  const requestBookChange = useCallback((book: string) => {
    if (legs.length === 0) {
      setSelectedBook(book); setLegs([]);
    } else {
      setPendingBook(book);
    }
  }, [legs]);
  const confirmBookChange = useCallback(() => {
    if (pendingBook != null) {
      setSelectedBook(pendingBook); setLegs([]); setPendingBook(null);
    }
  }, [pendingBook]);
  const cancelBookChange = useCallback(() => setPendingBook(null), []);


  return (
    <div style={{maxWidth:"100%",margin:"0 auto",padding:"8px 16px 12px",color:C.text,height:"calc(100vh - 72px)",display:"flex",flexDirection:"column",overflow:"hidden"}}>

      {/* CONFIRMATION MODAL — sportsbook switch with existing legs */}
      {pendingBook !== null && (
        <div style={{position:"fixed",inset:0,zIndex:100,display:"flex",alignItems:"center",justifyContent:"center"}}>
          <div onClick={cancelBookChange} style={{position:"absolute",inset:0,background:"rgba(0,0,0,0.6)"}} />
          <div style={{position:"relative",background:"#0f172a",border:"1px solid #1e293b",borderRadius:14,padding:24,maxWidth:400,width:"90%",textAlign:"center",zIndex:1}}>
            <h3 style={{fontSize:15,fontWeight:800,color:C.gold,margin:"0 0 8px"}}>Change Sportsbook?</h3>
            <p style={{fontSize:12,color:C.muted,lineHeight:1.6,margin:"0 0 20px"}}>
              Changing sportsbooks will clear your current parlay because odds and market availability may differ between sportsbooks.
            </p>
            <div style={{display:"flex",gap:8,justifyContent:"center"}}>
              <button onClick={cancelBookChange} style={{padding:"8px 20px",borderRadius:8,fontSize:12,fontWeight:700,background:C.card,border:"1px solid "+C.border,color:C.muted,cursor:"pointer"}}>Cancel</button>
              <button onClick={confirmBookChange} style={{padding:"8px 20px",borderRadius:8,fontSize:12,fontWeight:700,background:"rgba(201,168,76,0.15)",border:"1px solid "+C.gold,color:C.gold,cursor:"pointer"}}>Change Sportsbook</button>
            </div>
          </div>
        </div>
      )}

      {/* HEADER ROW */}
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:10,flexWrap:"wrap",gap:8}}>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <Layers size={22} color={C.gold}/>
          <h1 style={{fontSize:18,fontWeight:800,margin:0}}>Parlay Builder</h1>
        </div>
        <span style={{fontSize:11,color:C.subtle}}>{availableBooks.length} sportsbooks available</span>
      </div>

      {/* SPORTSBOOK TILE GRID */}
      {!selectedBook && (
        <div style={{marginBottom:8}}>
          <div style={{fontSize:10,fontWeight:700,color:C.subtle,textTransform:"uppercase",letterSpacing:1,marginBottom:6}}>
            {loading?"Loading sportsbooks…":"Choose a sportsbook"}
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill, minmax(140px, 1fr))",gap:6}}>
            {visibleBooks.map(b=>{
              const name = formatBookmakerName(b);
              const sel = selectedBook===b;
              return (
                <button key={b} onClick={()=>requestBookChange(b)}
                  style={{
                    padding:"8px 10px",borderRadius:8,fontSize:11,fontWeight:700,
                    background:sel?"rgba(201,168,76,0.12)":"rgba(255,255,255,0.03)",
                    border:sel?"1px solid rgba(201,168,76,0.4)":"1px solid "+C.border,
                    color:sel?C.gold:C.muted,cursor:"pointer",
                    textAlign:"center",transition:"all 0.1s",
                    whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis",
                  }}>{name}</button>
              );
            })}
          </div>
          {hiddenCount>0 && (
            <button onClick={()=>setShowAllBooks(!showAllBooks)}
              style={{
                marginTop:6,padding:"5px 14px",borderRadius:6,fontSize:10,fontWeight:700,
                background:"rgba(255,255,255,0.02)",border:"1px solid "+C.border,
                color:C.gold,cursor:"pointer",display:"flex",alignItems:"center",gap:4,
              }}>
              {showAllBooks?"Show Less":"Show More ("+hiddenCount+" more)"}
              <ChevronDown size={12} style={{transform:showAllBooks?"rotate(180deg)":"none",transition:"transform 0.15s"}}/>
            </button>
          )}
        </div>
      )}

      {/* Active sportsbook indicator — compact bar when selected */}
      {selectedBook && (
        <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:8,padding:"6px 10px",borderRadius:8,background:"rgba(201,168,76,0.08)",border:"1px solid rgba(201,168,76,0.2)"}}>
          <span style={{fontSize:10,fontWeight:700,color:C.subtle,textTransform:"uppercase"}}>Sportsbook</span>
          <span style={{fontSize:12,fontWeight:800,color:C.gold}}>{formatBookmakerName(selectedBook)}</span>
          <button onClick={()=>requestBookChange("")} style={{marginLeft:"auto",background:"none",border:"none",color:C.subtle,cursor:"pointer",fontSize:10}}>Change</button>
        </div>
      )}

      {/* LEAGUE TABS */}
      <div style={{display:"flex",gap:4,marginBottom:10,flexWrap:"wrap"}}>
        {LEAGUES.map(lg=>(
          <button key={lg} onClick={()=>goLeague(lg)}
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
            <input type="text" value={stakeFocused?stake:stake||"10"} onFocus={()=>setStakeFocused(true)} onBlur={()=>setStakeFocused(false)}
            onChange={e=>{const v=e.target.value;if(v===""||/^\d*\.?\d{0,2}$/.test(v))setStake(v);}}
            placeholder="Stake" style={{width:"100%",padding:"6px 10px",borderRadius:8,background:"#1a1f33",border:"1px solid "+C.border,color:C.text,fontSize:12,fontWeight:600,outline:"none",boxSizing:"border-box"}}/>
            <div style={{display:"flex",justifyContent:"space-between",fontSize:11,marginTop:6}}><span style={{color:C.subtle}}>Payout</span><span style={{fontWeight:800,color:C.gold}}>${result.payout.toFixed(2)}</span></div>
            <div style={{display:"flex",justifyContent:"space-between",fontSize:11}}><span style={{color:C.subtle}}>Profit</span><span style={{fontWeight:800,color:C.gold}}>${result.profit.toFixed(2)}</span></div>
          </div>)}
        </div>

        {/* CENTER: Games list — date-navigated, viewport-constrained */}
                <div style={{background:C.card,borderRadius:14,border:"1px solid "+C.border,padding:12,display:"flex",flexDirection:"column",overflow:"hidden"}}>
                  <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:6}}>
                    <span style={{fontSize:10,fontWeight:700,color:C.subtle,textTransform:"uppercase",letterSpacing:1}}>{activeLeague} Games</span>
                  </div>
                  {/* Date navigation bar */}
                  {dateNav.length>0 && (
                    <div style={{display:"flex",alignItems:"center",gap:2,marginBottom:8,overflowX:"auto"}}>
                      <button onClick={()=>setSelectedDateIdx(i=>Math.max(0,i-1))} disabled={selectedDateIdx===0}
                        style={{padding:"3px 6px",borderRadius:4,fontSize:10,fontWeight:700,background:"none",border:"1px solid "+C.border,color:selectedDateIdx===0?C.subtle:C.gold,cursor:selectedDateIdx===0?"default":"pointer"}}>‹</button>
                      {dateNav.map((d,i)=>(
                        <button key={d.date} onClick={()=>setSelectedDateIdx(i)} style={{
                          padding:"3px 8px",borderRadius:4,fontSize:10,fontWeight:700,whiteSpace:"nowrap",
                          background:i===selectedDateIdx?"rgba(201,168,76,0.1)":C.card,
                          border:i===selectedDateIdx?"1px solid "+C.gold:"1px solid transparent",
                          color:i===selectedDateIdx?C.gold:C.muted,cursor:"pointer",
                          opacity:Math.abs(i-selectedDateIdx)>3?0.4:1,
                        }}>{d.sh.toUpperCase()}</button>
                      ))}
                      <button onClick={()=>setSelectedDateIdx(i=>Math.min(dateNav.length-1,i+1))} disabled={selectedDateIdx>=dateNav.length-1}
                        style={{padding:"3px 6px",borderRadius:4,fontSize:10,fontWeight:700,background:"none",border:"1px solid "+C.border,color:selectedDateIdx>=dateNav.length-1?C.subtle:C.gold,cursor:selectedDateIdx>=dateNav.length-1?"default":"pointer"}}>›</button>
                    </div>
                  )}
                  {/* Selected date heading */}
                  {selectedDate && <div style={{fontSize:9,fontWeight:700,color:C.gold,textTransform:"uppercase",letterSpacing:1,marginBottom:6}}>{selectedDate.label}</div>}
                  {/* Games for selected date */}
                  <div style={{flex:1,overflowY:"auto",minHeight:0}}>
                  {loading?<p style={{color:C.muted,fontSize:11,textAlign:"center",padding:20}}>Loading...</p>
                  :selectedDateGames.length===0?<p style={{color:C.subtle,fontSize:11,textAlign:"center",padding:20}}>No {activeLeague} games on this date.</p>
                  :selectedDateGames.map(ev=>{
                    const sel = selectedGameId===ev.id;
                    return (<button key={ev.id} onClick={()=>setSelectedGameId(ev.id)} style={{
                      display:"flex",alignItems:"center",justifyContent:"space-between",width:"100%",padding:"7px 10px",borderRadius:8,marginBottom:2,fontSize:12,fontWeight:600,
                      background:sel?"rgba(201,168,76,0.08)":"rgba(255,255,255,0.01)",border:sel?"1px solid rgba(201,168,76,0.3)":"1px solid transparent",color:sel?C.gold:C.text,cursor:"pointer",textAlign:"left"
                    }}>
                      <span style={{whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis",minWidth:0}}>{ev.away_team?.abbreviation||"AWY"} @ {ev.home_team?.abbreviation||"HOM"}</span>
                      <span style={{fontSize:9,color:C.subtle,flexShrink:0,marginLeft:4}}>{timeEDT(ev.start_time)}</span>
                    </button>);
                  })}
                  </div>
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
