#!/usr/bin/env python3
"""
Fast PMP AI Cache Builder - Parallel Processing
------------------------------------------------
Sử dụng concurrent processing để cache nhiều câu hỏi cùng lúc.
Nhanh hơn 5-10 lần so với version tuần tự.

Cách sử dụng:
    python cache_ai_fast.py 1-100           # Cache câu 1-100 với 5 workers
    python cache_ai_fast.py 1-100 --workers 10  # Dùng 10 workers (nhanh hơn)
    python cache_ai_fast.py 1-100 --lang en     # Tiếng Anh
    python cache_ai_fast.py 1-100 --force       # Ghi đè cache cũ
"""

import os
import sys
import argparse
import time
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import httpx

try:
    from huggingface_hub import InferenceClient
except ImportError:
    print("❌ Error: Module 'huggingface_hub' chưa được cài đặt.")
    print("   Vui lòng chạy: pip install huggingface_hub")
    sys.exit(1)

# Load environment variables
load_dotenv('.env.local')
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv('VITE_SUPABASE_URL') or os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('VITE_SUPABASE_ANON_KEY') or os.getenv('SUPABASE_KEY')
HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY')
HF_MODEL = os.getenv('HF_MODEL') or "Qwen/Qwen2.5-7B-Instruct"

# Validate
if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: SUPABASE_URL và SUPABASE_KEY chưa được cấu hình!")
    sys.exit(1)

if not HUGGINGFACE_API_KEY:
    print("❌ Error: HUGGINGFACE_API_KEY chưa được cấu hình!")
    sys.exit(1)

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=minimal'
}

# Shared HTTP client for better performance
http_client = httpx.Client(timeout=60.0)

def get_theory_prompt(question: str, options: str, language: str) -> str:
    """Tạo prompt cho Theory"""
    language_instruction = 'Vui lòng trả lời bằng tiếng Việt.' if language == 'vi' else 'Please respond in English.'
    
    if language == 'vi':
        prompt_structure = """## Dịch câu hỏi sang tiếng Việt

Dịch câu hỏi chính sang tiếng Việt một cách chính xác và dễ hiểu.

Sau đó dịch TỪNG đáp án dưới dạng DANH SÁCH (bullet list):

- **A.** [Bản dịch đáp án A]
- **B.** [Bản dịch đáp án B]
- **C.** [Bản dịch đáp án C]
- **D.** [Bản dịch đáp án D]

## Cơ sở lý thuyết các thuật ngữ trong câu hỏi

Liệt kê và giải thích TẤT CẢ các PMP concepts, processes, knowledge areas, và thuật ngữ quản lý dự án được đề cập trong câu hỏi.

Định dạng cho mỗi thuật ngữ:
- **Tên thuật ngữ** (in đậm, không có dấu hai chấm)
- Giải thích ngắn gọn và đầy đủ về thuật ngữ đó theo PMBOK Guide (trên dòng mới)

## Cơ sở lý thuyết các thuật thuật ngữ trong đáp án

Liệt kê và giải thích TẤT CẢ các PMP concepts, processes, và thuật ngữ quản lý dự án xuất hiện trong các đáp án (A, B, C, D).

Định dạng cho mỗi thuật ngữ:
- **Tên thuật ngữ** (in đậm, không có dấu hai chấm)
- Giải thích ngắn gọn và đầy đủ về thuật ngữ đó theo PMBOK Guide (trên dòng mới)"""
        
        formatting_rules = """FORMATTING RULES (DO NOT include these rules in your response):
- Each answer option must be a bullet point, NOT a heading
- Do NOT use colons after term names
- Do NOT create separate headings for answer options
- Start directly with content sections"""
    else:
        prompt_structure = """## Theoretical Foundation of Question Terms

List and explain ALL PMP concepts, processes, knowledge areas, and project management terms mentioned in the question.

Format for each term:
- **Term name** (bold, NO colon)
- Concise but thorough explanation based on PMBOK Guide (on new line)

## Theoretical Foundation of Answer Terms

List and explain ALL PMP concepts, processes, and project management terms appearing in the answers (A, B, C, D).

Format for each term:
- **Term name** (bold, NO colon)
- Concise but thorough explanation based on PMBOK Guide (on new line)"""
        
        formatting_rules = """FORMATTING RULES (DO NOT include these rules in your response):
- Do NOT use colons after term names
- Start directly with content sections"""
    
    return f"""You are a Project Management Professional (PMP) expert. Provide theoretical foundation for this question based on PMBOK Guide and PMI standards.

Question: {question}

Options:
{options}

{language_instruction}

IMPORTANT: Start directly with the theoretical content. Do NOT include any greetings, introductions, conclusions, or the formatting rules themselves.

{formatting_rules}

Provide a comprehensive theoretical breakdown:

{prompt_structure}

Keep the theory organized and easy to reference (max 500 words)."""


