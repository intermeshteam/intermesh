import { Buffer } from 'buffer';
import crypto from 'crypto';
import WebSocket from 'ws';

// ============================================================================
// MOTEUR CRYPTOGRAPHIQUE COMPATIBLE PYTHON (RSA-OAEP + AES-256-GCM)
// ============================================================================

export class NexusCrypto {
  static generateKeyPair() {
    return crypto.generateKeyPairSync('rsa', {
      modulusLength: 2048,
      publicKeyEncoding: { type: 'spki', format: 'pem' },
      privateKeyEncoding: { type: 'pkcs8', format: 'pem' }
    });
  }

  static encryptFor(recipientPublicKeyPem, plaintext) {
    const aesKey = crypto.randomBytes(32);
    const iv = crypto.randomBytes(12);

    const cipher = crypto.createCipheriv('aes-256-gcm', aesKey, iv);
    let ciphertext = cipher.update(plaintext, 'utf8', 'base64');
    ciphertext += cipher.final('base64');
    const tag = cipher.getAuthTag();

    const combinedCiphertext = Buffer.concat([
      Buffer.from(ciphertext, 'base64'),
      tag
    ]);

    const encryptedAesKey = crypto.publicEncrypt({
      key: recipientPublicKeyPem,
      padding: crypto.constants.RSA_PKCS1_OAEP_PADDING,
      oaepHash: 'sha256'
    }, aesKey);

    const envelope = {
      ek: encryptedAesKey.toString('base64'),
      n: iv.toString('base64'),
      ct: combinedCiphertext.toString('base64')
    };

    return Buffer.from(JSON.stringify(envelope)).toString('base64');
  }

  static decryptWith(privateKeyPem, encryptedB64) {
    const envelope = JSON.parse(Buffer.from(encryptedB64, 'base64').toString('utf8'));

    const encryptedAesKey = Buffer.from(envelope.ek, 'base64');
    const iv = Buffer.from(envelope.n, 'base64');
    const combinedCiphertext = Buffer.from(envelope.ct, 'base64');

    const tag = combinedCiphertext.subarray(combinedCiphertext.length - 16);
    const ciphertext = combinedCiphertext.subarray(0, combinedCiphertext.length - 16);

    const aesKey = crypto.privateDecrypt({
      key: privateKeyPem,
      padding: crypto.constants.RSA_PKCS1_OAEP_PADDING,
      oaepHash: 'sha256'
    }, encryptedAesKey);

    const decipher = crypto.createDecipheriv('aes-256-gcm', aesKey, iv);
    decipher.setAuthTag(tag);
    let decrypted = decipher.update(ciphertext, 'base64', 'utf8');
    decrypted += decipher.final('utf8');

    return decrypted;
  }
}

// ============================================================================
// AGENT NEXUS JAVASCRIPT
// ============================================================================

export class NexusAgent {
  constructor({ name, capabilities = [], roles = [], permissions = [], metadata = {}, hubUrl = 'ws://localhost:8765', encrypt = true }) {
    this.name = name;
    this.capabilities = capabilities;
    this.roles = roles.length ? roles : ['standard'];
    this.permissions = permissions;
    this.metadata = metadata;
    this.hubUrl = hubUrl;
    this.encrypt = encrypt;

    this.ws = null;
    this.token = null;
    this.publicKeyCache = {};
    this.pendingRequests = {};
    this.pendingTasks = {};

    const { publicKey, privateKey } = NexusCrypto.generateKeyPair();
    this.privateKeyPem = privateKey;
    this.publicKeyPem = publicKey;

    this.identity = {
      name: this.name,
      capabilities: this.capabilities,
      roles: this.roles,
      permissions: this.permissions,
      created_at: Date.now() / 1000,
      metadata: this.metadata,
      public_key: this.publicKeyPem
    };

    this.identity.fingerprint = this._computeFingerprint();
  }

  _computeFingerprint() {
    const data = {
      agent_id: this.name,
      name: this.name,
      capabilities: [...this.capabilities].sort(),
      roles: [...this.roles].sort(),
      permissions: [...this.permissions].sort(),
      created_at: this.identity.created_at
    };
    return crypto.createHash('sha256').update(JSON.stringify(data)).digest('hex');
  }

  onMessage(handler) { this.messageHandler = handler; }
  onRequest(handler) { this.requestHandler = handler; }
  onTask(handler) { this.taskHandler = handler; }

