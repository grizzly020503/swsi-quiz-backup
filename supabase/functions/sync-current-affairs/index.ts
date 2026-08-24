import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const REPO = "grizzly020503/swsi-quiz-backup";
const SOURCES = new Set(["衛生福利部焦點新聞","衛生福利部公告訊息","中央社社會","中央社生活","中央社政治","中央社國際"]);
const CATEGORIES = new Set(["兒少保護","家暴與性暴力","心理健康與成癮","長照與高齡","社會救助與居住","身障與人權","移工與新住民","少年司法與犯罪防治","性別與家庭政策","災害與社區工作","社工專業與社福制度"]);

function json(body: unknown,status=200){return new Response(JSON.stringify(body),{status,headers:{"content-type":"application/json; charset=utf-8"}})}
async function verifyRepoToken(token:string){
  const r=await fetch(`https://api.github.com/repos/${REPO}`,{headers:{Authorization:`Bearer ${token}`,Accept:"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"swsi-current-affairs-sync/1.0"}});
  if(!r.ok)return false;
  const repo=await r.json();
  return repo?.full_name===REPO&&repo?.private===true;
}
function safeArticleUrl(value:unknown){
  try{
    const u=new URL(String(value||""));
    if(u.protocol!=="https:")return false;
    return u.hostname==="cna.com.tw"||u.hostname.endsWith(".cna.com.tw")||u.hostname==="mohw.gov.tw"||u.hostname.endsWith(".mohw.gov.tw");
  }catch{return false}
}
Deno.serve(async(req:Request)=>{
  if(req.method!=="POST")return json({error:"POST only"},405);
  const token=(req.headers.get("authorization")||"").replace(/^Bearer\s+/i,"").trim();
  if(!token||!(await verifyRepoToken(token)))return json({error:"unauthorized GitHub workflow"},403);
  let body:any; try{body=await req.json()}catch{return json({error:"invalid JSON"},400)}
  const items=Array.isArray(body?.items)?body.items:[];
  if(items.length>200)return json({error:"too many items"},400);
  for(const x of items){
    if(!x||!/^[a-f0-9]{32}$/i.test(String(x.id||"")))return json({error:"invalid id"},400);
    if(typeof x.title!=="string"||!x.title.trim())return json({error:`invalid title ${x.id}`},400);
    if(!SOURCES.has(String(x.source_name||"")))return json({error:`source rejected ${x.id}`},400);
    if(!safeArticleUrl(x.source_url))return json({error:`source_url rejected ${x.id}`},400);
    if(!CATEGORIES.has(String(x.category||"")))return json({error:`category rejected ${x.id}`},400);
    const score=Number(x.relevance_score); if(!Number.isInteger(score)||score<0||score>10)return json({error:`score rejected ${x.id}`},400);
    if(!["taiwan","international"].includes(String(x.region||"")))return json({error:`region rejected ${x.id}`},400);
  }
  const url=Deno.env.get("SUPABASE_URL"),key=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if(!url||!key)return json({error:"Supabase env missing"},500);
  const sb=createClient(url,key,{auth:{persistSession:false}});
  const now=new Date().toISOString();
  let upserted=0;
  for(let i=0;i<items.length;i+=100){
    const batch=items.slice(i,i+100),ids=batch.map((x:any)=>String(x.id));
    const {data:oldRows,error:oldErr}=await sb.from("current_affairs").select("id,status,manual_note,first_seen_at").in("id",ids);
    if(oldErr)return json({error:`read existing: ${oldErr.message}`},500);
    const oldMap=new Map((oldRows||[]).map((r:any)=>[r.id,r]));
    const rows=batch.map((x:any)=>{
      const old:any=oldMap.get(String(x.id));
      return {
        id:String(x.id),title:String(x.title).slice(0,500),summary:String(x.summary||"").slice(0,600),
        source_name:String(x.source_name),source_url:String(x.source_url),source_feed:String(x.source_feed||""),
        published_at:x.published_at||null,region:String(x.region),category:String(x.category),relevance_score:Number(x.relevance_score),
        exam_tags:Array.isArray(x.exam_tags)?x.exam_tags.slice(0,15).map(String):[],subjects:Array.isArray(x.subjects)?x.subjects.slice(0,5).map(String):[],
        status:old?.status||"candidate",manual_note:old?.manual_note||null,first_seen_at:old?.first_seen_at||now,last_seen_at:now,updated_at:now
      };
    });
    const {error}=await sb.from("current_affairs").upsert(rows,{onConflict:"id"});
    if(error)return json({error:`upsert: ${error.message}`},500);
    upserted+=rows.length;
  }
  const cutoff=new Date(Date.now()-1000*60*60*24*548).toISOString();
  await sb.from("current_affairs").update({status:"archived",updated_at:now}).eq("status","candidate").lt("published_at",cutoff);
  await sb.from("current_affairs_sync_runs").insert({fetched_count:Number(body?.fetched_count||0),accepted_count:items.length,note:`feeds=${Array.isArray(body?.feed_errors)?body.feed_errors.length:0} errors`});
  return json({ok:true,upserted,feed_errors:Array.isArray(body?.feed_errors)?body.feed_errors:[]});
});
