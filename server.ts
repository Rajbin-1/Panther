/**
 * Panther Agent - Local Gateway & Dev Server
 * Manages Python agent runtime lifecycle, proxies API calls, and serves React frontend.
 */

import express, { Request, Response } from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { spawn, ChildProcess } from 'child_process';
import http from 'http';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3000;
const PYTHON_PORT = parseInt(process.env.PANTHER_PORT || '5050', 10);
const PYTHON_URL = `http://127.0.0.1:${PYTHON_PORT}`;

// Parse JSON bodies
app.use(express.json());

let pythonProcess: ChildProcess | null = null;
let pythonStartingPromise: Promise<void> | null = null;
let consecutiveProxyErrors = 0;

// Start Python agent runtime process
function startPythonRuntime(): Promise<void> {
  if (pythonStartingPromise) {
    return pythonStartingPromise;
  }

  const promise: Promise<void> = new Promise<void>((resolve) => {
    console.log(`[Host] Launching Python Agent Runtime on port ${PYTHON_PORT}...`);
    const runtimeScript = path.resolve(__dirname, 'python_runtime', 'main.py');

    if (pythonProcess) {
      try {
        pythonProcess.kill('SIGTERM');
      } catch {
        // ignore
      }
      pythonProcess = null;
    }

    pythonProcess = spawn('python3', [runtimeScript], {
      env: {
        ...process.env,
        PANTHER_PORT: PYTHON_PORT.toString(),
        PYTHONUNBUFFERED: '1',
      },
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    pythonProcess.stdout?.on('data', (data) => {
      console.log(`[Python] ${data.toString().trim()}`);
    });

    pythonProcess.stderr?.on('data', (data) => {
      console.error(`[Python Err] ${data.toString().trim()}`);
    });

    pythonProcess.on('exit', (code, signal) => {
      console.log(`[Python] Process exited with code ${code}, signal ${signal}`);
      pythonProcess = null;
    });

    // Wait until Python HTTP server is responding
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await fetch(`${PYTHON_URL}/api/health`, { signal: AbortSignal.timeout(1000) });
        if (res.ok) {
          clearInterval(interval);
          consecutiveProxyErrors = 0;
          console.log('[Host] Python Agent Runtime is healthy and ready.');
          resolve();
        }
      } catch {
        if (attempts > 40) {
          clearInterval(interval);
          console.warn('[Host] Python Agent Runtime startup poll timed out, continuing...');
          resolve();
        }
      }
    }, 250);
  }).finally(() => {
    pythonStartingPromise = null;
  });

  pythonStartingPromise = promise;
  return promise;
}

async function ensurePythonRuntime(): Promise<void> {
  if (!pythonProcess) {
    await startPythonRuntime();
  } else if (pythonStartingPromise) {
    await pythonStartingPromise;
  }
}

// Proxy all /api/* routes to Python Agent Runtime using http.request
app.use('/api', async (req: Request, res: Response) => {
  await ensurePythonRuntime();

  const payload = req.method !== 'GET' && req.method !== 'HEAD' && req.body && Object.keys(req.body).length > 0
    ? JSON.stringify(req.body)
    : null;

  const headers: Record<string, string | number> = {
    'Content-Type': req.headers['content-type'] || 'application/json',
    'Connection': 'close',
  };
  if (payload) {
    headers['Content-Length'] = Buffer.byteLength(payload);
  }

  const options: http.RequestOptions = {
    hostname: '127.0.0.1',
    port: PYTHON_PORT,
    path: `/api${req.url}`,
    method: req.method,
    headers,
    agent: false,
    timeout: 10000,
  };

  const proxyReq = http.request(options, (proxyRes) => {
    consecutiveProxyErrors = 0;
    res.status(proxyRes.statusCode || 200);
    for (const [k, v] of Object.entries(proxyRes.headers)) {
      if (v) res.setHeader(k, v);
    }
    proxyRes.pipe(res);
  });

  proxyReq.on('timeout', () => {
    proxyReq.destroy(new Error('Proxy connection timed out to Python runtime'));
  });

  proxyReq.on('error', (err) => {
    consecutiveProxyErrors++;
    console.error(`[Proxy Error] Request to ${options.path} failed (${consecutiveProxyErrors}):`, err.message);

    // If Python runtime becomes repeatedly unresponsive, automatically restart it
    if (consecutiveProxyErrors >= 5) {
      console.warn('[Host] Excessive proxy errors detected; triggering Python runtime recycle...');
      consecutiveProxyErrors = 0;
      if (pythonProcess) {
        pythonProcess.kill('SIGKILL');
        pythonProcess = null;
      }
      startPythonRuntime().catch(console.error);
    }

    if (!res.headersSent) {
      res.status(502).json({
        error: 'Python Agent Runtime unavailable or starting up.',
        detail: err.message,
      });
    }
  });

  if (payload) {
    proxyReq.write(payload);
  }
  proxyReq.end();
});

async function main() {
  await startPythonRuntime();

  // Dev mode: Mount Vite middleware
  if (process.env.NODE_ENV !== 'production') {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    // Production mode: Serve dist folder
    app.use(express.static(path.resolve(__dirname, 'dist')));
    app.get('*', (_req: Request, res: Response) => {
      res.sendFile(path.resolve(__dirname, 'dist', 'index.html'));
    });
  }

  const server = app.listen(PORT, '0.0.0.0', () => {
    console.log(`[Panther Agent] Running on http://0.0.0.0:${PORT}`);
  });

  // Graceful shutdown handling
  const cleanShutdown = () => {
    console.log('[Host] Shutting down Panther Agent...');
    if (pythonProcess) {
      pythonProcess.kill('SIGTERM');
    }
    server.close(() => {
      console.log('[Host] Server closed.');
      process.exit(0);
    });
  };

  process.on('SIGINT', cleanShutdown);
  process.on('SIGTERM', cleanShutdown);
}

main().catch((err) => {
  console.error('[Host Fatal]', err);
  if (pythonProcess) {
    (pythonProcess as ChildProcess).kill('SIGTERM');
  }
  process.exit(1);
});
