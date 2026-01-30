// JavaScript serverless function for Vercel
// Vercel handles compilation for JS/TS in /api easily.
// Make sure to select Node.js 18.x+ in Vercel settings.

const HUGGINGFACE_API_KEY = process.env.HUGGINGFACE_API_KEY || process.env.VITE_HUGGINGFACE_API_KEY || '';
const HF_MODEL = process.env.HF_MODEL || process.env.VITE_HF_MODEL || "meta-llama/Llama-3.1-70B-Instruct";
// OpenAI-compatible endpoint via Router (REQUIRED due to deprecation of api-inference)
const HF_API_URL = "https://router.huggingface.co/hf-inference/v1/chat/completions";

export default async function handler(req, res) {
    // 1. CORS Headers
    res.setHeader('Access-Control-Allow-Credentials', 'true');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,PATCH,DELETE,POST,PUT');
    res.setHeader(
        'Access-Control-Allow-Headers',
        'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version'
    );

    // 2. Handle Options
    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    // 3. Only POST
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        console.log(`[API] Processing request for model: ${HF_MODEL}`);

        if (!HUGGINGFACE_API_KEY) {
            console.error('[API] Error: Missing HUGGINGFACE_API_KEY');
            return res.status(500).json({ error: 'Server configuration error: Missing API Key' });
        }

        const { messages, max_tokens = 2000, temperature = 0.1 } = req.body;

        if (!messages || !Array.isArray(messages)) {
            return res.status(400).json({ error: 'Invalid request body' });
        }

        console.log(`[API] Calling external HF API: ${HF_API_URL}`);

        // Native fetch (Node 18+)
        const response = await fetch(HF_API_URL, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${HUGGINGFACE_API_KEY}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: HF_MODEL,
                messages,
                max_tokens,
                temperature
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`[API] HF Error ${response.status}:`, errorText);

            if (response.status === 429 || response.status === 503) {
                return res.status(503).json({ error: 'AI_SERVICE_UNAVAILABLE', details: errorText });
            }

            return res.status(response.status).json({
                error: 'Upstream API Error',
                details: errorText
            });
        }

        const data = await response.json();

        if (!data.choices || data.choices.length === 0) {
            return res.status(500).json({ error: 'No content generated' });
        }

        return res.status(200).json(data);

    } catch (error) {
        console.error('[API] Internal Error:', error);
        return res.status(500).json({
            error: 'Internal Server Error',
            message: error.message
        });
    }
}