def get_explanation_prompt(question: str, options: str, correct_answer: str, language: str) -> str:
    """Tạo prompt cho Explanation"""
    language_instruction = 'Vui lòng trả lời bằng tiếng Việt.' if language == 'vi' else 'Please respond in English.'
    
    prompt_structure = f"""## Giải thích câu hỏi

Phân tích yêu cầu chính của câu hỏi, xác định các điểm mấu chốt cần chú ý theo PMBOK Guide.

## Giải thích đáp án đúng

Tại sao đáp án {correct_answer} là đúng? Giải thích chi tiết dựa trên các nguyên tắc và quy trình PMP.

## Tại sao không chọn các đáp án khác

Phân tích TỪNG đáp án sai một cách riêng biệt. Mỗi đáp án phải được giải thích trên một đoạn văn riêng theo định dạng:

**Đáp án X:**
[Giải thích tại sao đáp án này sai và không phù hợp với best practices của PMI]

## Các lỗi thường gặp

Liệt kê các lỗi mà thí sinh hay mắc phải khi làm dạng câu hỏi này.

## Mẹo để nhớ

Cung cấp các mẹo, tricks để áp dụng cho các câu hỏi tương tự trong kỳ thi PMP.

QUAN TRỌNG: 
- Khi đề cập đến các keywords hoặc concepts, viết chúng ở dạng **in đậm** KHÔNG CÓ dấu hai chấm (:) phía sau
- Mỗi đáp án trong phần giải thích phải xuống dòng riêng biệt
- Ví dụ: **Keyword** chứ không phải **Keyword:**""" if language == 'vi' else f"""## Question Analysis

Analyze the main requirements of the question and identify the key points based on PMBOK Guide.

## Correct Answer Explanation

Why is answer {correct_answer} correct? Explain in detail based on PMP principles and processes.

## Why Other Answers Are Wrong

Analyze each incorrect answer and explain why they don't align with PMI best practices.

## Common Mistakes

List the mistakes students often make on this type of PMP question.

## Tips to Remember

Provide tips and tricks to apply to similar questions in the PMP exam.

IMPORTANT: When mentioning keywords or concepts in content, write them in **bold** withOUT colons (:) after. Example: **Keyword** NOT **Keyword:**"""
    
    return f"""You are a Project Management Professional (PMP) expert. Analyze this PMP exam question based on PMBOK Guide and PMI standards.

Question: {question}

Options:
{options}

Correct Answer: {correct_answer}

{language_instruction}

IMPORTANT: Start directly with the analysis. Do NOT include any greetings, introductions, or conclusions. Go straight to the structured content.

Do NOT use colons (:) after bold keywords. Write descriptions on the same line or new line without colons.

Provide a comprehensive explanation:

{prompt_structure}

Keep the explanation structured and easy to understand (max 600 words)."""


def call_huggingface(prompt: str, max_retries: int = 3) -> Optional[str]:
    """Gọi Hugging Face API với retry"""
    client = InferenceClient(api_key=HUGGINGFACE_API_KEY)
    
    for attempt in range(max_retries):
        try:
            messages = [
                {"role": "system", "content": "You are a helpful PMP expert assistant specializing in project management and PMBOK Guide."},
                {"role": "user", "content": prompt}
            ]
            
            response = client.chat_completion(
                model=HF_MODEL,
                messages=messages,
                max_tokens=1500,
                temperature=0.7
            )
            return response.choices[0].message.content
            
        except Exception as e:
            error_str = str(e)
            
            # Log FULL error for debugging
            if attempt == 0:  # Only log first attempt
                print(f"\n      ⚠️ FULL ERROR: {error_str}\n")
            
            if '503' in error_str.lower() or 'loading' in error_str.lower():
                if attempt < max_retries - 1:
                    print(f"      ⏳ Model loading, waiting 10s...")
                    time.sleep(10)
                    continue
            
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            
            return None
    
    return None


