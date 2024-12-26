import os
from dotenv import load_dotenv

load_dotenv(override=True)

def get_discord_bot_token():
    return os.getenv("DISCORD_BOT_TOKEN")

def get_gemini_api_key():
    return os.getenv("GEMINI_API_KEY")

def get_default_model():
    return os.getenv("DEFAULT_MODEL", "gemini-exp-1206")

def get_default_context_size():
    return int(os.getenv("DEFAULT_CONTEXT_SIZE", "2097152"))

def get_default_system_prompt():
  return (
      "Tu t'appelles Ruber et tu es un robot humanoïde inventé par PseudoRouge. "
      "Tu es capable de comprendre et de répondre aux messages des utilisateurs. "
      "Les messages des utilisateurs te sont transmis avec le nom d'utilisateur affiché en premier, suivi de deux points, puis du contenu du message. Par exemple: 'Utilisateur A: Bonjour !'. "
      "Tu n'es pas censé imiter ce format, répond de la manière la plus naturelle possible."
  )