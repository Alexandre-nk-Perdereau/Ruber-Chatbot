import google.generativeai as genai
from utils.config import get_gemini_api_key, get_default_model
import logging
from google.api_core import exceptions as core_exceptions
import time

logger = logging.getLogger(__name__)

def setup_gemini_api():
    genai.configure(api_key=get_gemini_api_key())

def generate_response(messages, model_name=None, system_prompt=None, max_retries=3):
    setup_gemini_api()
    model = genai.GenerativeModel(model_name or get_default_model())
    for attempt in range(max_retries):
        try:
            logger.info(f"Messages envoyés à l'API : {messages}")
            if system_prompt:
                final_messages = [{"role": "user", "parts": [system_prompt]}] + [msg for msg in messages if msg["role"] in ("user", "model")]
            else:
                final_messages = [msg for msg in messages if msg["role"] in ("user", "model")]

            if all(isinstance(part, str) for msg in final_messages for part in msg["parts"]):
                # Cas texte seul : On envoie une liste simple de strings
                text_parts = [part for msg in final_messages for part in msg["parts"]]
                response = model.generate_content(text_parts, stream=True)
            else:
                # Cas multimodal : On envoie la structure de messages actuelle
                response = model.generate_content(final_messages, stream=True)

            return response
        except core_exceptions.InternalServerError as e:
            if attempt < max_retries - 1:
                wait_time = 5
                logger.warning(f"Erreur 500 détectée (tentative {attempt + 1}/{max_retries}). Nouvelle tentative dans {wait_time} secondes... Détails de l'erreur : {e}")
                time.sleep(wait_time)
            else:
                logger.error(f"Erreur 500 après {max_retries} tentatives. Abandon. Détails de l'erreur : {e}")
                raise
        except Exception as e:
            logger.error(f"Erreur lors de l'appel à l'API Gemini: {e}")
            raise

def count_tokens(text, model_name=None):
    setup_gemini_api()
    model = genai.GenerativeModel(model_name or get_default_model())
    return model.count_tokens(text).total_tokens

def handle_api_error(error):
    if isinstance(error, core_exceptions.GoogleAPIError):
        if error.code == 400:
            return "Erreur de requête. Veuillez vérifier le format des messages envoyés."
        elif error.code == 500:
            return f"Erreur interne du serveur Gemini. Veuillez réessayer plus tard. Détails de l'erreur : {error}"
        else:
            return f"Erreur de l'API Gemini: {error.message}"
    else:
        return "Une erreur inconnue s'est produite."

def generate_images(prompt, aspect_ratio="1:1", negative_prompt=None):
    setup_gemini_api()
    imagen = genai.ImageGenerationModel("image-3-generate-001")

    result = imagen.generate_images(
        prompt=prompt,
        number_of_images=2,
        aspect_ratio=aspect_ratio,
        negative_prompt=negative_prompt
    )
    return result


def list_models():
    setup_gemini_api()
    return list(genai.list_models())