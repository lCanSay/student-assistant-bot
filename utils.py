import json
import os
from typing import List, Dict, Any

def load_data(filepath: str) -> Any:
    """
    Load data from a JSON file.
    """
    if not os.path.exists(filepath):
        return {} if filepath.endswith('contacts.json') else []
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return {} if filepath.endswith('contacts.json') else []

def search_knowledge_base(user_message: str, faq_data: List[Dict]) -> str:
    """
    Search for keywords in the user message and return relevant text chunks.
    """
    found_texts = []
    message_lower = user_message.lower()
    
    for item in faq_data:
        keywords = item.get("keywords", [])
        for keyword in keywords:
            if keyword.lower() in message_lower:
                found_texts.append(item.get("text", ""))
                break # Avoid adding same text multiple times if multiple keywords match
                
    return "\n\n".join(found_texts)

def search_files(user_message: str, files_data: List[Dict]) -> List[Dict]:
    """
    Search for files based on keywords in the user message.
    """
    found_files = []
    message_lower = user_message.lower()
    
    for item in files_data:
        keywords = item.get("keywords", [])
        for keyword in keywords:
            if keyword.lower() in message_lower:
                found_files.append(item)
                break
                
    return found_files

def save_file_entry(entry_dict: Dict, filepath: str) -> None:
    """
    Append a new file entry to the database.
    """
    data = load_data(filepath)
    if isinstance(data, list):
        data.append(entry_dict)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving to {filepath}: {e}")

def update_file_entry(file_id: str, new_keywords: List[str], new_caption: str, filepath: str) -> bool:
    """
    Update an existing file entry in the database.
    """
    data = load_data(filepath)
    if not isinstance(data, list):
        return False
        
    updated = False
    for item in data:
        if item.get("file_id") == file_id:
            item["keywords"] = new_keywords
            item["caption"] = new_caption
            updated = True
            break
            
    if updated:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error updating {filepath}: {e}")
            return False
            
    return False
