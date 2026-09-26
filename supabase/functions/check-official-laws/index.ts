import "jsr:@supabase/functions-js/edge-runtime.d.ts";

Deno.serve(() => new Response(
  JSON.stringify({ disabled: true, message: "Deprecated bulk MOJ downloader. Official legal watching is handled by GitHub Actions and sync-legal-watch." }),
  { status: 410, headers: { "content-type": "application/json; charset=utf-8" } },
));
