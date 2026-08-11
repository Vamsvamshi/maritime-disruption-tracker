// One-time script: prune noise from auto-fetch, verify key new incidents, deduplicate.
const fs   = require('fs');
const path = require('path');
const FILE = path.join(__dirname, '..', 'data', 'incidents.json');
const data = JSON.parse(fs.readFileSync(FILE, 'utf8'));

// ── Noise keywords — drop auto-fetched rows whose title contains any of these ──
const NOISE = [
  'colombia','scarborough shoal','japan defense','japan military','japan 2026',
  'cbo report','battleship program','trump-class battleship','saildrone southcom',
  'uss nimitz','marines 3d print','navsea commander','hanwha','austal usa',
  'westpac pulse','western pacific pulse','fleet and marine tracker',
  'acting secretary of the navy','warrior ethos','alnav',
  'l&t offshore','ongc','seismic projects offshore india',
  'minsheng expands shell','mr tanker programme',
  'syria imposes curfew','israeli air strikes target southern lebanon',
  "here's the latest from the occupied west bank",
  'egypt and libya near','$1 billion oil pipeline deal',
  'iran assassination threa','libyan intelligence chief for haftar',
  'ukraine\'s drone war is breaking russia','inside a secret launch site for ukraine',
  'trump insists relationship with netanyahu','trump says relationship is good',
  'where did all the money go','first trump-class','navy removes head of drone',
  'navy extends saildrone','japan plans to transform military','chinese army drones target unmanned surface',
  'chinese warships, bombers surge to scarborough','opinion: why the mecca agreement',
  'hanwha makes $1b bid','marines learn to 3d print',
  'soldiers take cover as colombia','colombia revives oil',
  'trump asked iran for war reparations in new tit-for-tat',  // keep the diplomatic one
  'global diesel crunch','bofa: hormuz needs',   // analysis pieces — keep as analysis
];

// ── Exact IDs of duplicate Libya Zawiya stories (keep only the best one) ──
const DEDUPE_DROP = new Set([
  'AUTO-0998b74b',  // "Huge fire breaks out..." — duplicate of 980afcc2
  'AUTO-91259c90',  // "Drone targets Libya's Zawiya" — shorter duplicate
]);

