import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import datetime
from tkinter import filedialog
import os

class TeacherTimetableApp(tk.Tk):
    def __init__(self):
        super().__init__()
        # Set title including app version read from VERSION.txt (fallback v0.0.0)
        version = self.get_app_version()
        self.title(f"Teacher Timetable Manager — {version}")
        # Start maximized so the window decorations (close button) remain visible
        self.default_size = (1200, 800)  # width, height when not fullscreen
        self.is_fullscreen = False
        self.is_maximized = True
        try:
            # On Windows, this maximizes the window while keeping decorations
            self.state("zoomed")
        except tk.TclError:
            # Fallback - set geometry to screen size
            self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        # Bind F11 to toggle fullscreen; Escape to exit fullscreen (and center)
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.exit_fullscreen)
        
        # Database setup
        self.db_path = "school.db"
        self.create_database()
        
        # Configure ttk style
        self.setup_style()
        
        # Days and periods configuration
        self.days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        self.periods = list(range(1, 9))  # Periods 1..8

        # Default period timings (editable): map period -> (start_time, end_time)
        # Times are datetime.time objects (24-hour). Edit these to your school's schedule.
        self.period_times = {
            1: (datetime.time(8, 30), datetime.time(9, 15)),
            2: (datetime.time(9, 15), datetime.time(10, 0)),
            3: (datetime.time(10, 0), datetime.time(10, 45)),
            4: (datetime.time(10, 45), datetime.time(11, 30)),
            5: (datetime.time(11, 30), datetime.time(12, 15)),
            6: (datetime.time(12, 15), datetime.time(13, 0)),
            7: (datetime.time(13, 0), datetime.time(13, 45)),
            8: (datetime.time(13, 45), datetime.time(14, 30)),
        }

        # For auto-update scheduling (store after id)
        self._status_after_id = None
        # For highlight auto-update scheduling (every 5 seconds)
        self._highlight_after_id = None
        # Highlight colour for current cell
        self.highlight_color = "#00FF84"  # bright green
        self.highlight_color_dim = "#F87400"  # dimmed light green
        # Blink interval (milliseconds) - use 500ms toggle per user's rule
        self.blink_interval = 500
        # Simple blink state: False = base color, True = highlight color
        self.blink_state = True

        # Load any persisted period timings from DB (overwrites defaults if present)
        try:
            self.load_period_times()
        except Exception:
            # If loading fails, keep defaults
            pass

        # Subject color mapping for timetable cells
        self.subject_colors = {}
        self.color_palette = [
            "#4CC562", "#AED6F1", "#F5B7B1", "#D2B4DE", "#ABEBC6", "#FADBD8",
            "#D6EAF8", "#F9EBEA", "#E8DAEF", "#FDEBD0"
        ]
        self.next_color_idx = 0

        # Current selected teacher
        self.current_teacher_id = None
        # New API: explicit selected teacher id as integer when a teacher is selected
        self.selected_teacher_id = None
        # For bulk selection (checkboxes) in the teachers list
        self.selected_teacher_ids = set()
        # Bulk-delete mode flag (when true, Select checkboxes are shown)
        self.bulk_delete_mode = False
        
        # Color scheme for buttons
        self.color_add = "#3EBD3A"      # Green for Add
        self.color_edit = "#3B82F6"     # Blue for Edit
        self.color_delete = "#E93D3D"   # Red for Delete
        self.color_exit = "#E91212"     # Red for Exit
        self.text_color = "#FFFFFF"     # White text
        
        # Build the basic UI quickly, then finish heavy widgets shortly after
        self.create_basic_layout()

        # Load initial (essential) data only: teachers list
        self.load_teachers()

        # Finish the heavier UI parts shortly after showing the window to improve startup time
        try:
            self.after(100, self.finish_setup)
        except Exception:
            # Fallback: build immediately
            try:
                self.finish_setup()
            except Exception:
                pass
    
    def setup_style(self):
        """Configure ttk style for modern appearance"""
        style = ttk.Style()
        style.theme_use("clam")
        
        style.configure("Title.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Normal.TLabel", font=("Segoe UI", 11, "normal"))
        style.configure("Heading.TLabel", font=("Segoe UI", 15, "bold"))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TEntry", font=("Segoe UI", 10))
        style.configure("Treeview", font=("Segoe UI", 11), rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 12, "bold"))

        # Details panel / selected teacher background color
        # Change the hex to your preferred color (light pastel shown here)
        details_bg = "#C4CAC2"
        style.configure("Details.TLabelframe", background=details_bg, bordercolor="#000000")
        style.configure("Details.TLabelframe.Label", background=details_bg, font=("Segoe UI", 11, "bold"))
        # New styles: bold name and bold detail lines
        style.configure("Details.Name.TLabel", background=details_bg, font=("Segoe UI", 13, "bold"))
        style.configure("Details.Info.TLabel", background=details_bg, font=("Segoe UI", 11, "bold"))
        style.configure("Details.TLabel", background=details_bg, font=("Segoe UI", 11))

    def get_subject_color(self, subject):
        """Return a consistent color for a subject. Assign a new color if first time seen."""
        if not subject:
            return getattr(self, 'default_btn_bg', self.cget('bg'))
        key = subject.strip().lower()
        if key in self.subject_colors:
            return self.subject_colors[key]
        color = self.color_palette[self.next_color_idx % len(self.color_palette)]
        self.subject_colors[key] = color
        self.next_color_idx += 1
        return color
    
    def create_database(self):
        """Create SQLite database and tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Teachers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                degree TEXT,
                main_subject TEXT
            )
        """)
        
        # Timetable table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS timetable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                day_of_week TEXT NOT NULL,
                period_number INTEGER NOT NULL,
                class_name TEXT NOT NULL,
                subject TEXT NOT NULL,
                FOREIGN KEY(teacher_id) REFERENCES teachers(id)
            )
        """)

        # Period timings table (persist editable period start/end times)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS period_times (
                period_number INTEGER PRIMARY KEY,
                start TEXT NOT NULL,
                end TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
        # Add `subjects` column to teachers if not present (simple migration)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(teachers)")
        cols = [r[1] for r in cursor.fetchall()]
        if 'subjects' not in cols:
            try:
                cursor.execute("ALTER TABLE teachers ADD COLUMN subjects TEXT")
            except Exception:
                pass
        conn.commit()
        conn.close()

    def load_period_times(self):
        """Load period timings from DB into `self.period_times`. If empty, populate DB from defaults."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM period_times")
        try:
            count = cursor.fetchone()[0]
        except Exception:
            count = 0

        # If DB table empty, insert defaults from self.period_times
        if count == 0 and getattr(self, 'period_times', None):
            for pnum, (start, end) in sorted(self.period_times.items()):
                cursor.execute("INSERT OR REPLACE INTO period_times (period_number, start, end) VALUES (?, ?, ?)",
                               (pnum, start.strftime('%H:%M'), end.strftime('%H:%M')))
            conn.commit()

        # Now load into mapping (overwrite in-memory)
        cursor.execute("SELECT period_number, start, end FROM period_times ORDER BY period_number")
        rows = cursor.fetchall()
        new_map = {}
        for pnum, start_s, end_s in rows:
            try:
                start_t = datetime.time.fromisoformat(start_s)
                end_t = datetime.time.fromisoformat(end_s)
            except Exception:
                # fallback to defaults if parse fails
                if pnum in getattr(self, 'period_times', {}):
                    start_t, end_t = self.period_times[pnum]
                else:
                    continue
            new_map[pnum] = (start_t, end_t)

        if new_map:
            self.period_times = new_map

        conn.close()

    def get_app_version(self):
        """Read VERSION.txt from the app folder and return its text, or default to v0.0.0."""
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            version_file = os.path.join(base, "VERSION.txt")
            if os.path.isfile(version_file):
                with open(version_file, "r", encoding="utf-8") as f:
                    txt = f.read().strip()
                    return txt if txt else "v0.0.0"
            return "v0.0.0"
        except Exception:
            return "v0.0.0"
    
    def create_basic_layout(self):
        """Create the two-panel main layout"""
        """Create the two-panel main layout"""
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # LEFT PANEL - Teachers
        self.left_frame = ttk.Frame(self.main_frame, width=300)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))
        self.left_frame.pack_propagate(False)
        
        # Card container for Teachers (bordered)
        self.card_frame = tk.Frame(self.left_frame, bd=1, relief='solid', background="#C4CAC2")
        self.card_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        ttk.Label(self.card_frame, text="Teachers", style="Title.TLabel").pack(anchor="w", pady=(6, 8), padx=6)

        # Live search bar for teachers
        search_frame = ttk.Frame(self.card_frame)
        search_frame.pack(fill=tk.X, pady=(0, 6))
        self.search_var = tk.StringVar()
        # Use tk.Entry so we can easily control placeholder fg color
        # Make the search entry shorter and give it a visible border
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=("Segoe UI", 10), width=28, relief='solid', bd=1)
        self.search_entry.pack(side=tk.LEFT, anchor='w', padx=(0, 6))
        try:
            # subtle highlight border for some platforms
            self.search_entry.config(highlightthickness=1, highlightbackground="#cfcfcf", highlightcolor="#cfcfcf")
        except Exception:
            pass
        # Placeholder behaviour
        self._search_placeholder = "Search teacher..."
        self.search_entry.insert(0, self._search_placeholder)
        try:
            self.search_entry.config(fg="gray")
        except Exception:
            pass
        self.search_entry.bind("<FocusIn>", lambda e: self._clear_search_placeholder())
        self.search_entry.bind("<FocusOut>", lambda e: self._add_search_placeholder())
        # Call filter_teachers(text) on every key release
        self.search_entry.bind("<KeyRelease>", lambda e: self.filter_teachers(self.search_var.get().strip()))

        # Teachers Treeview
        # Add a Select column for bulk deletion (shows a checkbox-like mark)
        # Create Treeview with Select column present but hidden from display by default
        self.teachers_tree = ttk.Treeview(
            self.card_frame,
            columns=("Select", "Name", "Main Subject"),
            displaycolumns=("Name", "Main Subject"),
            height=15,
            show="headings"
        )
        # Hide Select column by default; it will be shown when entering bulk-delete mode
        self.teachers_tree.column("Select", width=0, anchor="center")
        # Reduce Name column width to make it shorter in the UI
        self.teachers_tree.column("Name", width=160, stretch=False)
        self.teachers_tree.column("Main Subject", width=130, anchor="center")
        self.teachers_tree.heading("Select", text="Select")
        self.teachers_tree.heading("Name", text="Name")
        self.teachers_tree.heading("Main Subject", text="Main Subject")
        self.teachers_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10), padx=6)
        # Alternate row colors for readability
        self.teachers_tree.tag_configure('evenrow', background="#fafaff")
        self.teachers_tree.tag_configure('oddrow', background="#e6ebf4")

        # Single-row selection handling (for details/import)
        self.teachers_tree.bind("<<TreeviewSelect>>", self.on_teacher_selected)
        # Click handler for toggling the Select column checkbox
        self.teachers_tree.bind("<Button-1>", self.on_tree_click)
        
        # Teacher buttons
        teacher_btn_frame = ttk.Frame(self.card_frame)
        teacher_btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        tk.Button(teacher_btn_frame, text="➕ Add Teacher", command=self.add_teacher_dialog,
            bg=self.color_add, fg=self.text_color, font=("Segoe UI", 10, "bold"),
            activebackground="#059669", cursor="hand2").pack(side=tk.LEFT, padx=2)
        tk.Button(teacher_btn_frame, text="Edit Teacher", command=self.edit_teacher_dialog,
            bg=self.color_edit, fg=self.text_color, font=("Segoe UI", 10, "bold"),
            activebackground="#1D4ED8", cursor="hand2").pack(side=tk.LEFT, padx=2)
        # Bulk delete selected teachers (uses the Select column checkboxes)
        self.delete_selected_btn = tk.Button(teacher_btn_frame, text="        Delete       ", command=self.toggle_bulk_delete_mode,
            bg=self.color_delete, fg=self.text_color, font=("Segoe UI", 10, "bold"),
            activebackground="#B91C1C", cursor="hand2")
        self.delete_selected_btn.pack(side=tk.LEFT, padx=2)
        # Cancel button for bulk-delete mode (created but not packed until needed)
        self.cancel_bulk_delete_btn = tk.Button(teacher_btn_frame, text="Cancel", command=self.exit_bulk_delete_mode,
            bg="#6B7280", fg=self.text_color, font=("Segoe UI", 10, "bold"),
            activebackground="#4B5563", cursor="hand2")
        # Import teachers button placed on its own row to ensure visibility
        import_btn_frame = ttk.Frame(self.card_frame)
        import_btn_frame.pack(fill=tk.X, pady=(6, 6), padx=6)
        tk.Button(import_btn_frame, text="📥 Import Teachers from Excel", command=self.import_teachers_from_excel,
            bg=self.color_add, fg=self.text_color, font=("Segoe UI", 9, "bold"),
            activebackground="#059669", cursor="hand2").pack(fill=tk.X)
        
        # RIGHT PANEL - Timetable
        self.right_frame = ttk.Frame(self.main_frame)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Card container for Selected Teacher + Timetable (bordered)
        self.card_frame_right = tk.Frame(self.right_frame, bd=1, relief='solid', background="#C4CAC2")
        self.card_frame_right.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Teacher details (inside the right card)
        # apply the Details style so the frame (and its label area) show color
        details_frame = ttk.LabelFrame(self.card_frame_right, text="Selected Teacher", padding=10, style="Details.TLabelframe")
        details_frame.pack(fill=tk.X, pady=(0, 10), padx=6)

        # Use the Details.TLabel style so label backgrounds match the frame
        self.teacher_name_label = ttk.Label(details_frame, text="No teacher selected", style="Details.Name.TLabel")
        self.teacher_name_label.pack(anchor="w")
        
        # Degree row: bold "Degree:" prefix and normal-weight value label
        degree_frame = ttk.Frame(details_frame)
        degree_frame.pack(anchor="w")
        # prefix (bold word "Degree:")
        self.teacher_degree_prefix = ttk.Label(degree_frame, text="", style="Details.Info.TLabel")
        self.teacher_degree_prefix.pack(side=tk.LEFT)
        # degree value (normal)
        self.teacher_degree_label = ttk.Label(degree_frame, text="", style="Details.TLabel")
        self.teacher_degree_label.pack(side=tk.LEFT, padx=(6,0))
        
        # Subject line: normal weight
        # make main subject bold
        self.teacher_subject_label = ttk.Label(details_frame, text="", style="Details.Info.TLabel")
        self.teacher_subject_label.pack(anchor="w")

        # Live status area for current/next class
        status_frame = ttk.Frame(details_frame)
        status_frame.pack(fill=tk.X, pady=(6, 0))

        # StringVars for live updates
        self.current_time_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="")
        self.next_var = tk.StringVar(value="")
        self.remaining_var = tk.StringVar(value="")

        # Display current system time and status
        ttk.Label(status_frame, textvariable=self.current_time_var, style="Normal.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(status_frame, textvariable=self.status_var, style="Heading.TLabel").grid(row=1, column=0, sticky="w", pady=(4,0))
        ttk.Label(status_frame, textvariable=self.next_var, style="Normal.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(status_frame, textvariable=self.remaining_var, style="Normal.TLabel").grid(row=3, column=0, sticky="w")
        
        # Timetable section (grid layout) inside the right card
        ttk.Label(self.card_frame_right, text="Timetable", style="Title.TLabel").pack(anchor="w", pady=(10, 5), padx=6)

        # Use a canvas for horizontal scrolling
        self.canvas_frame = ttk.Frame(self.card_frame_right)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=6)

        self.timetable_canvas = tk.Canvas(self.canvas_frame, height=360)
        h_scroll = ttk.Scrollbar(self.canvas_frame, orient='horizontal', command=self.timetable_canvas.xview)
        self.timetable_canvas.configure(xscrollcommand=h_scroll.set)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.timetable_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Frame inside canvas that will hold the grid
        self.timetable_grid_frame = ttk.Frame(self.timetable_canvas)
        self.timetable_canvas.create_window((0, 0), window=self.timetable_grid_frame, anchor='nw')

        # Heavy timetable grid and controls will be created later in finish_setup()
        # Prepare placeholders so finish_setup can populate them
        self.grid_buttons = {}  # (day, period) -> button (populated in finish_setup)

    def load_teachers(self):
        """Load all teachers into the treeview"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Order by name case-insensitive (A -> Z)
        cursor.execute("SELECT id, name, main_subject FROM teachers ORDER BY LOWER(name) ASC")
        teachers = cursor.fetchall()
        conn.close()
        
        # Clear treeview
        for item in self.teachers_tree.get_children():
            self.teachers_tree.delete(item)
        
        # Populate treeview with alternating row colors
        for idx, (teacher_id, name, main_subject) in enumerate(teachers):
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            # Show checkbox char depending on whether the teacher id is in selected_teacher_ids
            # Only show checkboxes when in bulk-delete mode
            if getattr(self, 'bulk_delete_mode', False):
                check = '☑' if teacher_id in getattr(self, 'selected_teacher_ids', set()) else '☐'
            else:
                check = ''
            self.teachers_tree.insert("", "end", iid=teacher_id, values=(check, name, main_subject or ""), tags=(tag,))

    def finish_setup(self):
        """Finish building the heavier UI parts (timetable grid and controls).

        This method is scheduled with `after()` shortly after startup so the
        main window appears quickly and heavy widgets are constructed in the
        background.
        """
        # Batch UI rendering: build grid without intermediate redraws, then call update once
        header_style = "Heading.TLabel"
        # Header row: empty top-left, then Period 1..8
        ttk.Label(self.timetable_grid_frame, text="DAY", style=header_style, borderwidth=1, relief="solid", anchor="center", padding=6).grid(row=0, column=0, sticky="nsew")
        for c, period in enumerate(self.periods, start=1):
            ttk.Label(self.timetable_grid_frame, text=f"Period {period}", style=header_style, borderwidth=1, relief="solid", anchor="center", padding=6).grid(row=0, column=c, sticky="nsew")

        for r, day in enumerate(self.days, start=1):
            # Day label
            ttk.Label(self.timetable_grid_frame, text=day.upper(), style="Normal.TLabel", borderwidth=1, relief="solid", padding=6).grid(row=r, column=0, sticky="nsew")
            for c, period in enumerate(self.periods, start=1):
                # Use a slightly larger font so class and subject names are more readable
                btn = tk.Button(self.timetable_grid_frame, text="----", width=14, height=2, wraplength=140,
                                font=("Segoe UI", 11, "bold"),
                                command=lambda d=day, p=period: self.on_cell_click(d, p))
                btn.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                # Right-click context menu to edit/delete
                btn.bind("<Button-3>", lambda e, d=day, p=period: self.on_cell_right_click(e, d, p))
                self.grid_buttons[(day, period)] = btn
                # capture default background color for resetting
                if not hasattr(self, 'default_btn_bg'):
                    self.default_btn_bg = btn.cget('bg')

        # Make columns expand evenly for nicer layout
        for col in range(len(self.periods) + 1):
            self.timetable_grid_frame.grid_columnconfigure(col, weight=1)

        # Update scrollregion and redraw once after creating all widgets
        self.timetable_grid_frame.update_idletasks()
        try:
            self.timetable_canvas.configure(scrollregion=self.timetable_canvas.bbox('all'))
        except Exception:
            pass

        # Add a small note on using the grid
        ttk.Label(self.card_frame_right, text="Tip: Click a cell to add/edit the period. Right-click for more options.", style="Normal.TLabel").pack(anchor="w", padx=6)

        # Timetable buttons (inside right card)
        timetable_btn_frame = ttk.Frame(self.card_frame_right)
        timetable_btn_frame.pack(fill=tk.X, pady=(10, 6), padx=6)
        tk.Button(timetable_btn_frame, text="➕ Add Period", command=self.add_period_dialog,
                  bg=self.color_add, fg=self.text_color, font=("Segoe UI", 10, "bold"),
                  activebackground="#059669", cursor="hand2").pack(side=tk.LEFT, padx=2)
        # Import timetable button (placed with timetable controls)
        self.import_timetable_btn = tk.Button(timetable_btn_frame, text="📄 Import Timetable", command=self.import_timetable_from_excel,
                                            bg="#0EA5A4", fg=self.text_color, font=("Segoe UI", 9, "bold"),
                                            activebackground="#0891B2", cursor="hand2", state='disabled')
        self.import_timetable_btn.pack(side=tk.LEFT, padx=2)
        tk.Button(timetable_btn_frame, text="🕒 Edit Period Timings", command=self.edit_period_timings_dialog,
                  bg="#6B21A8", fg=self.text_color, font=("Segoe UI", 10, "bold"),
                  activebackground="#4C1D95", cursor="hand2").pack(side=tk.LEFT, padx=6)
        tk.Button(timetable_btn_frame, text="Exit", command=self.quit,
                  bg=self.color_exit, fg=self.text_color, font=("Segoe UI", 10, "bold"),
                  activebackground="#634B4B", cursor="hand2").pack(side=tk.RIGHT, padx=2)

        # Start highlight auto-update loop now that timetable widgets exist
        try:
            self.start_auto_update_highlight()
        except Exception:
            pass

    def _clear_search_placeholder(self):
        try:
            if self.search_var.get() == self._search_placeholder:
                self.search_entry.delete(0, tk.END)
                self.search_entry.config(fg="black")
        except Exception:
            pass

    def _add_search_placeholder(self):
        try:
            if not self.search_var.get():
                self.search_entry.delete(0, tk.END)
                self.search_entry.insert(0, self._search_placeholder)
                self.search_entry.config(fg="gray")
        except Exception:
            pass

    def filter_teachers(self, text):
        """Filter teachers shown in the treeview by name (case-insensitive).

        This function is called on every <KeyRelease> from the search entry and
        must accept the raw text string as its single argument.
        """
        # If placeholder text is visible, treat as empty
        if getattr(self, '_search_placeholder', None) and text == self._search_placeholder:
            text = ''

        if not text:
            # Restore full list
            return self.load_teachers()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # case-insensitive search on name and main_subject
        term_lower = f"%{text.lower()}%"
        cursor.execute(
            "SELECT id, name, main_subject FROM teachers WHERE LOWER(name) LIKE ? OR LOWER(main_subject) LIKE ? ORDER BY LOWER(name) ASC",
            (term_lower, term_lower)
        )
        teachers = cursor.fetchall()
        conn.close()

        # Clear treeview
        for item in self.teachers_tree.get_children():
            self.teachers_tree.delete(item)

        # Populate filtered results preserving alternating colors and checkbox column
        for idx, (teacher_id, name, main_subject) in enumerate(teachers):
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            if getattr(self, 'bulk_delete_mode', False):
                check = '☑' if teacher_id in getattr(self, 'selected_teacher_ids', set()) else '☐'
            else:
                check = ''
            self.teachers_tree.insert("", "end", iid=teacher_id, values=(check, name, main_subject or ""), tags=(tag,))

    def import_teachers_from_excel(self):
        """Import teacher records from an Excel file into the `teachers` table.

        Required Excel columns (exact names): 'Name', 'Degree', 'Main Subject', 'Subjects'
        Blank rows (no Name) are ignored. Rows are inserted, existing DB rows are not modified.
        """
        file_path = filedialog.askopenfilename(title="Select Excel file",
                                               filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")])
        if not file_path:
            return

        try:
            import pandas as pd
            df = pd.read_excel(file_path, dtype=str)
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to read Excel file:\n{e}")
            return

        required_cols = ["Name", "Degree", "Main Subject", "Subjects"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            messagebox.showerror("Import Error", f"Missing required columns: {', '.join(missing)}")
            return

        inserted = 0
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            for _, row in df.iterrows():
                name = row.get("Name")
                # Ignore blank rows (no name)
                if pd.isna(name):
                    continue
                name_str = str(name).strip()
                if not name_str:
                    continue

                degree = row.get("Degree")
                degree_str = str(degree).strip() if not pd.isna(degree) else None
                main_subject = row.get("Main Subject")
                main_subject_str = str(main_subject).strip() if not pd.isna(main_subject) else None
                subjects = row.get("Subjects")
                subjects_str = str(subjects).strip() if not pd.isna(subjects) else None

                cursor.execute(
                    "INSERT INTO teachers (name, degree, main_subject, subjects) VALUES (?, ?, ?, ?)",
                    (name_str, degree_str, main_subject_str, subjects_str)
                )
                inserted += 1

            conn.commit()
        except Exception as e:
            conn.rollback()
            conn.close()
            messagebox.showerror("Import Error", f"Database error while importing:\n{e}")
            return
        conn.close()

        # Refresh UI
        try:
            self.load_teachers()
        except Exception:
            pass

        messagebox.showinfo("Import Complete", f"Imported {inserted} teacher(s) from Excel.")

    def import_timetable_from_excel(self):
        """Import timetable for the currently selected teacher.

        New rules:
          - Excel/CSV must contain only: Day, Period, Class (case-insensitive column names accepted)
          - The file must NOT contain a teacher column; timetable is imported only for the selected teacher.
          - Existing timetable rows for that teacher are deleted before inserting new rows.
        """
        # Ensure a teacher is selected
        if not getattr(self, 'selected_teacher_id', None):
            messagebox.showerror("Import Error", "Please select a teacher first.")
            return

        file_path = filedialog.askopenfilename(title="Select Timetable file",
                                               filetypes=[("Excel files", "*.xlsx *.xls"), ("CSV files", "*.csv"), ("All files", "*.*")])
        if not file_path:
            return

        try:
            import pandas as pd
            if file_path.lower().endswith('.csv'):
                df = pd.read_csv(file_path, dtype=str)
            else:
                df = pd.read_excel(file_path, dtype=str)
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to read file:\n{e}")
            return

        # Normalize column names (case-insensitive match)
        cols = [c for c in df.columns]
        def find_col(candidates):
            for cand in candidates:
                for c in cols:
                    if c.strip().lower() == cand.strip().lower():
                        return c
            return None

        day_col = find_col(['day', 'day of week', 'day_of_week'])
        period_col = find_col(['period', 'period number', 'period_number'])
        class_col = find_col(['class', 'class name', 'class_name'])
        subject_col = find_col(['subject', 'subjects'])

        if day_col is None or period_col is None or class_col is None:
            messagebox.showerror("Import Error", "Required columns missing. File must include Day, Period and Class columns.")
            return

        # Prepare DB connection. We'll update existing Day+Period rows and insert if missing
        teacher_id = self.selected_teacher_id
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        inserted = 0
        updated = 0
        skipped = 0
        # iterate and update/insert
        try:
            for _, row in df.iterrows():
                # Day
                d = row.get(day_col)
                if pd.isna(d) or not str(d).strip():
                    skipped += 1
                    continue
                day_val = str(d).strip()

                # Period -> int safely
                p = row.get(period_col)
                try:
                    if pd.isna(p):
                        raise ValueError
                    period_num = int(float(str(p).strip()))
                except Exception:
                    skipped += 1
                    continue

                # Class: clean (keep 'FREE' as a valid class name)
                cval = row.get(class_col)
                if pd.isna(cval) or not str(cval).strip():
                    class_name = ''
                else:
                    class_name = str(cval).strip()

                # Subject: optional. If present, trim; empty or NaN -> ''
                subj = ''
                if subject_col:
                    sval = row.get(subject_col)
                    if not pd.isna(sval) and str(sval).strip():
                        subj = str(sval).strip()

                # Try to update an existing row for this teacher/day/period
                cursor.execute("UPDATE timetable SET class_name = ?, subject = ? WHERE teacher_id = ? AND day_of_week = ? AND period_number = ?",
                               (class_name, subj, teacher_id, day_val, period_num))
                if cursor.rowcount == 0:
                    # no existing row -> insert
                    cursor.execute("INSERT INTO timetable (teacher_id, day_of_week, period_number, class_name, subject) VALUES (?, ?, ?, ?, ?)",
                                   (teacher_id, day_val, period_num, class_name, subj))
                    inserted += 1
                else:
                    updated += 1

            conn.commit()
        except Exception as e:
            conn.rollback()
            conn.close()
            messagebox.showerror("Import Error", f"Database error while importing timetable:\n{e}")
            return

        conn.close()

        # Refresh timetable UI for selected teacher
        try:
            # Keep teacher selection state; reload timetable grid
            self.load_timetable_for_teacher()
        except Exception:
            pass

        messagebox.showinfo("Import Complete", f"Imported {inserted} timetable rows for this teacher.")
    
    def on_teacher_selected(self, event):
        """Handle teacher selection"""
        selection = self.teachers_tree.selection()
        if selection:
            # Keep backward-compatible current_teacher_id (string iid)
            self.current_teacher_id = selection[0]
            # Also set explicit integer selected_teacher_id for import API
            try:
                self.selected_teacher_id = int(selection[0])
            except Exception:
                # fallback to None if conversion fails
                self.selected_teacher_id = None

            # Enable import timetable button when a teacher is selected
            try:
                if getattr(self, 'import_timetable_btn', None):
                    self.import_timetable_btn.config(state='normal')
            except Exception:
                pass

            self.load_teacher_details()
            self.load_timetable_for_teacher()
            # Start/restart highlight loop to highlight current class cell
            try:
                self.start_auto_update_highlight()
            except Exception:
                pass
            # Start auto-updating the current/next class status
            self.start_auto_update_status()
        else:
            # No selection: clear both selection variables and disable import button
            self.current_teacher_id = None
            self.selected_teacher_id = None
            try:
                if getattr(self, 'import_timetable_btn', None):
                    self.import_timetable_btn.config(state='disabled')
            except Exception:
                pass
    
    def load_teacher_details(self):
        """Load and display selected teacher's details"""
        if not self.current_teacher_id:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Load subjects CSV as well
        cursor.execute("SELECT name, degree, main_subject, subjects FROM teachers WHERE id = ?", (self.current_teacher_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            # result: name, degree, main_subject, subjects
            try:
                name, degree, main_subject, subjects_csv = result
            except Exception:
                name, degree, main_subject = result
                subjects_csv = None
            self.teacher_name_label.config(text=name)
            # show bold prefix and normal value separately
            self.teacher_degree_prefix.config(text="Degree:")
            self.teacher_degree_label.config(text=f"{degree or 'N/A'}")
            # Prefer to show the stored subjects CSV if available; otherwise show main_subject
            if subjects_csv and subjects_csv.strip():
                self.teacher_subject_label.config(text=f"Subjects: {subjects_csv}")
            else:
                self.teacher_subject_label.config(text=f"Main Subject: {main_subject or 'N/A'}")
            # Update status display immediately
            try:
                self.update_current_status()
            except Exception:
                # Safe guard: don't crash UI if status update fails
                pass

    
    def load_timetable_for_teacher(self):
        """Load timetable entries for selected teacher"""
        if not self.current_teacher_id:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, day_of_week, period_number, class_name, subject FROM timetable 
               WHERE teacher_id = ? ORDER BY 
               CASE day_of_week 
                   WHEN 'Monday' THEN 1
                   WHEN 'Tuesday' THEN 2
                   WHEN 'Wednesday' THEN 3
                   WHEN 'Thursday' THEN 4
                   WHEN 'Friday' THEN 5
                   WHEN 'Saturday' THEN 6
               END, period_number""",
            (self.current_teacher_id,)
        )
        entries = cursor.fetchall()
        conn.close()
        
        # Clear grid buttons
        for (day, period), btn in self.grid_buttons.items():
            btn.config(text="", bg=getattr(self, 'default_btn_bg', btn.cget('bg')), fg="#000000")
            # Remove any attached entry id
            if hasattr(btn, 'entry_id'):
                delattr(btn, 'entry_id')

        # Populate grid
        for entry_id, day, period, class_name, subject in entries:
            key = (day, period)
            if key in self.grid_buttons:
                btn = self.grid_buttons[key]
                color = self.get_subject_color(subject)
                btn.config(text=f"{class_name}\n{subject}", bg=color, fg="#000000")
                # Store entry_id on button for easy lookup
                btn.entry_id = entry_id
            else:
                # Unexpected day/period; skip
                pass
        # Update canvas scrollregion after making changes
        self.timetable_grid_frame.update_idletasks()
        self.timetable_canvas.configure(scrollregion=self.timetable_canvas.bbox('all'))
        # Update highlight immediately after populating
        try:
            self.update_highlight()
        except Exception:
            pass

    # ---- Current / Next class logic and auto-update ----
    def get_current_period(self):
        """Return a tuple (status, period_number, minutes_remaining).

        status: 'before' | 'during' | 'after'
        period_number: int or None
        minutes_remaining: int minutes or None
        """
        now_dt = datetime.datetime.now()
        now_time = now_dt.time()

        # Sort periods by number
        periods_sorted = sorted(self.period_times.items())
        if not periods_sorted:
            return ('after', None, None)

        first_start = periods_sorted[0][1][0]
        last_end = periods_sorted[-1][1][1]

        if now_time < first_start:
            return ('before', 1, None)
        if now_time >= last_end:
            return ('after', None, None)

        # Check which period we're in
        for pnum, (start, end) in periods_sorted:
            if start <= now_time < end:
                # compute minutes remaining
                end_dt = datetime.datetime.combine(now_dt.date(), end)
                delta = end_dt - now_dt
                minutes = max(0, int(delta.total_seconds() // 60))
                return ('during', pnum, minutes)

        # Fallback: between periods but after first
        # Determine next period
        for pnum, (start, end) in periods_sorted:
            if now_time < start:
                return ('between', pnum, None)

        return ('after', None, None)

    def get_current_class(self, teacher_id):
        """Return timetable entry for the teacher for the current period (or None).

        Returns a dict with keys: id, class_name, subject, period_number or None.
        """
        status, period_num, minutes = self.get_current_period()
        if status != 'during' or not period_num:
            return None

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        today = datetime.datetime.now().strftime('%A')
        cursor.execute("SELECT id, class_name, subject, period_number FROM timetable WHERE teacher_id = ? AND day_of_week = ? AND period_number = ?",
                       (teacher_id, today, period_num))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {'id': row[0], 'class_name': row[1], 'subject': row[2], 'period_number': row[3]}

    def get_next_class(self, teacher_id):
        """Return the next timetable entry (today) after the current time, or None.

        Returns dict with keys: id, class_name, subject, period_number or None.
        """
        now_status, current_period, _ = self.get_current_period()
        today = datetime.datetime.now().strftime('%A')

        # Create ordered list of period numbers
        ordered_periods = sorted(self.periods)

        # Determine search start
        if now_status == 'before':
            start_index = 0
        elif now_status in ('during', 'between') and current_period:
            # start after the current/next period
            try:
                start_index = ordered_periods.index(current_period) + 1
            except ValueError:
                start_index = 0
        else:
            # after or unknown
            start_index = len(ordered_periods)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for p in ordered_periods[start_index:]:
            cursor.execute("SELECT id, class_name, subject, period_number FROM timetable WHERE teacher_id = ? AND day_of_week = ? AND period_number = ?",
                           (teacher_id, today, p))
            row = cursor.fetchone()
            if row:
                conn.close()
                return {'id': row[0], 'class_name': row[1], 'subject': row[2], 'period_number': row[3]}
        conn.close()
        return None

    def update_current_status(self):
        """Update the StringVars for current time, current status and next class."""
        # Update current time display
        now = datetime.datetime.now()
        self.current_time_var.set(now.strftime('%I:%M %p (%A)'))

        if not self.current_teacher_id:
            self.status_var.set('No teacher selected')
            self.next_var.set('')
            self.remaining_var.set('')
            return

        teacher_id = self.current_teacher_id

        # Determine current period
        status, period_num, minutes = self.get_current_period()

        if status == 'before':
            self.status_var.set('School has not started yet.')
            # Next class (if any)
            nxt = self.get_next_class(teacher_id)
            if nxt:
                self.next_var.set(f"Next: {nxt['class_name']} (Period {nxt['period_number']})")
            else:
                self.next_var.set('No more classes today.')
            self.remaining_var.set('')
            return

        if status == 'after':
            self.status_var.set('School is over for today.')
            self.next_var.set('No more classes today.')
            self.remaining_var.set('')
            return

        if status == 'during':
            current = self.get_current_class(teacher_id)
            if current:
                self.status_var.set(f"Currently teaching: {current['class_name']} (Period {current['period_number']})")
            else:
                self.status_var.set(f"Teacher is FREE right now (Period {period_num})")

            # Next class
            nxt = self.get_next_class(teacher_id)
            if nxt:
                self.next_var.set(f"Next: {nxt['class_name']} (Period {nxt['period_number']})")
            else:
                self.next_var.set('No more classes today.')

            # Minutes remaining
            if minutes is not None:
                self.remaining_var.set(f"{minutes} min remaining in this period")
            else:
                self.remaining_var.set('')
            return

        # between periods
        if status == 'between':
            self.status_var.set(f"Teacher is FREE right now (Before Period {period_num})")
            nxt = self.get_next_class(teacher_id)
            if nxt:
                self.next_var.set(f"Next: {nxt['class_name']} (Period {nxt['period_number']})")
            else:
                self.next_var.set('No more classes today.')
            self.remaining_var.set('')

    def start_auto_update_status(self):
        """Start or restart the 1-minute auto-update for the status area."""
        # Cancel previous
        self.stop_auto_update_status()
        # Update immediately
        try:
            self.update_current_status()
        except Exception:
            pass
        # Schedule next update in 60 seconds
        try:
            self._status_after_id = self.after(60000, self.start_auto_update_status)
        except Exception:
            self._status_after_id = None

    def stop_auto_update_status(self):
        if getattr(self, '_status_after_id', None):
            try:
                self.after_cancel(self._status_after_id)
            except Exception:
                pass
            self._status_after_id = None

    # ---- Highlight loop for current class ----
    def update_highlight(self):
        """Reset all cells to default color and highlight only the selected teacher's current class cell."""
        # Reset all cells first
        default_bg = getattr(self, 'default_btn_bg', None)
        if default_bg is None:
            try:
                default_bg = self.cget('bg')
            except Exception:
                default_bg = "SystemButtonFace"

        for (day, period), btn in self.grid_buttons.items():
            try:
                btn.config(bg=default_bg, fg="#000000")
            except Exception:
                try:
                    btn.configure(background=default_bg)
                except Exception:
                    pass

        # Only highlight if a teacher is selected and we are in a 'during' period
        if not self.current_teacher_id:
            return

        status, period_num, _ = self.get_current_period()
        if status != 'during' or not period_num:
            return

        # Look up if this teacher has a timetable entry right now
        try:
            teacher_id = int(self.current_teacher_id)
        except Exception:
            teacher_id = self.current_teacher_id

        today = datetime.datetime.now().strftime('%A')
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM timetable WHERE teacher_id = ? AND day_of_week = ? AND period_number = ?",
                           (teacher_id, today, period_num))
            row = cursor.fetchone()
        except Exception:
            row = None
        conn.close()

        if row:
            key = (today, period_num)
            btn = self.grid_buttons.get(key)
            if btn:
                # Store the button reference for blinking
                self.current_highlight_btn = btn
                # Start blinking
                self.start_blink_animation()
        else:
            # No class currently, stop blinking
            self.stop_blink_animation()

    def start_blink_animation(self):
        """Start the smooth blinking animation for the current class cell."""
        # Cancel any existing blink animation
        self.stop_blink_animation()
        # Reset simple blink state
        self.blink_state = False
        # Preserve the original background (if button exists) so we can restore it later
        if hasattr(self, 'current_highlight_btn') and self.current_highlight_btn is not None:
            try:
                btn = self.current_highlight_btn
                if not getattr(btn, '_orig_bg', None):
                    btn._orig_bg = btn.cget('bg')
            except Exception:
                pass
        # Schedule first toggle
        try:
            self._blink_after_id = self.after(self.blink_interval, self.blink_highlight)
        except Exception:
            self._blink_after_id = None

    def stop_blink_animation(self):
        """Stop the blinking animation."""
        # Cancel any scheduled blink callback
        if getattr(self, '_blink_after_id', None):
            try:
                self.after_cancel(self._blink_after_id)
            except Exception:
                pass
            self._blink_after_id = None
        # Restore button's original background if available
        if hasattr(self, 'current_highlight_btn') and self.current_highlight_btn is not None:
            try:
                btn = self.current_highlight_btn
                orig = getattr(btn, '_orig_bg', None)
                if orig:
                    btn.config(bg=orig, fg="#000000")
                    try:
                        del btn._orig_bg
                    except Exception:
                        pass
            except Exception:
                pass

    def _interpolate_color(self, color1, color2, factor):
        """Interpolate between two hex colors. factor: 0.0 = color1, 1.0 = color2."""
        def hex_to_rgb(hex_color):
            h = hex_color.lstrip('#')
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        
        def rgb_to_hex(rgb):
            return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))
        
        rgb1 = hex_to_rgb(color1)
        rgb2 = hex_to_rgb(color2)
        
        # Interpolate each channel
        interp = tuple(
            rgb1[i] + (rgb2[i] - rgb1[i]) * factor
            for i in range(3)
        )
        return rgb_to_hex(interp)

    def blink_highlight(self):
        """Toggle blink between original bg and highlight color at blink_interval."""
        if not hasattr(self, 'current_highlight_btn') or self.current_highlight_btn is None:
            return

        btn = self.current_highlight_btn
        try:
            orig = getattr(btn, '_orig_bg', btn.cget('bg'))
            # toggle
            self.blink_state = not self.blink_state
            if self.blink_state:
                btn.config(bg=self.highlight_color, fg="#000000")
            else:
                btn.config(bg=orig, fg="#000000")
        except Exception:
            pass

        try:
            self._blink_after_id = self.after(self.blink_interval, self.blink_highlight)
        except Exception:
            self._blink_after_id = None

    def start_auto_update_highlight(self):
        """Start or restart the 5-second auto-update for the highlight area."""
        # Cancel previous
        self.stop_auto_update_highlight()
        # Update immediately
        try:
            self.update_highlight()
        except Exception:
            pass
        # Schedule next update in 5 seconds
        try:
            self._highlight_after_id = self.after(5000, self.start_auto_update_highlight)
        except Exception:
            self._highlight_after_id = None

    def stop_auto_update_highlight(self):
        if getattr(self, '_highlight_after_id', None):
            try:
                self.after_cancel(self._highlight_after_id)
            except Exception:
                pass
            self._highlight_after_id = None
        # Also stop blinking
        self.stop_blink_animation()

    def edit_period_timings_dialog(self):
        """Open a dialog to edit start/end times for each period."""
        dialog = tk.Toplevel(self)
        dialog.title("Edit Period Timings")
        dialog.geometry("420x400")
        dialog.resizable(False, False)

        main = ttk.Frame(dialog, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="Period", style="Heading.TLabel").grid(row=0, column=0, padx=6, pady=6)
        ttk.Label(main, text="Start (HH:MM)", style="Heading.TLabel").grid(row=0, column=1, padx=6, pady=6)
        ttk.Label(main, text="End (HH:MM)", style="Heading.TLabel").grid(row=0, column=2, padx=6, pady=6)

        entries = {}
        for i, pnum in enumerate(sorted(self.periods), start=1):
            ttk.Label(main, text=f"Period {pnum}:").grid(row=i, column=0, sticky="w", padx=6, pady=4)
            start_str = self.period_times.get(pnum, (datetime.time(0,0), datetime.time(0,0)))[0].strftime('%H:%M')
            end_str = self.period_times.get(pnum, (datetime.time(0,0), datetime.time(0,0)))[1].strftime('%H:%M')
            s_entry = ttk.Entry(main, width=12)
            s_entry.insert(0, start_str)
            s_entry.grid(row=i, column=1, padx=6, pady=4)
            e_entry = ttk.Entry(main, width=12)
            e_entry.insert(0, end_str)
            e_entry.grid(row=i, column=2, padx=6, pady=4)
            entries[pnum] = (s_entry, e_entry)

        button_frame = ttk.Frame(main)
        button_frame.grid(row=i+1, column=0, columnspan=3, pady=(12,0))

        def save_timings():
            # Validate and save to DB
            new_map = {}
            for pnum, (s_e, e_e) in entries.items():
                s_val = s_e.get().strip()
                e_val = e_e.get().strip()
                try:
                    s_t = datetime.time.fromisoformat(s_val)
                    e_t = datetime.time.fromisoformat(e_val)
                except Exception:
                    messagebox.showerror("Validation Error", f"Invalid time format for period {pnum}. Use HH:MM (24-hour).")
                    return
                if s_t >= e_t:
                    messagebox.showerror("Validation Error", f"Start time must be before end time for period {pnum}.")
                    return
                new_map[pnum] = (s_t, e_t)

            # Persist to DB
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            for pnum, (s_t, e_t) in new_map.items():
                cursor.execute("INSERT OR REPLACE INTO period_times (period_number, start, end) VALUES (?, ?, ?)",
                               (pnum, s_t.strftime('%H:%M'), e_t.strftime('%H:%M')))
            conn.commit()
            conn.close()

            # Update in-memory mapping and refresh status/timetable UI
            self.period_times.update(new_map)
            try:
                self.update_current_status()
            except Exception:
                pass
            messagebox.showinfo("Success", "Period timings updated.")
            dialog.destroy()

        ttk.Button(button_frame, text="Save", command=save_timings).pack(side=tk.LEFT, padx=6)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=6)

    
    def add_teacher_dialog(self):
        """Open add teacher dialog"""
        dialog = tk.Toplevel(self)
        dialog.title("Add Teacher")
        # Set dialog size and center it on the screen
        dialog_width, dialog_height = 480, 220
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = int((screen_w - dialog_width) / 2)
        y = int((screen_h - dialog_height) / 2)
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # Allow the entry column to expand
        main_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(main_frame, text="Name:").grid(row=0, column=0, sticky="w", pady=5)
        name_entry = ttk.Entry(main_frame, width=25)
        name_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
        name_entry.focus_set()
        
        ttk.Label(main_frame, text="Degree:").grid(row=1, column=0, sticky="w", pady=5)
        degree_entry = ttk.Entry(main_frame, width=25)
        degree_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
        
        ttk.Label(main_frame, text="Subjects (comma-separated):").grid(row=2, column=0, sticky="w", pady=5)
        # Provide a simple Entry + suggestion combobox to build a CSV list of subjects for the teacher
        try:
            all_subj = self.get_all_subjects()
        except Exception:
            all_subj = []
        subjects_entry = ttk.Entry(main_frame, width=25)
        subjects_entry.grid(row=2, column=1, sticky="ew", pady=5, padx=5)
        # Suggestion combobox + Add button
        subj_suggest = ttk.Combobox(main_frame, width=18, values=all_subj, state='normal')
        subj_suggest.grid(row=2, column=2, sticky="ew", pady=5, padx=5)
        def add_suggested_subject():
            s = subj_suggest.get().strip()
            if not s:
                return
            current = subjects_entry.get().strip()
            parts = [p.strip() for p in current.split(',') if p.strip()]
            if s not in parts:
                parts.append(s)
                subjects_entry.delete(0, tk.END)
                subjects_entry.insert(0, ', '.join(parts))
        ttk.Button(main_frame, text="Add", width=6, command=add_suggested_subject).grid(row=2, column=3, sticky="w", padx=(6,0))
        # Pre-fill the CSV if any
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=15)
        
        def save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Validation Error", "Name is required!")
                return
            
            degree = degree_entry.get().strip() or None
            subjects_csv = subjects_entry.get().strip()
            subject = None
            if subjects_csv:
                # Take the first subject from CSV as main_subject
                parts = [p.strip() for p in subjects_csv.split(',') if p.strip()]
                if parts:
                    subject = parts[0]
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO teachers (name, degree, main_subject, subjects) VALUES (?, ?, ?, ?)",
                         (name, degree, subject, subjects_csv or None))
            conn.commit()
            conn.close()
            
            self.load_teachers()
            dialog.destroy()
            messagebox.showinfo("Success", "Teacher added successfully!")
        
        tk.Button(button_frame, text="Save", command=save,
              bg=self.color_add, fg=self.text_color, font=("Segoe UI", 10, "bold"),
              activebackground="#059669").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=dialog.destroy,
              bg=self.color_exit, fg=self.text_color, font=("Segoe UI", 10, "bold"),
              activebackground="#1174FD").pack(side=tk.LEFT, padx=5)
    
    def edit_teacher_dialog(self):
        """Open edit teacher dialog"""
        if not self.current_teacher_id:
            messagebox.showerror("Error", "Please select a teacher to edit!")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name, degree, main_subject, subjects FROM teachers WHERE id = ?", (self.current_teacher_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return
        
        try:
            name, degree, main_subject, subjects_csv = result
        except Exception:
            name, degree, main_subject = result
            subjects_csv = None
        
        dialog = tk.Toplevel(self)
        dialog.title("Edit Teacher")
        dialog_width, dialog_height = 480, 220
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = int((screen_w - dialog_width) / 2)
        y = int((screen_h - dialog_height) / 2)
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # Allow the entry column to expand
        main_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(main_frame, text="Name:").grid(row=0, column=0, sticky="w", pady=5)
        name_entry = ttk.Entry(main_frame, width=25)
        name_entry.insert(0, name)
        name_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
        name_entry.focus_set()
        
        ttk.Label(main_frame, text="Degree:").grid(row=1, column=0, sticky="w", pady=5)
        degree_entry = ttk.Entry(main_frame, width=25)
        degree_entry.insert(0, degree or "")
        degree_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
        
        ttk.Label(main_frame, text="Subjects (comma-separated):").grid(row=2, column=0, sticky="w", pady=5)
        try:
            all_subj = self.get_all_subjects()
        except Exception:
            all_subj = []
        subjects_entry = ttk.Entry(main_frame, width=25)
        # Pre-fill with subjects if there's a `subjects` CSV, otherwise use `main_subject`
        try:
            # If teacher has 'subjects' csv column, that value will be preferred in `result` earlier
            if subjects_csv and subjects_csv.strip():
                subjects_entry.insert(0, subjects_csv)
            elif main_subject:
                subjects_entry.insert(0, main_subject)
        except Exception:
            pass
        subjects_entry.grid(row=2, column=1, sticky="ew", pady=5, padx=5)
        subj_suggest = ttk.Combobox(main_frame, width=18, values=all_subj, state='normal')
        subj_suggest.grid(row=2, column=2, sticky="ew", pady=5, padx=5)
        def add_suggested_subject_edit():
            s = subj_suggest.get().strip()
            if not s:
                return
            current = subjects_entry.get().strip()
            parts = [p.strip() for p in current.split(',') if p.strip()]
            if s not in parts:
                parts.append(s)
                subjects_entry.delete(0, tk.END)
                subjects_entry.insert(0, ', '.join(parts))
        ttk.Button(main_frame, text="Add", width=6, command=add_suggested_subject_edit).grid(row=2, column=3, sticky="w", padx=(6,0))
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=15)
        
        def update():
            new_name = name_entry.get().strip()
            if not new_name:
                messagebox.showerror("Validation Error", "Name is required!")
                return
            
            new_degree = degree_entry.get().strip() or None
            new_subject = subjects_entry.get().strip()
            # derive main subject as first CSV part
            main_subject_val = None
            if new_subject:
                parts = [p.strip() for p in new_subject.split(',') if p.strip()]
                if parts:
                    main_subject_val = parts[0]
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE teachers SET name = ?, degree = ?, main_subject = ?, subjects = ? WHERE id = ?",
                         (new_name, new_degree, main_subject_val, new_subject, self.current_teacher_id))
            conn.commit()
            conn.close()
            
            self.load_teachers()
            self.load_teacher_details()
            dialog.destroy()
            messagebox.showinfo("Success", "Teacher updated successfully!")
        
        tk.Button(button_frame, text="Update", command=update,
              bg=self.color_edit, fg=self.text_color, font=("Segoe UI", 10, "bold"),
              activebackground="#1D4ED8").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=dialog.destroy,
              bg=self.color_exit, fg=self.text_color, font=("Segoe UI", 10, "bold"),
              activebackground="#4B5563").pack(side=tk.LEFT, padx=5)
    
    def delete_teacher(self):
        """Delete selected teacher"""
        if not self.current_teacher_id:
            messagebox.showerror("Error", "Please select a teacher to delete!")
            return
        
        if messagebox.askyesno("Confirm", "Delete this teacher and all their timetable entries?"):
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM timetable WHERE teacher_id = ?", (self.current_teacher_id,))
            cursor.execute("DELETE FROM teachers WHERE id = ?", (self.current_teacher_id,))
            conn.commit()
            conn.close()
            
            self.current_teacher_id = None
            self.load_teachers()
            
            # Clear details and timetable
            self.teacher_name_label.config(text="No teacher selected")
            self.teacher_degree_label.config(text="")
            self.teacher_subject_label.config(text="")
            # Stop auto-updating status
            try:
                self.stop_auto_update_status()
            except Exception:
                pass
            # Stop highlight loop and reset cells
            try:
                self.stop_auto_update_highlight()
            except Exception:
                pass
            # Clear grid cells
            for (day, period), btn in self.grid_buttons.items():
                btn.config(text="", bg=getattr(self, 'default_btn_bg', btn.cget('bg')), fg="#000000")
                if hasattr(btn, 'entry_id'):
                    delattr(btn, 'entry_id')
            
            messagebox.showinfo("Success", "Teacher deleted successfully!")

    def on_tree_click(self, event):
        """Handle clicks on the teachers treeview. If the Select column was clicked, toggle checkbox state."""
        # Identify the region / column / row clicked
        try:
            col = self.teachers_tree.identify_column(event.x)
            row_iid = self.teachers_tree.identify_row(event.y)
        except Exception:
            return
        # Only handle checkbox toggling when in bulk-delete mode
        if not getattr(self, 'bulk_delete_mode', False):
            return

        # Select column is the first visible column (#1)
        if col == '#1' and row_iid:
            try:
                tid = int(row_iid)
            except Exception:
                # non-integer iid - ignore
                return 'break'

            if tid in self.selected_teacher_ids:
                self.selected_teacher_ids.remove(tid)
                self.teachers_tree.set(row_iid, 'Select', '☐')
            else:
                self.selected_teacher_ids.add(tid)
                self.teachers_tree.set(row_iid, 'Select', '☑')
            # Prevent default selection behavior when toggling checkbox
            return 'break'

    def toggle_bulk_delete_mode(self):
        """Toggle bulk-delete mode: enter mode to select checkboxes, click again to confirm deletion."""
        if not getattr(self, 'bulk_delete_mode', False):
            self.enter_bulk_delete_mode()
        else:
            # In bulk-delete mode: if there are selections, confirm deletion
            if self.selected_teacher_ids:
                # call delete_selected_teachers which does confirmation and deletion
                self.delete_selected_teachers()
            else:
                messagebox.showinfo("No Selection", "No teachers selected for deletion.")
            # Exit mode after action
            self.exit_bulk_delete_mode()

    def enter_bulk_delete_mode(self):
        """Enable bulk-delete mode: show checkboxes and a Cancel button."""
        self.bulk_delete_mode = True
        try:
            self.delete_selected_btn.config(text="Confirm Delete")
        except Exception:
            pass
        try:
            # Show the Select column and Cancel button by adjusting displaycolumns
            self.teachers_tree.config(displaycolumns=("Select", "Name", "Main Subject"))
            self.teachers_tree.column("Select", width=60)
            self.teachers_tree.heading("Select", text="Select")
        except Exception:
            pass
        try:
            self.cancel_bulk_delete_btn.pack(side=tk.LEFT, padx=2)
        except Exception:
            pass
        # Clear any previous selections
        self.selected_teacher_ids.clear()
        # Refresh tree to show checkboxes
        try:
            self.load_teachers()
        except Exception:
            pass

    def exit_bulk_delete_mode(self):
        """Disable bulk-delete mode and hide checkboxes."""
        self.bulk_delete_mode = False
        try:
            self.delete_selected_btn.config(text="        Delete       ")
        except Exception:
            pass
        try:
            # Hide the Select column again by removing it from displaycolumns
            self.teachers_tree.config(displaycolumns=("Name", "Main Subject"))
            self.teachers_tree.column("Select", width=0)
            self.teachers_tree.heading("Select", text="")
        except Exception:
            pass
        try:
            self.cancel_bulk_delete_btn.pack_forget()
        except Exception:
            pass
        # Clear selections and refresh
        self.selected_teacher_ids.clear()
        try:
            self.load_teachers()
        except Exception:
            pass

    def delete_selected_teachers(self):
        """Delete all teachers that are checked in the Select column (with confirmation)."""
        if not getattr(self, 'selected_teacher_ids', None):
            messagebox.showinfo("No Selection", "No teachers selected for deletion.")
            return

        # Confirm list of names to delete
        ids = sorted(list(self.selected_teacher_ids))
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, name FROM teachers WHERE id IN ({','.join(['?']*len(ids))})", tuple(ids))
        rows = cursor.fetchall()
        conn.close()

        names = [r[1] for r in rows]
        if not messagebox.askyesno("Confirm Delete", f"Delete the following teachers and their timetable entries?\n\n" + "\n".join(names)):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Delete timetable rows first
            cursor.execute(f"DELETE FROM timetable WHERE teacher_id IN ({','.join(['?']*len(ids))})", tuple(ids))
            cursor.execute(f"DELETE FROM teachers WHERE id IN ({','.join(['?']*len(ids))})", tuple(ids))
            conn.commit()
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete teachers:\n{e}")
            return

        # Clear selection set and refresh UI
        self.selected_teacher_ids.clear()
        self.current_teacher_id = None
        self.selected_teacher_id = None
        try:
            if getattr(self, 'import_timetable_btn', None):
                self.import_timetable_btn.config(state='disabled')
        except Exception:
            pass

        self.load_teachers()
        # Clear details and timetable grid
        try:
            self.teacher_name_label.config(text="No teacher selected")
            self.teacher_degree_label.config(text="")
            self.teacher_subject_label.config(text="")
        except Exception:
            pass
        for (day, period), btn in self.grid_buttons.items():
            btn.config(text="", bg=getattr(self, 'default_btn_bg', btn.cget('bg')), fg="#000000")
            if hasattr(btn, 'entry_id'):
                delattr(btn, 'entry_id')

        messagebox.showinfo("Success", "Selected teachers deleted successfully!")
    
    def add_period_dialog(self, day=None, period=None):
        """Open add period dialog. If day and period provided, prefill them."""
        if not self.current_teacher_id:
            messagebox.showerror("Error", "Please select a teacher first!")
            return
        
        dialog = tk.Toplevel(self)
        dialog.title("Add Period")
        dialog.geometry("350x250")
        dialog.resizable(False, False)
        
        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Day of Week:").grid(row=0, column=0, sticky="w", pady=8)
        day_combo = ttk.Combobox(main_frame, width=22, 
                                values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                                state="readonly")
        day_combo.grid(row=0, column=1, sticky="ew", pady=8, padx=5)
        
        ttk.Label(main_frame, text="Period Number:").grid(row=1, column=0, sticky="w", pady=8)
        period_entry = ttk.Entry(main_frame, width=25)
        period_entry.grid(row=1, column=1, sticky="ew", pady=8, padx=5)
        # Prefill if provided
        if day:
            day_combo.set(day)
        if period:
            period_entry.insert(0, str(period))
        
        ttk.Label(main_frame, text="Class Name:").grid(row=2, column=0, sticky="w", pady=8)
        # Use a Combobox restricted to classes/sections that the selected teacher teaches
        class_values = ['FREE']
        if self.current_teacher_id:
            try:
                teacher_classes = self.get_teacher_classes(self.current_teacher_id)
                # Prepend FREE and ensure uniqueness
                for c in teacher_classes:
                    if c and c not in class_values:
                        class_values.append(c)
            except Exception:
                pass
        # Make combobox editable so user can type a custom class/section if needed
        class_combo = ttk.Combobox(main_frame, width=22, values=class_values, state='normal')
        class_combo.grid(row=2, column=1, sticky="ew", pady=8, padx=5)
        # Smart default: if teacher has only one class, auto-select it
        if len(class_values) == 2 and class_values[1] != 'FREE':
            class_combo.set(class_values[1])
        
        ttk.Label(main_frame, text="Subject:").grid(row=3, column=0, sticky="w", pady=8)
        # Populate subject combobox from teacher's allowed subjects + global subjects (editable combobox)
        subject_values = []
        try:
            subject_values = self.get_all_subjects()
        except Exception:
            subject_values = []
        # Add teacher-specific subjects (ensures teacher-specific ones are included)
        if self.current_teacher_id:
            try:
                tsubj = self.get_teacher_subjects(self.current_teacher_id)
                for s in tsubj:
                    if s and s not in subject_values:
                        subject_values.append(s)
            except Exception:
                pass
        subject_values = [s for s in subject_values if s]
        # Make combobox editable so user can type a custom subject
        subject_combo = ttk.Combobox(main_frame, width=22, values=subject_values, state='normal')
        subject_combo.grid(row=3, column=1, sticky="ew", pady=8, padx=5)
        # If only one subject, preselect it
        if len(subject_values) == 1:
            subject_combo.set(subject_values[0])
        else:
            # If the teacher has a main_subject, prefer it
            try:
                if self.current_teacher_id:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT main_subject FROM teachers WHERE id = ?", (self.current_teacher_id,))
                    r = cursor.fetchone()
                    conn.close()
                    if r and r[0]:
                        subject_combo.set(r[0])
            except Exception:
                pass
        # Initially hide/disable subject input if class is FREE
        def update_subject_state():
            try:
                cls = class_combo.get().strip()
            except Exception:
                cls = ''
            if cls and cls.strip().upper() == 'FREE':
                try:
                    subject_combo.set('')
                except Exception:
                    pass
                try:
                    subject_combo.configure(state='disabled')
                except Exception:
                    pass
            else:
                try:
                    subject_combo.configure(state='normal')
                except Exception:
                    pass

        # Bind both selection and typing events to toggle subject enabled state
        class_combo.bind('<<ComboboxSelected>>', lambda e: update_subject_state())
        class_combo.bind('<KeyRelease>', lambda e: update_subject_state())
        # Run initial toggle
        update_subject_state()
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=15)
        
        def save():
            day = day_combo.get().strip()
            period_str = period_entry.get().strip()
            class_name = class_combo.get().strip()
            subject = ''
            try:
                # read from combobox if available
                subject = subject_combo.get().strip()
            except Exception:
                subject = ''
            
            # Subject is optional when class is FREE
            if not day or not period_str or not class_name or (class_name.strip().upper() != 'FREE' and not subject):
                messagebox.showerror("Validation Error", "All fields are required!")
                return
            
            try:
                period = int(period_str)
            except ValueError:
                messagebox.showerror("Validation Error", "Period number must be an integer!")
                return
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Check if an entry already exists for this teacher/day/period
            cursor.execute("SELECT id FROM timetable WHERE teacher_id = ? AND day_of_week = ? AND period_number = ?",
                         (self.current_teacher_id, day, period))
            exists = cursor.fetchone()
            if exists:
                messagebox.showerror("Validation Error", "A period already exists for this day and period! Use Edit instead.")
                conn.close()
                return
            # If this is a FREE period, store empty subject
            if class_name.strip().upper() == 'FREE':
                subject = ''
            cursor.execute("""INSERT INTO timetable (teacher_id, day_of_week, period_number, class_name, subject)
                           VALUES (?, ?, ?, ?, ?)""",
                                                 (self.current_teacher_id, day, period, class_name, subject))
            conn.commit()
            conn.close()
            
            self.load_timetable_for_teacher()
            dialog.destroy()
            messagebox.showinfo("Success", "Period added successfully!")
        
        ttk.Button(button_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def edit_period_dialog(self, day=None, period=None, period_id=None):
        """Open edit period dialog. If day/period provided, use them to resolve period_id."""
        if not self.current_teacher_id:
            messagebox.showerror("Error", "Please select a teacher first!")
            return
        
        # Resolve period_id if day and period given
        if period_id is None:
            if day is not None and period is not None:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM timetable WHERE teacher_id = ? AND day_of_week = ? AND period_number = ?",
                             (self.current_teacher_id, day, period))
                row = cursor.fetchone()
                conn.close()
                if row:
                    period_id = row[0]
                else:
                    messagebox.showerror("Error", "No period configured for this day and period.")
                    return
            else:
                messagebox.showerror("Error", "Please click a timetable cell to edit, or pass a day/period.")
                return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""SELECT day_of_week, period_number, class_name, subject FROM timetable WHERE id = ?""",
                      (period_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return
        
        day, period, class_name, subject = result
        
        dialog = tk.Toplevel(self)
        dialog.title("Edit Period")
        dialog.geometry("350x250")
        dialog.resizable(False, False)
        
        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Day of Week:").grid(row=0, column=0, sticky="w", pady=8)
        day_combo = ttk.Combobox(main_frame, width=22,
                                values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                                state="readonly")
        day_combo.set(day)
        day_combo.grid(row=0, column=1, sticky="ew", pady=8, padx=5)
        
        ttk.Label(main_frame, text="Period Number:").grid(row=1, column=0, sticky="w", pady=8)
        period_entry = ttk.Entry(main_frame, width=25)
        period_entry.insert(0, str(period))
        period_entry.grid(row=1, column=1, sticky="ew", pady=8, padx=5)
        
        ttk.Label(main_frame, text="Class Name:").grid(row=2, column=0, sticky="w", pady=8)
        # Use Combobox populated with the teacher's classes + FREE. Include current value if not present.
        class_values = ['FREE']
        if self.current_teacher_id:
            try:
                teacher_classes = self.get_teacher_classes(self.current_teacher_id)
                for c in teacher_classes:
                    if c and c not in class_values:
                        class_values.append(c)
            except Exception:
                pass
        # Ensure current class_name is selectable even if not in mapping
        if class_name and class_name not in class_values:
            class_values.append(class_name)
        # Editable combobox: keep allowed values but allow typing custom class names
        class_combo = ttk.Combobox(main_frame, width=22, values=class_values, state='normal')
        class_combo.set(class_name or '')
        class_combo.grid(row=2, column=1, sticky="ew", pady=8, padx=5)
        
        ttk.Label(main_frame, text="Subject:").grid(row=3, column=0, sticky="w", pady=8)
        # Subject combobox populated based on teacher's allowed subjects; include current subject if missing
        subject_values = []
        try:
            subject_values = self.get_all_subjects()
        except Exception:
            subject_values = []
        if self.current_teacher_id:
            try:
                tsubj = self.get_teacher_subjects(self.current_teacher_id)
                for s in tsubj:
                    if s and s not in subject_values:
                        subject_values.append(s)
            except Exception:
                pass
        # Ensure current subject is selectable
        if subject and subject not in subject_values:
            subject_values.append(subject)
        subject_values = [s for s in subject_values if s]
        subject_combo = ttk.Combobox(main_frame, width=22, values=subject_values, state='normal')
        subject_combo.set(subject or '')
        subject_combo.grid(row=3, column=1, sticky="ew", pady=8, padx=5)
        # Disable subject combobox when class is FREE
        def update_subject_state_edit():
            try:
                cls = class_combo.get().strip()
            except Exception:
                cls = ''
            if cls and cls.strip().upper() == 'FREE':
                try:
                    subject_combo.set('')
                except Exception:
                    pass
                try:
                    subject_combo.configure(state='disabled')
                except Exception:
                    pass
            else:
                try:
                    subject_combo.configure(state='normal')
                except Exception:
                    pass

        class_combo.bind('<<ComboboxSelected>>', lambda e: update_subject_state_edit())
        class_combo.bind('<KeyRelease>', lambda e: update_subject_state_edit())
        # Run initial toggle
        update_subject_state_edit()
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=15)
        
        def update():
            new_day = day_combo.get().strip()
            new_period_str = period_entry.get().strip()
            new_class = class_combo.get().strip()
            try:
                new_subject = subject_combo.get().strip()
            except Exception:
                new_subject = ''
            
            if not new_day or not new_period_str or not new_class or (new_class.strip().upper() != 'FREE' and not new_subject):
                messagebox.showerror("Validation Error", "All fields are required!")
                return
            
            try:
                new_period = int(new_period_str)
            except ValueError:
                messagebox.showerror("Validation Error", "Period number must be an integer!")
                return
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if new_class.strip().upper() == 'FREE':
                new_subject = ''
            cursor.execute("""UPDATE timetable SET day_of_week = ?, period_number = ?, class_name = ?, subject = ?
                           WHERE id = ?""",
                         (new_day, new_period, new_class, new_subject, period_id))
            conn.commit()
            conn.close()
            
            self.load_timetable_for_teacher()
            dialog.destroy()
            messagebox.showinfo("Success", "Period updated successfully!")
        
        tk.Button(button_frame, text="Update", command=update).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def delete_period(self):
        """Delete selected period"""
    def delete_period(self, day=None, period=None, period_id=None):
        """Delete a period by id or by day/period."""
        if not self.current_teacher_id:
            messagebox.showerror("Error", "Please select a teacher first!")
            return

        # Resolve period_id if needed
        if period_id is None:
            if day is None or period is None:
                messagebox.showerror("Error", "Please click a timetable cell to delete, or pass a day/period.")
                return
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM timetable WHERE teacher_id = ? AND day_of_week = ? AND period_number = ?",
                          (self.current_teacher_id, day, period))
            row = cursor.fetchone()
            conn.close()
            if not row:
                messagebox.showerror("Error", "No period exists for that day and period.")
                return
            period_id = row[0]

        if messagebox.askyesno("Confirm", "Delete this period?"):
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM timetable WHERE id = ?", (period_id,))
            conn.commit()
            conn.close()
            self.load_timetable_for_teacher()
            messagebox.showinfo("Success", "Period deleted successfully!")

    def get_teacher_classes(self, teacher_id):
        """Return a list of classes/sections that the teacher teaches.

        This function attempts several ways to read the teacher -> classes mapping without
        changing the existing storage:
        1. If a helper table exists (commonly named `teacher_classes` or `teacher_sections`),
           read from it (columns expected: teacher_id, class_name).
        2. If the `teachers` table contains a column like `classes` or `class_list` with
           comma-separated values, parse that.
        3. Fallback: derive distinct `class_name` values from the `timetable` table for that teacher.

        Returns a list of class strings (e.g. ['XI-E','XI-F']) or empty list.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1) Common helper tables to check
        candidate_tables = ['teacher_classes', 'teacher_sections', 'teacher_teaches', 'teacher_mapping']
        for tbl in candidate_tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
            if cursor.fetchone():
                try:
                    cursor.execute(f"SELECT class_name FROM {tbl} WHERE teacher_id = ?", (teacher_id,))
                    rows = cursor.fetchall()
                    classes = [r[0] for r in rows if r and r[0]]
                    if classes:
                        conn.close()
                        return sorted(list(dict.fromkeys(classes)))
                except Exception:
                    # table exists but schema unexpected; continue
                    pass

        # 2) Check `teachers` table for a column that may store comma-separated classes
        try:
            cursor.execute("PRAGMA table_info(teachers)")
            cols = [r[1].lower() for r in cursor.fetchall()]
            for col in ('classes', 'class_list', 'sections', 'teaches'):
                if col in cols:
                    cursor.execute(f"SELECT {col} FROM teachers WHERE id = ?", (teacher_id,))
                    row = cursor.fetchone()
                    if row and row[0]:
                        # Assume comma-separated values
                        parts = [p.strip() for p in str(row[0]).split(',') if p.strip()]
                        conn.close()
                        return sorted(list(dict.fromkeys(parts)))
        except Exception:
            pass

        # 3) Fallback: select distinct class_name from timetable for this teacher
        try:
            cursor.execute("SELECT DISTINCT class_name FROM timetable WHERE teacher_id = ?", (teacher_id,))
            rows = cursor.fetchall()
            classes = [r[0] for r in rows if r and r[0]]
            conn.close()
            return sorted(list(dict.fromkeys(classes)))
        except Exception:
            conn.close()
            return []

    def get_teacher_subjects(self, teacher_id):
        """Return a list of subjects that the teacher teaches.

        Strategy similar to `get_teacher_classes`:
        1) Try helper tables with `subject` column.
        2) Check `teachers` table for comma-separated subject fields (e.g. 'subjects').
        3) Fallback to distinct `subject` values from `timetable` for that teacher.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        candidate_tables = ['teacher_subjects', 'teacher_mapping', 'teacher_teaches', 'teacher_info']
        for tbl in candidate_tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
            if cursor.fetchone():
                try:
                    cursor.execute(f"SELECT subject FROM {tbl} WHERE teacher_id = ?", (teacher_id,))
                    rows = cursor.fetchall()
                    subjects = [r[0] for r in rows if r and r[0]]
                    if subjects:
                        conn.close()
                        return sorted(list(dict.fromkeys(subjects)))
                except Exception:
                    pass

        # Check teachers table for a CSV-like column named 'subjects' or similar
        try:
            cursor.execute("PRAGMA table_info(teachers)")
            cols = [r[1].lower() for r in cursor.fetchall()]
            for col in ('subjects', 'subject_list', 'teaches_subjects'):
                if col in cols:
                    cursor.execute(f"SELECT {col} FROM teachers WHERE id = ?", (teacher_id,))
                    row = cursor.fetchone()
                    if row and row[0]:
                        parts = [p.strip() for p in str(row[0]).split(',') if p.strip()]
                        conn.close()
                        return sorted(list(dict.fromkeys(parts)))
        except Exception:
            pass

        # Fallback: distinct subjects from timetable
        try:
            cursor.execute("SELECT DISTINCT subject FROM timetable WHERE teacher_id = ?", (teacher_id,))
            rows = cursor.fetchall()
            subjects = [r[0] for r in rows if r and r[0]]
            # Also include the teacher's `main_subject` (single subject column) if present
            try:
                cursor.execute("SELECT main_subject FROM teachers WHERE id = ?", (teacher_id,))
                r = cursor.fetchone()
                if r and r[0]:
                    subjects.append(r[0])
            except Exception:
                pass
            conn.close()
            return sorted(list(dict.fromkeys(subjects)))
        except Exception:
            conn.close()
            return []

    def get_all_subjects(self):
        """Return a list of all known subjects in the DB (teachers.main_subject + timetable subjects).

        This is used to populate comboboxes with suggestions while remaining editable.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        subjects = set()
        try:
            # Distinct subjects from timetable
            cursor.execute("SELECT DISTINCT subject FROM timetable")
            rows = cursor.fetchall()
            for r in rows:
                if r and r[0]:
                    subjects.add(r[0].strip())
        except Exception:
            pass
        try:
            # Teachers main_subject and subjects lists
            cursor.execute("SELECT DISTINCT main_subject, subjects FROM teachers")
            rows = cursor.fetchall()
            for main, subj_csv in rows:
                if main and main.strip():
                    subjects.add(main.strip())
                if subj_csv and subj_csv.strip():
                    parts = [p.strip() for p in str(subj_csv).split(',') if p.strip()]
                    for p in parts:
                        subjects.add(p)
        except Exception:
            pass
        except Exception:
            pass
        conn.close()
        return sorted([s for s in subjects if s])

    def on_cell_click(self, day, period):
        """Called when a timetable cell is left-clicked: add or edit depending on if entry exists."""
        if not self.current_teacher_id:
            messagebox.showerror("Error", "Please select a teacher first!")
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM timetable WHERE teacher_id = ? AND day_of_week = ? AND period_number = ?",
                      (self.current_teacher_id, day, period))
        row = cursor.fetchone()
        conn.close()

        if row:
            self.edit_period_dialog(day, period, period_id=row[0])
        else:
            self.add_period_dialog(day, period)

    def on_cell_right_click(self, event, day, period):
        """Right-click context menu for a timetable cell to Edit or Delete."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Add / Edit", command=lambda d=day, p=period: self.on_cell_click(d, p))
        menu.add_command(label="Delete", command=lambda d=day, p=period: self.delete_period(day=d, period=p))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen on/off (F11). When exiting fullscreen, center with default size."""
        if not getattr(self, "is_fullscreen", False):
            # Enter fullscreen, record previous window state
            self.prev_state = self.state()
            self.attributes("-fullscreen", True)
            self.is_fullscreen = True
        else:
            # Exit fullscreen, restore previous state (maximized or centered)
            self.attributes("-fullscreen", False)
            self.is_fullscreen = False
            if getattr(self, "prev_state", "") == "zoomed":
                try:
                    self.state("zoomed")
                except tk.TclError:
                    self.center_window(*getattr(self, "default_size", (1200, 800)))
            else:
                self.center_window(*getattr(self, "default_size", (1200, 800)))

    def exit_fullscreen(self, event=None):
        if getattr(self, "is_fullscreen", False):
            self.is_fullscreen = False
            self.attributes("-fullscreen", False)
            if getattr(self, "prev_state", "") == "zoomed":
                try:
                    self.state("zoomed")
                    return
                except tk.TclError:
                    pass
            self.center_window(*getattr(self, "default_size", (1200, 800)))

        def center_window(self, width, height):
            """Center the window for the given width and height."""
            self.update_idletasks()
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            x = int((screen_w - width) / 2)
            y = int((screen_h - height) / 2)
            self.geometry(f"{width}x{height}+{x}+{y}")
    
    
if __name__ == "__main__":
    app = TeacherTimetableApp()
    app.mainloop()