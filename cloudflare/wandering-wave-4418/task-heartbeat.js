// Public schedule metadata only. Never calls AI, Supabase, or write-capable GitHub APIs.
const HEARTBEAT_TASKS = [{"id":"public-monitoring-feed","workflow_file":"public-monitoring-feed.yml","max_age_hours":8,"accepted_events":["schedule"]},{"id":"public-uptime","workflow_file":"public-uptime.yml","max_age_hours":30,"accepted_events":["schedule"]},{"id":"backup-uptime","workflow_file":"backup-uptime.yml","max_age_hours":30,"accepted_events":["schedule"]},{"id":"moex-social-worker-sync","workflow_file":"moex-social-worker-sync.yml","max_age_hours":192,"accepted_events":["schedule"]},{"id":"full-corpus-question-qa","workflow_file":"full-corpus-qa.yml","max_age_hours":840,"accepted_events":["schedule"]},{"id":"official-pdf-batch-pipeline","workflow_file":"official-pdf-batch-pipeline.yml","max_age_hours":36,"accepted_events":["schedule"]}];
const HEARTBEAT_SCHEMA = `CREATE TABLE IF NOT EXISTS ops_task_heartbeat (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  scheduled_at TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  payload TEXT NOT NULL
)`;
const HEARTBEAT_SAVE = `INSERT INTO ops_task_heartbeat (id, scheduled_at, observed_at, payload)
VALUES (1, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET
scheduled_at=excluded.scheduled_at, observed_at=excluded.observed_at, payload=excluded.payload
WHERE excluded.scheduled_at > ops_task_heartbeat.scheduled_at`;

function heartbeatTask(task, runs, now) {
  const base = {id:task.id, workflow_file:task.workflow_file, max_age_hours:task.max_age_hours};
  if (!Array.isArray(runs)) return {...base,status:'error',failure_class:'invalid_response'};
  // A manual recovery or PR must never erase a failed scheduled run.
  const accepted = runs.filter(r=>r.event==='schedule' && r.head_branch==='main' &&
    r.status==='completed' && r.head_repository?.full_name==='grizzly020503/swsi-quiz-backup');
  accepted.sort((a,b)=>String(b.run_started_at||b.created_at||'').localeCompare(String(a.run_started_at||a.created_at||'')));
  if (!accepted.length) return {...base,status:'missing',failure_class:'no_scheduled_evidence'};
  const run=accepted[0], stamp=Date.parse(run.run_started_at||run.created_at);
  if (!Number.isFinite(stamp) || stamp>now+300000)
    return {...base,status:'error',failure_class:'invalid_run_timestamp'};
  const age=Math.max(0,(now-stamp)/3600000);
  const status=run.conclusion!=='success'?'failed':age>task.max_age_hours?'stale':'healthy';
  return {...base,status,run_id:run.id,last_run_at:new Date(stamp).toISOString(),
    age_hours:Math.round(age*100)/100,failure_class:status==='healthy'?'none':status};
}

async function heartbeatRuns(task) {
  const url='https://api.github.com/repos/grizzly020503/swsi-quiz-backup/actions/workflows/'+
    encodeURIComponent(task.workflow_file)+'/runs?event=schedule&branch=main&status=completed&per_page=10';
  // Workers supports manual/follow only; reject 3xx through !ok without following.
  const response=await fetch(url,{method:'GET',redirect:'manual',signal:AbortSignal.timeout(10000),
    headers:{'User-Agent':'swsi-cloudflare-task-heartbeat','Accept':'application/vnd.github+json'}});
  if (!response.ok) {
    const error=Error('github_http_'+response.status);
    // Only bounded numeric rate metadata; never persist upstream bodies/headers wholesale.
    const rate={};
    for (const [header,key,max] of [
      ['x-ratelimit-remaining','remaining',1000000000],
      ['x-ratelimit-reset','reset_epoch',9999999999],
      ['retry-after','retry_after_seconds',86400],
    ]) {
      const value=response.headers.get(header);
      if(value!==null && /^\d{1,10}$/.test(value) && Number(value)<=max) rate[key]=Number(value);
    }
    error.rate=rate;
    await response.body?.cancel().catch(()=>{});
    throw error;
  }
  if (Number(response.headers.get('content-length')||0)>1000000) throw Error('response_too_large');
  const reader=response.body.getReader();let bytes=0;const chunks=[];
  try {
    for (;;) {const {done,value}=await reader.read();if(done)break;bytes+=value.byteLength;
      if(bytes>1000000) throw Error('response_too_large');chunks.push(value);}
  } finally {await reader.cancel().catch(()=>{});}
  const buffer=new Uint8Array(bytes);let offset=0;for(const c of chunks){buffer.set(c,offset);offset+=c.byteLength;}
  const data=JSON.parse(new TextDecoder().decode(buffer));
  if (!Array.isArray(data.workflow_runs)) throw Error('invalid_response');
  return data.workflow_runs;
}

