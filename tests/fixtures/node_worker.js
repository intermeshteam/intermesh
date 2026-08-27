import { NexusAgent } from '../../sdk-js/src/index.js';

const hubPort = process.env.NEXUS_HUB_PORT || '8850';
const hubUrl = `ws://localhost:${hubPort}`;

const agent = new NexusAgent({
  name: 'node_processor',
  orgId: 'default',
  capabilities: ['text_processing', 'international_format'],
  roles: ['worker'],
  hubUrl: hubUrl,
  encrypt: true
});

agent.onTask(async (inputData, task) => {
  const text = inputData.text || '';
  // Inversion conforme Unicode (preservation des paires UTF-16 et caracteres internationaux)
  const processed = Array.from(text).reverse().join('');
  return {
    original: text,
    reversed: processed,
    language_runtime: 'Node.js ' + process.version,
    status: 'SUCCESS'
  };
});

agent.onRequest(async (content, sender) => {
  return {
    pong: true,
    sender: sender,
    runtime: 'Node.js ' + process.version
  };
});

async function run() {
  try {
    await agent.connect();
    if (process.send) {
      process.send('READY');
    }
  } catch (err) {
    process.exit(1);
  }
}

run();
