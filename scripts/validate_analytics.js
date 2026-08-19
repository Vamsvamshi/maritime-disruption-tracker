const fs = require('fs');
const path = require('path');

function fail(msg) {
  console.error(`VALIDATION FAILED: ${msg}`);
  process.exit(1);
}

function assert(cond, msg) {
  if (!cond) fail(msg);
}

function isNum(n) {
  return typeof n === 'number' && Number.isFinite(n);
}

const file = path.join(__dirname, '..', 'data', 'analytics_dashboard.json');
let raw;
try {
  raw = fs.readFileSync(file, 'utf8');
} catch (e) {
  fail(`Cannot read ${file}: ${e.message}`);
}

let data;
try {
  data = JSON.parse(raw);
} catch (e) {
  fail(`Invalid JSON: ${e.message}`);
}

assert(data.meta && data.meta.last_updated, 'meta.last_updated missing');
assert(data.client_exposure && Array.isArray(data.client_exposure.companies), 'client_exposure.companies missing');
assert(data.key_ports && Array.isArray(data.key_ports.ports), 'key_ports.ports missing');
assert(data.lng_terminals && Array.isArray(data.lng_terminals.terminals), 'lng_terminals.terminals missing');

for (const [idx, c] of data.client_exposure.companies.entries()) {
  assert(c.name, `client_exposure.companies[${idx}].name missing`);
  assert(isNum(c.lat) && isNum(c.lon), `client_exposure.companies[${idx}] invalid lat/lon`);
}

for (const [idx, p] of data.key_ports.ports.entries()) {
  assert(p.name, `key_ports.ports[${idx}].name missing`);
  assert(isNum(p.lat) && isNum(p.lon), `key_ports.ports[${idx}] invalid lat/lon`);
  assert(isNum(p.capacity_mbd), `key_ports.ports[${idx}] invalid capacity_mbd`);
}

for (const [idx, t] of data.lng_terminals.terminals.entries()) {
  assert(t.name, `lng_terminals.terminals[${idx}].name missing`);
  assert(isNum(t.lat) && isNum(t.lon), `lng_terminals.terminals[${idx}] invalid lat/lon`);
  assert(isNum(t.capacity_mtpa), `lng_terminals.terminals[${idx}] invalid capacity_mtpa`);
}

const requiredTop = [
  'shipping_disruptions',
  'bypass_pipeline_capacity',
  'vessel_flow_chokepoint',
  'storage',
  'transit_fee',
  'oil_prices_spreads',
  'shipping_rates_trend',
  'insurance_freight',
  'us_oil_lng_supplies'
];

for (const key of requiredTop) {
  assert(data[key], `${key} missing`);
}

console.log('analytics_dashboard.json validation passed');
