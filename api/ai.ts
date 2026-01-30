import type { VercelRequest, VercelResponse } from '@vercel/node';

const HUGGINGFACE_API_KEY = process.env.HUGGINGFACE_API_KEY || '';
const HF_MODEL = process.env.HF_MODEL || "meta-llama/Llama-3.1-70B-Instruct";
const HF_API_URL = `https://api-inference.huggingface.co/models/${HF_MODEL}/v1/chat/completions`;

export default async function handler(req: VercelRequest, res: VercelResponse) {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Credentials', 'true');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,PATCH,DELETE,POST,PUT');
    res.setHeader(
        'Access-Control-Allow-Headers',
        'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version'
    );

    // Handle preflight request
    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    // Only allow POST
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    // Validate API key
    if (!HUGGINGFACE_API_KEY) {
        return res.status(500).json({ error: 'Hugging Face API key not configured' });
    }

    try {
        const { messages, max_tokens = 2000, temperature = 0.1 } = req.body;

        if (!messages || !Array.isArray(messages)) {
            return res.status(400).json({ error: 'Invalid request: messages array required' });
        }

        // Call Hugging Face API
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
            console.error(`Hugging Face API error (${response.status}):`, errorText);

            // Check for rate limiting or service unavailable
            if (response.status === 429 || response.status === 503) {
                return res.status(503).json({
                    error: 'AI_SERVICE_UNAVAILABLE',
                    message: 'AI service is currently overloaded. Please try again later.'
                });
            }

            return res.status(response.status).json({
                error: 'Hugging Face API error',
                details: errorText
            });
        }

        const data = await response.json();

        if (!data.choices || data.choices.length === 0) {
            return res.status(500).json({ error: 'No response generated' });
        }

        // Return the response
        return res.status(200).json(data);

    } catch (error: any) {
        console.error('API proxy error:', error);
        return res.status(500).json({
            error: 'Internal server error',
            message: error?.message || 'Unknown error'
        });
    }
}
