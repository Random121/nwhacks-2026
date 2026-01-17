import base64
import io
import mss
from PIL import Image
from openai import OpenAI

# Configuration
MODEL_NAME = "google/gemini-2.0-flash-001"

class FocusDetector:
    def __init__(self, api_key):
        """Initialize the OpenAI client with OpenRouter base URL."""
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/FocusGuard",
                "X-Title": "FocusGuard Desktop App",
            }
        )

    def analyze_goal_criteria(self, goal):
        """Phase 1: Ask AI to define specific distractions for this goal."""
        try:
            prompt = (
                f"The user wants to focus on this goal: '{goal}'. "
                "List 3-5 specific categories of screen content (websites, apps, activities) "
                "that would be counterproductive or distracting for this specific goal. "
                "Return ONLY a comma-separated list of these categories."
            )

            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error analyzing goal: {e}")
            return None

    def _capture_screen_base64(self):
        """Internal helper: Captures screen and returns base64 string."""
        with mss.mss() as sct:
            # Capture the primary monitor
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)

            # Convert to PIL Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

            # Resize to optimize for API speed/cost (1024px is plenty)
            img.thumbnail((1024, 1024))

            # Save to buffer
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=80)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def check_current_screen(self, goal, criteria):
        """Phase 2: Captures screen and sends to AI for judgement."""
        try:
            base64_image = self._capture_screen_base64()
            
            prompt = (
                f"You are a productivity focus guard. "
                f"User Goal: '{goal}'. "
                f"Activities defined as distractions: {criteria}. "
                "Analyze this screenshot of the user's desktop. "
                "Determine if the user is currently distracted by irrelevant content. "
                "If they are working on their goal or have a blank desktop, they are NOT distracted. "
                "Answer strictly in this format: 'YES: [Reason]' or 'NO'."
            )

            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=100
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: {e}"