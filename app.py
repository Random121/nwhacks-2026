import threading
import time
import os
import tkinter.messagebox
from datetime import datetime
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from dotenv import load_dotenv
import pygame

from api.detection import FocusDetector
from api.webcam import EyeTracker
from api.slapper import Slapper

load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")
SERIAL_PORT = os.getenv("SERIAL_PORT")
SERIAL_BAUD = os.getenv("SERIAL_BAUD")

# Configuration
SOUND_FILE = "alert.mp3"

class FocusApp(ctk.CTk):
    slapper: Slapper

    def __init__(self):
        super().__init__()

        self.title("FocusGuard (Omni-monitoring)")
        self.geometry("500x600")
        ctk.set_appearance_mode("dark")

        # Logic Components
        self.detector = None
        self.eye_tracker = None

        # State
        self.is_running = False
        self.monitor_thread = None
        self.alert_showing = False
        self.last_alert_time = 0  # <--- NEW: Cooldown timer
        self.distraction_criteria = ""
        self.duration_minutes = 0

        # Audio Init
        try:
            pygame.mixer.init()
        except Exception as e:
            print(f"Audio init failed: {e}")

        try:
            self.slapper = Slapper(SERIAL_PORT, SERIAL_BAUD)
        except Exception:
            self.slapper = None

        self.setup_ui()

    def setup_ui(self):
        self.label_title = ctk.CTkLabel(self, text="FocusGuard AI", font=("Roboto", 24, "bold"))
        self.label_title.pack(pady=15)

        self.label_subtitle = ctk.CTkLabel(self, text="Eyes on the prize.", font=("Roboto", 12), text_color="gray")
        self.label_subtitle.pack(pady=(0, 15))

        self.entry_goal = ctk.CTkEntry(self, placeholder_text="e.g. Studying Algorithms")
        self.entry_goal.pack(pady=5, padx=20, fill="x")

        self.entry_time = ctk.CTkEntry(self, placeholder_text="Duration (min): 25")
        self.entry_time.pack(pady=5, padx=20, fill="x")

        self.btn_start = ctk.CTkButton(self, text="Start Session", command=self.toggle_session, fg_color="#1a73e8")
        self.btn_start.pack(pady=20)

        self.textbox_log = ctk.CTkTextbox(self, height=200)
        self.textbox_log.pack(pady=10, padx=20, fill="both", expand=True)
        self.textbox_log.insert("0.0", "Ready.\n")

    def log(self, message):
        self.after(0, lambda: self._update_log(message))

    def _update_log(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.textbox_log.insert("end", f"[{timestamp}] {message}\n")
        self.textbox_log.see("end")

    def play_sound(self):
        if os.path.exists(SOUND_FILE):
            try:
                pygame.mixer.music.load(SOUND_FILE)
                pygame.mixer.music.play()
            except Exception as e:
                print(f"Sound error: {e}")

    def toggle_session(self):
        if self.is_running:
            self.stop_session()
        else:
            self.start_session()

    def start_session(self):
        goal = self.entry_goal.get().strip()
        duration = self.entry_time.get().strip()

        if not goal or not duration:
            alert = CTkMessagebox(title="Error",
                                  message="Please fill in your goal and duration.",
                                  icon="cancel")
            alert.get()
            return

        if not API_KEY:
            alert = CTkMessagebox(title="Error",
                        message="API Key not found!",
                        icon="cancel")
            alert.get()
            return

        try:
            self.duration_minutes = int(duration)
        except ValueError:
            alert = CTkMessagebox(title="Error",
                                  message="Please enter a duration in minutes",
                                  icon="cancel")
            alert.get()
            return

        if self.duration_minutes <= 0:
            alert = CTkMessagebox(title="Error",
                                  message="You should focus for at least 1 minute!",
                                  icon="cancel")
            alert.get()
            return

        self.detector = FocusDetector(API_KEY)
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

    def stop_session(self):
        self.is_running = False
        if self.eye_tracker:
            self.eye_tracker.stop()

        self.btn_start.configure(text="Start Session", fg_color="#1a73e8")
        self.entry_goal.configure(state="normal")
        self.entry_time.configure(state="normal")
        self.log("Session stopped.")

    def show_alert(self, reason):
        """Shows alert, waits for user to close, then sets cooldown."""
        self.play_sound()

        if self.slapper is not None:
            self.slapper.slap_user()

        alert = CTkMessagebox(title="Stop getting distracted!",
                              message=reason,
                              option_1="I'm locking in for real now",
                              icon="warning",
                              topmost=True)
        alert.get()

        self.alert_showing = False

        # ✅ FIX: Give the user 5 seconds of peace to click "Stop" or get back to work
        self.last_alert_time = time.time()
        self.log("⏸️ Alert closed. Resuming in 5 seconds...")

    def show_session_end_alert(self):
        alert = CTkMessagebox(title="Good job!",
                              message="Great focus session!",
                              topmost=True)
        alert.get()

    def run_monitoring_loop(self, goal):
        self.log(f"Setting up for: '{goal}'...")
        self.distraction_criteria = self.detector.analyze_goal_criteria(goal)
        self.log(f"Policy: {self.distraction_criteria}")

        end_time = time.time() + (self.duration_minutes * 60)

        while self.is_running and time.time() < end_time:

            # --- COOLDOWN CHECK ---
            # If we just showed an alert, skip checking for 5 seconds
            if time.time() - self.last_alert_time < 5:
                time.sleep(1)
                continue

            # 1. Check Screen (Low Frequency)
            self.log("Scanning screen...")
            screen_result = self.detector.check_current_screen(goal, self.distraction_criteria)

            if screen_result and screen_result.upper().startswith("YES"):
                 reason = screen_result.split(":", 1)[1].strip() if ":" in screen_result else "Screen Content"
                 self.log(f"⚠️ SCREEN DISTRACTION: {reason}")
                 if not self.alert_showing:
                     self.alert_showing = True
                     self.after(0, lambda r=reason: self.show_alert(r))
                     # Sleep to prevent multiple triggers while waiting for UI thread
                     time.sleep(2)
                     continue

            # 2. Check Eyes (High Frequency Loop)
            # Run for ~10 seconds before checking screen again
            for _ in range(100):
                if not self.is_running: break

                # Double check cooldown inside the fast loop
                if time.time() - self.last_alert_time < 5:
                    break

                if self.eye_tracker.is_distracted:
                    reason = self.eye_tracker.distraction_reason
                    self.log(f"👀 EYE DISTRACTION: {reason}")

                    if not self.alert_showing:
                        self.alert_showing = True
                        self.after(0, lambda r=reason: self.show_alert(r))
                        time.sleep(2) # Brief pause so we don't spam requests
                        break # Break inner loop to handle alert

                time.sleep(0.1)

        if self.is_running:
            self.log("Session complete!")
            self.after(0, self.show_session_end_alert)
            self.after(0, self.stop_session)
            tkinter.messagebox.showinfo("Done", "Session Complete!")

if __name__ == "__main__":
    app = FocusApp()
    app.mainloop()