export async function runTaskHeartbeat(env, scheduledTime) {
  const now=Date.now();
  if (!Number.isFinite(scheduledTime)||scheduledTime>now+300000) throw Error('invalid_schedule');
  const observed=new Date(now).toISOString(), scheduled=new Date(scheduledTime).toISOString();
  const tasks=await Promise.all(HEARTBEAT_TASKS.map(async task=>{
    try {return heartbeatTask(task,await heartbeatRuns(task),now);}
    catch (error) {
      // Publish only bounded classifications; URLs, upstream bodies and secrets never leave this handler.
      const message=String(error?.message||'');
      const failure=/^github_http_\d{3}$/.test(message)?message:
        ['response_too_large','invalid_response'].includes(message)?message:'source_unavailable';
      return {id:task.id,workflow_file:task.workflow_file,max_age_hours:task.max_age_hours,status:'error',failure_class:failure,
        ...(/^github_http_\d{3}$/.test(message) && error.rate ? {upstream_rate:error.rate} : {})};
    }
  }));
  const unhealthy=tasks.filter(t=>t.status!=='healthy');
  const components={};
  for (const component of ['site','data_freshness','grading','ai','review_backlog']) {
    components[component]={status:'unknown',checked_at:observed,scope:component,
      failure_class:'not_probed',detail:{note:'This observer verifies scheduled tasks only.'}};
  }
  components.task_heartbeat={status:unhealthy.length?'failed':'healthy',checked_at:observed,
    scope:'github-main-schedules',failure_class:unhealthy.length?'scheduled_task_attention':'none',
    detail:{tasks_checked:tasks.length,attention:unhealthy.length}};
  const payload={schema_version:1,producer:'cloudflare-cron',generated_at:observed,
    scheduled_at:scheduled,independent_of:'github-actions',components,tasks};
  await env.AI_QUOTA_DB.prepare(HEARTBEAT_SCHEMA).run();
  await env.AI_QUOTA_DB.prepare(HEARTBEAT_SAVE).bind(scheduled,observed,JSON.stringify(payload)).run();
}

export async function readTaskHeartbeat(request, env) {
  const headers={'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store',
    'X-Content-Type-Options':'nosniff'};
  const reply=(data,status)=>new Response(JSON.stringify(data),{status,headers});
  if (request.method!=='GET') return new Response(null,{status:405,headers:{...headers,Allow:'GET'}});
  try {
    // GET never creates tables, triggers probes, writes state, or accepts caller-provided URLs.
    const row=await env.AI_QUOTA_DB.prepare('SELECT payload FROM ops_task_heartbeat WHERE id=1').first();
    if (!row) return reply({status:'awaiting_first_schedule',independent_monitoring_active:false},503);
    const data=JSON.parse(row.payload), age=(Date.now()-Date.parse(data.generated_at))/60000;
    const valid=data.producer==='cloudflare-cron' && data.schema_version===1 &&
      Array.isArray(data.tasks) && data.tasks.length===HEARTBEAT_TASKS.length;
    if(!valid) throw Error('invalid_stored_observation');
    const fresh=Number.isFinite(age)&&age>=-5&&age<=45;
    return reply({...data,observer_status:fresh?'fresh':'stale',independent_monitoring_active:fresh},fresh?200:503);
  } catch {
    return reply({status:'observation_unavailable',independent_monitoring_active:false},503);
  }
}