  async connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.hubUrl);

      this.ws.on('open', () => {
        const regMsg = {
          id: crypto.randomUUID(),
          version: 'nexus/v1',
          type: 'register',
          sender: this.name,
          content: { ...this.identity, agent_id: this.name }
        };
        this.ws.send(JSON.stringify(regMsg));
      });

      this.ws.on('message', (data) => {
        const msg = JSON.parse(data.toString());

        if (msg.type === 'registered') {
          this.token = msg.content.token;
          console.log(`✅ [${this.name}] Connecté en Node.js | E2E: ${this.encrypt ? '🔒 ON' : '🔓 OFF'}`);
          this._startListening();
          resolve();
        } else if (msg.type === 'error' && !this.token) {
          reject(new Error(msg.content));
        }
      });

      this.ws.on('error', reject);
    });
  }

  _startListening() {
    this.ws.on('message', async (data) => {
      const msg = JSON.parse(data.toString());

      if (['response', 'identity', 'discover_result'].includes(msg.type) && this.pendingRequests[msg.reply_to]) {
        const { resolve } = this.pendingRequests[msg.reply_to];
        delete this.pendingRequests[msg.reply_to];
        
        let content = msg.content;
        if (this.encrypt && msg.type === 'response' && typeof content === 'string') {
          content = JSON.parse(NexusCrypto.decryptWith(this.privateKeyPem, content));
        }
        resolve(content);
      }

      else if (msg.type === 'task_assign') {
        this._executeTask(msg.content);
      }

      else if (msg.type === 'task_update') {
        const task = msg.content;
        if (this.pendingTasks[task.task_id]) {
          const { resolve, reject } = this.pendingTasks[task.task_id];
          if (task.status === 'completed') {
            delete this.pendingTasks[task.task_id];
            let out = task.output_data;
            if (this.encrypt && typeof out === 'string') {
              out = JSON.parse(NexusCrypto.decryptWith(this.privateKeyPem, out));
            }
            resolve(out);
          } else if (task.status === 'failed') {
            delete this.pendingTasks[task.task_id];
            reject(new Error(task.error_message));
          }
        }
      }

      else if (msg.type === 'request') {
        let content = msg.content;
        if (this.encrypt && typeof content === 'string') {
          content = JSON.parse(NexusCrypto.decryptWith(this.privateKeyPem, content));
        }

        if (this.requestHandler) {
          let reply = await this.requestHandler(content, msg.sender);
          if (this.encrypt) {
            const pk = await this._fetchPublicKey(msg.sender);
            reply = NexusCrypto.encryptFor(pk, JSON.stringify(reply));
          }

          this.ws.send(JSON.stringify({
            id: crypto.randomUUID(),
            version: 'nexus/v1',
            type: 'response',
            sender: this.name,
            to: msg.sender,
            reply_to: msg.id,
            content: reply,
            token: this.token
          }));
        }
      }

      else if (msg.type === 'message') {
        let content = msg.content;
        if (this.encrypt && typeof content === 'string') {
          content = JSON.parse(NexusCrypto.decryptWith(this.privateKeyPem, content));
        }
        if (this.messageHandler) this.messageHandler(content, msg.sender);
      }
    });
  }

  async _executeTask(task) {
    console.log(`⚙️  [${this.name}] Exécution tâche: '${task.title}'`);
    
    task.status = 'running';
    this.ws.send(JSON.stringify({
      id: crypto.randomUUID(), version: 'nexus/v1', type: 'task_update',
      sender: this.name, content: task, token: this.token
    }));

    let input = task.input_data;
    if (this.encrypt && typeof input === 'string') {
      input = JSON.parse(NexusCrypto.decryptWith(this.privateKeyPem, input));
    }

    try {
      const output = await this.taskHandler(input, task);
      let encOutput = output;
      if (this.encrypt) {
        const pk = await this._fetchPublicKey(task.orchestrator);
        encOutput = NexusCrypto.encryptFor(pk, JSON.stringify(output));
      }
      task.status = 'completed';
      task.output_data = encOutput;
    } catch (err) {
      task.status = 'failed';
      task.error_message = err.message;
    }

    this.ws.send(JSON.stringify({
      id: crypto.randomUUID(), version: 'nexus/v1', type: 'task_update',
      sender: this.name, content: task, token: this.token
    }));
  }

  async _fetchPublicKey(agentName) {
    if (this.publicKeyCache[agentName]) return this.publicKeyCache[agentName];
    const data = await this.whoIs(agentName);
    this.publicKeyCache[agentName] = data.public_key;
    return data.public_key;
  }

  async whoIs(agentName) {
    return new Promise((resolve) => {
      const msgId = crypto.randomUUID();
      this.pendingRequests[msgId] = { resolve };
      this.ws.send(JSON.stringify({
        id: msgId, version: 'nexus/v1', type: 'who_is',
        sender: this.name, content: agentName, token: this.token
      }));
    });
  }

  async discover(query) {
    return new Promise((resolve) => {
      const msgId = crypto.randomUUID();
      this.pendingRequests[msgId] = { resolve };
      this.ws.send(JSON.stringify({
        id: msgId, version: 'nexus/v1', type: 'discover',
        sender: this.name, content: query, token: this.token
      }));
    });
  }

  async submitTask(title, assignee, inputData) {
    const pk = await this._fetchPublicKey(assignee);
    const encryptedInput = this.encrypt ? NexusCrypto.encryptFor(pk, JSON.stringify(inputData)) : inputData;

    const task = {
      task_id: crypto.randomUUID(),
      title,
      orchestrator: this.name,
      assignee,
      input_data: encryptedInput,
      status: 'pending',
      created_at: Date.now() / 1000,
      updated_at: Date.now() / 1000
    };

    return new Promise((resolve, reject) => {
      this.pendingTasks[task.task_id] = { resolve, reject };
      this.ws.send(JSON.stringify({
        id: crypto.randomUUID(), version: 'nexus/v1', type: 'task_submit',
        sender: this.name, content: task, token: this.token
      }));
      console.log(`📝 [${this.name}] Tâche Node.js soumise ➜ ${assignee} 🔒`);
    });
  }
}
