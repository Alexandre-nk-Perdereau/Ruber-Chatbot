import io
import logging
import base64
import PIL.Image

logger = logging.getLogger(__name__)

class MessageAttachment:
    """Handles different types of attachments for messages"""
    
    def __init__(self):
        self.SUPPORTED_MIME_TYPES = {
            'image': ['image/png', 'image/jpeg', 'image/heic', 'image/heif', 'image/webp'],
            'audio': ['audio/wav', 'audio/mp3', 'audio/mpeg', 'audio/aiff', 'audio/aac', 'audio/ogg', 'audio/flac'],
            'text': ['text/plain', 'application/json', 'text/markdown', 'application/pdf', 
                    'application/x-javascript', 'text/javascript', 'application/x-python',
                    'text/x-python', 'text/html', 'text/css', 'text/csv', 'text/xml', 'text/rtf'],
            'video': ['video/mp4', 'video/mpeg', 'video/mov', 'video/avi', 'video/x-flv',
                     'video/mpg', 'video/webm', 'video/wmv', 'video/3gpp']
        }
        self.MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
    
    async def process_attachment(self, attachment):
        """
        Process a Discord attachment and return it in the correct format for the Gemini API
        Returns:
            - Processed attachment data
            - Error message (if any)
        """
        try:
            if attachment.size >= self.MAX_FILE_SIZE:
                return None, "File exceeds 20MB limit"
            
            file_data = await attachment.read()
            content_type = attachment.content_type

            base_content_type = content_type.split(';')[0].strip()
            
            supported = False
            expected_types = []
            
            for category, types in self.SUPPORTED_MIME_TYPES.items():
                expected_types.extend(types)
                if base_content_type in types:
                    supported = True
                    if category == 'image':
                        return await self._process_image(file_data, content_type)
                    elif category == 'audio':
                        return await self._process_audio(file_data, content_type)
                    elif category == 'text':
                        return await self._process_text(file_data, base_content_type)
                    elif category == 'video':
                        return await self._process_video(file_data, content_type)
            
            if not supported:
                return None, f"Unsupported file type: {content_type}. Supported types are: {', '.join(expected_types)}"
            
            return None, "Unhandled content type"
            
        except Exception as e:
            logger.error(f"Error processing attachment: {str(e)}")
            return None, f"Error processing attachment: {str(e)}"

    async def _process_image(self, file_data, content_type):
        """Process image attachments"""
        try:
            with PIL.Image.open(io.BytesIO(file_data)) as img:
                with io.BytesIO() as output:
                    img.save(output, format="PNG")
                    processed_data = output.getvalue()
                    return {
                        "mime_type": "image/png",
                        "data": base64.b64encode(processed_data).decode('utf-8')
                    }, None
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return None, f"Error processing image: {str(e)}"

    async def _process_audio(self, file_data, content_type):
        """Process audio attachments"""
        return {
            "mime_type": content_type,
            "data": base64.b64encode(file_data).decode('utf-8')
        }, None

    async def _process_text(self, file_data, content_type):
        """Process text attachments"""
        if content_type == 'application/pdf':
            return {
                "mime_type": content_type,
                "data": base64.b64encode(file_data).decode('utf-8')
            }, None
        else:
            try:
                try:
                    text_content = file_data.decode('utf-8')
                except UnicodeDecodeError:
                    text_content = file_data.decode('utf-8-sig')
                return {"text": text_content}, None
            except Exception as e:
                logger.error(f"Error processing text file: {str(e)}")
                return None, "Error: File must be UTF-8 encoded"

    async def _process_video(self, file_data, content_type):
        """Process video attachments"""
        return {
            "mime_type": content_type,
            "data": base64.b64encode(file_data).decode('utf-8')
        }, None