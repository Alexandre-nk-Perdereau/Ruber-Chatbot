import os
import json
import logging
import base64
from utils.config import get_default_context_size, get_default_system_prompt, get_default_model
from utils.gemini import count_tokens

logger = logging.getLogger(__name__)

class ContextManager:
    """Manages conversation context and message history with token caching"""
    
    def __init__(self, channel_id, system_prompt=None):
        self.channel_id = channel_id
        self.contexts_dir = "contexts"
        self.context_file = os.path.join(self.contexts_dir, f"{channel_id}.json")
        self._ensure_contexts_directory()
        
        self.system_prompt = system_prompt or get_default_system_prompt()
        self.model_name = get_default_model()
        self.context_size = get_default_context_size()
        
        # Structure: {"messages": [...], "token_counts": [...], "total_tokens": int}
        self.context_data = self._load_context()
        
    def _ensure_contexts_directory(self):
        """Ensure the contexts directory exists"""
        os.makedirs(self.contexts_dir, exist_ok=True)

    def _load_context(self):
        """Load context from file or create new if doesn't exist"""
        try:
            with open(self.context_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    messages = data
                    token_counts = [count_tokens(msg["parts"][0], self.model_name) for msg in messages]
                    data = {
                        "messages": messages,
                        "token_counts": token_counts,
                        "total_tokens": sum(token_counts)
                    }
                
                # S'assurer que le premier message est le system prompt
                data["messages"][0] = {"role": "system", "parts": [self.system_prompt]}
                data["token_counts"][0] = count_tokens(self.system_prompt, self.model_name)
                data["total_tokens"] = sum(data["token_counts"])
                
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            # Créer un nouveau contexte
            system_tokens = count_tokens(self.system_prompt, self.model_name)
            return {
                "messages": [{"role": "system", "parts": [self.system_prompt]}],
                "token_counts": [system_tokens],
                "total_tokens": system_tokens
            }

    def save_context(self):
        """Save current context to file"""
        with open(self.context_file, "w", encoding="utf-8") as f:
            json.dump(self.context_data, f, ensure_ascii=False, indent=2)

    def add_message(self, role, content):
        """Add a message to the context with token counting"""
        if isinstance(content, str):
            content = [content]
        elif isinstance(content, list):
            encoded_content = []
            for item in content:
                if isinstance(item, dict) and "data" in item:
                    if item["mime_type"] == "text/plain":
                        encoded_content.append(item)
                    elif isinstance(item["data"], bytes):
                        encoded_item = {
                            "mime_type": item["mime_type"],
                            "data": base64.b64encode(item["data"]).decode("utf-8")
                        }
                        encoded_content.append(encoded_item)
                    else:
                        encoded_content.append(item)
                else:
                    encoded_content.append(item)
            content = encoded_content

        message = {"role": role, "parts": content}
        message_tokens = count_tokens(content[0], self.model_name)

        self.context_data["messages"].append(message)
        self.context_data["token_counts"].append(message_tokens)
        self.context_data["total_tokens"] += message_tokens

        self._trim_context()
        self.save_context()

    def _trim_context(self):
        """Trim context when it exceeds the token limit using cached token counts"""
        while (self.context_data["total_tokens"] > self.context_size and 
               len(self.context_data["messages"]) > 1):
            self.context_data["total_tokens"] -= self.context_data["token_counts"][1]
            self.context_data["messages"].pop(1)
            self.context_data["token_counts"].pop(1)

    def clear_context(self):
        """Clear context except system prompt"""
        system_tokens = self.context_data["token_counts"][0]
        self.context_data = {
            "messages": [self.context_data["messages"][0]],
            "token_counts": [system_tokens],
            "total_tokens": system_tokens
        }
        self.save_context()

    def get_context(self):
        """Get current context"""
        return self.context_data["messages"]

    def get_token_count(self):
        """Get current total token count"""
        return self.context_data["total_tokens"]

    def set_system_prompt(self, new_prompt):
        """Update system prompt with token recounting"""
        self.system_prompt = new_prompt
        new_tokens = count_tokens(new_prompt, self.model_name)
        
        self.context_data["total_tokens"] -= self.context_data["token_counts"][0]
        self.context_data["total_tokens"] += new_tokens
        
        self.context_data["messages"][0] = {"role": "system", "parts": [self.system_prompt]}
        self.context_data["token_counts"][0] = new_tokens
        
        self._trim_context()
        self.save_context()

    def set_model(self, new_model):
        """Update model name with token recounting"""
        old_model = self.model_name
        self.model_name = new_model
        
        new_token_counts = [count_tokens(msg["parts"][0], new_model) 
                          for msg in self.context_data["messages"]]
        
        self.context_data["token_counts"] = new_token_counts
        self.context_data["total_tokens"] = sum(new_token_counts)
        
        self._trim_context()
        self.save_context()

    def set_context_size(self, new_size):
        """Update context size"""
        self.context_size = new_size
        self._trim_context()
        self.save_context()