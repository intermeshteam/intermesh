import { Buffer } from 'buffer';
import crypto from 'crypto';
import WebSocket from 'ws';

export { NexusPipeline, PipelineError, fanOut } from './pipeline.js';

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
    const textToEncrypt = typeof plaintext === 'string' ? plaintext : JSON.stringify(plaintext);
    const aesKey = crypto.randomBytes(32);
    const iv = crypto.randomBytes(12);

    const cipher = crypto.createCipheriv('aes-256-gcm', aesKey, iv);
    let ciphertext = cipher.update(textToEncrypt, 'utf8', 'base64');
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
// AGENT NEXUS JAVASCRIPT / NODE.JS (COMPATIBLE PROTOCOLE nexus/v1)
// ============================================================================

export class NexusAgent {
  constructor({
    name,
    orgId = process.env.NEXUS_DEFAULT_ORG || 'default',
    apiKey = null,
    capabilities = [],
    roles = [],
    permissions = [],
    metadata = {},
    hubUrl = process.env.NEXUS_HUB_URL || 'ws://localhost:8765',
    encrypt = true
  }) {
    this.name = name;
    this.orgId = orgId;
    this.apiKey = apiKey;
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

    this.qualifiedName = this.orgId !== 'default' && !this.name.includes('/')
      ? `${this.orgId}/${this.name}`
      : this.name;

    this.identity = {
      agent_id: crypto.randomUUID(),
      name: this.name,
      org_id: this.orgId,
      qualified_name: this.qualifiedName,
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
      agent_id: this.identity.agent_id,
      name: this.name,
      org_id: this.orgId,
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
        const payload = { ...this.identity };
        if (this.apiKey) {
          payload.api_key = this.apiKey;
        }

        const regMsg = {
          id: crypto.randomUUID(),
          version: 'nexus/v1',
          type: 'register',
          sender: this.name,
          content: payload
        };
        this.ws.send(JSON.stringify(regMsg));
      });

      this.ws.on('message', (data) => {
        try {
          const msg = JSON.parse(data.toString());

          if (msg.type === 'registered') {
            this.token = msg.content.token;
            if (msg.content.qualified_name) {
              this.qualifiedName = msg.content.qualified_name;
              this.identity.qualified_name = msg.content.qualified_name;
            }
            if (msg.content.roles) this.identity.roles = msg.content.roles;
            if (msg.content.permissions) this.identity.permissions = msg.content.permissions;
            if (msg.content.org_id) {
              this.identity.org_id = msg.content.org_id;
              this.orgId = msg.content.org_id;
            }

            this._startListening();
            resolve();
          } else if (msg.type === 'error' && !this.token) {
            reject(new Error(msg.content));
          }
        } catch (err) {
          reject(err);
        }
      });