def get_cached_content(question_id: str, language: str, content_type: str) -> Optional[str]:
    """Kiểm tra cache"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/pmp_ai_cache"
        params = {
            'question_id': f'eq.{question_id}',
            'language': f'eq.{language}',
            'type': f'eq.{content_type}',
            'select': 'content'
        }
        
        response = http_client.get(url, headers=HEADERS, params=params)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return data[0]['content']
        return None
    except:
        return None


def save_to_cache(question_id: str, language: str, content_type: str, content: str) -> bool:
    """Lưu cache using UPSERT"""
    try:
        # Use UPSERT with on_conflict parameter
        # The unique constraint is on (question_id, language, type)
        url = f"{SUPABASE_URL}/rest/v1/pmp_ai_cache?on_conflict=question_id,language,type"
        
        data = {
            'question_id': question_id,
            'language': language,
            'type': content_type,
            'content': content
        }
        
        # Use Prefer: resolution=merge-duplicates for UPSERT
        upsert_headers = HEADERS.copy()
        upsert_headers['Prefer'] = 'resolution=merge-duplicates,return=minimal'
        
        response = http_client.post(url, headers=upsert_headers, json=data)
        
        if response.status_code not in [200, 201, 204]:
            print(f"      ⚠️ Save failed - Status: {response.status_code}, Response: {response.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"      ⚠️ Save exception: {e}")
        return False


def format_options(options: list) -> str:
    """Format options"""
    return '\n'.join([f"{chr(65+i)}. {opt}" for i, opt in enumerate(options)])


def process_single_content(question: dict, language: str, content_type: str, force: bool) -> dict:
    """Xử lý 1 loại content (theory hoặc explanation) cho 1 câu hỏi"""
    question_id = question['id']
    
    try:
        # Check cache
        if not force and get_cached_content(question_id, language, content_type):
            return {'id': question_id, 'type': content_type, 'status': 'cached'}
        
        # Generate content
        question_text = question['question']
        options = question['options']
        correct_answer = question['correct_answer']
        options_str = format_options(options)
        
        if content_type == 'theory':
            prompt = get_theory_prompt(question_text, options_str, language)
        else:
            prompt = get_explanation_prompt(question_text, options_str, correct_answer, language)
        
        print(f"      🔄 Calling HF API for Q{question_id} ({content_type})...")
        content = call_huggingface(prompt)
        
        if content:
            if save_to_cache(question_id, language, content_type, content):
                return {'id': question_id, 'type': content_type, 'status': 'success'}
            else:
                print(f"      ❌ Failed to save cache for Q{question_id} ({content_type})")
                return {'id': question_id, 'type': content_type, 'status': 'save_failed'}
        else:
            print(f"      ❌ API returned None for Q{question_id} ({content_type})")
            return {'id': question_id, 'type': content_type, 'status': 'api_failed'}
    
    except Exception as e:
        print(f"      ❌ EXCEPTION in process_single_content: {e}")
        import traceback
        traceback.print_exc()
        return {'id': question_id, 'type': content_type, 'status': 'exception', 'error': str(e)}


def fetch_questions(start: int, end: int) -> list:
    """Lấy câu hỏi từ Supabase"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/pmp_questions"
        params = {'select': '*'}
        
        response = http_client.get(url, headers=HEADERS, params=params)
        if response.status_code != 200:
            return []
        questions = response.json()
        
        def get_number(q):
            num_str = ''.join(filter(str.isdigit, q.get('id', '')))
            return int(num_str) if num_str else 0
        
        questions.sort(key=get_number)
        
        filtered = []
        for q in questions:
            num = get_number(q)
            if start <= num <= end:
                filtered.append(q)
        return filtered
    except Exception as e:
        print(f"❌ Error fetching questions: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description='Fast PMP AI Cache Builder (Parallel)')
    parser.add_argument('range', help='Range câu hỏi (VD: 1-100)')
    parser.add_argument('--lang', default='vi', choices=['vi', 'en'], help='Ngôn ngữ')
    parser.add_argument('--type', choices=['theory', 'explanation'], help='Loại nội dung')
    parser.add_argument('--force', action='store_true', help='Ghi đè cache cũ')
    parser.add_argument('--workers', type=int, default=5, help='Số workers song song (default: 5)')
    
    args = parser.parse_args()
    
    try:
        start, end = map(int, args.range.split('-'))
    except ValueError:
        print("❌ Invalid range format. Use: start-end (e.g., 1-100)")
        sys.exit(1)
    
    print(f"\n╔══════════════════════════════════════════════════════════════╗")
    print(f"║      Fast PMP AI Cache Builder (Parallel Processing)        ║")
    print(f"╠══════════════════════════════════════════════════════════════╣")
    print(f"║  Range: {start} - {end}")
    print(f"║  Language: {'Tiếng Việt' if args.lang == 'vi' else 'English'}")
    print(f"║  Workers: {args.workers} (parallel)")
    print(f"║  Model: {HF_MODEL}")
    print(f"╚══════════════════════════════════════════════════════════════╝\n")
    
    print(f"📚 Đang lấy câu hỏi từ {start} đến {end}...")
    questions = fetch_questions(start, end)
    print(f"✅ Tìm thấy {len(questions)} câu hỏi\n")
    
    if not questions:
        print("❌ Không tìm thấy câu hỏi nào!")
        return
    
    content_types = [args.type] if args.type else ['theory', 'explanation']
    
    # Tạo danh sách tasks
    tasks = []
    for q in questions:
        for content_type in content_types:
            tasks.append((q, args.lang, content_type, args.force))
    
    total_tasks = len(tasks)
    print(f"🚀 Bắt đầu xử lý {total_tasks} tasks với {args.workers} workers...\n")
    
    # Statistics
    stats = {'cached': 0, 'success': 0, 'failed': 0}
    start_time = time.time()
    
    # Process in parallel
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_single_content, q, lang, ctype, force): (q['id'], ctype)
            for q, lang, ctype, force in tasks
        }
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            q_id, ctype = futures[future]
            
            try:
                result = future.result()
                status = result['status']
                
                if status == 'cached':
                    stats['cached'] += 1
                    icon = '✓'
                elif status == 'success':
                    stats['success'] += 1
                    icon = '✅'
                else:
                    stats['failed'] += 1
                    icon = '❌'
                
                # Progress
                progress = (completed / total_tasks) * 100
                elapsed = time.time() - start_time
                eta = (elapsed / completed) * (total_tasks - completed) if completed > 0 else 0
                
                print(f"[{completed}/{total_tasks}] {icon} Q{q_id} ({ctype}) - {progress:.1f}% | ETA: {eta/60:.1f}m")
                
            except Exception as e:
                stats['failed'] += 1
                print(f"[{completed}/{total_tasks}] ❌ Q{q_id} ({ctype}) - Error: {e}")
    
    # Summary
    elapsed = time.time() - start_time
    print(f"\n╔══════════════════════════════════════════════════════════════╗")
    print(f"║                      SUMMARY                                 ║")
    print(f"╠══════════════════════════════════════════════════════════════╣")
    print(f"║  Total tasks: {total_tasks}")
    print(f"║  ✅ Success: {stats['success']}")
    print(f"║  ✓ Cached: {stats['cached']}")
    print(f"║  ❌ Failed: {stats['failed']}")
    print(f"║  ⏱️  Time: {elapsed/60:.1f} minutes")
    print(f"║  ⚡ Speed: {total_tasks/(elapsed/60):.1f} tasks/minute")
    print(f"╚══════════════════════════════════════════════════════════════╝\n")
    
    http_client.close()


if __name__ == "__main__":
    main()
