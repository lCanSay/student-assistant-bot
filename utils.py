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
