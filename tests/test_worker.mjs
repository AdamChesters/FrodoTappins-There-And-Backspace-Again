import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';
const root = new URL('../', import.meta.url);
const worker = (await import('data:text/javascript;base64,' + Buffer.from(readFileSync(new URL('worker.js', root))).toString('base64'))).default;
const fields = ['keystrokes','words','deletions','alt_tabs','power_cycles'];
const counts = n => Object.fromEntries(fields.map(f => [f,n]));
function database() {
  const sqlite = new DatabaseSync(':memory:');
  sqlite.exec(readFileSync(new URL('schema.sql',root),'utf8'));
  const db = {
    prepare(sql) {
      let values = [];
      return {
        bind(...v) {values = v; return this;},
        async first() {return sqlite.prepare(sql).get(...values) ?? null;},
        async all() {return {results: sqlite.prepare(sql).all(...values)};},
      };
    },
    async batch(statements) {
      sqlite.exec('BEGIN');
      try {
        const results = [];
        for (const statement of statements) results.push(await statement.all());
        sqlite.exec('COMMIT'); return results;
      } catch(e) {sqlite.exec('ROLLBACK'); throw e;}
    },
  };
  return {sqlite, db};
}
async function request(db, body, key='test', path='/sync') {
  const response = await worker.fetch(new Request('https://example.test'+path, {
    method:body === undefined ? 'GET':'POST', headers:{'X-API-Key':key},
    ...(body === undefined ? {} : {body:JSON.stringify(body)}),
  }), {DB:db,API_KEY:'test'});
  return {status:response.status, body:await response.json()};
}
const payload = (n=10, revision=0, id='desktop') => ({protocol:2,device_id:id,device_name:'Same name',totals:counts(n),expected_revision:revision});

test('cumulative CAS, stale/decreasing rejection, independent same-name IDs', async () => {
  const {db,sqlite} = database();
  assert.equal((await request(db,payload())).body.revision,1);
  assert.equal((await request(db,payload())).status,409);
  assert.equal((await request(db,payload(9,1))).status,409);
  assert.equal((await request(db,payload(20,1))).body.revision,2);
  assert.equal((await request(db,payload(30,1))).status,409);
  assert.equal((await request(db,payload(10,5,'missing'))).status,409);
  assert.equal((await request(db,payload(7,0,'laptop'))).status,200);
  const total = (await request(db,undefined,'test','/totals')).body;
  assert.equal(total.global.words,27); assert.equal(total.device_count,2);
  assert.equal(sqlite.prepare('SELECT COUNT(*) n FROM device_snapshots').get().n,2);
  assert.equal(sqlite.prepare("SELECT words FROM device_snapshots WHERE device_id='desktop'").get().words,20);
});

test('concurrent writers cannot silently replace one another', async () => {
  const {db} = database();
  await request(db,payload());
  // D1 serializes batches; simulate that while allowing requests to overlap.
  let queue = Promise.resolve(); const batch = db.batch.bind(db);
  db.batch = statements => {const result=queue.then(()=>batch(statements)); queue=result.catch(()=>{}); return result;};
  const result = await Promise.all([request(db,payload(20,1)),request(db,payload(30,1))]);
  assert.deepEqual(result.map(r=>r.status).sort(),[200,409]);
});

test('seven UTC days retained, dormant installation cumulative total survives', async () => {
  const {db,sqlite} = database();
  await request(db,payload(40,0,'dormant'));
  const insert = sqlite.prepare("INSERT INTO device_snapshots SELECT device_id, date('now',?),device_name,keystrokes,words,deletions,alt_tabs,power_cycles,revision,updated_at FROM device_totals");
  for(let day=1;day<=10;day++) insert.run(`-${day} days`);
  assert.equal((await request(db,payload(39,1,'dormant'))).status,409);
  assert.equal(sqlite.prepare('SELECT COUNT(*) n FROM device_snapshots').get().n,11);
  await request(db,payload());
  const rows=sqlite.prepare("SELECT snapshot_day FROM device_snapshots WHERE device_id='dormant'").all();
  assert.equal(rows.length,7);
  assert.equal((await request(db,undefined,'test','/totals')).body.global.words,50);
});

