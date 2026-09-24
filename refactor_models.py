import os
import re

def refactor_agent(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # If it's already using ai_client, skip
    if "from shared.ai_client import ai_client" in content:
        return False

    orig = content
    # Add import at the top
    if "import" in content:
        content = re.sub(r'^(import .*?\n)', r'\1from shared.ai_client import ai_client\n', content, count=1, flags=re.MULTILINE)
    else:
        content = "from shared.ai_client import ai_client\n" + content

    # Replace self.groq_api_key = os.getenv("GROQ_API_KEY") etc.
    content = re.sub(r'self\.groq_api_key\s*=\s*os\.getenv\(["\']GROQ_API_KEY["\']\)\n?', '', content)
    content = re.sub(r'self\.google_api_key\s*=\s*os\.getenv\(["\']GOOGLE_API_KEY["\']\)\n?', '', content)

    # We need to replace the entire _generate_json or _call_llm block, or any block that does:
    # if self.groq_api_key: ...
    # This is tricky with regex. Instead of regex for the block, we can just replace the actual generation calls.
    # Actually, a simpler way is to replace `genai.GenerativeModel(...)` and `Groq(...)` with ai_client.
    
    # Or, write a custom replacement for each file if there are few.
    # Let's inspect the files.
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return orig != content

for root, _, files in os.walk("backend/video_generation/agents"):
    for file in files:
        if file.endswith(".py"):
            refactor_agent(os.path.join(root, file))
