import threading
import time
import os
import tkinter.messagebox
from datetime import datetime
import customtkinter as ctk
from dotenv import load_dotenv  # <--- NEW IMPORT

# Import our module
from api.detection import FocusDetector

# Load variables from .env file into os.environ
load_dotenv()  # <--- LOAD THE FILE

# ==========================================
# 🔑 CONFIGURATION
# Now this works automatically because load_dotenv found the file
# ==========================================
API_KEY = os.getenv("OPENROUTER_API_KEY")

class FocusApp(ctk.CTk):
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

        self.setup_ui()

    def setup_ui(self):
        # Title
        self.label_title = ctk.CTkLabel(self, text="FocusGuard AI", font=("Roboto", 24, "bold"))
        self.label_title.pack(pady=15)

        self.label_subtitle = ctk.CTkLabel(self, text="Stay blocked in.", font=("Roboto", 12), text_color="gray")
        self.label_subtitle.pack(pady=(0, 15))

        # Goal Input
        self.label_goal = ctk.CTkLabel(self, text="What is your focus goal?")
        self.label_goal.pack(pady=(10, 0))
        self.entry_goal = ctk.CTkEntry(self, placeholder_text="e.g. Studying Algorithms")
        self.entry_goal.pack(pady=5, padx=20, fill="x")

        # Duration Input
        self.label_time = ctk.CTkLabel(self, text="Duration (minutes):")
        self.label_time.pack(pady=(10, 0))
        self.entry_time = ctk.CTkEntry(self, placeholder_text="25")
        self.entry_time.pack(pady=5, padx=20, fill="x")

        # Start/Stop Button
        self.btn_start = ctk.CTkButton(self, text="Start Focus Session", command=self.toggle_session, fg_color="#1a73e8")
        self.btn_start.pack(pady=20)

        # Status / Logs
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
            tkinter.messagebox.showerror("Error", "Please fill in your goal and duration.")
            return

        # Check if API Key was loaded successfully
        if not API_KEY:
            tkinter.messagebox.showerror("Config Error", "API Key not found in .env file!")
            return

        try:
            self.duration_minutes = int(duration)
        except ValueError:
            tkinter.messagebox.showerror("Error", "Duration must be a number.")
            return

        # Initialize the Detection Module
        self.detector = FocusDetector(API_KEY)

        self.is_running = True
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
                self.log(f"⚠️ DISTRACTION: {reason}")
                
                self.after(0, lambda r=reason: tkinter.messagebox.showwarning(
                    "FocusGuard Alert",
                    f"Get back to work!\n\nDetected: {r}"
                ))
            elif result and result.upper().startswith("NO"):
                self.log("✅ Focused.")
            else:
                self.log(f"❓ Analyzing...")

            for _ in range(15):
                if not self.is_running: break
                time.sleep(1)

        if self.is_running:
            self.log("Session complete!")
            self.after(0, lambda: tkinter.messagebox.showinfo("Finished", "Great focus session!"))
            self.after(0, self.stop_session)

if __name__ == "__main__":
    app = FocusApp()
    app.mainloop()