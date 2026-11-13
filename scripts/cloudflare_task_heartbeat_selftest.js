'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('cloudflare/wandering-wave-4418/worker.js','utf8');
const context={Response,Request,URL,AbortSignal,TextDecoder,Uint8Array,Date,console,
  fetch:async()=>{throw Error('unexpected network');}};
vm.createContext(context);vm.runInContext(source.replace(/^export default /,'globalThis.worker = '),context);
const tasks=JSON.parse(vm.runInContext('JSON.stringify(HEARTBEAT_TASKS)',context));
const registry=JSON.parse(fs.readFileSync('data/ops_task_registry.v1.json')).tasks;
assert.deepEqual(tasks,registry.map(({id,workflow_file,max_age_hours,accepted_events})=>({id,workflow_file,max_age_hours,accepted_events})));
assert(tasks.every(t=>t.accepted_events.length===1&&t.accepted_events[0]==='schedule'));
const now=Date.now(),task=tasks[0];
const row=(patch={})=>({id:123,event:'schedule',head_branch:'main',status:'completed',conclusion:'success',
 run_started_at:new Date(now-3600000).toISOString(),head_repository:{full_name:'grizzly020503/swsi-quiz-backup'},...patch});
const evaluate=rows=>JSON.parse(JSON.stringify(context.heartbeatTask(task,rows,now)));
assert.equal(evaluate([row()]).status,'healthy');
assert.equal(evaluate([row({conclusion:'failure'}),row({id:124,event:'workflow_dispatch'})]).status,'failed');
for(const patch of [{event:'pull_request'},{event:'workflow_dispatch'},{head_branch:'topic'},{status:'in_progress'},
 {head_repository:{full_name:'other/repo'}}]) assert.equal(evaluate([row(patch)]).status,'missing');
assert.equal(evaluate([row({run_started_at:new Date(now-9*3600000).toISOString()})]).status,'stale');
assert.equal(evaluate([row({run_started_at:new Date(now+3600000).toISOString()})]).status,'error');
assert.equal(evaluate([row({run_started_at:'invalid'})]).status,'error');
const statements=[];let stored=null,network=0;
const env={AI_QUOTA_DB:{prepare(sql){
 statements.push(sql);return {bind(...args){this.args=args;return this;},
 async run(){if(sql.startsWith('INSERT'))stored=JSON.parse(this.args[2]);return {success:true};},
 async first(){return stored?{payload:JSON.stringify(stored)}:null;}};
}}};
(async()=>{
 const req=()=>new Request('https://example.test/ops/task-heartbeat');
 assert.equal((await context.worker.fetch(req(),env)).status,503);
 assert(!statements.some(s=>/CREATE|INSERT|UPDATE/.test(s)));
 statements.length=0;
 assert.equal((await context.worker.fetch(new Request(req(),{method:'POST'}),env)).status,405);
 assert.equal(statements.length,0);
 context.fetch=async(url,options)=>{
   network++;
   assert.equal(options.method,'GET');assert.equal(options.redirect,'error');
   assert(!options.headers.Authorization);assert.equal(new URL(url).hostname,'api.github.com');
   assert.equal(new URL(url).searchParams.get('event'),'schedule');
   return Response.json({workflow_runs:[row()]});
 };
 await context.worker.scheduled({cron:'*/15 * * * *',scheduledTime:now},env);
 assert.equal(network,6);assert.equal(stored.components.task_heartbeat.status,'healthy');
 assert.equal(stored.components.grading.status,'unknown');
 assert.equal(statements.length,2);assert(statements[1].includes('excluded.scheduled_at > ops_task_heartbeat.scheduled_at'));
 let res=await context.worker.fetch(req(),env);assert.equal(res.status,200);
 assert.equal((await res.json()).independent_monitoring_active,true);
 assert.equal(network,6,'public GET may not trigger probes');
 stored.generated_at=new Date(now-46*60000).toISOString();
 res=await context.worker.fetch(req(),env);assert.equal(res.status,503);
 assert.equal((await res.json()).independent_monitoring_active,false);
 context.fetch=async()=>new Response('private error body',{status:429});
 await context.worker.scheduled({cron:'*/15 * * * *',scheduledTime:now+1},env);
 assert.equal(stored.tasks[0].failure_class,'github_http_429');
 assert(!JSON.stringify(stored).includes('private error body'));
 context.fetch=async()=>{throw Error('secret must not leak');};
 await context.worker.scheduled({cron:'*/15 * * * *',scheduledTime:now+2},env);
 assert.equal(stored.tasks[0].failure_class,'source_unavailable');
 assert(!JSON.stringify(stored).includes('secret'));
 await assert.rejects(context.worker.scheduled({cron:'wrong',scheduledTime:now},env));
 const config=fs.readFileSync('wrangler.jsonc','utf8');assert(config.includes('"crons": ["*/15 * * * *"]'));
 console.log('INDEPENDENT HEARTBEAT CONTRACT PASS: schedule-only history, failure/staleness, 6 bounded GETs, no public probe/write, sanitized errors, monotonic one-row storage');
})().catch(e=>{console.error(e);process.exitCode=1;});