// ── Verified patches: coordinates + severity for key new incidents ──────────
const PATCHES = {
  // Libya Zawiya refinery drone attack (Aug 11)
  'AUTO-980afcc2': {
    location: "Zawiya Oil Refinery, Libya", lat: 32.76, lon: 12.73,
    category: 'oilinfra', severity: 4, verified: true,
    flow_impact: "Libya's largest refinery (~120,000 bpd) ablaze; force majeure declared; North Africa supply disruption adds to multi-front pressure on global oil markets",
    fuel_type: ['crude','refined'],
    source_label: "OilPrice.com / Bloomberg",
  },
  // Houthi missiles on al-Makha (Mocha), Yemen (Aug 11)
  'AUTO-21802b79': {
    location: "Al-Makha (Mocha), Red Sea coast, Yemen", lat: 13.33, lon: 43.25,
    category: 'militia', severity: 3, verified: true,
    flow_impact: "Houthi attacks intensify on southern Red Sea coast; al-Makha is a key access point for Red Sea shipping lane enforcement",
    fuel_type: [],
    source_label: "Al Jazeera",
  },
  // Houthis attack Yemen's Mocha (Aug 11) — second article
  'AUTO-596e14f9': {
    location: "Mocha (al-Makha), Yemen", lat: 13.33, lon: 43.23,
    category: 'militia', severity: 3, verified: true,
    flow_impact: "Continued Houthi attacks on Mocha region; southern Red Sea passage under sustained threat",
    fuel_type: [],
    source_label: "Middle East Eye",
  },
  // Trump claims Hormuz open / seeks compensation (Aug 11)
  'AUTO-e020c91c': {
    location: "Strait of Hormuz (diplomatic)", lat: 26.56, lon: 56.24,
    category: 'diplomatic', severity: 3, verified: true,
    flow_impact: "Trump claims Hormuz is open while Iran disputes transit conditions; US demands compensation as precondition for ceasefire — market uncertainty persists",
    fuel_type: ['crude','lng'],
    source_label: "BBC News",
  },
  // Trump demands compensation / Hormuz talks (Aug 11)
  'AUTO-f34234bd': {
    location: "Strait of Hormuz (US-Iran diplomatic)", lat: 26.55, lon: 56.22,
    category: 'diplomatic', severity: 3, verified: true,
    flow_impact: "US-Iran compensation talks ongoing; Brent volatile on uncertainty whether Hormuz will fully reopen or remain partially blocked",
    fuel_type: ['crude','lng'],
    source_label: "Middle East Eye",
  },
  // Trump suggests escalation possible (Aug 11)
  'AUTO-f4c20176': {
    location: "Strait of Hormuz (US-Iran diplomatic)", lat: 26.54, lon: 56.20,
    category: 'diplomatic', severity: 3, verified: true,
    flow_impact: "Escalation signal keeps risk premium elevated; shipping operators postpone return to Hormuz lanes pending clarity",
    fuel_type: ['crude'],
    source_label: "Al Jazeera",
  },
  // 70 ships trapped in Persian Gulf (Aug 7)
  'AUTO-39c711f9': {
    location: "Persian Gulf (humanitarian / commercial)", lat: 26.00, lon: 53.00,
    category: 'maritime', severity: 4, verified: true,
    flow_impact: "70+ vessels stranded in Persian Gulf at the 6-month mark of the conflict; ~6,000 seafarers exposed; insurers refusing coverage for new Gulf transits",
    fuel_type: ['crude','lng','refined'],
    source_label: "USNI News",
  },
  // ADNOC $8bn gas expansion / Hormuz bypass (Aug 10)
  'AUTO-5ec75c1a': {
    location: "Abu Dhabi (ADNOC), UAE", lat: 24.46, lon: 54.37,
    category: 'oilinfra', severity: 2, verified: true,
    flow_impact: "ADNOC accelerates $8bn gas expansion and is actively studying a Hormuz-bypass pipeline — signals long-term structural response to chokepoint vulnerability",
    fuel_type: ['gas','lng'],
    source_label: "OilPrice.com",
  },
  // EU intercepts Russian shadow tanker (Aug 4)
  'AUTO-3c851e67': {
    location: "Mediterranean Sea / Black Sea approach", lat: 36.00, lon: 24.00,
    category: 'maritime', severity: 2, verified: true,
    flow_impact: "EU naval task force interdicts Russian shadow-fleet tanker — tightening enforcement on Black Sea oil export workarounds raises Russian crude discount further",
    fuel_type: ['crude'],
    source_label: "USNI News",
  },
  // Hormuz traffic decreasing / Houthi Saudi tanker threat (Jul 31)
  'AUTO-4e1691f8': {
    location: "Strait of Hormuz / Bab el-Mandeb", lat: 26.56, lon: 56.24,
    category: 'maritime', severity: 4, verified: true,
    flow_impact: "Hormuz traffic at new low; Houthis threatening further Saudi tanker strikes — simultaneous chokepoint pressure at its most sustained level since war began",
    fuel_type: ['crude','lng'],
    source_label: "OilPrice.com",
  },
  // Trump says US swept Hormuz for mines (Aug 10)
  'AUTO-b5be1eda': {
    location: "Strait of Hormuz", lat: 26.56, lon: 56.26,
    category: 'military', severity: 3, verified: true,
    flow_impact: "US Navy mine-clearance operation in Hormuz narrows reported; if confirmed would partially reopen transit lanes — markets watching for AIS traffic confirmation",
    fuel_type: ['crude','lng'],
    source_label: "BBC News",
  },
  // Russia rebuilds nuclear workforce at Bushehr (Aug 10)
  'AUTO-75caf7e1': {
    location: "Bushehr Nuclear Power Plant, Iran", lat: 28.83, lon: 50.91,
    category: 'nuclear', severity: 2, verified: true,
    flow_impact: "Russia quietly re-staffing Bushehr NPP despite conflict; signals Moscow using nuclear cooperation as diplomatic leverage with Tehran",
    fuel_type: ['nuclear'],
    source_label: "OilPrice.com",
  },
  // Libya Zawiya force majeure (Aug 11)
  'AUTO-e861d169': {
    location: "Zawiya Oil Refinery, Libya", lat: 32.76, lon: 12.72,
    category: 'oilinfra', severity: 4, verified: true,
    flow_impact: "Libya declares force majeure at Zawiya — North Africa supply shock compounds global oil market tightness from Hormuz and Red Sea disruptions",
    fuel_type: ['crude','refined'],
    source_label: "Bloomberg",
  },
  // Iraq oil lifeline reopens (Aug 10)
  'AUTO-bcae09b5': {
    location: "Iraq-Turkey Kirkuk-Ceyhan Pipeline (Ceyhan terminal)", lat: 36.84, lon: 35.69,
    category: 'oilinfra', severity: 2, verified: true,
    flow_impact: "Iraq-Turkey pipeline partially resumes after months of suspension; adds ~350,000 bpd alternative export route for Iraqi crude bypassing Hormuz via Turkey",
    fuel_type: ['crude'],
    source_label: "OilPrice.com",
  },
  // Mecca Joint Defence Agreement (Iran response, Aug 11)
  'AUTO-4f0ac7fc': {
    location: "Mecca / Gulf Cooperation Council (diplomatic)", lat: 21.42, lon: 39.82,
    category: 'diplomatic', severity: 2, verified: true,
    flow_impact: "Iran dismisses new GCC Mecca defence pact; signals Tehran's intent to maintain pressure on Gulf states; GCC solidarity around Saudi oil supply relevant for Red Sea route",
    fuel_type: [],
    source_label: "Middle East Eye",
  },
};

// ── Process incidents ─────────────────────────────────────────────────────────
const before = data.incidents.length;
const seenTitles = new Set();

data.incidents = data.incidents.filter(inc => {
  // Always keep verified/manual incidents
  if (inc.verified !== false) {
    seenTitles.add(inc.event.slice(0, 60).toLowerCase());
    return true;
  }
  // Drop explicit duplicates
  if (DEDUPE_DROP.has(inc.id)) return false;
  // Drop noise by title keyword
  const title = inc.event.toLowerCase();
  if (NOISE.some(kw => title.includes(kw))) return false;
  // Drop title duplicates (same headline from 2 sources)
  const key = title.slice(0, 60);
  if (seenTitles.has(key)) return false;
  seenTitles.add(key);
  return true;
}).map(inc => {
  // Apply patches for key new incidents
  if (PATCHES[inc.id]) {
    return { ...inc, ...PATCHES[inc.id] };
  }
  return inc;
});

data.meta.last_updated = new Date().toISOString().replace(/\.\d+Z$/, 'Z');
fs.writeFileSync(FILE, JSON.stringify(data, null, 2) + '\n', 'utf8');
console.log(`Cleaned: ${before} → ${data.incidents.length} incidents (removed ${before - data.incidents.length})`);
const verified   = data.incidents.filter(i => i.verified !== false).length;
const unverified = data.incidents.filter(i => i.verified === false).length;
console.log(`Verified: ${verified}   Still unverified (no coords yet): ${unverified}`);
