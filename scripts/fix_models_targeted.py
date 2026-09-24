import os
import re

files_to_fix = [
    "backend/video_generation/agents/storyboard_agent.py",
    "backend/video_generation/agents/story_agent.py",
    "backend/video_generation/agents/teaching_planner_agent.py",
    "backend/video_generation/agents/board_understanding_agent.py",
    "backend/video_generation/agents/codegen_agent.py",
    "backend/video_generation/agents/document_embedder.py",
    "backend/video_generation/agents/latex_agents.py",
    "backend/video_generation/agents/notes_agent.py",
    "backend/video_qa/annotation_handler.py",
    "backend/latex_video/narration_planner.py",
    "backend/local_server.py",
    "app/services/reasoning/stem_solver.py",
    "app/services/recognition/vision_recognizer.py"
]

for filepath in files_to_fix:
    if not os.path.exists(filepath): continue
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    out = []
    in_gen_json = False
    in_call_groq = False
    for line in lines:
        if "def _generate_json(" in line:
            in_gen_json = True
            indent = line[:line.find("def")]
            out.append(line)
            out.append(indent + "    from shared.ai_client import ai_client\n")
            out.append(indent + "    import json\n")
            out.append(indent + "    import re as _re\n")
            out.append(indent + "    try:\n")
            out.append(indent + "        resp = ai_client.generate_content(prompt, json_schema={'type': 'object'})\n")
            out.append(indent + "        match = _re.search(r'\\{.*\\}', resp, flags=_re.S)\n")
            out.append(indent + "        if match:\n")
            out.append(indent + "            return json.loads(match.group(0))\n")
            out.append(indent + "        return json.loads(resp)\n")
            out.append(indent + "    except Exception as e:\n")
            out.append(indent + "        print(f'[Agent] error: {e}')\n")
            out.append(indent + "        return {}\n")
            continue
            
        if in_gen_json:
            if line.strip().startswith("def "):
                in_gen_json = False
            else:
                continue

        if "def _call_groq(" in line:
            in_call_groq = True
            indent = line[:line.find("def")]
            out.append(line)
            out.append(indent + "    from shared.ai_client import ai_client\n")
            out.append(indent + "    return ai_client.generate_content(prompt)\n")
            continue

        if in_call_groq:
            if line.strip().startswith("def "):
                in_call_groq = False
            else:
                continue

        out.append(line)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(out)
        
    print(f"Fixed {filepath}")