test('batch failure rolls back totals and snapshots', async () => {
  const {db,sqlite} = database();
  sqlite.exec("CREATE TRIGGER fail_snapshot BEFORE INSERT ON device_snapshots BEGIN SELECT RAISE(ABORT,'fixture failure'); END");
  assert.equal((await request(db,payload())).status,503);
  assert.equal(sqlite.prepare('SELECT COUNT(*) n FROM device_totals').get().n,0);
});

test('legacy full daily history collapses, validates and remains monotonic', async () => {
  const {db,sqlite} = database();
  const legacy = {device_id:'desktop',device_name:'Same name',days:[
    {day:'2020-01-01',words:10},{day:'2026-09-22',words:20},
  ]};
  assert.equal((await request(db,legacy)).status,200);
  assert.equal((await request(db,legacy)).status,200);
  assert.equal(sqlite.prepare('SELECT words FROM device_totals').get().words,30);
  assert.equal((await request(db,{...legacy,days:[legacy.days[1]]})).status,409);
  assert.equal((await request(db,{...legacy,days:[legacy.days[0],legacy.days[0]]})).status,400);
  assert.equal((await request(db,{...legacy,days:[{day:'2026-02-30'}]})).status,400);
});

test('rejects malformed, unsafe and unauthorized requests', async () => {
  const {db} = database();
  for(const body of [null,[],{...payload(),expected_revision:-1},{...payload(),totals:{words:2}},
    {...payload(),totals:counts(Number.MAX_SAFE_INTEGER+1)}, {...payload(),totals:counts(true)},
    {...payload(),device_id:'../../bad'}]) assert.equal((await request(db,body)).status,400);
  assert.equal((await request(db,payload(),'wrong')).status,401);
  assert.equal((await request(db,{...payload(),padding:'x'.repeat(2*1024*1024)})).status,400);
});

test('additive legacy migration preserves all counts and repeat/backfill safety', async () => {
  const {db,sqlite} = database();
  sqlite.exec(`CREATE TABLE stats(device_id TEXT,device_name TEXT,day TEXT,keystrokes INTEGER,words INTEGER,deletions INTEGER,alt_tabs INTEGER,power_cycles INTEGER,updated_at TEXT,PRIMARY KEY(device_id,day));
    INSERT INTO stats VALUES ('desktop','Old name','2026-01-01',10,5,2,1,0,'2026-01-01'),('desktop','New name','2026-09-22',20,10,3,2,1,'2026-09-22'),('laptop','New name','2026-09-22',7,4,1,0,1,'2026-09-22');`);
  const migrate = readFileSync(new URL('migrate-v2.sql',root),'utf8');
  sqlite.exec(migrate); sqlite.exec(migrate);
  assert.equal(sqlite.prepare("SELECT revision FROM device_totals WHERE device_id='desktop'").get().revision,1);
  assert.equal((await request(db,undefined,'test','/totals')).body.global.words,19);
  assert.equal(sqlite.prepare("SELECT device_name FROM device_totals WHERE device_id='desktop'").get().device_name,'New name');
  assert.equal((await request(db,payload(50,1))).status,200);
  sqlite.exec(migrate);
  assert.equal(sqlite.prepare("SELECT words FROM device_totals WHERE device_id='desktop'").get().words,50);
  sqlite.exec("UPDATE stats SET words=100 WHERE device_id='laptop'"); sqlite.exec(migrate);
  assert.equal(sqlite.prepare("SELECT words FROM device_totals WHERE device_id='laptop'").get().words,100);
  assert.equal(sqlite.prepare('SELECT COUNT(*) n FROM stats').get().n,3);
});
