import threading
import time
import base64
import io
import os
import tkinter.messagebox
from datetime import datetime

import customtkinter as ctk
import mss
from PIL import Image
from openai import OpenAI

# Configuration
# Default OpenRouter/Gemini Model
# We use Gemini 2.0 Flash because it is extremely fast and cheap for continuous vision tasks.
MODEL_NAME = "google/gemini-2.0-flash-001"

class FocusApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("FocusGuard (Powered by Gemini)")
        self.geometry("500x650")
        ctk.set_appearance_mode("dark")

        # State variables
        self.is_running = False
        self.monitor_thread = None
        self.client = None
        self.distraction_criteria = ""
        self.start_time = None
        self.duration_minutes = 0

        self.setup_ui()

    def setup_ui(self):
        # Title
        self.label_title = ctk.CTkLabel(self, text="FocusGuard AI", font=("Roboto", 24, "bold"))
        self.label_title.pack(pady=15)

        self.label_subtitle = ctk.CTkLabel(self, text="via OpenRouter & Gemini", font=("Roboto", 12), text_color="gray")
        self.label_subtitle.pack(pady=(0, 15))

        # API Key Input
        self.api_frame = ctk.CTkFrame(self)
        self.api_frame.pack(pady=5, padx=20, fill="x")

        self.label_api = ctk.CTkLabel(self.api_frame, text="OpenRouter API Key:")
        self.label_api.pack(anchor="w", padx=10, pady=(10,0))

        self.entry_api = ctk.CTkEntry(self.api_frame, placeholder_text="sk-or-...")
        # Check env var for convenience
        if os.getenv("OPENROUTER_API_KEY"):
            self.entry_api.insert(0, os.getenv("OPENROUTER_API_KEY"))
        self.entry_api.pack(fill="x", padx=10, pady=(5, 10))

        # Goal Input
        self.label_goal = ctk.CTkLabel(self, text="What is your focus goal?")
        self.label_goal.pack(pady=(10, 0))
        self.entry_goal = ctk.CTkEntry(self, placeholder_text="e.g. Completing the quarterly financial report")
        self.entry_goal.pack(pady=5, padx=20, fill="x")

        # Duration Input
        self.label_time = ctk.CTkLabel(self, text="Duration (minutes):")
        self.label_time.pack(pady=(10, 0))
        self.entry_time = ctk.CTkEntry(self, placeholder_text="25")
        self.entry_time.pack(pady=5, padx=20, fill="x")

        # Start/Stop Button
        self.btn_start = ctk.CTkButton(self, text="Start Focus Session", command=self.toggle_session, fg_color="#1a73e8") # Gemini Blue
        self.btn_start.pack(pady=20)

        # Status / Logs
        self.textbox_log = ctk.CTkTextbox(self, height=200)
        self.textbox_log.pack(pady=10, padx=20, fill="both", expand=True)
        self.textbox_log.insert("0.0", "Ready. Please enter your key and goal.\n")

    def log(self, message):
        """Thread-safe logging"""
        self.after(0, lambda: self._update_log(message))

    def _update_log(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.textbox_log.insert("end", f"[{timestamp}] {message}\n")
        self.textbox_log.see("end")

    def toggle_session(self):
        if self.is_running:
            self.stop_session()
        else:
            self.start_session()

    def start_session(self):
        api_key = self.entry_api.get().strip()
        goal = self.entry_goal.get().strip()
        duration = self.entry_time.get().strip()

        if not api_key or not goal or not duration:
            tkinter.messagebox.showerror("Error", "Please fill in all fields.")
            return

        try:
            self.duration_minutes = int(duration)
        except ValueError:
            tkinter.messagebox.showerror("Error", "Duration must be a number.")
            return

        # Initialize OpenAI Client pointed at OpenRouter
        # OpenRouter is API-compatible with the OpenAI python library
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            # OpenRouter specific headers for rankings/stats
            default_headers={
                "HTTP-Referer": "https://github.com/FocusGuard",
                "X-Title": "FocusGuard Desktop App",
            }
        )

        self.is_running = True
        self.btn_start.configure(text="Stop Session", fg_color="#d93025") # Red
        self.entry_goal.configure(state="disabled")
        self.entry_time.configure(state="disabled")
        self.entry_api.configure(state="disabled")

        # Start the monitoring thread
        self.monitor_thread = threading.Thread(target=self.run_monitoring_loop, args=(goal,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def stop_session(self):
        self.is_running = False
        self.btn_start.configure(text="Start Focus Session", fg_color="#1a73e8")
        self.entry_goal.configure(state="normal")
        self.entry_time.configure(state="normal")
        self.entry_api.configure(state="normal")
        self.log("Session stopped.")

    def analyze_goal(self, goal):
        """Phase 1: Ask Gemini to define what is distracting."""
        self.log(f"Consulting Gemini about goal: '{goal}'...")
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
            criteria = response.choices[0].message.content
            self.log(f"Gemini identified distractions: {criteria}")
            return criteria
        except Exception as e:
            self.log(f"API Error (Goal Analysis): {e}")
            return None

    def capture_screen(self):
        """Captures screen, resizes, and encodes to base64."""
        with mss.mss() as sct:
            # Capture the primary monitor
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)

            # Convert to PIL Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

            # Resize image. Gemini Flash handles high res well, but 1024px is plenty and faster to upload.
            img.thumbnail((1024, 1024))

            # Save to buffer
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=80)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def check_for_distraction(self, base64_image, goal, criteria):
        """Phase 2: Send screen to Gemini Vision."""
        try:
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
            self.log(f"API Error (Vision): {e}")
            return "Error"

    def run_monitoring_loop(self, goal):
        # 1. Generate criteria using Gemini (Text)
        self.distraction_criteria = self.analyze_goal(goal)
        if not self.distraction_criteria:
            self.log("Failed to generate criteria. Stopping.")
            self.after(0, self.stop_session)
            return

        start_time_epoch = time.time()
        end_time_epoch = start_time_epoch + (self.duration_minutes * 60)

        self.log(f"Session started. Monitoring every 15 seconds.")

        # 2. Monitoring Loop
        while self.is_running and time.time() < end_time_epoch:

            # Capture Screen
            try:
                b64_img = self.capture_screen()

                # Analyze with Gemini (Vision)
                result = self.check_for_distraction(b64_img, goal, self.distraction_criteria)

                # Process Result
                if result and result.upper().startswith("YES"):
                    reason = result.split(":", 1)[1].strip() if ":" in result else "Unknown distraction"
                    self.log(f"⚠️ DISTRACTION: {reason}")

                    # Alert User
                    self.after(0, lambda r=reason: tkinter.messagebox.showwarning(
                        "FocusGuard Alert",
                        f"Gemini detected a distraction!\n\nReason: {r}\n\nGoal: {goal}"
                    ))
                elif result and result.upper().startswith("NO"):
                    self.log("✅ On track.")
                else:
                    self.log(f"❓ Ambiguous result: {result}")

            except Exception as e:
                self.log(f"Loop Error: {e}")

            # Wait 15 seconds to save tokens/cost
            # Check is_running periodically during sleep to allow instant stop
            for _ in range(15):
                if not self.is_running: break
                time.sleep(1)

        if self.is_running:
            self.log("Time is up! Great work.")
            self.after(0, lambda: tkinter.messagebox.showinfo("Finished", "Focus session complete!"))
            self.after(0, self.stop_session)

if __name__ == "__main__":
    app = FocusApp()
    app.mainloop()