# ocr_space_client.py
import requests
import base64
import os
from typing import Optional

class OCRSpaceClient:
    """
    Клиент для OCR.space API.
    Документация: https://ocr.space/ocrapi
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.ocr.space/parse/image"
    
    def from_file(self, file_path: str, language: str = "rus") -> Optional[str]:
        """
        Распознаёт текст с файла на диске.
        
        Args:
            file_path: путь к изображению (JPG, PNG, BMP, GIF, PDF)
            language: код языка (rus, eng, и т.д.)
            
        Returns:
            Распознанный текст или None при ошибке
        """
        if not os.path.exists(file_path):
            print(f"[OCR] Файл не найден: {file_path}")
            return None
        
        try:
            with open(file_path, 'rb') as f:
                response = requests.post(
                    self.base_url,
                    headers={'apikey': self.api_key},
                    files={'file': f},
                    data={'language': language, 'isOverlayRequired': False}
                )
            
            result = response.json()
            
            if result.get('IsErroredOnProcessing'):
                error_msg = result.get('ErrorMessage', ['Unknown error'])[0]
                print(f"[OCR] Ошибка: {error_msg}")
                return None
            
            parsed_text = result['ParsedResults'][0]['ParsedText']
            return parsed_text.strip()
            
        except Exception as e:
            print(f"[OCR] Исключение: {e}")
            return None
    
    def from_url(self, image_url: str, language: str = "rus") -> Optional[str]:
        """
        Распознаёт текст с изображения по URL.
        """
        try:
            response = requests.post(
                self.base_url,
                headers={'apikey': self.api_key},
                data={
                    'url': image_url,
                    'language': language,
                    'isOverlayRequired': False
                }
            )
            
            result = response.json()
            
            if result.get('IsErroredOnProcessing'):
                return None
            
            return result['ParsedResults'][0]['ParsedText'].strip()
            
        except Exception as e:
            print(f"[OCR] Ошибка: {e}")
            return None


# Пример использования
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    API_KEY = os.getenv("OCR_SPACE_API_KEY")
    
    if not API_KEY:
        print("❌ Укажи OCR_SPACE_API_KEY в .env файле")
        exit()
    
    client = OCRSpaceClient(API_KEY)
    
    # Распознаём фото
    text = client.from_file("photo_prava.jpg")
    
    if text:
        print("=== РАСПОЗНАННЫЙ ТЕКСТ ===")
        print(text)
    else:
        print("Не удалось распознать текст")