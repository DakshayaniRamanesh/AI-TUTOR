import os

filepath = 'app/services/reasoning/stem_solver.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# We need to replace the `get_gemini_ai_answer` function.
# Let's find its start and end.
start_str = 'def get_gemini_ai_answer(question: str, mode: str = "study") -> dict:'
end_str = 'def solve_stem_question(question: str, mode: str = "study") -> dict:'

start_idx = content.find(start_str)
end_idx = content.find(end_str)

if start_idx == -1 or end_idx == -1:
    print("Could not find function boundaries")
    exit(1)

new_func = '''def get_gemini_ai_answer(question: str, mode: str = "study") -> dict:
    """
    Calls the local backend /api/ask endpoint to get an AI answer.
    """
    local_ans = get_local_stem_answer(question, mode=mode)
    if local_ans:
        return local_ans

    try:
        backend_url = os.getenv("BACKEND_URL", f"http://127.0.0.1:{os.getenv('PORT', '8000')}").rstrip("/")
        resp = requests.post(
            f"{backend_url}/api/ask",
            json={"question": question, "mode": mode},
            timeout=15.0
        )
        if resp.status_code == 200:
            data = resp.json()
            raw_output = data.get("raw_output", "")
            asked_explain = data.get("asked_explain", False)
            
            text_clean = clean_ai_response(raw_output)
            text_pretty = to_pretty_math(text_clean)
            
            if mode == "classroom":
                return {
                    "hints": text_pretty,
                    "short_solution": text_pretty,
                    "full_solution": text_pretty,
                    "solution": text_pretty,
                    "is_direct_math": True
                }
            if "Explanation:" in text_pretty:
                parts = text_pretty.split("Explanation:", 1)
                short_sol = parts[0].strip()
                full_sol = text_pretty.strip()
            else:
                short_sol = text_pretty.strip()
                full_sol = text_pretty.strip()

            return {
                "hints": short_sol,
                "short_solution": short_sol,
                "full_solution": full_sol,
                "solution": full_sol if asked_explain else short_sol,
                "is_direct_math": not asked_explain
            }
    except Exception as e:
        print(f"[STEM Solver] Error connecting to local backend AI: {e}")
    
    return {}

'''

new_content = content[:start_idx] + new_func + content[end_idx:]

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_content)
    
print("Successfully replaced get_gemini_ai_answer")