      this.ws.on('error', reject);
    });
  }

  _startListening() {
    this.ws.on('message', async (data) => {
      try {
        const msg = JSON.parse(data.toString());

        if (['response', 'identity', 'discover_result', 'admin_result'].includes(msg.type) && this.pendingRequests[msg.reply_to]) {
          const { resolve } = this.pendingRequests[msg.reply_to];
          delete this.pendingRequests[msg.reply_to];

          let content = msg.content;
          if (this.encrypt && msg.type === 'response' && typeof content === 'string') {
            try {
              content = JSON.parse(NexusCrypto.decryptWith(this.privateKeyPem, content));
            } catch {
              content = NexusCrypto.decryptWith(this.privateKeyPem, content);
            }
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
                try {
                  out = JSON.parse(NexusCrypto.decryptWith(this.privateKeyPem, out));
                } catch {
                  out = NexusCrypto.decryptWith(this.privateKeyPem, out);
                }
              }
              resolve(out);
            } else if (task.status === 'failed') {
              delete this.pendingTasks[task.task_id];
              reject(new Error(task.error_message || 'Tâche échouée.'));
            }
          }
        }

        else if (msg.type === 'request') {
          let content = msg.content;
          if (this.encrypt && typeof content === 'string') {
            try {
              content = JSON.parse(NexusCrypto.decryptWith(this.privateKeyPem, content));
            } catch {
              content = NexusCrypto.decryptWith(this.privateKeyPem, content);
            }
          }

          if (this.requestHandler) {
            let reply = await this.requestHandler(content, msg.sender);
            if (this.encrypt) {
              const pk = await this._fetchPublicKey(msg.sender);
              if (pk) {
                reply = NexusCrypto.encryptFor(pk, reply);
              }
            }

            this.ws.send(JSON.stringify({
              id: crypto.randomUUID(),
              version: 'nexus/v1',
              type: 'response',
              sender: this.qualifiedName,
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
            try {
              content = JSON.parse(NexusCrypto.decryptWith(this.privateKeyPem, content));
            } catch {
              content = NexusCrypto.decryptWith(this.privateKeyPem, content);
            }
          }
          if (this.messageHandler) this.messageHandler(content, msg.sender);
        }

        else if (msg.type === 'error') {
          if (msg.reply_to && this.pendingRequests[msg.reply_to]) {
            const { reject } = this.pendingRequests[msg.reply_to];
            delete this.pendingRequests[msg.reply_to];
            reject(new Error(msg.content));
          }
        }
      } catch (err) {
        // En cas de paquet malformé, ne pas crasher la boucle d'écoute
      }
    });
  }

  async _executeTask(task) {
    task.status = 'running';
    this.ws.send(JSON.stringify({
      id: crypto.randomUUID(),
      version: 'nexus/v1',
      type: 'task_update',
      sender: this.qualifiedName,
      content: task,
      token: this.token
    }));

    let input = task.input_data;
    if (this.encrypt && typeof input === 'string') {
      try {
        input = JSON.parse(NexusCrypto.decryptWith(this.privateKeyPem, input));
      } catch {
        input = NexusCrypto.decryptWith(this.privateKeyPem, input);
      }
    }

    try {
      if (!this.taskHandler) throw new Error('Aucun handler de tâche configuré.');
      const output = await this.taskHandler(input, task);
      let encOutput = output;
      if (this.encrypt) {
        const pk = await this._fetchPublicKey(task.orchestrator);
        if (pk) {
          encOutput = NexusCrypto.encryptFor(pk, output);
        }
      }
      task.status = 'completed';
      task.output_data = encOutput;
    } catch (err) {
      task.status = 'failed';
      task.error_message = err.message;
    }

    this.ws.send(JSON.stringify({
      id: crypto.randomUUID(),
      version: 'nexus/v1',
      type: 'task_update',
      sender: this.qualifiedName,
      content: task,
      token: this.token
    }));
  }

  async _fetchPublicKey(agentName) {
    if (this.publicKeyCache[agentName]) return this.publicKeyCache[agentName];
    try {
      const data = await this.whoIs(agentName, 3000);
      if (data && data.public_key) {
        this.publicKeyCache[agentName] = data.public_key;
        return data.public_key;
      }
    } catch {
      // Ignorer si indisponible
    }
    return null;
  }

  async whoIs(agentName, timeoutMs = 5000) {
    return new Promise((resolve, reject) => {
      const msgId = crypto.randomUUID();
      const timer = setTimeout(() => {
        delete this.pendingRequests[msgId];
        reject(new Error(`who_is timed out after ${timeoutMs}ms`));
      }, timeoutMs);

      this.pendingRequests[msgId] = {
        resolve: (val) => { clearTimeout(timer); resolve(val); },
        reject: (err) => { clearTimeout(timer); reject(err); }
      };

      this.ws.send(JSON.stringify({
        id: msgId,
        version: 'nexus/v1',
        type: 'who_is',
        sender: this.qualifiedName,
        content: agentName,
        token: this.token
      }));
    });
  }

  async discover(query, timeoutMs = 5000) {
    return new Promise((resolve, reject) => {
      const msgId = crypto.randomUUID();
      const timer = setTimeout(() => {
        delete this.pendingRequests[msgId];
        reject(new Error(`discover timed out after ${timeoutMs}ms`));
      }, timeoutMs);

      this.pendingRequests[msgId] = {
        resolve: (val) => { clearTimeout(timer); resolve(val); },
        reject: (err) => { clearTimeout(timer); reject(err); }
      };

      this.ws.send(JSON.stringify({
        id: msgId,
        version: 'nexus/v1',
        type: 'discover',
        sender: this.qualifiedName,
        content: query,
        token: this.token
      }));
    });
  }

  async submitTask(title, assignee, inputData, timeoutMs = 15000) {
    let encryptedInput = inputData;
    if (this.encrypt) {
      const pk = await this._fetchPublicKey(assignee);
      if (pk) {
        encryptedInput = NexusCrypto.encryptFor(pk, inputData);
      }
    }

    const task = {
      task_id: crypto.randomUUID(),
      title,
      orchestrator: this.qualifiedName,
      assignee,
      input_data: encryptedInput,
      status: 'pending',
      created_at: Date.now() / 1000,
      updated_at: Date.now() / 1000
    };

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        delete this.pendingTasks[task.task_id];
        reject(new Error(`Tâche '${title}' expirée (${timeoutMs / 1000}s).`));
      }, timeoutMs);

      this.pendingTasks[task.task_id] = {
        resolve: (val) => { clearTimeout(timer); resolve(val); },
        reject: (err) => { clearTimeout(timer); reject(err); }
      };

      this.ws.send(JSON.stringify({
        id: crypto.randomUUID(),
        version: 'nexus/v1',
        type: 'task_submit',
        sender: this.qualifiedName,
        to: assignee,
        content: task,
        token: this.token
      }));
    });
  }
}
