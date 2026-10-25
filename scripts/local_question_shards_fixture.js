'use strict';
// Test-only transport for the real canonical corpus. No generated/mock questions.
const fs = require('fs');
const path = require('path');
module.exports = async function serveLocalQuestionShards(context) {
  const directory = path.resolve(process.cwd(), 'cdn/question-shards');
  await context.route('https://wandering-wave-4418.c022050333.workers.dev/question-shards/**', route => {
    const name = decodeURIComponent(new URL(route.request().url()).pathname.slice('/question-shards/'.length));
    if (!name || path.basename(name) !== name) return route.fulfill({status:404,body:'not found'});
    const file = path.join(directory, name);
    if (!fs.existsSync(file)) return route.fulfill({status:404,body:'not found'});
    return route.fulfill({status:200,contentType:'application/json; charset=utf-8',
      headers:{'Access-Control-Allow-Origin':'*'},body:fs.readFileSync(file)});
  });
};
