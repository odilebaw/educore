# EduCore - Gemini AI Client

from google import genai
from google.genai import types
import os
import json
from PIL import Image
import io


class GeminiClient:
    def __init__(self):
        self.keys = [
            os.getenv("GEMINI_API_KEY_1"),
            os.getenv("GEMINI_API_KEY_2"),
            os.getenv("GEMINI_API_KEY_3"),
            os.getenv("GEMINI_API_KEY_4"),
        ]
        self.current_key_index = 0
        self.model_name = "gemini-2.5-flash-lite"

    def _get_client(self):
        key = self.keys[self.current_key_index]
        return genai.Client(api_key=key)

    def generate(self, prompt, image=None):
        """Oddiy matn generatsiyasi yoki rasm bilan generatsiya."""
        for i in range(len(self.keys)):
            try:
                client = self._get_client()
                if image:
                    response = client.models.generate_content(
                        model=self.model_name,
                        contents=[prompt, image]
                    )
                else:
                    response = client.models.generate_content(
                        model=self.model_name,
                        contents=prompt
                    )
                return response.text
            except Exception:
                self.current_key_index = (self.current_key_index + 1) % len(self.keys)
        raise Exception("Barcha Gemini API kalitlari ishlamayapti")

    def generate_with_image(self, prompt, image_data):
        """Rasm bilan generatsiya."""
        if isinstance(image_data, bytes):
            image = Image.open(io.BytesIO(image_data))
        else:
            image = image_data
        return self.generate(prompt, image=image)

    def generate_test(self, topic, level, num_questions):
        """Test yaratish funksiyasi."""
        prompt = f"""
    Ingliz tili o'quvchilari uchun test yarating.
    
    Mavzu: {topic}
    Daraja: {level}
    Savol soni: {num_questions}
    
    FAQAT JSON formatda javob bering, boshqa hech narsa yozmang:
    {{
        "questions": [
            {{
                "question": "Savol matni",
                "options": {{
                    "A": "Variant A",
                    "B": "Variant B", 
                    "C": "Variant C",
                    "D": "Variant D"
                }},
                "correct": "A",
                "explanation": "Nima uchun A to'g'ri"
            }}
        ]
    }}
    """
        max_attempts = 3
        last_error = None

        for attempt in range(max_attempts):
            try:
                response_text = self.generate(prompt)
                cleaned = response_text.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

                result = json.loads(cleaned)
                return result
            except json.JSONDecodeError as e:
                last_error = e
                continue

        raise Exception(f"JSON parse xatosi (3 marta urinildi): {last_error}")

    def check_homework(self, homework_description, image_data):
        """Homework tekshirish funksiyasi."""
        prompt = f"""
    Sen mehribon va sabr-toqatli ingliz tili o'qituvchisisan.
    
    O'quvchi quyidagi vazifani bajargan: "{homework_description}"
    
    Rasmda o'quvchining qo'lyozmasi bor. Uni tahlil qilib:
    
    1. Avval o'quvchini rag'batlantir (1-2 gap)
    2. Xatolarini tushuntirib, to'g'ri variantini ko'rsat
    3. Oxirida foizda baho ber: "Siz vazifani X% samaradorlik bilan bajaribsiz"
    
    Javobni O'ZBEK TILIDA ber. Mehribon va ijobiy uslubda yoz.
    """
        return self.generate_with_image(prompt, image_data)
