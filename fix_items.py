import os
import glob

def fix_to_dict():
    items_dir = r"c:\Users\shami\OneDrive\Documents\GitHub\AI-TUTOR\app\ui\items"
    for file_path in glob.glob(os.path.join(items_dir, "*.py")):
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        changed = False
        in_to_dict = False
        for i, line in enumerate(lines):
            if "def to_dict(" in line:
                in_to_dict = True
            elif in_to_dict and "return {" in line:
                # Add item_id to the return dict
                lines[i] = line.replace("return {", "return {\n            \"item_id\": getattr(self, \"item_id\", \"\"),")
                changed = True
                in_to_dict = False
        
        if changed:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"Updated {file_path}")

fix_to_dict()
