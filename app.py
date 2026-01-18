import threading
import time
import os
import tkinter.messagebox
from datetime import datetime
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from dotenv import load_dotenv

from api.detection import FocusDetector
from api.slapper import Slapper

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
SERIAL_PORT = os.getenv("SERIAL_PORT")
SERIAL_BAUD = os.getenv("SERIAL_BAUD")

class FocusApp(ctk.CTk):
    slapper: Slapper

    def __init__(self):
        super().__init__()

        self.title("FocusGuard")
        self.geometry("500x550")
        ctk.set_appearance_mode("dark")

        # State variables
        self.is_running = False
        self.monitor_thread = None
        self.detector = None
        self.distraction_criteria = ""
        self.duration_minutes = 0

        # New flag to prevent spamming alerts
        self.alert_showing = False

        try:
            self.slapper = Slapper(SERIAL_PORT, SERIAL_BAUD)
        except Exception:
            self.slapper = None

        self.setup_ui()

    def setup_ui(self):
        self.label_title = ctk.CTkLabel(self, text="FocusGuard AI", font=("Roboto", 24, "bold"))
        self.label_title.pack(pady=15)

        self.label_subtitle = ctk.CTkLabel(self, text="Stay locked in.", font=("Roboto", 12), text_color="gray")
        self.label_subtitle.pack(pady=(0, 15))

        self.label_goal = ctk.CTkLabel(self, text="What is your focus goal?")
        self.label_goal.pack(pady=(10, 0))
        self.entry_goal = ctk.CTkEntry(self, placeholder_text="e.g. Studying Algorithms")
        self.entry_goal.pack(pady=5, padx=20, fill="x")

        self.label_time = ctk.CTkLabel(self, text="Duration (minutes):")
        self.label_time.pack(pady=(10, 0))
        self.entry_time = ctk.CTkEntry(self, placeholder_text="25")
        self.entry_time.pack(pady=5, padx=20, fill="x")

        self.btn_start = ctk.CTkButton(self, text="Start Focus Session", command=self.toggle_session, fg_color="#1a73e8")
        self.btn_start.pack(pady=20)

        self.textbox_log = ctk.CTkTextbox(self, height=200)
        self.textbox_log.pack(pady=10, padx=20, fill="both", expand=True)
        self.textbox_log.insert("0.0", "Ready. Enter your goal to begin.\n")

    def log(self, message):
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
        self.is_running = True
        self.alert_showing = False  # Reset on start

        self.btn_start.configure(text="Stop Session", fg_color="#d93025")
        self.entry_goal.configure(state="disabled")
        self.entry_time.configure(state="disabled")

        self.monitor_thread = threading.Thread(target=self.run_monitoring_loop, args=(goal,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def stop_session(self):
        self.is_running = False
        self.btn_start.configure(text="Start Focus Session", fg_color="#1a73e8")
        self.entry_goal.configure(state="normal")
        self.entry_time.configure(state="normal")
        self.log("Session stopped.")

    def show_alert(self, reason):
        """Display distraction alert to user."""
        if self.slapper is not None:
            self.slapper.slap_user()

        alert = CTkMessagebox(title="Stop getting distracted!",
                              message=reason,
                              option_1="I'm locking in for real now",
                              icon="warning",
                              topmost=True)
        alert.get()

        self.alert_showing = False

    def show_session_end_alert(self):
        alert = CTkMessagebox(title="Good job!",
                              message="Great focus session!",
                              topmost=True)
        alert.get()

    def run_monitoring_loop(self, goal):
        self.log(f"Analyzing goal: '{goal}'...")

        self.distraction_criteria = self.detector.analyze_goal_criteria(goal)

        if not self.distraction_criteria:
            self.log("Failed to connect to AI. Check .env file.")
            self.after(0, self.stop_session)
            return

        self.log(f"Avoid: {self.distraction_criteria}")

        start_time_epoch = time.time()
        end_time_epoch = start_time_epoch + (self.duration_minutes * 60)

        while self.is_running and time.time() < end_time_epoch:

            result = self.detector.check_current_screen(goal, self.distraction_criteria)

            if result and result.upper().startswith("YES"):
                reason = result.split(":", 1)[1].strip() if ":" in result else "Distraction"

                # Always log it
                self.log(f"⚠️ DISTRACTION: {reason}")

                # Only show alert if one isn't already open
                if not self.alert_showing:
                    self.alert_showing = True
                    self.after(0, lambda r=reason: self.show_alert(r))
                else:
                    print("Alert skipped (already showing)")

            elif result and result.upper().startswith("NO"):
                self.log("✅ Focused.")
                # If they are focused now, ensure we are ready to alert next time
                self.alert_showing = False
            else:
                self.log(f"❓ Analyzing...")

            # Sleep Loop
            for _ in range(15):
                if not self.is_running: break
                time.sleep(1)

        if self.is_running:
            self.log("Session complete!")
            self.after(0, self.show_session_end_alert)
            self.after(0, self.stop_session)

if __name__ == "__main__":
    app = FocusApp()
    app.mainloop()