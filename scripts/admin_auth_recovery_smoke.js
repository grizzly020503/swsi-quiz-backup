const assert=require('assert');
const {chromium}=require('playwright');

const base=process.argv[2]||'http://127.0.0.1:4174/admin/index.html';

const mockSdk=String.raw\`
(() => {
  const state={
    session:null,
    listener:null,
    calls:[],
    setSession(session){this.session=session;},
    emit(event,session){
      this.session=session||null;
      if(this.listener)this.listener(event,session||null);
    }
  };
  window.__SWSI_ADMIN_AUTH_TEST__=state;
  window.supabase={
    createClient(){
      return {
        auth:{
          getSession:async()=>({data:{session:state.session}}),
          signInWithPassword:async(args)=>{state.calls.push({name:'signInWithPassword',args});return {error:null};},
          resetPasswordForEmail:async(email,opts)=>{state.calls.push({name:'resetPasswordForEmail',email,opts});return {error:null};},
          signInWithOtp:async(args)=>{state.calls.push({name:'signInWithOtp',args});return {error:null};},
          updateUser:async(args)=>{state.calls.push({name:'updateUser',args});return {error:null};},
          signOut:async()=>{state.calls.push({name:'signOut'});state.session=null;return {error:null};},
          onAuthStateChange(cb){state.listener=cb;return {data:{subscription:{unsubscribe(){}}}};}
        }
      };
    }
  };
})();
\`;

const adminPayload={
  generated_at:'2026-09-26T00:00:00Z',
  summary:{questions:4800,essays:0,feedback_pending:0,unresolved_legal_watch_hits:0},
  feedback:[],
  analytics:{enabled:false},
  ai_telemetry:{enabled:true,status:'idle',requests_60m:0,successes_60m:0,rate_limited_60m:0,hard_errors_60m:0}
};

async function installRoutes(page){
  await page.route('https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2',route=>
    route.fulfill({status:200,contentType:'application/javascript',body:mockSdk})
  );
  await page.route('https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/swsi-admin',async route=>{
    const headers=route.request().headers();
    assert.strictEqual(headers.authorization,'Bearer test-admin-token','admin fetch did not use mocked session token');
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(adminPayload)});
  });
}

async function calls(page,name){
  return await page.evaluate(n=>window.__SWSI_ADMIN_AUTH_TEST__.calls.filter(x=>x.name===n),name);
}

(async()=>{
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:390,height:844}});
  const page=await context.newPage();
  const pageErrors=[];
  page.on('pageerror',e=>pageErrors.push(String(e&&e.message||e)));
  await installRoutes(page);

  // Normal boot: unauthenticated users must see login only.
  await page.goto(base,{waitUntil:'load',timeout:15000});
  await page.waitForSelector('#loginView:not(.hidden)');
  assert(await page.locator('#recoveryView').evaluate(el=>el.classList.contains('hidden')),'recovery view leaked on normal boot');
  assert(await page.locator('#adminView').evaluate(el=>el.classList.contains('hidden')),'admin view leaked before auth');

  // Password recovery must use an explicit recovery callback and preserve account enumeration privacy.
  await page.fill('#email','admin-test@example.invalid');
  await page.click('#resetBtn');
  await page.waitForFunction(()=>window.__SWSI_ADMIN_AUTH_TEST__.calls.some(x=>x.name==='resetPasswordForEmail'));
  const reset=(await calls(page,'resetPasswordForEmail'))[0];
  assert.strictEqual(reset.email,'admin-test@example.invalid');
  const resetUrl=new URL(reset.opts.redirectTo);
  assert.strictEqual(resetUrl.searchParams.get('adminAuth'),'1');
  assert.strictEqual(resetUrl.searchParams.get('authMode'),'recovery');
  assert((await page.locator('#loginMessage').innerText()).includes('不會透露帳號是否存在'),'recovery response leaks account existence semantics');

  // Magic link must be a distinct callback mode and must never create a user.
  await page.click('#magicBtn');
  await page.waitForFunction(()=>window.__SWSI_ADMIN_AUTH_TEST__.calls.some(x=>x.name==='signInWithOtp'));
  const magic=(await calls(page,'signInWithOtp'))[0].args;
  assert.strictEqual(magic.options.shouldCreateUser,false);
  const magicUrl=new URL(magic.options.emailRedirectTo);
  assert.strictEqual(magicUrl.searchParams.get('authMode'),'magic');

  // Recovery callback must lock the dashboard even before a session is available.
  await page.goto(base+'?adminAuth=1&authMode=recovery#type=recovery',{waitUntil:'load',timeout:15000});
  await page.waitForSelector('#recoveryView:not(.hidden)');
  assert(await page.locator('#loginView').evaluate(el=>el.classList.contains('hidden')),'login view visible during recovery');
  assert(await page.locator('#adminView').evaluate(el=>el.classList.contains('hidden')),'dashboard visible during recovery');

  // PASSWORD_RECOVERY with a session must still remain in recovery mode.
  await page.evaluate(()=>{
    window.__SWSI_ADMIN_AUTH_TEST__.emit('PASSWORD_RECOVERY',{access_token:'test-admin-token'});
  });
  await page.waitForFunction(()=>!document.getElementById('recoveryView').classList.contains('hidden'));
  assert(await page.locator('#adminView').evaluate(el=>el.classList.contains('hidden')),'dashboard unlocked before password update');

  // Validation must reject mismatched and weak passwords without calling updateUser.
  await page.fill('#newPassword','StrongPassword1!');
  await page.fill('#confirmPassword','DifferentPassword1!');
  await page.click('#recoveryForm button[type="submit"]');
  assert((await page.locator('#recoveryMessage').innerText()).includes('兩次密碼不一致'),'mismatch validation missing');
  assert.strictEqual((await calls(page,'updateUser')).length,0);

  await page.fill('#newPassword','weakpassword1!');
  await page.fill('#confirmPassword','weakpassword1!');
  await page.click('#recoveryForm button[type="submit"]');
  assert((await page.locator('#recoveryMessage').innerText()).includes('至少 12 個字元'),'strength validation missing');
  assert.strictEqual((await calls(page,'updateUser')).length,0);

  // Only a valid password update may clear recoveryMode and load the dashboard.
  await page.fill('#newPassword','StrongPassword1!');
  await page.fill('#confirmPassword','StrongPassword1!');
  await page.click('#recoveryForm button[type="submit"]');
  await page.waitForFunction(()=>window.__SWSI_ADMIN_AUTH_TEST__.calls.some(x=>x.name==='updateUser'));
  const update=(await calls(page,'updateUser'))[0].args;
  assert.strictEqual(update.password,'StrongPassword1!');
  await page.waitForSelector('#adminView:not(.hidden)',{timeout:3000});
  assert.strictEqual(new URL(page.url()).search,'','recovery query not cleared after successful password update');
  assert.strictEqual(new URL(page.url()).hash,'','recovery hash not cleared after successful password update');
  assert(await page.locator('#recoveryView').evaluate(el=>el.classList.contains('hidden')),'recovery view remained visible after success');

  assert.deepStrictEqual(pageErrors,[],\`page errors: \${pageErrors.join(' | ')}\`);
  await browser.close();
  console.log('ADMIN AUTH RECOVERY BROWSER SMOKE OK');
})().catch(err=>{console.error(err&&err.stack||err);process.exit(1);});
