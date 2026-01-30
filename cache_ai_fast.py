"""
PMP AI Cache Builder - Version 2.1 (Enhanced Logic & Professional Analysis)
---------------------------------------------------------------------
- Role: Senior PMP Mentor (PMBOK 7 & Agile Practice Guide)
- Features: 
    + Strict English technical terms with Vietnamese explanations.
    + Forced correct answer alignment from Database.
    + JSON options parsing & clean formatting.
    + Deep situational analysis.
"""

import os
import sys
import argparse
import time
import json
from typing import Optional, List, Dict
from dotenv import load_dotenv
import httpx

try:
    from huggingface_hub import InferenceClient
except ImportError:
    print("❌ Error: Module 'huggingface_hub' chưa được cài đặt.")
    print("   Vui lòng chạy: pip install huggingface_hub python-dotenv httpx")
    sys.exit(1)

# --- 1. CẤU HÌNH HỆ THỐNG ---
load_dotenv()

SUPABASE_URL = os.getenv('VITE_SUPABASE_URL') or os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('VITE_SUPABASE_ANON_KEY') or os.getenv('SUPABASE_KEY')
HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY')
# Khuyến nghị Qwen2.5-72B để tuân thủ định dạng tốt nhất
HF_MODEL = os.getenv('HF_MODEL') or "meta-llama/Llama-3.1-70B-Instruct"

if not all([SUPABASE_URL, SUPABASE_KEY, HUGGINGFACE_API_KEY]):
    print("❌ Error: Thiếu cấu hình .env (SUPABASE_URL, SUPABASE_KEY, HUGGINGFACE_API_KEY)!")
    sys.exit(1)

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=minimal'
}

# --- 2. LOGIC PROMPT TỐI ƯU ---

def get_theory_prompt(question: str, options: str, language: str) -> str:
    target_lang = "Tiếng Việt" if language == 'vi' else "English"
    
    return f"""You are a world-class PMP Instructor. 
STRICT RULES:
1. All technical PMP terms (e.g., 'Critical Path', 'Risk Register', 'Sprint Retrospective') MUST remain in English.
2. Provide detailed explanations in {target_lang}.
3. DO NOT repeat explanations if a term appears in both the question and options.
4. Focus on the 'Why' and 'How' it's used in project management.

Question: {question}
Options:
{options}

Format the response as follows:
## Cơ sở lý thuyết các khái niệm
- **[English Term]**: [Detailed explanation in {target_lang}]
- **[English Term]**: [Detailed explanation...]

## Các công cụ và kỹ thuật (Tools & Techniques)
- **[English Term]**: [Specific purpose and application in this context]
"""

def get_explanation_prompt(question: str, options: str, correct_letter: str, language: str) -> str:
    target_lang = "Tiếng Việt" if language == 'vi' else "English"
    
    # Trích xuất nội dung text của đáp án đúng để ép AI
    correct_text = "N/A"
    for line in options.split('\n'):
        if line.startswith(f"{correct_letter}."):
            correct_text = line.replace(f"{correct_letter}. ", "")
            break

    return f"""You are a PMP Mentor. 
STRICT RULES:
1. The correct answer is {correct_letter}: "{correct_text}". You MUST justify this answer.
2. Use {target_lang} for the explanation but KEEP technical terms in English.
3. Provide a deep analysis of the situation (Lifecycle: Agile/Predictive/Hybrid).

Question: {question}
Options:
{options}

Format the response as follows:
## Phân tích tình huống
[Phân tích ngữ cảnh dự án, xác định vấn đề cốt lõi và giai đoạn của dự án.]

## Giải thích đáp án đúng ({correct_letter})
[Giải thích tại sao "{correct_text}" là lựa chọn tốt nhất dựa trên PM Mindset và tiêu chuẩn PMI.]

## Tại sao các đáp án khác không phù hợp
[Phân tích chi tiết từng phương án còn lại và lý do loại trừ chúng.]

## PMP Mindset
[Một quy tắc vàng hoặc mẹo rút ra từ câu hỏi này.]
"""

# --- 3. API & DATABASE COMMUNICATION ---

def call_huggingface(prompt: str) -> Optional[str]:
    client = InferenceClient(api_key=HUGGINGFACE_API_KEY)
    try:
        messages = [
            {"role": "system", "content": "You are a professional PMP tutor. You keep technical terms in English but explain in the requested language. You never use Chinese/Japanese characters."},
            {"role": "user", "content": prompt}
        ]
        response = client.chat_completion(
            model=HF_MODEL,
            messages=messages,
            max_tokens=2000,
            temperature=0.1 # Thấp để đảm bảo tính logic và bám sát prompt
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"   ⚠️ API Error: {str(e)[:100]}...")
        return None

