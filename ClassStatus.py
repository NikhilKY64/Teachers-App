import tkinter as tk
from tkinter import ttk, messagebox
try:
    from supabase import create_client
except ImportError:
    create_client = None
import json
from datetime import datetime
import sqlite3
import customtkinter as ctk
import os

class ClassStatusApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("System")  # Modes: "System", "Dark", "Light"
        ctk.set_default_color_theme("dark-blue")  # Themes: "blue", "green", "dark-blue"
        
        self.title("Class Status")
        # Open in centered window with good size
        self.default_size = (900, 700)  # width, height
        self.is_fullscreen = False
        self.resizable(True, True)
        
        # Center the window
        self.update_idletasks()
        width, height = self.default_size
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        # Bind F11 to toggle fullscreen; Escape to exit fullscreen
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.exit_fullscreen)
        
        # Appearance mode
        self.appearance_mode = "System"
        ctk.set_appearance_mode(self.appearance_mode)        
        # Hardcoded Supabase credentials (replace with your actual values)
        # Try to load from main app's database first
        main_db_path = 'database.db'
        if os.path.exists(main_db_path):
            try:
                conn = sqlite3.connect(main_db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key = 'supabase_url'")
                row = cursor.fetchone()
                if row and row[0]:
                    self.supabase_url = row[0]
                cursor.execute("SELECT value FROM settings WHERE key = 'supabase_key'")
                row = cursor.fetchone()
                if row and row[0]:
                    self.supabase_key = row[0]
                conn.close()
            except:
                pass
        if not hasattr(self, 'supabase_url') or not self.supabase_url:
            self.supabase_url = "supabase_url"  # Replace with your Supabase URL
        if not hasattr(self, 'supabase_key') or not self.supabase_key:
            self.supabase_key = "supabase_key"  # Replace with your anon public key
        
        # Supabase client - will be set after login
        self.supabase = None
        self.classroom_data = None
        
        # DB setup
        self.db_path = 'ClassStatus.db'
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS login (id INTEGER PRIMARY KEY, classroom TEXT)''')
        self.conn.commit()
        
        # Frames
        self.login_frame = ctk.CTkFrame(self)
        self.main_frame = ctk.CTkFrame(self)
        
        # Check for stored login
        self.cursor.execute('SELECT classroom FROM login LIMIT 1')
        row = self.cursor.fetchone()
        if row:
            self.logged_classroom = row[0]
            # Try auto-login
            try:
                self.supabase = create_client(self.supabase_url, self.supabase_key)
                response = self.supabase.table('classrooms').select('*').eq('name', self.logged_classroom).execute()
                if response.data:
                    data = response.data[0]
                    self.classroom_data = data
                    try:
                        self.timetable = json.loads(data.get('timetable_json', '[]'))
                    except:
                        self.timetable = []
                    try:
                        period_times_list = json.loads(data.get('period_times_json', '[]'))
                        self.period_times = {p: (s, e) for p, s, e in period_times_list}
                    except:
                        self.period_times = {}
                    self.main_frame.pack(fill=tk.BOTH, expand=True)
                    try:
                        self.show_main()
                    except Exception as e:
                        messagebox.showerror("Error", f"Auto-login failed: {e}")
                        self.show_login()
                else:
                    self.cursor.execute('DELETE FROM login')
                    self.conn.commit()
                    self.show_login()
            except Exception as e:
                messagebox.showerror("Error", f"Auto-login failed: {e}")
                self.show_login()
        else:
            self.show_login()

    def get_mode_button_text(self):
        if self.appearance_mode == "Dark":
            return "Light Mode"
        else:
            return "Dark Mode"

    def toggle_mode(self):
        if self.appearance_mode == "System":
            self.appearance_mode = "Dark"
        elif self.appearance_mode == "Dark":
            self.appearance_mode = "Light"
        else:
            self.appearance_mode = "System"
        ctk.set_appearance_mode(self.appearance_mode)
        if hasattr(self, 'mode_button'):
            self.mode_button.configure(text=self.get_mode_button_text())
        # Refresh the main screen to update theme-dependent colors
        if hasattr(self, 'main_frame') and self.main_frame.winfo_exists():
            self.show_main()

    def update_time(self):
        now = datetime.now()
        if hasattr(self, 'time_label'):
            self.time_label.configure(text=f"⏰ {now.strftime('%H:%M:%S')}")
        self.after(1000, self.update_time)

    def show_login(self):
        # Clear login_frame
        for widget in self.login_frame.winfo_children():
            widget.destroy()
        
        # Pack the login frame
        self.login_frame.pack(fill=tk.BOTH, expand=True)
        
        # Show loading screen first
        self.show_loading_screen("Loading classrooms...")
        
        # Fetch classrooms in background
        self.after(100, self.load_classrooms_async)

    def show_loading_screen(self, message):
        # Clear login_frame
        for widget in self.login_frame.winfo_children():
            widget.destroy()
        
        # Loading container
        loading_container = ctk.CTkFrame(self.login_frame, fg_color="transparent")
        loading_container.pack(expand=True, fill="both", padx=40, pady=40)
        
        # Loading frame
        loading_frame = ctk.CTkFrame(loading_container, corner_radius=15)
        loading_frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        # Loading message
        loading_label = ctk.CTkLabel(loading_frame, text=message, 
                                   font=("Arial", 16))
        loading_label.pack(pady=(40, 20), padx=20)
        
        # Loading animation (simple dots)
        self.loading_dots = ctk.CTkLabel(loading_frame, text="⏳", 
                                       font=("Arial", 24))
        self.loading_dots.pack(pady=(0, 40), padx=20)
        self.animate_loading()

    def animate_loading(self):
        if hasattr(self, 'loading_dots') and self.loading_dots.winfo_exists():
            current = self.loading_dots.cget("text")
            if current == "⏳":
                self.loading_dots.configure(text="⌛")
            else:
                self.loading_dots.configure(text="⏳")
            self.after(500, self.animate_loading)

    def load_classrooms_async(self):
        # Fetch classrooms
        self.classrooms = []
        try:
            if not self.supabase:
                self.supabase = create_client(self.supabase_url, self.supabase_key)
            response = self.supabase.table('classrooms').select('name').execute()
            self.classrooms = [row['name'] for row in response.data]
        except Exception as e:
            self.classrooms = []
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to fetch classrooms: {e}"))
        
        # Show login screen
        self.after(0, self.show_login_form)

    def show_login_form(self):
        # Clear login_frame
        for widget in self.login_frame.winfo_children():
            widget.destroy()
        
        # Stop loading animation
        if hasattr(self, 'animate_loading'):
            # Remove the after callback by not calling it again
            pass
        
        # Main container
        main_container = ctk.CTkFrame(self.login_frame, fg_color="transparent")
        main_container.pack(expand=True, fill="both", padx=40, pady=40)
        
        # Title
        title_label = ctk.CTkLabel(main_container, text="Class Status Login", 
                                 font=("Arial", 24, "bold"))
        title_label.pack(pady=(20, 40))
        
        # Content frame
        content_frame = ctk.CTkFrame(main_container, corner_radius=15)
        content_frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        if not self.classrooms:
            messagebox.showinfo("No Classrooms", "No classrooms found. Please ensure classrooms are synced from the main app.")
        
        # Classroom selection
        classroom_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        classroom_frame.pack(fill="x", padx=30, pady=(30, 15))
        
        classroom_label = ctk.CTkLabel(classroom_frame, text="Select Classroom:", 
                                     font=("Arial", 16, "bold"))
        classroom_label.pack(anchor="w", pady=(0, 8))
        
        self.classroom_combo = ctk.CTkComboBox(classroom_frame, values=self.classrooms, 
                                             state="readonly", font=("Arial", 14),
                                             height=40, corner_radius=8)
        self.classroom_combo.pack(fill="x")
        
        # Password
        password_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        password_frame.pack(fill="x", padx=30, pady=(15, 30))
        
        password_label = ctk.CTkLabel(password_frame, text="Password:", 
                                    font=("Arial", 16, "bold"))
        password_label.pack(anchor="w", pady=(0, 8))
        
        self.password_entry = ctk.CTkEntry(password_frame, show="*", 
                                         font=("Arial", 14), height=40,
                                         corner_radius=8)
        self.password_entry.pack(fill="x")
        
        # Login button
        button_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=30, pady=(20, 30))
        
        login_button = ctk.CTkButton(button_frame, text="Login", 
                                   command=self.login, height=45,
                                   corner_radius=8, font=("Arial", 16, "bold"))
        login_button.pack(fill="x")
        
        # Bind Enter key to login
        self.password_entry.bind("<Return>", lambda e: self.login())
        self.classroom_combo.bind("<Return>", lambda e: self.login())
        
    def load_main_async(self):
        try:
            self.login_frame.pack_forget()
            self.main_frame.pack(fill=tk.BOTH, expand=True)
            self.show_main()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load main screen: {e}")
            self.show_login()

    def login(self):
        classroom = self.classroom_combo.get()
        password = self.password_entry.get()
        
        if not classroom or not password:
            messagebox.showerror("Error", "Classroom and password are required")
            return
        
        try:
            if not self.supabase:
                self.supabase = create_client(self.supabase_url, self.supabase_key)
            # Fetch classroom data
            response = self.supabase.table('classrooms').select('*').eq('name', classroom).execute()
            if response.data:
                data = response.data[0]
                if data['password'] == password:
                    self.classroom_data = data
                    try:
                        self.timetable = json.loads(data.get('timetable_json', '[]'))
                    except:
                        self.timetable = []
                    try:
                        period_times_list = json.loads(data.get('period_times_json', '[]'))
                        self.period_times = {p: (s, e) for p, s, e in period_times_list}
                    except:
                        self.period_times = {}
                    self.logged_classroom = classroom
                    # Store in DB
                    self.cursor.execute('INSERT OR REPLACE INTO login (id, classroom) VALUES (1, ?)', (classroom,))
                    self.conn.commit()
                    
                    # Show loading screen before main
                    self.show_loading_screen("Loading classroom data...")
                    self.after(500, self.load_main_async)
                else:
                    messagebox.showerror("Error", "Invalid password")
            else:
                messagebox.showerror("Error", "Classroom not found")
        except Exception as e:
            messagebox.showerror("Error", f"Login failed: {e}")
            self.supabase = None

    def show_main(self):
        # clear main_frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        # Main container
        main_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        main_container.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Header section
        header_frame = ctk.CTkFrame(main_container, corner_radius=15, height=80)
        header_frame.pack(fill="x", pady=(0, 20))
        header_frame.pack_propagate(False)
        
        # Mode button in top right
        self.mode_button = ctk.CTkButton(header_frame, text=self.get_mode_button_text(), 
                                       command=self.toggle_mode, width=120, height=35,
                                       corner_radius=8, font=("Arial", 12))
        self.mode_button.pack(side="right", padx=20, pady=15)
        
        # Title
        title_label = ctk.CTkLabel(header_frame, text=f"Welcome to {self.logged_classroom}", 
                                 font=("Arial", 20, "bold"))
        title_label.pack(side="left", padx=20, pady=15)
        
        # Time display
        time_frame = ctk.CTkFrame(main_container, corner_radius=10)
        time_frame.pack(fill="x", pady=(0, 20))
        
        time_title = ctk.CTkLabel(time_frame, text="Current Time", 
                                font=("Arial", 14, "bold"))
        time_title.pack(pady=(10, 5))
        
        self.time_label = ctk.CTkLabel(time_frame, text=f"⏰ {datetime.now().strftime('%H:%M:%S')}", 
                                     font=("Arial", 18, "bold"))
        self.time_label.pack(pady=(0, 10))
        self.update_time()
        
        # Status section
        status_frame = ctk.CTkFrame(main_container, corner_radius=15)
        status_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        # get current time
        now = datetime.now()
        
        # Current period info
        day = now.strftime("%A")
        period = self.get_current_period()
        if period:
            # find teacher for this classroom, day, period
            teacher = None
            for t_id, d, p, c, s in self.timetable:
                if d == day and p == period and c.upper().replace('-', '').replace(' ', '') == self.logged_classroom.upper().replace('-', '').replace(' ', ''):
                    teacher = (t_id, s)
                    break
            if teacher:
                teacher_id, teacher_name = teacher
                
                # Current class card
                current_card = ctk.CTkFrame(status_frame, corner_radius=12)
                current_card.pack(fill="x", padx=20, pady=(20, 10))
                
                period_label = ctk.CTkLabel(current_card, text=f"📚 Current Period: {period}", 
                                          font=("Arial", 16, "bold"))
                period_label.pack(pady=(15, 5), padx=15)
                
                teacher_label = ctk.CTkLabel(current_card, text=f"👨‍🏫 Teacher: {teacher_name}", 
                                           font=("Arial", 14))
                teacher_label.pack(pady=(0, 15), padx=15)
                
                # Check if already confirmed
                confirmed = False
                if self.supabase:
                    try:
                        response = self.supabase.table('teacher_reached_logs').select('id').eq('date', datetime.now().date().isoformat()).eq('class', self.logged_classroom.upper().replace('-', '').replace(' ', '')).eq('period', period).eq('confirmation_source', 'classroom').execute()
                        if response.data:
                            confirmed = True
                    except Exception:
                        pass
                
                if not confirmed:
                    confirm_btn = ctk.CTkButton(current_card, text="✅ Confirm Teacher Reached", 
                                              command=lambda: self.confirm_reached(teacher_id, teacher_name, period), 
                                              font=("Arial", 14, "bold"), height=40,
                                              corner_radius=8, fg_color="#28a745",
                                              hover_color="#218838")
                    confirm_btn.pack(pady=(0, 15), padx=15, fill="x")
                else:
                    confirmed_label = ctk.CTkLabel(current_card, text="✅ Already Confirmed", 
                                                 font=("Arial", 14, "bold"), text_color="#28a745")
                    confirmed_label.pack(pady=(0, 15), padx=15)
            else:
                # No class scheduled for current period - use theme-appropriate colors
                if ctk.get_appearance_mode() == "Dark":
                    bg_color = "#2d3748"  # Dark gray background
                    text_color = "#fbbf24"  # Yellow/amber text for dark mode
                else:
                    bg_color = "#fff3cd"  # Light yellow background
                    text_color = "#856404"  # Orange text for light mode
                
                no_class_card = ctk.CTkFrame(status_frame, corner_radius=12, fg_color=bg_color, border_width=2, border_color=text_color)
                no_class_card.pack(fill="x", padx=20, pady=(20, 10))
                no_class_label = ctk.CTkLabel(no_class_card, text="📭 No class scheduled for current period", 
                                            font=("Arial", 14), text_color=text_color)
                no_class_label.pack(pady=15, padx=15)
        else:
            # No current period - use theme-appropriate colors
            if ctk.get_appearance_mode() == "Dark":
                bg_color = "#2d1b1b"  # Dark red background
                text_color = "#fc8181"  # Light red text for dark mode
            else:
                bg_color = "#f8d7da"  # Light red background
                text_color = "#721c24"  # Dark red text for light mode
            
            no_period_card = ctk.CTkFrame(status_frame, corner_radius=12, fg_color=bg_color, border_width=2, border_color=text_color)
            no_period_card.pack(fill="x", padx=20, pady=(20, 10))
            no_period_label = ctk.CTkLabel(no_period_card, text="⏰ No current period (outside school hours)", 
                                         font=("Arial", 14), text_color=text_color)
            no_period_label.pack(pady=15, padx=15)
        
        # Next period preview
        next_period = self.get_next_period()
        if next_period:
            next_teacher = None
            next_start_time = None
            for t_id, d, p, c, s in self.timetable:
                if d == day and p == next_period and c.upper().replace('-', '').replace(' ', '') == self.logged_classroom.upper().replace('-', '').replace(' ', ''):
                    next_teacher = s
                    break
            
            # Get the start time of next period
            if next_period in self.period_times:
                next_start_time = self.period_times[next_period][0]  # start time string
            
            # Only show next period card if there's a teacher scheduled
            if next_teacher:
                next_card = ctk.CTkFrame(status_frame, corner_radius=12)
                next_card.pack(fill="x", padx=20, pady=(10, 20))
                
                next_title = ctk.CTkLabel(next_card, text=f"🔜 Next Period: {next_period}", 
                                        font=("Arial", 16, "bold"))
                next_title.pack(pady=(15, 5), padx=15)
                
                next_teacher_label = ctk.CTkLabel(next_card, text=f"👨‍🏫 {next_teacher}", 
                                                font=("Arial", 14))
                next_teacher_label.pack(pady=(0, 5), padx=15)
                
                # Time remaining
                if next_start_time:
                    try:
                        next_start = datetime.strptime(next_start_time, "%H:%M:%S").time()
                        current_time = now.time()
                        
                        # Create datetime objects for calculation
                        today = now.date()
                        next_datetime = datetime.combine(today, next_start)
                        current_datetime = datetime.combine(today, current_time)
                        
                        if next_datetime > current_datetime:
                            time_diff = next_datetime - current_datetime
                            hours, remainder = divmod(time_diff.seconds, 3600)
                            minutes, seconds = divmod(remainder, 60)
                            
                            if hours > 0:
                                time_remaining = f"⏱️ {hours}h {minutes}m {seconds}s remaining"
                            elif minutes > 0:
                                time_remaining = f"⏱️ {minutes}m {seconds}s remaining"
                            else:
                                time_remaining = f"⏱️ {seconds}s remaining"
                            
                            time_label = ctk.CTkLabel(next_card, text=time_remaining, 
                                                    font=("Arial", 12, "italic"))
                            time_label.pack(pady=(0, 15), padx=15)
                        else:
                            # Next period already started or passed
                            time_label = ctk.CTkLabel(next_card, text="⏱️ Starting soon...", 
                                                    font=("Arial", 12, "italic"))
                            time_label.pack(pady=(0, 15), padx=15)
                    except Exception:
                        pass  # Skip time calculation if error
            else:
                # No class scheduled for next period - show themed message
                if ctk.get_appearance_mode() == "Dark":
                    bg_color = "#1a365d"  # Dark blue background
                    text_color = "#63b3ed"  # Light blue text for dark mode
                else:
                    bg_color = "#d1ecf1"  # Light blue background
                    text_color = "#0c5460"  # Dark blue text for light mode
                
                no_next_class_card = ctk.CTkFrame(status_frame, corner_radius=12, fg_color=bg_color, border_width=2, border_color=text_color)
                no_next_class_card.pack(fill="x", padx=20, pady=(10, 20))
                no_class_label = ctk.CTkLabel(no_next_class_card, text="📭 No more classes scheduled for today", 
                                            font=("Arial", 14, "italic"), text_color=text_color)
                no_class_label.pack(pady=15, padx=15)
                pass
        
        # Footer buttons
        footer_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        footer_frame.pack(fill="x", pady=(0, 10))
        
        refresh_btn = ctk.CTkButton(footer_frame, text="🔄 Refresh", command=self.show_main, 
                                  font=("Arial", 14), height=40, corner_radius=8,
                                  fg_color="#6c757d", hover_color="#5a6268")
        refresh_btn.pack(side="left", padx=(20, 10), expand=True)
        
        logout_btn = ctk.CTkButton(footer_frame, text="🚪 Logout", command=self.logout, 
                                 font=("Arial", 14, "bold"), height=40, corner_radius=8)
        logout_btn.pack(side="right", padx=(10, 20), expand=True)
        
        # Auto refresh every minute
        self.after(60000, self.show_main)

    def get_current_period(self):
        now = datetime.now().time()
        for p, (s, e) in self.period_times.items():
            start_time = datetime.strptime(s, "%H:%M:%S").time()
            end_time = datetime.strptime(e, "%H:%M:%S").time()
            if start_time <= now <= end_time:
                return p
        return None

    def get_next_period(self):
        now = datetime.now().time()
        next_start = None
        next_p = None
        for p, (s, e) in self.period_times.items():
            start_time = datetime.strptime(s, "%H:%M:%S").time()
            if start_time > now:
                if next_start is None or start_time < next_start:
                    next_start = start_time
                    next_p = p
        return next_p

    def confirm_reached(self, teacher_id, teacher_name, period):
        # insert to supabase
        if self.supabase:
            try:
                self.supabase.table('teacher_reached_logs').insert({
                    'teacher_id': teacher_id,
                    'name': teacher_name,
                    'class': self.logged_classroom.upper().replace('-', '').replace(' ', ''),
                    'room': self.logged_classroom,
                    'period': period,
                    'date': datetime.now().date().isoformat(),
                    'reached_timestamp': datetime.now().isoformat(),
                    'confirmation_source': 'classroom'
                }).execute()
                messagebox.showinfo("Success", "Confirmed")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to confirm: {e}")
        else:
            messagebox.showerror("Error", "No internet connection")
        self.show_main()

    

    def toggle_fullscreen(self, event=None):
        """Toggle between fullscreen and windowed mode."""
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        """Enter fullscreen mode."""
        self.attributes("-fullscreen", True)
        self.is_fullscreen = True

    def exit_fullscreen(self, event=None):
        """Exit fullscreen mode."""
        self.attributes("-fullscreen", False)
        self.is_fullscreen = False
        # Restore to centered window
        width, height = self.default_size
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def logout(self):
        self.cursor.execute('DELETE FROM login')
        self.conn.commit()
        self.main_frame.pack_forget()
        self.show_login()

if __name__ == "__main__":
    app = ClassStatusApp()
    app.mainloop()