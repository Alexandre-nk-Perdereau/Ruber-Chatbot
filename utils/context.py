import base64
import os
import json
from utils.gemini import count_tokens
from utils.config import get_default_context_size, get_default_system_prompt, get_default_model

class ChannelContext:
    def __init__(self, channel_id, system_prompt=None, context_size=None, model_name=None):
        self.channel_id = channel_id
        self.system_prompt = system_prompt or get_default_system_prompt()
        self.context_size = context_size or get_default_context_size()
        self.model_name = model_name or get_default_model()
        self.context_file = os.path.join("contexts", f"{channel_id}.json")
        self.messages = self.load_context()

    def _ensure_contexts_directory_exists(self):
        contexts_dir = os.path.dirname(self.context_file)
        os.makedirs(contexts_dir, exist_ok=True)

    def load_context(self):
        self._ensure_contexts_directory_exists()
        try:
            with open(self.context_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                data[0] = {"role": "system", "parts": [self.system_prompt]}
                return data
        except FileNotFoundError:
            return [{"role": "system", "parts": [self.system_prompt]}]

    def save_context(self):
        with open(self.context_file, "w", encoding="utf-8") as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=4)

    def add_message(self, role, content):
        if isinstance(content, list):
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
        elif isinstance(content, str):
            content = [content]
        else:
            content = [content]
        message = {"role": role, "parts": content}
        self.messages.append(message)
        self.trim_context()
        self.save_context()
    
    def get_context(self):
        decoded_messages = []
        for msg in self.messages:
            if msg["role"] in ("user", "model"):
                decoded_parts = []
                for part in msg["parts"]:
                    if isinstance(part, dict) and "data" in part:
                        if part["mime_type"] == "text/plain":
                            decoded_parts.append(part)
                        elif isinstance(part["data"], str):
                            try:
                                decoded_data = base64.b64decode(part["data"])
                                decoded_parts.append({"mime_type": part["mime_type"], "data": decoded_data})
                            except Exception as e:
                                print(f"Erreur lors du décodage base64 : {e}")
                                decoded_parts.append(part)
                        else:
                            decoded_parts.append(part)
                    elif isinstance(part, str):
                        decoded_parts.append(part)
                    else:
                        decoded_parts.append(part)
                decoded_messages.append({"role": msg["role"], "parts": decoded_parts})
            else:
                decoded_messages.append(msg)
        return decoded_messages

    def trim_context(self):
        token_count = sum(count_tokens(msg["parts"][0], self.model_name) for msg in self.messages)
        while token_count > self.context_size:
            if len(self.messages) > 1:
                removed_message = self.messages.pop(1)
                token_count -= count_tokens(removed_message["parts"][0], self.model_name)
            else:
                print("Error: The context is still too big! (Something went wrong)")
                break

    def clear_context(self):
        self.messages = [{"role": "system", "parts": [self.system_prompt]}]
        self.save_context()

    def download_context(self):
        context_str = ""
        for message in self.messages:
            role = message["role"].capitalize()
            content = message['parts'][0]
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and 'data' in item:
                        context_str += f"{role}: Fichier - {item.get('filename', 'unknown')} (Type: {item.get('mime_type', 'unknown')})\n"
                    else:
                        context_str += f"{role}: {item}\n"
            else:
                context_str += f"{role}: {content}\n"
            context_str += "\n"
        return context_str

    def set_system_prompt(self, new_system_prompt):
        self.system_prompt = new_system_prompt
        self.messages[0] = {"role": "system", "parts": [self.system_prompt]}
        self.trim_context()
        self.save_context()

    def set_context_size(self, new_context_size):
        self.context_size = new_context_size
        self.trim_context()
        self.save_context()

    def set_model(self, new_model):
        self.model_name = new_model
        self.trim_context()
        self.save_context()