def fetch_questions(start: int, end: int) -> List[Dict]:
    try:
        url = f"{SUPABASE_URL}/rest/v1/pmp_questions"
        with httpx.Client() as client:
            resp = client.get(url, headers=HEADERS, params={'select': '*'})
            if resp.status_code != 200: 
                print(f"❌ DB Error: {resp.text}")
                return []
            
            data = resp.json()
            # Hàm trích xuất số từ ID (VD: "Q1" -> 1)
            def extract_num(q):
                num_part = ''.join(filter(str.isdigit, str(q.get('id', ''))))
                return int(num_part) if num_part else 0
            
            data.sort(key=extract_num)
            return [q for q in data if start <= extract_num(q) <= end]
    except Exception as e:
        print(f"❌ Fetch Error: {e}")
        return []

def save_to_cache(q_id: str, lang: str, c_type: str, content: str):
    url = f"{SUPABASE_URL}/rest/v1/pmp_ai_cache"
    with httpx.Client() as client:
        # Xóa bản ghi cũ nếu có (upsert logic)
        client.delete(url, headers=HEADERS, params={'question_id': f'eq.{q_id}', 'language': f'eq.{lang}', 'type': f'eq.{c_type}'})
        # Ghi mới
        payload = {'question_id': q_id, 'language': lang, 'type': c_type, 'content': content}
        client.post(url, headers=HEADERS, json=payload)

def get_cached_content(q_id: str, lang: str, c_type: str) -> Optional[str]:
    url = f"{SUPABASE_URL}/rest/v1/pmp_ai_cache"
    params = {'question_id': f'eq.{q_id}', 'language': f'eq.{lang}', 'type': f'eq.{c_type}', 'select': 'content'}
    with httpx.Client() as client:
        r = client.get(url, headers=HEADERS, params=params)
        return r.json()[0]['content'] if r.status_code == 200 and r.json() else None

# --- 4. EXECUTION ---

def main():
    parser = argparse.ArgumentParser(description='PMP AI Cache Builder Professional')
    parser.add_argument('range', help='Range câu hỏi (VD: 1-50)')
    parser.add_argument('--lang', default='vi', choices=['vi', 'en'])
    parser.add_argument('--force', action='store_true', help='Ghi đè cache cũ')
    args = parser.parse_args()

    try:
        start, end = map(int, args.range.split('-'))
    except ValueError:
        print("❌ Định dạng range sai. Ví dụ: 1-10")
        return

    print(f"\n{'='*60}")
    print(f"🚀 PMP AI BUILDER PRO: {start} -> {end} ({args.lang.upper()})")
    print(f"🤖 Model: {HF_MODEL}")
    print(f"{'='*60}\n")

    questions = fetch_questions(start, end)
    if not questions:
        print("⚠️ Không tìm thấy câu hỏi nào.")
        return

    for idx, q in enumerate(questions):
        q_id = q['id']
        correct_letter = q.get('correct_answer', 'A')
        print(f"[{idx+1}/{len(questions)}] Processing ID: {q_id} (Answer: {correct_letter})...")
        
        # Parse options: Database lưu dạng '["A...","B..."]' (string JSON)
        try:
            raw_options = q.get('options', [])
            if isinstance(raw_options, str):
                options_list = json.loads(raw_options)
            else:
                options_list = raw_options
        except Exception:
            options_list = []

        # Làm sạch options: loại bỏ prefix 'A. ' nếu có để format lại đồng nhất
        clean_options = []
        for i, opt in enumerate(options_list):
            prefix = f"{chr(65+i)}. "
            content = opt.replace(prefix, "") if opt.startswith(prefix) else opt
            clean_options.append(f"{chr(65+i)}. {content}")
        
        options_str = '\n'.join(clean_options)
        
        for c_type in ['theory', 'explanation']:
            if not args.force:
                if get_cached_content(q_id, args.lang, c_type):
                    print(f"   - {c_type.capitalize()}: Skipped (Exists)")
                    continue

            print(f"   - {c_type.capitalize()}: Generating...", end="", flush=True)
            
            if c_type == 'theory':
                prompt = get_theory_prompt(q['question'], options_str, args.lang)
            else:
                prompt = get_explanation_prompt(q['question'], options_str, correct_letter, args.lang)
            
            result = call_huggingface(prompt)
            if result:
                save_to_cache(q_id, args.lang, c_type, result)
                print(" ✅ Done.")
            else:
                print(" ❌ Failed.")
            
            time.sleep(1) # Tránh rate limit API

    print(f"\n🎉 Finished! Range {args.range} is ready.")

if __name__ == "__main__":
    main()