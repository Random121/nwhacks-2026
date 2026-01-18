import base64
import io
import mss
from PIL import Image
from openai import OpenAI

# Configuration
MODEL_NAME = "google/gemini-2.0-flash-001"

class FocusDetector:
    def __init__(self, api_key):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/Random121/nwhacks-2026",
                "X-Title": "FocusGuard Desktop App",
            }
        )

    def analyze_goal_criteria(self, goal):
        """
        Phase 1: Ask AI to define the 'Rules of Engagement'.
        We now ask it to distinguish between helper content vs. distractions.
        """
        try:
            prompt = (
                f"The user wants to focus on this goal: '{goal}'. "
                "Define a concise 'Distraction Policy' for this session. "
                "IMPORTANT: Distinguish between productive usage vs. distraction on the same platform. "
                "Example: If the goal is 'coding', specify that 'YouTube (Tutorials/Docs)' are ALLOWED, "
                "but 'YouTube (Entertainment/Music)' are DISTRACTIONS. "
                "Return a short paragraph listing what is allowed and what is banned."
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
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            img.thumbnail((1024, 1024))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=80)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def check_current_screen(self, goal, criteria):
        """
        Phase 2: Analyze screen with strict context awareness.
        """
        try:
            base64_image = self._capture_screen_base64()

            prompt = (
                f"You are a strict but fair productivity guard. "
                f"User Goal: '{goal}'. "
                f"Policy: {criteria}. "
                "Analyze this screenshot. "
                "CRITICAL INSTRUCTION: Context matters. "
                "- If the user is on a site like YouTube, Reddit, or Twitter, READ the specific content (video title, post text). "
                "- If the content directly supports the goal (e.g. a tutorial video, a documentation thread), say 'NO'. "
                "- If the content is unrelated entertainment (e.g. music, memes, gaming), say 'YES'. "
                "- If the screen is blank or code editor, say 'NO'. "
                "Response format: 'YES: [Specific Reason]' or 'NO'."
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