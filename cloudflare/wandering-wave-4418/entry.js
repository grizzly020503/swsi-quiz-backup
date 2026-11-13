import aiWorker from './worker.js';
import { runTaskHeartbeat, readTaskHeartbeat } from './task-heartbeat.js';

// Preserve the reviewed AI implementation and pass every other request unchanged.
export default {
  async scheduled(controller, env) {
    if (controller.cron !== '*/15 * * * *') throw Error('unexpected heartbeat cron');
    await runTaskHeartbeat(env, controller.scheduledTime);
  },
  async fetch(request, env, ctx) {
    if (new URL(request.url).pathname === '/ops/task-heartbeat') {
      return readTaskHeartbeat(request, env);
    }
    return aiWorker.fetch(request, env, ctx);
  }
};
