import { supabase } from './supabase';
import type { Language } from '../types';

// Hugging Face Configuration
const HUGGINGFACE_API_KEY = import.meta.env.VITE_HUGGINGFACE_API_KEY || '';
const HF_MODEL = import.meta.env.VITE_HF_MODEL || "meta-llama/Llama-3.1-70B-Instruct";
const HF_API_URL = `https://api-inference.huggingface.co/models/${HF_MODEL}/v1/chat/completions`;

interface HFMessage {
    role: 'system' | 'user' | 'assistant';
    content: string;
}

interface HFChatRequest {
    model: string;
    messages: HFMessage[];
    max_tokens: number;
    temperature: number;
}

interface HFChatResponse {
    choices: Array<{
        message: {
            content: string;
        };
    }>;
}

async function callHuggingFaceAPI(prompt: string): Promise<string> {
    if (!HUGGINGFACE_API_KEY) {
        throw new Error('No Hugging Face API Key configured');
    }

    try {
        console.log(`🤖 Calling Hugging Face API with model: ${HF_MODEL}...`);

        const messages: HFMessage[] = [
            {
                role: "system",
                content: "You are a professional PMP tutor. You keep technical terms in English but explain in the requested language. You never use Chinese/Japanese characters."
            },
            {
                role: "user",
                content: prompt
            }
        ];

        const requestBody: HFChatRequest = {
            model: HF_MODEL,
            messages: messages,
            max_tokens: 2000,
            temperature: 0.1 // Low temperature for logical and consistent responses
        };

        const response = await fetch(HF_API_URL, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${HUGGINGFACE_API_KEY}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`❌ Hugging Face API error (${response.status}):`, errorText);

            // Check for rate limiting or service unavailable
            if (response.status === 429 || response.status === 503) {
                throw new Error('AI_SERVICE_UNAVAILABLE');
            }

            throw new Error(`Hugging Face API error: ${response.status} - ${errorText}`);
        }

        const data: HFChatResponse = await response.json();

        if (!data.choices || data.choices.length === 0) {
            console.error('❌ No choices in Hugging Face response');
            throw new Error('No response generated');
        }

        const text = data.choices[0].message.content;

        if (!text || text.trim() === '') {
            console.error('❌ Empty response from Hugging Face');
            throw new Error('Empty response generated');
        }

        console.log('✅ Hugging Face API call successful');
        return text;

    } catch (error: any) {
        const errorMsg = error?.message || String(error);
        console.error('❌ Hugging Face API call failed:', errorMsg);

        // Re-throw with appropriate error type
        if (errorMsg.includes('AI_SERVICE_UNAVAILABLE')) {
            throw new Error('AI_SERVICE_UNAVAILABLE');
        }

        throw error;
    }
}

async function getCachedAIContent(
    questionId: string,
    language: Language,
    type: 'explanation' | 'theory'
): Promise<string | null> {
    try {
        const { data, error } = await supabase
            .from('pmp_ai_cache')
            .select('content')
            .eq('question_id', questionId)
            .eq('language', language)
            .eq('type', type)
            .order('created_at', { ascending: false })
            .limit(1)
            .maybeSingle();

        if (error) {
            console.error(`❌ Database error fetching cache for Q${questionId} (${type}, ${language}):`, {
                message: error.message,
                code: error.code,
                details: error.details,
                hint: error.hint
            });
            return null;
        }

        if (!data) {
            console.log(`📭 No cache found in DB for Q${questionId} (${type}, ${language})`);
            return null;
        }

        // Validate content is not empty or error message
        if (!data.content || data.content.trim() === '' || data.content === 'No response generated') {
            console.warn(`⚠️ Invalid cache content for Q${questionId} (${type}, ${language}), will regenerate`);
            return null;
        }

        return data.content;
    } catch (err) {
        console.error(`❌ Exception in getCachedAIContent:`, err);
        return null;
    }
}

async function setCachedAIContent(
    questionId: string,
    language: Language,
    type: 'explanation' | 'theory',
    content: string
): Promise<void> {
    try {
        await supabase.from('pmp_ai_cache').upsert({
            question_id: questionId,
            language,
            type,
            content,
        });
    } catch (error) {
        console.error('Error caching AI content:', error);
    }
}

