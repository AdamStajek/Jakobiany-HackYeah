import { useState } from "react";
import { Link } from "react-router-dom";
import { Minus, Plus, MapPin } from "lucide-react";
import type { PlaceSummary } from "../data/types";

const streets = [
  "M50 -20L150 165L270 262L370 350L470 455L620 650", "M150 -20L220 108L310 190L420 278L555 362L720 430",
  "M300 -20L296 96L326 178L322 280L355 395L340 520L360 680", "M455 -20L438 98L472 170L458 270L500 350L520 455L505 680",
  "M610 -20L560 95L575 205L555 300L620 390L700 462", "M-30 95L122 118L230 100L345 126L460 112L595 145L730 132",
  "M-30 205L105 188L205 220L310 205L430 226L545 205L730 250", "M-30 315L120 292L220 325L335 305L455 335L575 310L730 350",
  "M-30 420L95 398L210 435L325 410L438 446L570 425L730 470", "M-30 535L105 505L220 548L340 520L455 565L585 530L730 575",
];

const buildings = [
  [36,34,78,43],[129,26,67,55],[211,42,58,38],[337,28,78,50],[478,32,54,42],[553,54,92,40],
  [31,132,61,49],[112,137,73,37],[205,122,53,55],[483,137,66,48],[571,158,77,38],[31,227,76,53],
  [125,239,49,58],[512,245,62,45],[600,267,70,42],[42,340,64,43],[128,349,74,50],[224,363,48,37],
  [492,365,70,51],[590,378,79,42],[27,454,82,48],[125,466,55,39],[207,472,76,51],[394,481,72,44],
  [548,484,49,48],[616,500,67,35],[48,573,68,40],[145,584,81,43],[258,566,55,53],[403,586,77,39],[520,574,68,47],[610,590,60,37],
];

