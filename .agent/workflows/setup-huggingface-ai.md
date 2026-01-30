---
description: Setup Hugging Face AI Integration on Vercel
---

This workflow sets up a robust Hugging Face AI integration using Vercel Serverless Functions and the official `@huggingface/inference` library. This prevents CORS issues and handles API endpoint updates automatically.

1. Install required dependencies
// turbo
```bash
npm install @huggingface/inference
```

2. Create/Update Serverless Function (`api/ai.js`)
Create the file `api/ai.js` with the following content. This function acts as a secure proxy to call Hugging Face API using environment variables.

```javascript
import { HfInference } from "@huggingface/inference";

const hf = new HfInference(process.env.HUGGINGFACE_API_KEY);

export default async function handler(req, res) {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Credentials', 'true');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,PATCH,DELETE,POST,PUT');
    res.setHeader(
        'Access-Control-Allow-Headers',
        'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version'
    );

    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        const { messages, max_tokens, temperature } = req.body;
        const model = process.env.HF_MODEL || "meta-llama/Llama-3.3-70B-Instruct";

        if (!process.env.HUGGINGFACE_API_KEY) {
             console.error("Missing HUGGINGFACE_API_KEY");
             return res.status(500).json({ error: "Server configuration error" });
        }

        console.log(`[API] Calling Hugging Face: ${model}`);
        
        const response = await hf.chatCompletion({
            model: model,
            messages: messages,
            max_tokens: max_tokens || 2000,
            temperature: temperature || 0.7
        });

        return res.status(200).json(response);
    } catch (error) {
        console.error("HF Error:", error);
         // Check for rate limiting
        if (error.statusCode === 503 || error.statusCode === 429) {
            return res.status(503).json({ error: 'AI_SERVICE_UNAVAILABLE', details: error.message });
        }
        return res.status(500).json({ error: error.message });
    }
}
```

3. Configure `vercel.json` rewrites
Update or create `vercel.json` to exclude `/api` from SPA rewrites. This is CRITICAL to avoid 404 errors on API calls.

```json
{
    "rewrites": [
        {
            "source": "/((?!api/.*).*)",
            "destination": "/index.html"
        }
    ]
}
```

4. Create/Update Deployment Guide
Create a `VERCEL_ENV_SETUP.md` file to instruct the user on setting environment variables (`HUGGINGFACE_API_KEY`, `HF_MODEL`) on Vercel Dashboard.

5. Verify Client-side Call
Ensure the client-side code calls `/api/ai` instead of the external URL directly.
