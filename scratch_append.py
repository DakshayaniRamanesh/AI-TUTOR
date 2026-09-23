content = open('backend/local_server.py').read()

ask_endpoint = '''
from pydantic import BaseModel

class AskRequest(BaseModel):
    question: str
    mode: str = 'study'

@app.post("/api/ask")
async def ask_ai(req: AskRequest):
    """
    LLM generation endpoint for AI Q&A.
    """
    import os
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
    
    question = req.question
    mode = req.mode
    
    keywords = ["explain", "explanation", "why", "how", "steps", "step by step", "show work", "show steps", "elaborate", "detail", "details", "derive", "derivation", "proof", "prove"]
    asked_explain = any(k in question.lower() for k in keywords)

    if mode == "classroom":
        prompt = (
            "You are a concise STEM solver for a classroom blackboard.\\n"
            "CRITICAL: Do NOT output any thinking process, reasoning steps, or analysis.\\n"
            "Output ONLY the direct answer.\\n\\n"
            f"Question: {question}\\n\\n"
            "Format strictly as:\\n"
            "Answer: <direct answer>"
        )
    else:
        prompt = (
            "You are a helpful AI tutor in ASK AI.\\n"
            "CRITICAL: Do NOT output any internal thinking process, reasoning steps, analysis, or monologue.\\n"
            "Provide the question, direct answer, and then a clear, concise explanation with 2-3 bullet points.\\n\\n"
            f"Question: {question}\\n\\n"
            "Format strictly as:\\n"
            f"Question: {question}\\n"
            "Answer: <direct answer with clean math notation>\\n\\n"
            "Explanation:\\n"
            "- <concise step or key point 1>\\n"
            "- <concise step or key point 2>"
        )

    raw_output = ""
    if groq_key and not groq_key.startswith("your_"):
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=600
            )
            raw_output = resp.choices[0].message.content
        except Exception as e:
            print(f"[Backend] Groq failed: {e}")
            raw_output = ""

    if not raw_output and gemini_key and not gemini_key.startswith("your_"):
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            resp = model.generate_content(prompt)
            raw_output = resp.text
        except Exception as e:
            print(f"[Backend] Gemini failed: {e}")
            from fastapi.responses import JSONResponse
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    if not raw_output:
        from fastapi.responses import JSONResponse
        return JSONResponse({"status": "error", "message": "All LLM backends failed or no keys configured."}, status_code=500)

    return {"status": "ok", "raw_output": raw_output, "asked_explain": asked_explain}
'''

content += '\n' + ask_endpoint + '\n'
open('backend/local_server.py', 'w').write(content)
