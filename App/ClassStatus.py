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

class ClassStatusApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("System")  # Modes: "System", "Dark", "Light"
        ctk.set_default_color_theme("dark-blue")  # Themes: "blue", "green", "dark-blue"
        
        self.title("Class Status")
        self.geometry("500x400")
        self.resizable(False, False)        
        # Center the window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        # Appearance mode
        self.appearance_mode = "System"
        ctk.set_appearance_mode(self.appearance_mode)        
        # Hardcoded Supabase credentials (replace with your actual values)
        self.supabase_url = "https://neeozcpahsixsrolhxib.supabase.co"  # Replace with your Supabase URL
        self.supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5lZW96Y3BhaHNpeHNyb2xoeGliIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY1NzE0NjEsImV4cCI6MjA4MjE0NzQ2MX0.NhnKH8u4Yt6sb7xoTz2MPIRqisDz0XVA_f-5M6vzOvg"  # Replace with your anon public key
        
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
                    self.timetable = json.loads(data['timetable_json'])
                    self.period_times = {p: (s, e) for p, s, e in json.loads(data['period_times_json'])}
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

    def update_time(self):
        now = datetime.now()
        if hasattr(self, 'time_label'):
            self.time_label.configure(text=f"Current Time: {now.strftime('%H:%M:%S')}")
        self.after(1000, self.update_time)

    def show_login(self):
        # Clear login_frame
        for widget in self.login_frame.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(self.login_frame, text="Class Status Login", font=("Arial", 18, "bold")).pack(pady=20)
        
        # Fetch classrooms
        classrooms = []
        try:
            if not self.supabase:
                self.supabase = create_client(self.supabase_url, self.supabase_key)
            response = self.supabase.table('classrooms').select('name').execute()
            classrooms = [row['name'] for row in response.data]
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch classrooms: {e}")
        
        ctk.CTkLabel(self.login_frame, text="Select Classroom:", font=("Arial", 14)).pack(pady=10)
        self.classroom_combo = ctk.CTkComboBox(self.login_frame, values=classrooms, state="readonly", font=("Arial", 12))
        self.classroom_combo.pack(pady=5)
        
        ctk.CTkLabel(self.login_frame, text="Password:", font=("Arial", 14)).pack(pady=10)
        self.password_entry = ctk.CTkEntry(self.login_frame, show="*", font=("Arial", 12))
        self.password_entry.pack(pady=5)
        
        ctk.CTkButton(self.login_frame, text="Login", command=self.login, font=("Arial", 12, "bold")).pack(pady=20)
        
        self.login_frame.pack(fill=tk.BOTH, expand=True)

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
                    self.timetable = json.loads(data['timetable_json'])
                    self.period_times = {p: (s, e) for p, s, e in json.loads(data['period_times_json'])}
                    self.logged_classroom = classroom
                    # Store in DB
                    self.cursor.execute('INSERT OR REPLACE INTO login (id, classroom) VALUES (1, ?)', (classroom,))
                    self.conn.commit()
                    self.login_frame.pack_forget()
                    self.main_frame.pack(fill=tk.BOTH, expand=True)
                    try:
                        self.show_main()
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to load main screen: {e}")
                        self.show_login()
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
        
        # Top frame for mode button
        top_frame = ctk.CTkFrame(self.main_frame, height=50)
        top_frame.pack(fill=tk.X, pady=5)
        self.mode_button = ctk.CTkButton(top_frame, text=self.get_mode_button_text(), command=self.toggle_mode, width=100, height=30)
        self.mode_button.pack(side=tk.LEFT, padx=10, pady=5)
        
        # get current time
        now = datetime.now()
        
        ctk.CTkLabel(self.main_frame, text=f"Logged in as: {self.logged_classroom}", font=("Arial", 16, "bold")).pack(pady=10)
        
        self.time_label = ctk.CTkLabel(self.main_frame, text=f"Current Time: {now.strftime('%H:%M:%S')}", font=("Arial", 12))
        self.time_label.pack(pady=5)
        self.update_time()
        
        # get current period
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
                ctk.CTkLabel(self.main_frame, text=f"Period: {period}", font=("Arial", 16, "bold")).pack(pady=10)
                ctk.CTkLabel(self.main_frame, text=f"Teacher: {teacher_name}", font=("Arial", 14)).pack(pady=10)
                
                # Check if already confirmed for this period
                confirmed = False
                if self.supabase:
                    try:
                        response = self.supabase.table('teacher_reached_logs').select('id').eq('date', datetime.now().date().isoformat()).eq('class', self.logged_classroom.upper().replace('-', '').replace(' ', '')).eq('period', period).eq('confirmation_source', 'classroom').execute()
                        if response.data:
                            confirmed = True
                    except Exception:
                        pass
                
                if not confirmed:
                    ctk.CTkButton(self.main_frame, text="Confirm Teacher Reached", command=lambda: self.confirm_reached(teacher_id, teacher_name, period), font=("Arial", 12)).pack(pady=20)
                else:
                    ctk.CTkLabel(self.main_frame, text="Already Confirmed for this Period", font=("Arial", 14), text_color="green").pack(pady=20)
            else:
                ctk.CTkLabel(self.main_frame, text="No class scheduled").pack(pady=10)
        else:
            ctk.CTkLabel(self.main_frame, text="No current period").pack(pady=10)
        
        # Show next period teacher
        next_period = self.get_next_period()
        if next_period:
            next_teacher = None
            for t_id, d, p, c, s in self.timetable:
                if d == day and p == next_period and c.upper().replace('-', '').replace(' ', '') == self.logged_classroom:
                    next_teacher = s
                    break
            teacher_text = next_teacher if next_teacher else "No class scheduled"
            ctk.CTkLabel(self.main_frame, text=f"Next Period ({next_period}): {teacher_text}", font=("Arial", 14)).pack(pady=10)
        
        # Refresh button
        ctk.CTkButton(self.main_frame, text="Refresh", command=self.show_main, font=("Arial", 12)).pack(pady=5)
        # Logout button
        ctk.CTkButton(self.main_frame, text="Logout", command=self.logout, fg_color="red", font=("Arial", 12)).pack(pady=10)
        # update every minute
        self.after(60000, self.show_main)

    def get_current_period(self):
        now = datetime.now().time()
        for p, (s, e) in self.period_times.items():
            start_time = datetime.strptime(s, "%H:%M").time()
            end_time = datetime.strptime(e, "%H:%M").time()
            if start_time <= now <= end_time:
                return p
        return None

    def get_next_period(self):
        now = datetime.now().time()
        next_start = None
        next_p = None
        for p, (s, e) in self.period_times.items():
            start_time = datetime.strptime(s, "%H:%M").time()
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

    

    def logout(self):
        self.cursor.execute('DELETE FROM login')
        self.conn.commit()
        self.main_frame.pack_forget()
        self.show_login()

if __name__ == "__main__":
    app = ClassStatusApp()
    app.mainloop()