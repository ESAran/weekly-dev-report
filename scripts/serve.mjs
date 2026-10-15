import { startServer } from './server.mjs';

const port = Number(process.env.PORT ?? 4173);
const service = await startServer({ port });
console.log(`Local: ${service.url}`);
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, async () => { await service.close(); process.exit(0); });