function getTheoryPrompt(question: string, options: string, language: Language): string {
    const targetLang = language === 'vi' ? "Tiếng Việt" : "English";

    return `You are a world-class PMP Instructor. 
STRICT RULES:
1. All technical PMP terms (e.g., 'Critical Path', 'Risk Register', 'Sprint Retrospective') MUST remain in English.
2. Provide detailed explanations in ${targetLang}.
3. DO NOT repeat explanations if a term appears in both the question and options.
4. Focus on the 'Why' and 'How' it's used in project management.

Question: ${question}
Options:
${options}

Format the response as follows:
## Cơ sở lý thuyết các khái niệm
- **[English Term]**: [Detailed explanation in ${targetLang}]
- **[English Term]**: [Detailed explanation...]

## Các công cụ và kỹ thuật (Tools & Techniques)
- **[English Term]**: [Specific purpose and application in this context]
`;
}

function getExplanationPrompt(question: string, options: string, correctAnswer: string, language: Language): string {
    const targetLang = language === 'vi' ? "Tiếng Việt" : "English";

    // Extract the text of the correct answer
    let correctText = "N/A";
    const optionLines = options.split('\n');
    for (const line of optionLines) {
        if (line.startsWith(`${correctAnswer}.`)) {
            correctText = line.replace(`${correctAnswer}. `, "");
            break;
        }
    }

    return `You are a PMP Mentor. 
STRICT RULES:
1. The correct answer is ${correctAnswer}: "${correctText}". You MUST justify this answer.
2. Use ${targetLang} for the explanation but KEEP technical terms in English.
3. Provide a deep analysis of the situation (Lifecycle: Agile/Predictive/Hybrid).

Question: ${question}
Options:
${options}

Format the response as follows:
## Phân tích tình huống
[Phân tích ngữ cảnh dự án, xác định vấn đề cốt lõi và giai đoạn của dự án.]

## Giải thích đáp án đúng (${correctAnswer})
[Giải thích tại sao "${correctText}" là lựa chọn tốt nhất dựa trên PM Mindset và tiêu chuẩn PMI.]

## Tại sao các đáp án khác không phù hợp
[Phân tích chi tiết từng phương án còn lại và lý do loại trừ chúng.]

## PMP Mindset
[Một quy tắc vàng hoặc mẹo rút ra từ câu hỏi này.]
`;
}

export async function getAIExplanation(
    question: string,
    options: string,
    correctAnswer: string,
    questionId: string,
    language: Language = 'vi'
): Promise<string> {
    // Check cache first
    const cached = await getCachedAIContent(questionId, language, 'explanation');
    if (cached) {
        console.log(`✅ Cache HIT for explanation: Q${questionId} (${language})`);
        return cached;
    }
    console.log(`🔄 Cache MISS - Calling Hugging Face API for explanation: Q${questionId} (${language})`);

    const prompt = getExplanationPrompt(question, options, correctAnswer, language);
    const content = await callHuggingFaceAPI(prompt);

    // Only cache if content is valid
    if (content && content.trim() !== '' && content !== 'No response generated') {
        await setCachedAIContent(questionId, language, 'explanation', content);
    } else {
        console.warn(`⚠️ Not caching invalid explanation for Q${questionId}`);
    }

    return content;
}

export async function getAITheory(
    question: string,
    options: string,
    questionId: string,
    language: Language = 'vi'
): Promise<string> {
    // Check cache first
    const cached = await getCachedAIContent(questionId, language, 'theory');
    if (cached) {
        console.log(`✅ Cache HIT for theory: Q${questionId} (${language})`);
        return cached;
    }
    console.log(`🔄 Cache MISS - Calling Hugging Face API for theory: Q${questionId} (${language})`);

    const prompt = getTheoryPrompt(question, options, language);
    const content = await callHuggingFaceAPI(prompt);

    // Only cache if content is valid
    if (content && content.trim() !== '' && content !== 'No response generated') {
        await setCachedAIContent(questionId, language, 'theory', content);
    } else {
        console.warn(`⚠️ Not caching invalid theory for Q${questionId}`);
    }

    return content;
}
