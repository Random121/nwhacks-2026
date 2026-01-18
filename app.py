import threading
import time
import os
import tkinter.messagebox
from datetime import datetime
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from dotenv import load_dotenv
from PIL import Image

from api.detection import FocusDetector
from api.webcam import EyeTracker
from api.slapper import Slapper
from api.audio import VoiceAudio

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
SERIAL_PORT = os.getenv("SERIAL_PORT")
SERIAL_BAUD = os.getenv("SERIAL_BAUD")
AI_STUDIO_API_KEY = os.getenv("AI_STUDIO_API_KEY")
OPENROUTER_API_KEY = AI_STUDIO_API_KEY
ELEVENLABS_VOICE_ID = "KLZOWyG48RjZkAAjuM89"

class FocusApp(ctk.CTk):
    slapper: Slapper
    voice: VoiceAudio

    def __init__(self):
        super().__init__()

        self.title("Get Back to Work")
        self.geometry("600x750")
        ctk.set_appearance_mode("dark")
        self.center_window()

        self.detector = None
        self.eye_tracker = None
        self.is_running = False
        self.alert_showing = False
        self.last_alert_time = 0
        self.distraction_criteria = ""
        self.duration_minutes = 0

        try:
            self.slapper = Slapper(SERIAL_PORT, SERIAL_BAUD)
        except Exception:
            self.slapper = None

        self.voice = VoiceAudio(key=ELEVENLABS_API_KEY)
        self.setup_ui()

    def center_window(self):
        self.update_idletasks()
        width = 600
        height = 750
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def setup_ui(self):
        self.label_title = ctk.CTkLabel(self, text="Get Back to Work", font=("Roboto", 24, "bold"))
        self.label_title.pack(pady=(15, 5))

        self.label_subtitle = ctk.CTkLabel(self, text="Eyes on your goal.", font=("Roboto", 12), text_color="gray")
        self.label_subtitle.pack(pady=(0, 10))

        # Camera Feed
        self.camera_frame = ctk.CTkFrame(self, width=320, height=240, fg_color="black")
        self.camera_frame.pack(pady=10)
        self.camera_label = ctk.CTkLabel(self.camera_frame, text="Camera Off", width=320, height=240)
        self.camera_label.pack()

        self.entry_goal = ctk.CTkEntry(self, placeholder_text="e.g. Studying Algorithms")
        self.entry_goal.pack(pady=5, padx=20, fill="x")

        self.entry_time = ctk.CTkEntry(self, placeholder_text="Duration (min): 25")
        self.entry_time.pack(pady=5, padx=20, fill="x")

        self.btn_start = ctk.CTkButton(self, text="Start Session", command=self.toggle_session, fg_color="#1a73e8")
        self.btn_start.pack(pady=10)

        self.textbox_log = ctk.CTkTextbox(self, height=150)
        self.textbox_log.pack(pady=10, padx=20, fill="both", expand=True)
        self.textbox_log.insert("0.0", "Ready.\n")

    def log(self, message):
        self.after(0, lambda: self._update_log(message))

    def _update_log(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.textbox_log.insert("end", f"[{timestamp}] {message}\n")
        self.textbox_log.see("end")

    def play_sound(self, reason):
        self.voice.play(ELEVENLABS_VOICE_ID, "Stop getting distracted! Apologize and get back to work!")

    def toggle_session(self):
        if self.is_running:
            self.stop_session()
        else:
            self.start_session()

    def start_session(self):
        goal = self.entry_goal.get().strip()
        duration = self.entry_time.get().strip()

        if not goal or not duration or not OPENROUTER_API_KEY:
            CTkMessagebox(title="Error", message="Missing inputs or API Key", icon="cancel")
            return

        try:
            self.duration_minutes = int(duration)
        except ValueError:
            return

        self.detector = FocusDetector(OPENROUTER_API_KEY)
        self.eye_tracker = EyeTracker()
        self.eye_tracker.start()

        self.is_running = True
        self.alert_showing = False
        self.last_alert_time = 0

        self.btn_start.configure(text="Stop Session", fg_color="#d93025")
        self.entry_goal.configure(state="disabled")
        self.entry_time.configure(state="disabled")

        self.monitor_thread = threading.Thread(target=self.run_monitoring_loop, args=(goal,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

        self.update_camera_feed()

    def update_camera_feed(self):
        if not self.is_running:
            self.camera_label.configure(image=None, text="Camera Off")
            return

        if self.eye_tracker:
            frame = self.eye_tracker.get_frame()
            if frame is not None:
                pil_img = Image.fromarray(frame)
                pil_img = pil_img.resize((320, 240))
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(320, 240))
                self.camera_label.configure(image=ctk_img, text="")
            else:
                self.camera_label.configure(text="Camera Paused/Loading...")

        self.after(30, self.update_camera_feed)

    def stop_session(self):
        self.is_running = False
        if self.eye_tracker:
            self.eye_tracker.stop()

        self.btn_start.configure(text="Start Session", fg_color="#1a73e8")
        self.entry_goal.configure(state="normal")
        self.entry_time.configure(state="normal")
        self.log("Session stopped.")

    def show_alert(self, reason):
        # 1. PAUSE CAMERA (Fixes audio interference)
        self.log("Pausing Camera for Audio...")
        if self.eye_tracker:
            self.eye_tracker.set_paused(True)

        # 2. SHOW ALERT VISUALLY
        alert = CTkMessagebox(title="Stop getting distracted!",
                            message=reason,
                            option_1="I'll apologize and lock in",
                            icon="warning",
                            topmost=True)

        # 3. PLAY SOUND (Delayed slightly so popup renders first)
        alert.after(500, lambda: self.play_sound(reason))

        if self.slapper: self.slapper.slap_user()

        # 4. WAIT FOR USER ACKNOWLEDGE
        alert.get()

        # 5. APOLOGY LOOP
        while True:
            if not self.is_running: break

            # This blocks for ~5 seconds
            did_apologize = self.voice.listen_for_apology()
            print("Apology result:", did_apologize)

            if did_apologize:
                break

            if self.slapper: self.slapper.slap_user()

            retry = CTkMessagebox(title="You must apologize!",
                    message="I didn't hear an apology. Say 'Sorry' or 'My Bad'.",
                    option_1="Try Again",
                    icon="warning",
                    topmost=True)
            retry.get()

        # 6. RESUME CAMERA
        self.log("Resuming Camera...")
        if self.eye_tracker:
            self.eye_tracker.set_paused(False)

        self.alert_showing = False
        self.last_alert_time = time.time()

    def show_session_end_alert(self):
        CTkMessagebox(title="Good job!", message="Great focus session!", topmost=True)

    def run_monitoring_loop(self, goal):
        self.log(f"Setting up for: '{goal}'...")
        self.distraction_criteria = self.detector.analyze_goal_criteria(goal)
        self.log(f"Policy: {self.distraction_criteria}")

        end_time = time.time() + (self.duration_minutes * 60)

        while self.is_running and time.time() < end_time:
            if time.time() - self.last_alert_time < 5:
                time.sleep(1)
                continue

            # 1. Screen Check
            self.log("Scanning screen...")
            screen_result = self.detector.check_current_screen(goal, self.distraction_criteria)

            if screen_result and screen_result.upper().startswith("YES"):
                 reason = screen_result.split(":", 1)[1].strip() if ":" in screen_result else "Screen Content"
                 self.log(f"SCREEN: {reason}")
                 if not self.alert_showing:
                     self.alert_showing = True
                     # Use 'after' to run show_alert on Main Thread to prevent crashes
                     self.after(0, lambda r=reason: self.show_alert(r))
                     time.sleep(5) # Wait for alert to resolve
                     continue

            # 2. Eye Check
            for _ in range(50):
                if not self.is_running: break
                if time.time() - self.last_alert_time < 5: break

                if self.eye_tracker.is_distracted and not self.eye_tracker.paused:
                    reason = self.eye_tracker.distraction_reason
                    self.log(f"EYES: {reason}")
                    if not self.alert_showing:
                        self.alert_showing = True
                        self.after(0, lambda r=reason: self.show_alert(r))
                        time.sleep(5)
                        break
                time.sleep(0.1)

        if self.is_running:
            self.log("Session complete!")
            self.after(0, self.show_session_end_alert)
            self.after(0, self.stop_session)

if __name__ == "__main__":
    app = FocusApp()
    app.mainloop()