export default function MapView({ places, route = false }: { places: PlaceSummary[]; route?: boolean }) {
  const [zoom, setZoom] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const active = places.find((p) => p.id === selected);

  return <div className="map-view">
    <svg viewBox="0 0 700 650" aria-hidden="true" className="map-drawing">
      <defs>
        <filter id="map-shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="1" stdDeviation="1" floodOpacity=".18" /></filter>
        <pattern id="building-grid" width="12" height="12" patternUnits="userSpaceOnUse"><path d="M0 12L12 0" stroke="#e0e0dd" strokeWidth=".7" /></pattern>
      </defs>
      <g transform={`translate(${350 - 350 * zoom} ${325 - 325 * zoom}) scale(${zoom})`}>
        <rect width="700" height="650" fill="#f4f3ef" />

        <path d="M0 76Q74 42 150 66L174 178Q101 218 18 181Z" fill="#dcebcf" />
        <path d="M466 445Q548 416 645 451L680 551Q575 587 473 548Z" fill="#dcebcf" />
        <path d="M274 105Q354 72 435 114Q476 188 440 282Q414 350 351 392Q279 350 252 280Q220 187 274 105Z" fill="#d7e9cc" />
        <path d="M291 127Q351 98 414 129Q445 191 418 264Q396 321 351 357Q299 326 275 266Q249 193 291 127Z" fill="#f4f3ef" />
        <g fill="#b8d8a6">{[[38,93],[65,115],[108,85],[132,139],[489,477],[532,458],[575,498],[625,475],[648,525],[260,172],[436,196],[276,298],[424,309]].map(([cx,cy],i)=><circle key={i} cx={cx} cy={cy} r={i%3===0?7:5}/>)}</g>

        <path d="M-55 503Q95 435 210 469T401 506Q513 532 755 470" fill="none" stroke="#c7e7f2" strokeWidth="73" />
        <path d="M-55 468Q90 399 220 438T410 472Q530 498 755 438" fill="none" stroke="#fff" strokeWidth="3" opacity=".8" />
        <path d="M-55 538Q105 470 210 503T394 541Q525 565 755 505" fill="none" stroke="#b4d3dc" strokeWidth="2" />

        <path d="M525 -20Q507 104 542 192T586 365" fill="none" stroke="#d3d0ca" strokeWidth="13" />
        <path d="M525 -20Q507 104 542 192T586 365" fill="none" stroke="#fff" strokeWidth="5" strokeDasharray="10 7" />

        <g fill="#e7e5df" stroke="#d8d6d0">{buildings.map(([x,y,width,height],i)=><rect key={i} x={x} y={y} width={width} height={height} rx="3" />)}</g>
        <g fill="url(#building-grid)" opacity=".5"><rect x="299" y="159" width="105" height="103" rx="4"/><rect x="288" y="278" width="126" height="54" rx="4"/></g>

        <g fill="none" strokeLinecap="round" strokeLinejoin="round">
          {streets.map((d,i)=><path key={`c${i}`} d={d} stroke="#dedbd4" strokeWidth="12"/>)}
          {streets.map((d,i)=><path key={`r${i}`} d={d} stroke="#fff" strokeWidth="8"/>)}
          <path d="M-30 382Q130 365 233 383Q340 402 453 379T730 397" stroke="#d6d0bf" strokeWidth="22"/><path d="M-30 382Q130 365 233 383Q340 402 453 379T730 397" stroke="#fff4d8" strokeWidth="16"/>
          <path d="M199 -20Q244 104 238 206Q233 324 292 418T332 680" stroke="#d6d0bf" strokeWidth="22"/><path d="M199 -20Q244 104 238 206Q233 324 292 418T332 680" stroke="#fff4d8" strokeWidth="16"/>
          <path d="M667 -20Q632 92 646 210Q660 313 622 414T605 680" stroke="#e1c98c" strokeWidth="25"/><path d="M667 -20Q632 92 646 210Q660 313 622 414T605 680" stroke="#fff0bd" strokeWidth="18"/>
        </g>
        <g strokeLinecap="round"><path d="M279 424L302 514" stroke="#c6c1b5" strokeWidth="25"/><path d="M279 424L302 514" stroke="#fff4d8" strokeWidth="17"/><path d="M598 429L611 511" stroke="#c6c1b5" strokeWidth="25"/><path d="M598 429L611 511" stroke="#fff0bd" strokeWidth="17"/></g>

        <rect x="307" y="181" width="91" height="76" rx="5" fill="#eee3cf" stroke="#d3c4aa" strokeWidth="2"/><rect x="342" y="197" width="18" height="44" rx="2" fill="#d9c5a6"/>
        <path d="M284 390L351 366L398 405L369 449L304 443Z" fill="#e6dfd3" stroke="#cbc3b8" strokeWidth="2"/><path d="M329 398L348 383L365 400L360 430L333 430Z" fill="#cdbfa9"/>

        <g fontFamily="Inter, Segoe UI, sans-serif" textAnchor="middle" paintOrder="stroke" stroke="#f4f3ef" strokeWidth="4" strokeLinejoin="round">
          <g fill="#6c6d69" fontSize="11" fontWeight="600" letterSpacing="1.2"><text x="352" y="151">STARE MIASTO</text><text x="485" y="431">KAZIMIERZ</text><text x="414" y="604">PODGÓRZE</text><text x="116" y="335">PIASEK</text></g>
          <g fill="#3d4a43" fontSize="10.5" strokeWidth="3"><text x="352" y="223" fontWeight="650">Rynek Główny</text><text x="351" y="421" fontWeight="650">Zamek Królewski na Wawelu</text><text x="73" y="151">Park Jordana</text><text x="522" y="501">Bulwary Wiślane</text><text x="552" y="98">Kraków Główny</text></g>
          <g fill="#77766f" fontSize="8.5" strokeWidth="3"><text x="180" y="378" transform="rotate(4 180 378)">al. Zygmunta Krasińskiego</text><text x="238" y="92" transform="rotate(72 238 92)">Karmelicka</text><text x="642" y="288" transform="rotate(86 642 288)">al. 29 Listopada</text><text x="449" y="376">Starowiślna</text></g>
          <text x="166" y="502" fill="#4d8da7" stroke="#c7e7f2" fontSize="13" fontStyle="italic" transform="rotate(-10 166 502)">Wisła</text>
        </g>
        <g fill="#fff" stroke="#7f9481" strokeWidth="2" filter="url(#map-shadow)"><circle cx="354" cy="282" r="7"/><circle cx="471" cy="334" r="7"/><circle cx="116" cy="252" r="7"/><circle cx="544" cy="143" r="7"/></g>
        <g fill="#58765e" fontSize="8" textAnchor="middle" fontWeight="700"><text x="354" y="285">i</text><text x="471" y="337">●</text><text x="116" y="255">P</text><text x="544" y="146">T</text></g>

        {route && <><path d="M425 83L382 128L390 184L438 261L365 330L315 440" stroke="white" strokeWidth="13" fill="none" strokeLinecap="round" strokeLinejoin="round"/><path d="M425 83L382 128L390 184L438 261L365 330L315 440" stroke="#1a73e8" strokeWidth="7" fill="none" strokeLinecap="round" strokeLinejoin="round"/><circle cx="425" cy="83" r="10" fill="#1a73e8" stroke="white" strokeWidth="4"/><circle cx="315" cy="440" r="10" fill="#c84b31" stroke="white" strokeWidth="4"/></>}
      </g>
    </svg>

    {!route && places.map((p)=><button key={p.id} className={`map-pin ${p.assessment?.status !== "meets_requirements" ? "uncertain" : ""}`} style={{left:`${50+(p.location.lon-19.936)*1800*zoom}%`,top:`${50-(p.location.lat-50.061)*1800*zoom}%`}} onClick={()=>setSelected(p.id)} aria-label={`Pokaż na mapie: ${p.name}`}><MapPin size={26}/><span>{(p.facts||[]).some((f)=>f.status==="unconfirmed")?"?":"✓"}</span></button>)}
    {active && <div className="map-popup"><button className="close" aria-label="Zamknij szczegóły znacznika" onClick={()=>setSelected(null)}>×</button><strong>{active.name}</strong><p>{active.address||"Adres nieznany"}</p><Link to={`/place/${encodeURIComponent(active.id)}`}>Zobacz szczegóły →</Link></div>}
    <div className="map-controls"><button aria-label="Powiększ mapę" disabled={zoom>=1.8} onClick={()=>setZoom((z)=>Math.min(1.8,z+.2))}><Plus/></button><button aria-label="Pomniejsz mapę" disabled={zoom<=1} onClick={()=>setZoom((z)=>Math.max(1,z-.2))}><Minus/></button></div>
    <div className="map-caption">Mapa poglądowa · dane © OpenStreetMap</div>
  </div>;
}
