import tkinter as tk                 # Standard Tkinter GUI toolkit (base widgets)
from tkinter import ttk, messagebox  # ttk: themed widgets, messagebox: dialogs for info/warning/error
import sqlite3                       # SQLite database for persistent storage
import datetime                      # Date and time utilities
from datetime import datetime as _dt_now  # Alias for current datetime (used for timestamps)
import shutil                             # File operations (copying database for backup)
from tkinter import filedialog, simpledialog  # File dialogs and simple input dialogs
import os                       # OS-level utilities (paths, file existence)
import re                       # Regular expressions (used for filename sanitization)
import pandas as pd             # Data analysis library (Excel/CSV import/export)
from openpyxl import Workbook   # Excel file creation (used for export)
import subprocess               # Running external processes (restart app, open files)
import sys                      # System-specific parameters and functions (script path, interpreter)
import ctypes                   # ShellExecute for elevation

try:
    import customtkinter as ctk
    _USE_CTK = True
except Exception:
    ctk = None
    _USE_CTK = False

# Safe CustomTkinter integration:
# - Do NOT monkey-patch the `tkinter` module or its classes.
# - Create a `BaseTk` alias that uses `ctk.CTk` when available, otherwise `tk.Tk`.
# This lets the app window use CustomTkinter safely while avoiding global
# monkey-patching that can confuse CTk internals during destroy/cleanup.
if _USE_CTK and getattr(ctk, 'CTk', None):
    BaseTk = ctk.CTk
else:
    BaseTk = tk.Tk

class TeacherTimetableApp(BaseTk):
    def __init__(self):
        super().__init__()
        # Start withdrawn to build UI off-screen and avoid initial flicker
        try:
            self.withdraw()
            self._started_withdrawn = True
        except Exception:
            self._started_withdrawn = False
        # Set title including app version read from VERSION.txt (fallback v0.0.0)
        version = self.get_app_version()
        self.title(f"Teacher App — {version}")
        # Start maximized so the window decorations (close button) remain visible
        self.default_size = (1200, 800)  # width, height when not fullscreen
        self.is_fullscreen = True
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
        # Keyboard shortcuts: adjust timetable size (Ctrl + Plus / Ctrl + Minus)
        try:
            # Main bindings (covers common layouts)
            self.bind("<Control-plus>", lambda e: self._change_timetable_size(1))
            self.bind("<Control-=>", lambda e: self._change_timetable_size(1))
            self.bind("<Control-KP_Add>", lambda e: self._change_timetable_size(1))
            self.bind("<Control-minus>", lambda e: self._change_timetable_size(-1))
            self.bind("<Control-KP_Subtract>", lambda e: self._change_timetable_size(-1))
        except Exception:
            pass
        # Global shortcuts
        try:
            self.bind_all('<Control-s>', lambda e: self.focus_search())
            self.bind_all('<Control-S>', lambda e: self.focus_search())
            self.bind_all('<Control-p>', lambda e: self.print_timetable())
            # Ctrl+T to toggle pin/unpin of the selected teacher
            try:
                self.bind_all('<Control-t>', lambda e: self.toggle_pin_current_teacher())
            except Exception:
                pass
        except Exception:
            pass
        
        # Database setup
        self.db_path = "database.db"
        self.create_database()
        # Load persisted settings (e.g. layout_mode) from DB
        try:
            self.load_settings()
        except Exception:
            # If loading settings fails, default to 'new'
            self.layout_mode = 'new'
        # Configure ttk style
        # Initialize theme system then configure style and apply saved theme
        try:
            self.init_themes()
        except Exception:
            self.themes = {}
        self.setup_style()

        # Store the theme to apply later after UI is built (if any)
        try:
            self._saved_theme = self.load_ui_theme()
        except Exception:
            self._saved_theme = None
        
        # Days and periods configuration
        self.days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        self.periods = list(range(1, 9))  # Periods 1 to 8

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
        self.blink_color = "#00FF84"  # bright green
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
        # Layout mode will be loaded from DB during initialization; ensure attribute exists
        if not hasattr(self, 'layout_mode'):
            self.layout_mode = 'new'
        
        # Color scheme for buttons
        self.color_add = "#3EBD3A"      # Green for Add
        self.color_edit = "#3B82F6"     # Blue for Edit
        self.color_delete = "#E93D3D"   # Red for Delete
        self.color_exit = "#E91212"     # Red for Exit
        self.text_color = "#FFFFFF"     # White text
        # Muted color used for timetable cell text to make the subject line appear lighter
        self.timetable_text_muted_color = "#2B2424"
        # Timetable font size (can be adjusted via Settings)
        try:
            val = self.load_setting('timetable_text_size', None)
            self.timetable_font_size = int(val) if val is not None else 12
        except Exception:
            self.timetable_font_size = 12
        
        # Create menu bar
        self.create_menu_bar()
        
        # Build the basic UI quickly, then finish heavy widgets shortly after
        self.create_basic_layout()

        # Load initial (essential) data only: teachers list
        self.load_teachers()

        # Apply saved layout preference (old/new)
        try:
            self.apply_layout_mode()
        except Exception:
            pass

        # Finish the heavier UI parts shortly after showing the window to improve startup time
        try:
            # Build the heavy UI as soon as possible while still withdrawn to avoid flicker
            self.after(0, self.finish_setup)
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
        
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Normal.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("TButton", font=("Segoe UI", 12))
        style.configure("TEntry", font=("Segoe UI", 12))
        # Increase tree font and row height for improved readability
        style.configure("Treeview", font=("Segoe UI", 14), rowheight=35)
        style.configure("Treeview.Heading", font=("Segoe UI", 14, "bold"))

        # Details panel / selected teacher background color
        # Change the hex to your preferred color (light pastel shown here)
        details_bg = "#C4CAC2"
        style.configure("Details.TLabelframe", background=details_bg, bordercolor="#000000",border=8, relief="solid")
        style.configure("Details.TLabelframe.Label", background=details_bg, font=("Segoe UI", 16, "bold"))
        # New styles: bold name and bold detail lines
        # Larger fonts for the Selected Teacher panel for better readability
        style.configure("Details.Name.TLabel", background=details_bg, font=("Segoe UI", 20, "bold"))
        style.configure("Details.Info.TLabel", background=details_bg, font=("Segoe UI", 16, "bold"))
        style.configure("Details.TLabel", background=details_bg, font=("Segoe UI", 18))
        # Slim scrollbar style for teacher list
        try:
            style.configure('Slim.Vertical.TScrollbar', background='#9CA3AF', troughcolor='#E5E7EB',
                             bordercolor="#000000", arrowcolor='#374151')
        except Exception:
            pass

    # --- Theme system ---
    def init_themes(self):
        """Define available themes and their color tokens."""
        self.themes = {
            "oled": {
                "bg_frame": "#000000",
                "panel_bg": "#000000",
                "text": "#FFFFFF",
                "btn_bg": "#111111",
                "btn_fg": "#FFFFFF",
                "btn_hover": "#222222",
                "btn_danger": "#EF4444",
                "btn_disabled": "#475569",
                "tree_bg": "#000000",
                "tree_header_bg": "#000000",
                "tree_header_fg": "#FFFFFF",
                "tree_row_even": "#000000",
                "tree_row_odd": "#111111",
                "cell_bg": "#000000",
                "cell_text": "#FFFFFF",
                "highlight": "#FFD700",
                "scrollbar_bg": "#000000",
            }
        }

    def load_ui_theme(self):
        """Do not load theme from database. Return None to use default tkinter colors."""
        return None

    def change_theme(self, theme_key):
        """Apply theme without persisting (do not save to database)."""
        if theme_key not in self.themes:
            messagebox.showerror("Theme Error", f"Unknown theme: {theme_key}")
            return
        try:
            self.apply_theme(theme_key)
            # Do NOT save theme to database - no persistence
        except Exception as e:
            messagebox.showerror("Theme Error", f"Failed to apply theme: {e}")

    def apply_theme(self, theme_name):
        """Apply colors from theme across ttk styles and tk widgets immediately.

        This updates ttk.Style entries and also updates existing tk widgets so
        the UI updates without restart.
        """
        if theme_name not in self.themes:
            return
        t = self.themes[theme_name]
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        # If CustomTkinter is available, set appearance mode
        try:
            if _USE_CTK and ctk:
                # map theme to CTk appearance mode: light vs dark
                if theme_name in ('light', 'pastel'):
                    ctk.set_appearance_mode('light')
                else:
                    ctk.set_appearance_mode('dark')
        except Exception:
            pass

        # Frames and labels
        try:
            style.configure('TFrame', background=t['bg_frame'])
            style.configure('TLabel', background=t['bg_frame'], foreground=t['text'])
            style.configure('Title.TLabel', background=t['bg_frame'], foreground=t['text'])
            style.configure('Normal.TLabel', background=t['bg_frame'], foreground=t['text'])
            style.configure('Heading.TLabel', background=t['bg_frame'], foreground=t['text'])
            style.configure('Details.TLabelframe', background=t.get('panel_bg', t['bg_frame']))
            style.configure('Details.TLabelframe.Label', background=t.get('panel_bg', t['bg_frame']), foreground=t['text'])
            style.configure('Details.Name.TLabel', background=t.get('panel_bg', t['bg_frame']), foreground=t['text'])
            style.configure('Details.Info.TLabel', background=t.get('panel_bg', t['bg_frame']), foreground=t['text'])
        except Exception:
            pass

        # Treeview
        try:
            style.configure('Treeview', background=t['tree_bg'], fieldbackground=t['tree_bg'], foreground=t['text'])
            style.configure('Treeview.Heading', background=t['tree_header_bg'], foreground=t['tree_header_fg'])
        except Exception:
            pass

        # Buttons (ttk)
        try:
            style.configure('TButton', background=t['btn_bg'], foreground=t['btn_fg'])
        except Exception:
            pass

        # Option defaults
        try:
            self.option_add('*Button.Background', t['btn_bg'])
            self.option_add('*Button.Foreground', t['btn_fg'])
            self.option_add('*Entry.Background', t.get('panel_bg', '#FFFFFF'))
            self.option_add('*Entry.Foreground', t['text'])
        except Exception:
            pass

        # Update existing widgets explicitly (supports both tk and CTk wrappers)
        try:
            # card frames
            if hasattr(self, 'card_frame'):
                try:
                    # CTkFrame uses fg_color
                    try:
                        self.card_frame.configure(fg_color=t.get('panel_bg', t['bg_frame']))
                    except Exception:
                        self.card_frame.config(background=t.get('panel_bg', t['bg_frame']))
                except Exception:
                    pass
            if hasattr(self, 'card_frame_right'):
                try:
                    try:
                        self.card_frame_right.configure(fg_color=t.get('panel_bg', t['bg_frame']))
                    except Exception:
                        self.card_frame_right.config(background=t.get('panel_bg', t['bg_frame']))
                except Exception:
                    pass

            # canvas
            if hasattr(self, 'timetable_canvas'):
                try:
                    self.timetable_canvas.config(bg=t.get('cell_bg', t['bg_frame']))
                except Exception:
                    pass

            # search entry
            try:
                if hasattr(self, 'search_entry'):
                    try:
                        self.search_entry.configure(fg_color=t.get('panel_bg', '#FFFFFF'))
                    except Exception:
                        self.search_entry.config(bg=t.get('panel_bg', '#FFFFFF'))
                    try:
                        self.search_entry.config(fg=t.get('text', '#000000'))
                    except Exception:
                        pass
            except Exception:
                pass

            # treeview row tags
            try:
                self.teachers_tree.tag_configure('evenrow', background=t.get('tree_row_even', t['tree_bg']))
                self.teachers_tree.tag_configure('oddrow', background=t.get('tree_row_odd', t['tree_bg']))
            except Exception:
                pass

            # scrollbar
            try:
                if getattr(self, 'teachers_vscroll', None):
                    try:
                        self.teachers_vscroll.configure(fg_color=t.get('scrollbar_bg', '#E5E7EB'))
                    except Exception:
                        self.teachers_vscroll.config(bg=t.get('scrollbar_bg', '#E5E7EB'))
            except Exception:
                pass

            # Try to update any stored button-like widgets; attempt CTk-style then tk-style
            for name, w in list(self.__dict__.items()):
                try:
                    try:
                        # CTk-style
                        w.configure(fg_color=t.get('btn_bg', '#3EBD3A'), text_color=t.get('btn_fg', '#FFFFFF'), hover_color=t.get('btn_hover', '#059669'))
                    except Exception:
                        # tk-style fallback
                        try:
                            w.config(bg=t.get('btn_bg', '#3EBD3A'), fg=t.get('btn_fg', '#FFFFFF'), activebackground=t.get('btn_hover', '#059669'))
                        except Exception:
                            pass
                except Exception:
                    pass

            # timetable grid buttons - set text color only, keep background default
            try:
                for key, btn in getattr(self, 'grid_buttons', {}).items():
                    try:
                        # Set text color where supported
                        try:
                            btn.configure(text_color=t.get('cell_text', t['text']))
                        except Exception:
                            try:
                                btn.config(fg=t.get('cell_text', t['text']))
                            except Exception:
                                pass
                        # Keep background as default; do not apply colored backgrounds to cells
                    except Exception:
                        pass
            except Exception:
                pass

        except Exception:
            pass

        # Update instance-level tokens used elsewhere
        try:
            self.timetable_text_muted_color = t.get('cell_text', self.timetable_text_muted_color)
            self.default_btn_bg = t.get('cell_bg', getattr(self, 'default_btn_bg', self.cget('bg')))
            self.blink_color = t.get('highlight', self.blink_color)
            self.color_add = t.get('btn_bg', self.color_add)
            self.color_edit = t.get('btn_bg', self.color_edit)
            self.color_delete = t.get('btn_danger', self.color_delete)
            self.color_exit = t.get('btn_danger', self.color_exit)
            self.text_color = t.get('btn_fg', self.text_color)
        except Exception:
            pass

        # Refresh dynamic areas
        try:
            self.load_teachers()
        except Exception:
            pass
        try:
            self.load_timetable_for_teacher()
        except Exception:
            pass

    def create_menu_bar(self):
        """Create a simplified menu bar: File, Edit, View, Tools, Help."""
        menu_font = ("Segoe UI", 13)
        menubar = tk.Menu(self, font=menu_font)
        self.config(menu=menubar)

        # --- File ---
        file_menu = tk.Menu(menubar, tearoff=0, font=menu_font)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Import Teachers from Excel", command=self.import_teachers_from_excel)
        file_menu.add_command(label="Import Timetable from Excel", command=self.import_timetable_from_excel)
        file_menu.add_command(label="Export Teachers", command=self.export_teachers_to_excel)
        file_menu.add_command(label="Export Timetable", command=self.export_timetable_to_excel)
        file_menu.add_separator()
        file_menu.add_command(label="Backup Database...", command=self.backup_database)
        file_menu.add_separator()
        file_menu.add_command(label="Restart App", command=self.restart_app)
        # Add option to run the installer uninstaller (Inno Setup creates `unins000.exe`)
        file_menu.add_separator()
        file_menu.add_command(label="Delete App", command=self.delete_app)
        file_menu.add_command(label="Exit", command=self.quit)

        # --- Edit ---
        edit_menu = tk.Menu(menubar, tearoff=0, font=menu_font)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Add Teacher", command=self.add_teacher_dialog)
        edit_menu.add_command(label="Edit Teacher", command=self.edit_teacher_dialog)
        edit_menu.add_command(label="Delete Teacher", command=self.toggle_bulk_delete_mode)
        edit_menu.add_separator()
        edit_menu.add_command(label="Add Period", command=self.add_period_dialog)
        # edit_menu.add_command(label="Edit Period", command=self.edit_period_dialog)
        edit_menu.add_command(label="Delete Period", command=self.delete_period)

        # --- View ---
        view_menu = tk.Menu(menubar, tearoff=0, font=menu_font)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Layout Mode (Old/New)", command=self.toggle_layout_mode)
        view_menu.add_command(label="Adjust Timetable size", command=self.adjust_timetable_text_size_dialog)
        view_menu.add_command(label="Dark mode (OLED)", command=lambda: self.change_theme('oled'))
        # view_menu.add_command(label="Toggle Toolbar / Show Buttons", command=self.toggle_toolbar)

        # --- Tools ---
        tools_menu = tk.Menu(menubar, tearoff=0, font=menu_font)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        # tools_menu.add_command(label="Edit Period Timings", command=self.edit_period_timings_dialog)
        tools_menu.add_command(label="Change Blink Interval", command=self.change_blink_interval_dialog)
        tools_menu.add_command(label="Manage Colors", command=self.manage_colors_dialog)
        tools_menu.add_separator()
        tools_menu.add_command(label="Print Timetable", command=self.print_timetable)
        tools_menu.add_command(label="Print Multiple Timetables", command=self.print_multiple_timetables)

        # --- Help ---
        help_menu = tk.Menu(menubar, tearoff=0, font=menu_font)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="How to Use", command=self.show_help_dialog)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts_dialog)
        help_menu.add_command(label="About", command=self.show_about_dialog)

        # Keep references to menus for keyboard shortcuts that post menus
        try:
            self.menubar = menubar
            # store menu refs in order: File, Edit, View, Tools, Help
            self._menu_refs = [file_menu, edit_menu, view_menu, tools_menu, help_menu]
        except Exception:
            self._menu_refs = []

    def backup_database(self):
        """Backup the application's SQLite database to a user-chosen location.

        Opens a Save As dialog with a sensible default filename, copies
        the `database.db` file using `shutil.copy2`, and shows a success
        or error message.
        """
        try:
            # Prepare default filename: database_bkp_YYYY-MM-DD_HH-MM.db
            ts = _dt_now.now().strftime("%Y-%m-%d_%H-%M")
            default_name = f"database_bkp_{ts}.db"

            path = filedialog.asksaveasfilename(
                title="Backup Database",
                defaultextension=".db",
                initialfile=default_name,
                filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")]
            )

            # User cancelled
            if not path:
                return

            # Ensure source DB exists
            src = getattr(self, 'db_path', 'database.db')
            if not os.path.exists(src):
                messagebox.showerror("Backup Failed", f"Source database not found: {src}")
                return

            # Copy preserving metadata
            shutil.copy2(src, path)

            messagebox.showinfo("Backup Complete", f"Backup saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Backup Failed", str(e))

    def delete_app(self):
        """Launch Inno Setup uninstaller `unins000.exe` from the application folder.

        Behaviour (file-only):
        - Confirm with the user using messagebox
        - Look for `unins000.exe` next to the running executable (supports PyInstaller)
        - If missing, show an error directing user to Windows Settings
        - If found, launch elevated with ShellExecute and quit after a short delay
        """
        try:
            # 1) Confirm
            confirm = messagebox.askyesno("Uninstall", "This will uninstall the application. Continue?")
            if not confirm:
                return

            # 2) Locate application directory (support PyInstaller)
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                # When running as script
                app_dir = os.path.dirname(os.path.abspath(__file__))

            unins_path = os.path.join(app_dir, 'unins000.exe')

            # 3) If missing, show explicit message
            if not os.path.exists(unins_path):
                messagebox.showerror("Uninstaller missing", "Uninstaller missing. Please uninstall from Windows Settings → Apps.")
                return

            # 4) Launch with elevation using ShellExecute
            try:
                ctypes.windll.shell32.ShellExecuteW(None, 'runas', unins_path, None, None, 1)
            except Exception:
                # Fallback to simple spawn if ShellExecute fails
                try:
                    subprocess.Popen([unins_path])
                except Exception:
                    messagebox.showerror('Delete App', 'Failed to launch uninstaller.')
                    return

            # 5) Close the app after a short delay so uninstaller can remove files
            try:
                self.after(300, lambda: (self.quit(), os._exit(0)))
            except Exception:
                try:
                    self.quit()
                    os._exit(0)
                except Exception:
                    pass
        except Exception as e:
            messagebox.showerror('Delete App Failed', str(e))

    def toggle_toolbar(self):
        """Toggle visibility of the toolbar / main buttons (old layout)."""
        try:
            vis = getattr(self, 'toolbar_visible', True)
            if vis:
                try:
                    self.hide_main_buttons()
                except Exception:
                    pass
                self.toolbar_visible = False
            else:
                try:
                    self.show_main_buttons()
                except Exception:
                    pass
                self.toolbar_visible = True
        except Exception:
            # Fallback: ensure toolbar is visible
            try:
                self.show_main_buttons()
                self.toolbar_visible = True
            except Exception:
                pass

    def get_subject_color(self, subject):
        """Return a consistent color for a subject. Always return default background (no colored fill)."""
        # Do not use subject-based colors; keep cells with default background for a cleaner look.
        return getattr(self, 'default_btn_bg', self.cget('bg'))

    # --- Added: subject small-caps formatting helpers ---
    def format_subject(self, text):
        """Convert a subject string into Unicode small-caps-ish characters.

        This method maps standard latin letters to visually smaller Unicode
        small-cap (or similar) characters when available. Characters without a
        small-cap equivalent fall back to lowercase so the second line of the
        timetable cell appears visually smaller without adding extra widgets.
        """
        if not text:
            return ""

        # Cache mapping on the instance to avoid rebuilding on each call
        if not hasattr(self, '_small_caps_map'):
            self._small_caps_map = {
                'a': 'ᴀ', 'b': 'ʙ', 'c': 'c', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ',
                'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
                'o': 'ᴏ', 'p': 'ᴘ', 'q': 'q', 'r': 'ʀ', 's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ',
                'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ'
            }

        out_chars = []
        for ch in str(text):
            lower = ch.lower()
            if lower in self._small_caps_map:
                out_chars.append(self._small_caps_map[lower])
            else:
                # preserve digits, punctuation and unknowns as-is (or lowercased)
                # to avoid introducing unexpected glyphs
                if lower.isalpha():
                    out_chars.append(lower)
                else:
                    out_chars.append(ch)

        return ''.join(out_chars)

    def format_cell(self, label, class_name, subject, show_subject=True):
        """Format and apply text to a timetable cell `label`.

        - Converts `subject` to small-caps using `format_subject`.
        - If show_subject is True, sets the label's text to two lines: "CLASS\nsubject".
        - If show_subject is False, sets the label's text to class_name only.
        - Applies a muted foreground color to the label so the subject
          (already visually smaller) appears lighter while keeping the
          overall layout and widget the same.

        Returns the composed text string for convenience.
        """
        if show_subject:
            formatted_subject = self.format_subject(subject)
            # Emphasize class name by uppercasing it so it stands out on the first line
            class_display = (str(class_name) or '').upper()
            text = f"{class_display}\n{formatted_subject}"
        else:
            text = class_name
        try:
            # Attempt to set a larger font and center alignment for timetable cells
            try:
                label.config(text=text, fg=self.timetable_text_muted_color, font=("Segoe UI", getattr(self, 'timetable_font_size', 12), "bold"), justify='center')
            except Exception:
                label.config(text=text, fg=self.timetable_text_muted_color)
        except Exception:
            # If label cannot be configured for some reason, still return the text
            pass
        return text
    # --- End added helpers ---
    
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
        
        # Settings table for storing small app preferences (layout_mode, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
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
        # Ensure additional columns exist for new features (safe migrations)
        # Add is_pinned if missing
        extras = {
            'is_pinned': 'INTEGER DEFAULT 0'
        }
        for col, col_def in extras.items():
            if col not in cols:
                try:
                    cursor.execute(f"ALTER TABLE teachers ADD COLUMN {col} {col_def}")
                except Exception:
                    # If column already exists or ALTER fails, continue
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

    # --- Settings persistence helpers ---
    def save_setting(self, key, value):
        """Save a simple key/value setting into the settings table."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def load_setting(self, key, default=None):
        """Load a single setting value from settings table or return default."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            if row and row[0] is not None:
                return row[0]
        except Exception:
            pass
        return default

    def _change_timetable_size(self, delta):
        """Adjust timetable font size by `delta` (positive or negative).

        This updates existing grid buttons, updates any open dialog variable,
        and persists the value to settings.
        """
        try:
            cur = int(getattr(self, 'timetable_font_size', 12))
            new = max(8, min(48, cur + int(delta)))
            if new == cur:
                return
            self.timetable_font_size = new
            # update grid buttons
            try:
                for btn in getattr(self, 'grid_buttons', {}).values():
                    try:
                        btn.config(font=("Segoe UI", self.timetable_font_size, "bold"))
                    except Exception:
                        pass
            except Exception:
                pass
            # if dialog is open, update its IntVar so the slider/label reflect change
            try:
                if getattr(self, '_timetable_size_dialog_var', None) is not None:
                    try:
                        self._timetable_size_dialog_var.set(self.timetable_font_size)
                    except Exception:
                        pass
            except Exception:
                pass
            # persist
            try:
                self.save_setting('timetable_text_size', str(self.timetable_font_size))
            except Exception:
                pass
        except Exception:
            pass

    def adjust_timetable_text_size_dialog(self):
        """Open a small dialog allowing the user to adjust timetable size."""
        try:
            dlg = tk.Toplevel(self)
            dlg.title("Adjust Timetable Size")
            dlg.transient(self)
            dlg.grab_set()
            dlg.resizable(False, False)
            frm = ttk.Frame(dlg, padding=12)
            frm.pack(fill=tk.BOTH, expand=True)
            ttk.Label(frm, text="Timetable size:", font=("Segoe UI", 11)).pack(anchor='w')
            orig_size = int(getattr(self, 'timetable_font_size', 12))
            var = tk.IntVar(value=orig_size)
            # expose var so external shortcuts can update dialog while open
            try:
                self._timetable_size_dialog_var = var
            except Exception:
                pass
            # live-updating scale
            scale = tk.Scale(frm, from_=8, to=48, orient='horizontal', variable=var, length=300)
            scale.pack(pady=8)

            # show current value label
            value_label = ttk.Label(frm, text=f"{orig_size}px", font=("Segoe UI", 10))
            value_label.pack(anchor='w')

            btn_frame = ttk.Frame(frm)
            btn_frame.pack(fill=tk.X, pady=(6,0))

            def apply_size(size):
                # apply size to instance (live preview, not persisted)
                try:
                    self.timetable_font_size = int(size)
                except Exception:
                    return
                # Update existing grid buttons to use new font
                try:
                    for btn in getattr(self, 'grid_buttons', {}).values():
                        try:
                            btn.config(font=("Segoe UI", self.timetable_font_size, "bold"))
                        except Exception:
                            pass
                except Exception:
                    pass

            def on_scale(val):
                try:
                    value = int(float(val))
                except Exception:
                    value = getattr(self, 'timetable_font_size', orig_size)
                # update label and apply live
                try:
                    value_label.config(text=f"{value}px")
                except Exception:
                    pass
                apply_size(value)

            # bind live update
            try:
                scale.config(command=on_scale)
            except Exception:
                # fallback: trace the variable
                try:
                    var.trace_add('write', lambda *a: on_scale(var.get()))
                except Exception:
                    pass

            def on_ok():
                # persist chosen value
                try:
                    new_size = int(var.get())
                except Exception:
                    new_size = getattr(self, 'timetable_font_size', orig_size)
                self.timetable_font_size = new_size
                try:
                    self.save_setting('timetable_text_size', str(self.timetable_font_size))
                except Exception:
                    pass
                # clear dialog var
                try:
                    del self._timetable_size_dialog_var
                except Exception:
                    pass
                dlg.destroy()

            def on_cancel():
                # revert to original size
                try:
                    self.timetable_font_size = orig_size
                    for btn in getattr(self, 'grid_buttons', {}).values():
                        try:
                            btn.config(font=("Segoe UI", self.timetable_font_size, "bold"))
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    del self._timetable_size_dialog_var
                except Exception:
                    pass
                dlg.destroy()

            ok = ttk.Button(btn_frame, text="OK", command=on_ok)
            ok.pack(side=tk.LEFT, padx=(0,6))
            cancel = ttk.Button(btn_frame, text="Cancel", command=on_cancel)
            cancel.pack(side=tk.LEFT)
        except Exception:
            messagebox.showerror("Error", "Failed to open text size dialog.")

    def ask_filename_large(self, title, prompt, initial_value=""):
        """Show a larger, modal filename input dialog and return the string or None.

        This dialog is larger than the default `simpledialog.askstring` and
        uses bigger fonts for readability on smaller displays.
        """
        try:
            dlg = tk.Toplevel(self)
            dlg.title(title)
            dlg.transient(self)
            dlg.grab_set()
            # Larger default size and center relative to parent
            try:
                w, h = 520, 140
                x = self.winfo_rootx() + max(20, (self.winfo_width() - w) // 2)
                y = self.winfo_rooty() + max(20, (self.winfo_height() - h) // 2)
                dlg.geometry(f"{w}x{h}+{x}+{y}")
            except Exception:
                pass

            frm = ttk.Frame(dlg, padding=12)
            frm.pack(fill=tk.BOTH, expand=True)
            lbl = ttk.Label(frm, text=prompt, font=("Segoe UI", 12))
            lbl.pack(anchor='w', pady=(0,6))

            var = tk.StringVar(value=initial_value)
            entry = tk.Entry(frm, textvariable=var, font=("Segoe UI", 14), width=40, relief='solid', bd=1)
            entry.pack(fill=tk.X, pady=(0,8))
            try:
                entry.focus()
                entry.selection_range(0, tk.END)
            except Exception:
                pass

            result = {'value': None}

            def on_ok():
                val = var.get().strip()
                if val:
                    result['value'] = val
                dlg.destroy()

            def on_cancel():
                dlg.destroy()

            btn_frame = ttk.Frame(frm)
            btn_frame.pack(fill=tk.X)
            ok = ttk.Button(btn_frame, text="OK", command=on_ok)
            ok.pack(side=tk.LEFT, padx=(0,6))
            cancel = ttk.Button(btn_frame, text="Cancel", command=on_cancel)
            cancel.pack(side=tk.LEFT)

            # allow Enter/Escape
            dlg.bind('<Return>', lambda e: on_ok())
            dlg.bind('<Escape>', lambda e: on_cancel())

            self.wait_window(dlg)
            return result['value']
        except Exception:
            return None

    def load_settings(self):
        """Load settings from DB and populate instance attributes.

        Currently only supports `layout_mode`.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", ("layout_mode",))
            row = cursor.fetchone()
            if row and row[0] in ("old", "new"):
                self.layout_mode = row[0]
            else:
                # default to new layout and persist
                self.layout_mode = 'new'
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("layout_mode", self.layout_mode))
                conn.commit()
            conn.close()
        except Exception:
            # on error, ensure an attribute exists
            self.layout_mode = 'new'

    def apply_layout_mode(self):
        """Apply the loaded layout mode to the UI (show/hide buttons)."""
        try:
            if getattr(self, 'layout_mode', 'new') == 'old':
                self.show_main_buttons()
            else:
                self.hide_main_buttons()
        except Exception:
            pass

    def get_app_version(self):
        """Read VERSION.txt from the app folder and return its text, or default to v0.0.0."""
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            version_file = os.path.join(base, "VERSION.txt")
            if os.path.isfile(version_file):
                with open(version_file, "r", encoding="utf-8") as f:
                    txt = f.read().strip()
                    return txt if txt else "v1.5.1"
            return "v1.5.1"
        except Exception:
            return "v1.5.1"

    def restart_app(self):
        """Restart the application."""
        try:
            # Get the current script path
            script_path = os.path.abspath(__file__)
            # Close the current window
            self.destroy()
            # Restart the app with the same Python interpreter
            subprocess.Popen([sys.executable, script_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to restart app: {e}")
    
    def create_basic_layout(self):
        """Create the two-panel main layout"""
        """Create the two-panel main layout"""
        self.main_frame = ttk.Frame(self)
        # Remove outer horizontal padding so right panel can sit flush against window edge
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=10)
        
        # LEFT PANEL - Teachers
        self.left_frame = ttk.Frame(self.main_frame, width=420)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))
        self.left_frame.pack_propagate(False)
        
        # Card container for Teachers (bordered)
        self.card_frame = tk.Frame(self.left_frame, bd=1, relief='solid', background="#C4CAC2")
        self.card_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        ttk.Label(self.card_frame, text="Teachers", style="Title.TLabel").pack(anchor="w", pady=(6, 8), padx=6)

        # Live search bar for teachers
        search_frame = ttk.Frame(self.card_frame)
        search_frame.pack(fill=tk.X, pady=(0, 6), side=tk.TOP)
        self.search_var = tk.StringVar()
        # Use tk.Entry so we can easily control placeholder fg color
        # Make the search entry shorter and give it a visible border
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=("Segoe UI", 14), width=36, relief='solid', bd=1)
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

        # Show shortcut hint when hovering over the search box
        try:
            self.search_entry.bind('<Enter>', lambda e: self._show_hint(e, 'Ctrl+S'))
            self.search_entry.bind('<Leave>', lambda e: self._hide_tooltip())
        except Exception:
            pass

        # Teachers Treeview with slim vertical scrollbar
        # Wrap the Treeview in a frame so we can place a thin scrollbar beside it
        # Make the tree frame expand and leave space at the bottom for pinned buttons
        self.teachers_tree_frame = ttk.Frame(self.card_frame)
        self.teachers_tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10), padx=6, side=tk.TOP)
        # Add a Select column for bulk deletion (shows a checkbox-like mark)
        # Create Treeview with Select column present but hidden from display by default
        self.teachers_tree = ttk.Treeview(
            self.teachers_tree_frame,
            columns=("Select", "Name", "Main Subject"),
            displaycolumns=("Name", "Main Subject"),
            height=15,
            show="headings"
        )
        # Hide Select column by default; it will be shown when entering bulk-delete mode
        self.teachers_tree.column("Select", width=0, anchor="center")
        # Reduce Name column width to make it shorter in the UI
        # Wider columns to accommodate larger font and longer names
        self.teachers_tree.column("Name", width=220, stretch=False)
        self.teachers_tree.column("Main Subject", width=160, anchor="center")
        self.teachers_tree.heading("Select", text="Select")
        self.teachers_tree.heading("Name", text="Name")
        self.teachers_tree.heading("Main Subject", text="Main Subject")
        # Vertical scrollbar for Teachers list — use tk.Scrollbar with explicit width and colors for visibility
        try:
            # Create a clearly visible, slightly wider scrollbar to ensure it's noticeable on all platforms
            self.teachers_vscroll = tk.Scrollbar(self.teachers_tree_frame, orient='vertical', command=self.teachers_tree.yview,
            width=12, bg='#D1D5DB', troughcolor='#E5E7EB', activebackground='#9CA3AF')
            self.teachers_tree.configure(yscrollcommand=self.teachers_vscroll.set)
        except Exception:
            # As a last resort, create a basic scrollbar without styling
            try:
                self.teachers_vscroll = tk.Scrollbar(self.teachers_tree_frame, orient='vertical', command=self.teachers_tree.yview)
                self.teachers_tree.configure(yscrollcommand=self.teachers_vscroll.set)
            except Exception:
                self.teachers_vscroll = None

        # Use grid so the scrollbar occupies its own column and doesn't overlap the Treeview headings
        try:
            self.teachers_tree_frame.grid_rowconfigure(0, weight=1)
            self.teachers_tree_frame.grid_columnconfigure(0, weight=1)
            self.teachers_tree.grid(row=0, column=0, sticky='nsew')
            if self.teachers_vscroll:
                self.teachers_vscroll.grid(row=0, column=1, sticky='ns')
        except Exception:
            # Fallback to pack if grid fails for some reason
            try:
                if self.teachers_vscroll:
                    self.teachers_vscroll.pack(side=tk.RIGHT, fill=tk.Y)
                self.teachers_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            except Exception:
                pass
        # Alternate row colors for readability
        self.teachers_tree.tag_configure('evenrow', background="#fafaff")
        self.teachers_tree.tag_configure('oddrow', background="#e6ebf4")

        # Single-row selection handling (for details/import)
        self.teachers_tree.bind("<<TreeviewSelect>>", self.on_teacher_selected)
        # Click handler for toggling the Select column checkbox
        self.teachers_tree.bind("<Button-1>", self.on_tree_click)
        # Keyboard navigation when tree has focus
        self.teachers_tree.bind('<Up>', lambda e: self._on_tree_up_down('up'))
        self.teachers_tree.bind('<Down>', lambda e: self._on_tree_up_down('down'))
        # Show hint on hover for pinned teachers (stars in the list)
        try:
            self.teachers_tree.bind('<Motion>', self._on_tree_motion)
        except Exception:
            pass
        
        # Teacher buttons
        # Pin teacher buttons to the bottom of the left card so they remain visible
        self.teacher_btn_frame = ttk.Frame(self.card_frame)
        self.teacher_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0), padx=6)
        
        # Buttons moved to the menu bar (Actions). Keep references but do not pack.
        self.add_teacher_btn = tk.Button(self.teacher_btn_frame, text="➕ Add Teacher", command=self.add_teacher_dialog,
            bg=self.color_add, fg=self.text_color, font=("Segoe UI", 12, "bold"),
            activebackground="#059669", cursor="hand2")
        self.edit_teacher_btn = tk.Button(self.teacher_btn_frame, text="Edit Teacher", command=self.edit_teacher_dialog,
            bg=self.color_edit, fg=self.text_color, font=("Segoe UI", 12, "bold"),
            activebackground="#1D4ED8", cursor="hand2")
        # Bulk delete selected teachers (uses the Select column checkboxes)
        self.delete_selected_btn = tk.Button(self.teacher_btn_frame, text="        Delete       ", command=self.toggle_bulk_delete_mode,
            bg=self.color_delete, fg=self.text_color, font=("Segoe UI", 12, "bold"),
            activebackground="#B91C1C", cursor="hand2")
        # Cancel button for bulk-delete mode (created but not packed until needed)
        self.cancel_bulk_delete_btn = tk.Button(self.teacher_btn_frame, text="Cancel", command=self.exit_bulk_delete_mode,
            bg="#6B7280", fg=self.text_color, font=("Segoe UI", 12, "bold"),
            activebackground="#4B5563", cursor="hand2")
        # Bulk confirm frame (hidden by default) contains Confirm and Cancel buttons shown during bulk-delete
        self.bulk_confirm_frame = ttk.Frame(self.card_frame)
        self.confirm_bulk_delete_btn = tk.Button(self.bulk_confirm_frame, text="Confirm Delete", command=self.delete_selected_teachers,
            bg=self.color_delete, fg=self.text_color, font=("Segoe UI", 12, "bold"), activebackground="#B91C1C", cursor="hand2")
        self.cancel_bulk_btn = tk.Button(self.bulk_confirm_frame, text="Cancel", command=self.exit_bulk_delete_mode,
            bg="#6B7280", fg=self.text_color, font=("Segoe UI", 12, "bold"), activebackground="#4B5563", cursor="hand2")
        # Import teachers button placed on its own row to ensure visibility
        # Pin import button area to bottom as well
        self.import_btn_frame = ttk.Frame(self.card_frame)
        self.import_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 6), padx=6)
        # Import button moved to Actions menu; keep widget reference but do not pack.
        self.import_teachers_btn = tk.Button(self.import_btn_frame, text="📥 Import Teachers from Excel", command=self.import_teachers_from_excel,
            bg=self.color_add, fg=self.text_color, font=("Segoe UI", 11, "bold"),
            activebackground="#059669", cursor="hand2")
        
        # RIGHT PANEL - Timetable
        self.right_frame = ttk.Frame(self.main_frame)
        # Pin the right frame to the right edge (no horizontal padding)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=0)

        # Card container for Selected Teacher + Timetable (bordered)
        self.card_frame_right = tk.Frame(self.right_frame, bd=1, relief='solid', background="#C4CAC2")
        self.card_frame_right.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Teacher details (inside the right card)
        # apply the Details style so the frame (and its label area) show color
        details_frame = ttk.LabelFrame(self.card_frame_right, text="Selected Teacher", padding=10, style="Details.TLabelframe")
        details_frame.pack(fill=tk.X, pady=(0, 10), padx=6)

        # Top row: name area with next/prev buttons and pin
        top_row = ttk.Frame(details_frame)
        top_row.pack(fill=tk.X)

        # Name and controls frame
        name_ctrl_frame = ttk.Frame(top_row)
        name_ctrl_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ctrl_row = ttk.Frame(name_ctrl_frame)
        ctrl_row.pack(fill=tk.X)

        # Teacher name label (previous/next arrows removed per user request)
        self.teacher_name_label = ttk.Label(ctrl_row, text="No teacher selected", style="Details.Name.TLabel")
        self.teacher_name_label.pack(side=tk.LEFT, anchor='w')

        # Pin button (star)
        self.pin_btn = tk.Button(ctrl_row, text="☆", command=self.toggle_pin_current_teacher, cursor='hand2')
        self.pin_btn.pack(side=tk.RIGHT)
        try:
            self.pin_btn.bind('<Enter>', lambda e: self._show_hint(e, 'Ctrl+T'))
            self.pin_btn.bind('<Leave>', lambda e: self._hide_tooltip())
        except Exception:
            pass

        # Degree row: bold "Degree:" prefix and normal-weight value label
        degree_frame = ttk.Frame(details_frame)
        degree_frame.pack(anchor="w", pady=(6,0))
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

        # (No additional contact details fields shown per current configuration)
        
        # Timetable section (grid layout) inside the right card
        ttk.Label(self.card_frame_right, text="Timetable", style="Title.TLabel").pack(anchor="w", pady=(10, 5), padx=6)

        # Use a canvas for horizontal scrolling
        self.canvas_frame = ttk.Frame(self.card_frame_right)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=6)

        self.timetable_canvas = tk.Canvas(self.canvas_frame, height=360)
        h_scroll = ttk.Scrollbar(self.canvas_frame, orient='horizontal', command=self.timetable_canvas.xview)
        self.timetable_canvas.configure(xscrollcommand=h_scroll.set)
        # Pin the horizontal scrollbar at the bottom and let the canvas expand above the pinned button bar
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.timetable_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Frame inside canvas that will hold the grid
        self.timetable_grid_frame = ttk.Frame(self.timetable_canvas)
        self.timetable_canvas.create_window((0, 0), window=self.timetable_grid_frame, anchor='nw')

        # Heavy timetable grid and controls will be created later in finish_setup()
        # Prepare placeholders so finish_setup can populate them
        self.grid_buttons = {}  # (day, period) -> button (populated in finish_setup)

    def load_teachers(self):
        """Load all teachers into the treeview"""
        # Preserve current selection so UI actions that reload the list don't clear it
        try:
            prev_selection = set(self.teachers_tree.selection())
        except Exception:
            prev_selection = set()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Order by pinned first, then by name case-insensitive
        cursor.execute("SELECT id, name, main_subject, COALESCE(is_pinned,0) as is_pinned FROM teachers ORDER BY is_pinned DESC, LOWER(name) ASC")
        teachers = cursor.fetchall()
        conn.close()

        # Clear treeview
        for item in self.teachers_tree.get_children():
            self.teachers_tree.delete(item)

        # Populate filtered results preserving alternating colors and checkbox column
        self.visible_teacher_ids = []
        for idx, row in enumerate(teachers):
            teacher_id, name, main_subject, is_pinned = row
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            if getattr(self, 'bulk_delete_mode', False):
                check = '☑' if teacher_id in getattr(self, 'selected_teacher_ids', set()) else '☐'
            else:
                check = ''
            display_name = f"⭐ {name}" if is_pinned else name
            self.teachers_tree.insert("", "end", iid=teacher_id, values=(check, display_name, main_subject or ""), tags=(tag,))
            self.visible_teacher_ids.append(str(teacher_id))

        # Restore any previous selection that still exists
        try:
            for iid in prev_selection:
                if self.teachers_tree.exists(iid):
                    self.teachers_tree.selection_add(iid)
        except Exception:
            pass

    def _show_tooltip(self, event, period, timing):
        """Show a tooltip with period timing on hover."""
        self._hide_tooltip()  # Clear any existing tooltip
        tooltip = tk.Toplevel(self)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
        label = tk.Label(tooltip, text=f"Period {period}\n{timing}", background="#FFFACD", relief="solid", bd=1, font=("Segoe UI", 9), padx=5, pady=3)
        label.pack()
        self._current_tooltip = tooltip

    def _show_hint(self, event, text: str):
        """Show a small hint/tooltip below the cursor with given text."""
        try:
            self._hide_tooltip()
        except Exception:
            pass
        try:
            tooltip = tk.Toplevel(self)
            tooltip.wm_overrideredirect(True)
            # Create label
            label = tk.Label(tooltip, text=text, background="#F3F4F6", relief="solid", bd=1, font=("Segoe UI", 11), padx=6, pady=4)
            label.pack()
            tooltip.update_idletasks()
            # Position directly below cursor
            x = event.x_root - 60
            y = event.y_root + 10
            tooltip.wm_geometry(f"+{x}+{y}")
            self._current_tooltip = tooltip
        except Exception:
            pass

    def _hide_tooltip(self):
        """Hide the tooltip."""
        if hasattr(self, '_current_tooltip') and self._current_tooltip:
            try:
                self._current_tooltip.destroy()
            except Exception:
                pass
            self._current_tooltip = None

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
        
        # Store tooltip ID for later cleanup
        self._tooltip_id = None
        
        for c, period in enumerate(self.periods, start=1):
            start_t, end_t = self.period_times.get(period, (datetime.time(8, 0), datetime.time(9, 0)))
            period_label = ttk.Label(self.timetable_grid_frame, text=f"Period {period}", style=header_style, borderwidth=1, relief="solid", anchor="center", padding=6)
            period_label.grid(row=0, column=c, sticky="nsew")
            
            # Store timing info on the label for tooltip
            timing_text = f"{start_t.strftime('%H:%M')}-{end_t.strftime('%H:%M')}"
            period_label.timing_info = timing_text
            
            # Bind hover events to show/hide tooltip
            period_label.bind("<Enter>", lambda e, p=period, t=timing_text: self._show_tooltip(e, p, t))
            period_label.bind("<Leave>", lambda e: self._hide_tooltip())
            # Click to open Edit Period Timings dialog
            period_label.bind("<Button-1>", lambda e, p=period: self.edit_period_timings_dialog())

        for r, day in enumerate(self.days, start=1):
            # Day label
            ttk.Label(self.timetable_grid_frame, text=day.upper(), style="Normal.TLabel", borderwidth=2, relief="solid", padding=6).grid(row=r, column=0, sticky="nsew")
            for c, period in enumerate(self.periods, start=1):
                # Larger, more readable timetable cell buttons: bigger font and wraplength
                # Create a container frame around the button so we can animate its border/background
                container = tk.Frame(self.timetable_grid_frame, bd=3, relief='solid', highlightthickness=1)
                container.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                btn = tk.Button(container, text="----", width=13, height=2, wraplength=180,
                                font=("Segoe UI", getattr(self, 'timetable_font_size', 12), "bold"),
                                command=lambda d=day, p=period: self.on_cell_click(d, p))
                # leave inner padding so the container frame edge (border) remains visible
                btn.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
                # Right-click context menu to edit/delete
                btn.bind("<Button-3>", lambda e, d=day, p=period: self.on_cell_right_click(e, d, p))
                # Hover tooltip: show "Click to Add/delete" on mouse enter
                btn.bind("<Enter>", lambda e: self._show_hint(e, "Click to Add/delete"))
                btn.bind("<Leave>", lambda e: self._hide_tooltip())
                # store the button and its container, and capture default container background for resetting
                btn._container = container
                self.grid_buttons[(day, period)] = btn
                if not hasattr(self, 'default_btn_bg'):
                    try:
                        self.default_btn_bg = container.cget('bg')
                    except Exception:
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

        # (Tip label removed per user request)

        # Timetable buttons (inside right card)
        self.timetable_btn_frame = ttk.Frame(self.card_frame_right)
        # Pin timetable buttons to the bottom so they remain visible on short screens
        self.timetable_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 6), padx=6)
        # Timetable toolbar actions moved to the Actions menu; keep widget references but do not pack
        self.add_period_btn = tk.Button(self.timetable_btn_frame, text="➕ Add Period", command=self.add_period_dialog,
            bg=self.color_add, fg=self.text_color, font=("Segoe UI", 12, "bold"),
            activebackground="#059669", cursor="hand2")
        # Import timetable button (moved to Actions menu)
        self.import_timetable_btn = tk.Button(self.timetable_btn_frame, text="📄 Import Timetable", command=self.import_timetable_from_excel,
            bg="#0EA5A4", fg=self.text_color, font=("Segoe UI", 11, "bold"),
            activebackground="#0891B2", cursor="hand2", state='disabled')
        self.edit_period_timings_btn = tk.Button(self.timetable_btn_frame, text="🕒 Edit Period Timings", command=self.edit_period_timings_dialog,
            bg="#6B21A8", fg=self.text_color, font=("Segoe UI", 12, "bold"),
            activebackground="#4C1D95", cursor="hand2")
        self.exit_btn = tk.Button(self.timetable_btn_frame, text="Exit", command=self.quit,
            bg=self.color_exit, fg=self.text_color, font=("Segoe UI", 12, "bold"),
            activebackground="#634B4B", cursor="hand2")

        # Small visible Print button on the timetable controls (calls same print flow as Ctrl+P / menu)
        try:
            self.print_timetable_btn = tk.Button(self.timetable_btn_frame, text="🖨️ Print", command=self.print_timetable,
                bg="#374151", fg=self.text_color, font=("Segoe UI", 11, "bold"),
                activebackground="#111827", cursor="hand2")
            self.print_timetable_btn.pack(side=tk.LEFT, padx=6)
        except Exception:
            # If anything goes wrong, don't crash the UI - keep the rest functional
            pass

        # Start highlight auto-update loop now that timetable widgets exist
        try:
            self.start_auto_update_highlight()
        except Exception:
            pass
        # Re-apply layout preference now that all timetable buttons/frames exist
        try:
            self.apply_layout_mode()
        except Exception:
            pass
        
        # Apply the saved theme NOW that all UI widgets are built and visible
        # Only apply if a theme was loaded (skip if None - use default tkinter colors)
        try:
            saved_theme = getattr(self, '_saved_theme', None)
            if saved_theme and saved_theme in self.themes:
                self.apply_theme(saved_theme)
        except Exception:
            pass

        # Ensure the window is visible and maximized on startup to avoid
        # brief flicker or half-size appearance on some platforms (Windows).
        try:
            try:
                self.deiconify()
            except Exception:
                pass
            # Let geometry settle
            try:
                self.update_idletasks()
            except Exception:
                pass
            try:
                if sys.platform.startswith("win"):
                    # Best-effort maximize on Windows
                    self.state("zoomed")
                else:
                    # Fallback: set geometry to full screen size
                    self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
            except Exception:
                pass
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

    def toggle_layout_mode(self):
        """Toggle between old layout (buttons visible) and new layout (buttons in menu)."""
        if getattr(self, 'layout_mode', 'new') == 'new':
            self.layout_mode = 'old'
        else:
            self.layout_mode = 'new'
        # Persist the new setting
        try:
            self.save_setting('layout_mode', self.layout_mode)
        except Exception:
            pass
        # Apply the chosen layout
        try:
            self.apply_layout_mode()
        except Exception:
            pass
        messagebox.showinfo("Layout Changed", f"Switched to {self.layout_mode.upper()} layout mode.")

    def show_main_buttons(self):
        """Show all buttons on the main screen (old layout)."""
        try:
            # Show teacher button frames (pinned to bottom)
            # Pack the three main teacher buttons in the first frame
            self.teacher_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0), padx=6)
            self.add_teacher_btn.pack(side=tk.LEFT, padx=3, pady=5)
            self.edit_teacher_btn.pack(side=tk.LEFT, padx=3, pady=5)
            self.delete_selected_btn.pack(side=tk.LEFT, padx=3, pady=5)
            
            # Pack import button frame below the teacher buttons
            self.import_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 6), padx=6)
            self.import_teachers_btn.pack(side=tk.LEFT, padx=3, pady=5)
            
            # Show timetable button frame
            if hasattr(self, 'timetable_btn_frame'):
                self.timetable_btn_frame.pack(side=tk.TOP, fill=tk.X, pady=(10, 6), padx=6)
            
            # Pack timetable buttons horizontally
            if hasattr(self, 'add_period_btn'):
                self.add_period_btn.pack(side=tk.LEFT, padx=3, pady=5)
            if hasattr(self, 'import_timetable_btn'):
                self.import_timetable_btn.pack(side=tk.LEFT, padx=3, pady=5)
            if hasattr(self, 'edit_period_timings_btn'):
                self.edit_period_timings_btn.pack(side=tk.LEFT, padx=3, pady=5)
            
            # Exit button at the right
            if hasattr(self, 'exit_btn'):
                self.exit_btn.pack(side=tk.RIGHT, padx=3, pady=5)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to show buttons: {e}")

    def hide_main_buttons(self):
        """Hide all buttons from the main screen (new layout)."""
        try:
            # Unpack all buttons
            self.add_teacher_btn.pack_forget()
            self.edit_teacher_btn.pack_forget()
            self.delete_selected_btn.pack_forget()
            self.import_teachers_btn.pack_forget()
            
            if hasattr(self, 'add_period_btn'):
                self.add_period_btn.pack_forget()
            if hasattr(self, 'import_timetable_btn'):
                self.import_timetable_btn.pack_forget()
            if hasattr(self, 'edit_period_timings_btn'):
                self.edit_period_timings_btn.pack_forget()
            if hasattr(self, 'exit_btn'):
                self.exit_btn.pack_forget()
            
            # Hide the button frames to remove extra space
            self.teacher_btn_frame.pack_forget()
            self.import_btn_frame.pack_forget()
            if hasattr(self, 'timetable_btn_frame'):
                self.timetable_btn_frame.pack_forget()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to hide buttons: {e}")

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
        # Include pinned status so pinned teachers can be shown first in filtered results
        cursor.execute(
            "SELECT id, name, main_subject, COALESCE(is_pinned,0) as is_pinned FROM teachers WHERE LOWER(name) LIKE ? OR LOWER(main_subject) LIKE ? ORDER BY is_pinned DESC, LOWER(name) ASC",
            (term_lower, term_lower)
        )
        teachers = cursor.fetchall()
        conn.close()

        # Clear treeview
        for item in self.teachers_tree.get_children():
            self.teachers_tree.delete(item)

        # Populate filtered results with alternating row colors
        self.visible_teacher_ids = []
        for idx, row in enumerate(teachers):
            teacher_id, name, main_subject, is_pinned = row
            self.visible_teacher_ids.append(teacher_id)
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            pin_marker = "★" if is_pinned else ""
            self.teachers_tree.insert("", tk.END, iid=teacher_id, values=("", name, main_subject), tags=(tag,))

    def _on_tree_motion(self, event):
        """Handle motion events on the treeview to show pin hint for starred teachers."""
        try:
            item = self.teachers_tree.identify_row(event.y)
            if not item:
                self._hide_tooltip()
                return
            # Get item values
            values = self.teachers_tree.item(item, 'values')
            if not values:
                self._hide_tooltip()
                return
            # Check if the displayed name starts with a star (pinned)
            display_name = str(values[1]) if len(values) > 1 else ''
            if display_name.startswith('⭐'):
                # Show hint when hovering over pinned teacher
                self._show_hint(event, 'Ctrl+T to Unpin teacher')
            else:
                self._hide_tooltip()
        except Exception:
            pass
        
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

    def export_teachers_to_excel(self):
        """Export all teachers to an Excel file."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name, degree, main_subject, subjects FROM teachers ORDER BY LOWER(name) ASC")
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                messagebox.showwarning("Export", "No teachers to export.")
                return

            # Create DataFrame
            df = pd.DataFrame(rows, columns=["Name", "Degree", "Main Subject", "Subjects"])

            # Ask for filename (in-app) then ask location
            name = self.ask_filename_large("Filename", "Enter filename for teachers export (without extension):", initial_value="teachers_export")
            if not name:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Teachers to Excel",
                initialfile=f"{name}.xlsx",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
            if not file_path:
                return

            # Write to Excel
            df.to_excel(file_path, index=False, sheet_name="Teachers")
            messagebox.showinfo("Export Complete", f"Teachers exported to {file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export teachers:\n{e}")

    def export_timetable_to_excel(self):
        """Export selected teacher's timetable to an Excel file."""
        if not self.current_teacher_id:
            messagebox.showerror("Export Error", "Please select a teacher first.")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get teacher name
            cursor.execute("SELECT name FROM teachers WHERE id = ?", (self.current_teacher_id,))
            teacher_result = cursor.fetchone()
            if not teacher_result:
                messagebox.showerror("Export Error", "Teacher not found.")
                return
            teacher_name = teacher_result[0]

            # Get timetable
            cursor.execute(
                """SELECT day_of_week, period_number, class_name, subject FROM timetable 
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
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                messagebox.showwarning("Export", "No timetable entries to export.")
                return

            # Create DataFrame
            df = pd.DataFrame(rows, columns=["Day", "Period", "Class", "Subject"])

            # Ask for filename (in-app) then ask location
            name = self.ask_filename_large("Filename", f"Enter filename for {teacher_name} timetable export (without extension):", initial_value=f"{teacher_name}_timetable")
            if not name:
                return
            file_path = filedialog.asksaveasfilename(
                title=f"Export Timetable for {teacher_name} to Excel",
                initialfile=f"{name}.xlsx",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
            if not file_path:
                return

            # Write to Excel with formatting
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name=f"{teacher_name}")
                # Get the workbook and worksheet to add some formatting
                workbook = writer.book
                worksheet = writer.sheets[f"{teacher_name}"]
                # Auto-fit columns
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except Exception:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

            messagebox.showinfo("Export Complete", f"Timetable for {teacher_name} exported to {file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export timetable:\n{e}")
    
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
        # Load subjects CSV as well as profile and contact fields
        cursor.execute("SELECT name, degree, main_subject, subjects, COALESCE(is_pinned,0) FROM teachers WHERE id = ?", (self.current_teacher_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            # result: name, degree, main_subject, subjects, is_pinned
            try:
                name, degree, main_subject, subjects_csv, is_pinned = result
            except Exception:
                # Fallback if older schema
                name, degree, main_subject = result[:3]
                subjects_csv = None
                is_pinned = 0
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
            # No editable contact fields to populate (feature removed)
            # Update pin button state
            try:
                self.update_pin_button_state()
            except Exception:
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
            btn.config(text="", bg=getattr(self, 'default_btn_bg', btn.cget('bg')), fg=self.timetable_text_muted_color)
            # Remove any attached entry id
            if hasattr(btn, 'entry_id'):
                delattr(btn, 'entry_id')

        # Check if teacher teaches only one subject
        teacher_subjects = self.get_teacher_subjects(self.current_teacher_id)
        show_subject_in_cells = len(teacher_subjects) > 1
        
        # Populate grid
        for entry_id, day, period, class_name, subject in entries:
            key = (day, period)
            if key in self.grid_buttons:
                btn = self.grid_buttons[key]
                # Format text with subject in smaller/muted representation (using special character)
                # Use format_cell(label, ...) to set the text and apply
                # a muted foreground so the subject appears lighter while the
                # class line remains readable (no extra widgets added).
                # If teacher teaches only one subject, hide the subject and show only class name.
                self.format_cell(btn, class_name, subject, show_subject=show_subject_in_cells)
                # Do not set background color; keep cells with default background for cleaner appearance.
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

    # ----- Navigation, pinning, photo and printing helpers -----
    def _on_tree_up_down(self, direction):
        try:
            if direction == 'up':
                self.previous_teacher()
            else:
                self.next_teacher()
        except Exception:
            pass
        return 'break'

    def sanitize_filename(self, name: str, fallback: str = 'file') -> str:
        """Return a filesystem-safe filename base (no extension)."""
        try:
            if not name:
                return fallback
            # Replace path separators and illegal chars with underscore
            s = str(name).strip()
            # Replace spaces with underscore
            s = s.replace(' ', '_')
            # Remove any characters except alphanum, underscore, dash and dot
            s = re.sub(r'[^A-Za-z0-9_\-\.]+', '', s)
            # Trim length to reasonable size
            return s[:120] if s else fallback
        except Exception:
            return fallback

    def focus_search(self):
        try:
            if getattr(self, 'search_entry', None):
                self.search_entry.focus_set()
                try:
                    self.search_entry.selection_range(0, tk.END)
                except Exception:
                    pass
        except Exception:
            pass

    def post_menu_index(self, idx):
        try:
            if not getattr(self, '_menu_refs', None):
                return
            if idx < 0 or idx >= len(self._menu_refs):
                return
            menu = self._menu_refs[idx]
            # Post menu near window top-left
            x = self.winfo_rootx() + 10
            y = self.winfo_rooty() + 30
            try:
                menu.post(x, y)
            except Exception:
                pass
        except Exception:
            pass

    def select_teacher_by_id(self, iid):
        try:
            if not iid:
                return
            self.teachers_tree.selection_set(iid)
            try:
                self.teachers_tree.see(iid)
            except Exception:
                pass
            # Trigger the same handler used for click selection
            try:
                self.on_teacher_selected(None)
            except Exception:
                pass
        except Exception:
            pass

    def previous_teacher(self):
        try:
            vids = getattr(self, 'visible_teacher_ids', None)
            if not vids:
                vids = list(self.teachers_tree.get_children())
                self.visible_teacher_ids = [str(x) for x in vids]
            cur = str(self.current_teacher_id) if self.current_teacher_id is not None else None
            if not cur or cur not in self.visible_teacher_ids:
                return
            idx = self.visible_teacher_ids.index(cur)
            if idx <= 0:
                # stay on first (simpler behaviour)
                return
            prev_iid = self.visible_teacher_ids[idx - 1]
            self.select_teacher_by_id(prev_iid)
        except Exception:
            pass

    def next_teacher(self):
        try:
            vids = getattr(self, 'visible_teacher_ids', None)
            if not vids:
                vids = list(self.teachers_tree.get_children())
                self.visible_teacher_ids = [str(x) for x in vids]
            cur = str(self.current_teacher_id) if self.current_teacher_id is not None else None
            if not cur or cur not in self.visible_teacher_ids:
                return
            idx = self.visible_teacher_ids.index(cur)
            if idx >= len(self.visible_teacher_ids) - 1:
                return
            next_iid = self.visible_teacher_ids[idx + 1]
            self.select_teacher_by_id(next_iid)
        except Exception:
            pass

    def toggle_pin_current_teacher(self):
        try:
            if not self.current_teacher_id:
                return
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(is_pinned,0) FROM teachers WHERE id = ?", (self.current_teacher_id,))
            row = cursor.fetchone()
            cur = int(row[0]) if row and row[0] is not None else 0
            new = 0 if cur == 1 else 1
            cursor.execute("UPDATE teachers SET is_pinned = ? WHERE id = ?", (new, self.current_teacher_id))
            conn.commit()
            conn.close()
            # Refresh list and UI
            try:
                self.load_teachers()
            except Exception:
                pass
            try:
                self.update_pin_button_state()
            except Exception:
                pass
        except Exception:
            pass

    def update_pin_button_state(self):
        try:
            if not getattr(self, 'pin_btn', None) or not self.current_teacher_id:
                return
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(is_pinned,0) FROM teachers WHERE id = ?", (self.current_teacher_id,))
            row = cursor.fetchone()
            conn.close()
            is_pinned = int(row[0]) if row and row[0] is not None else 0
            # Filled star for pinned
            try:
                self.pin_btn.config(text='★' if is_pinned else '☆')
            except Exception:
                pass
        except Exception:
            pass

    def change_photo_dialog(self):
        # Profile photo feature removed; no operation
        return

    def load_profile_photo(self):
        # Profile photo feature removed; no operation
        return

    # Teacher contact details feature removed: no save_teacher_details method

    def print_timetable(self):
        try:
            if not self.current_teacher_id:
                messagebox.showinfo("No Teacher Selected", "Please select a teacher to print the timetable.")
                return
            # Ask for filename (without extension) first, using teacher name as default, then show Save-As dialog prefilled
            # Try to get teacher name for a better default
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM teachers WHERE id = ?", (self.current_teacher_id,))
                row = cursor.fetchone()
                conn.close()
                teacher_name = row[0] if row else f"teacher_{self.current_teacher_id}"
            except Exception:
                teacher_name = f"teacher_{self.current_teacher_id}"
            default_name = f"{self.sanitize_filename(teacher_name)}_timetable"
            name = self.ask_filename_large("Filename", "Enter filename for timetable PDF (without extension):", initial_value=default_name)
            if not name:
                return
            file_path = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[('PDF files','*.pdf')], title='Save Timetable PDF', initialfile=f"{name}.pdf")
            if not file_path:
                return
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.pdfgen import canvas as pdfcanvas
            except Exception:
                messagebox.showerror("Missing Dependency", "The reportlab library is required to generate PDFs. Install it with: pip install reportlab")
                return
            # Generate PDF for single teacher
            self._generate_pdf_for_teachers([int(self.current_teacher_id)], file_path)
            # Optionally open
            try:
                if sys.platform.startswith('win'):
                    os.startfile(file_path)
                else:
                    subprocess.Popen(['xdg-open', file_path])
            except Exception:
                pass
            messagebox.showinfo("Print Complete", f"Timetable saved to {file_path}")
        except Exception as e:
            messagebox.showerror("Print Error", f"Failed to print timetable: {e}")

    def print_multiple_timetables(self):
        try:
            # Dialog to multi-select teachers
            dlg = tk.Toplevel(self)
            dlg.title('Select teachers to print')
            dlg.transient(self)
            dlg.grab_set()
            lb = tk.Listbox(dlg, selectmode='multiple', width=60)
            lb.pack(padx=10, pady=10)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM teachers ORDER BY LOWER(name) ASC")
            rows = cursor.fetchall()
            conn.close()
            id_map = []
            for i,(tid,name) in enumerate(rows):
                id_map.append(tid)
                lb.insert('end', name)
            # Also keep a parallel list of names for default filename generation
            name_map = [r[1] for r in rows]

            def on_ok():
                sel = lb.curselection()
                if not sel:
                    messagebox.showinfo('No Selection','Please select at least one teacher.')
                    return
                chosen_ids = [id_map[i] for i in sel]
                # Ask for filename first, then Save-As with that name
                # Create a friendlier default: if one teacher selected use their name, else include first name and count
                default_name = 'timetables'
                try:
                    if len(sel) == 1:
                        default_name = f"{self.sanitize_filename(name_map[sel[0]])}_timetable"
                    else:
                        first = self.sanitize_filename(name_map[sel[0]])
                        default_name = f"timetables_{first}_and_{len(sel)-1}others"
                except Exception:
                    default_name = 'timetables'
                name = self.ask_filename_large('Filename', 'Enter filename for multi-timetable PDF (without extension):', initial_value=default_name)
                if not name:
                    return
                file_path = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[('PDF files','*.pdf')], title='Save Multi Timetable PDF', initialfile=f"{name}.pdf")
                if not file_path:
                    return
                try:
                    self._generate_pdf_for_teachers(chosen_ids, file_path)
                    try:
                        if sys.platform.startswith('win'):
                            os.startfile(file_path)
                        else:
                            subprocess.Popen(['xdg-open', file_path])
                    except Exception:
                        pass
                    messagebox.showinfo('Done', f'Multi-page PDF saved to {file_path}')
                except Exception as e:
                    messagebox.showerror('Error', f'Failed to generate PDF: {e}')
                finally:
                    try:
                        dlg.destroy()
                    except Exception:
                        pass

            btn_frame = ttk.Frame(dlg)
            btn_frame.pack(fill='x', pady=(0,10))
            ttk.Button(btn_frame, text='Print', command=on_ok).pack(side='left', padx=8)
            ttk.Button(btn_frame, text='Cancel', command=lambda: dlg.destroy()).pack(side='right', padx=8)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to open selection dialog: {e}')

    def _generate_pdf_for_teachers(self, teacher_id_list, file_path):
        # Helper: produce a neat, table-based PDF using reportlab.platypus
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
        except Exception:
            raise RuntimeError('reportlab is required for PDF generation')

        PAGE_WIDTH, PAGE_HEIGHT = A4
        margin = 36
        doc = SimpleDocTemplate(file_path, pagesize=A4, leftMargin=margin, rightMargin=margin, topMargin=margin, bottomMargin=margin)
        elements = []
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=TA_LEFT, fontSize=16, leading=20)
        subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], alignment=TA_LEFT, fontSize=11, leading=14)
        cell_style = ParagraphStyle('Cell', parent=styles['Normal'], alignment=TA_CENTER, fontSize=9, leading=11)
        small_left = ParagraphStyle('SmallLeft', parent=styles['Normal'], alignment=TA_LEFT, fontSize=9, leading=11)

        # Precompute a mapping of timetable entries per teacher
        for idx, tid in enumerate(teacher_id_list):
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name, degree, main_subject FROM teachers WHERE id = ?", (tid,))
            row = cursor.fetchone() or ('Unknown', '', '')
            name, degree, main_subj = row

            cursor.execute("SELECT day_of_week, period_number, class_name, subject FROM timetable WHERE teacher_id = ?", (tid,))
            rows = cursor.fetchall()
            conn.close()

            # Build a dict for quick lookup
            entry_map = {}
            for day, period, class_name, subject in rows:
                entry_map[(day, period)] = (class_name or '', subject or '')

            # Header
            elements.append(Paragraph('Teacher Timetable', title_style))
            elements.append(Paragraph(f'<b>{name}</b>', subtitle_style))
            if degree or main_subj:
                elements.append(Paragraph(f'{degree or ""} {"- " + main_subj if main_subj else ""}', small_left))
            elements.append(Spacer(1, 8))

            # Table data: periods as columns (top, horizontal), days as rows (left, vertical)
            days = list(self.days)
            periods = list(self.periods)
            # Header row: empty top-left cell, then periods across
            header = ['Day'] + [f'Period {p}' for p in periods]
            data = [header]

            # Data rows: one per day
            for d in days:
                row_cells = [Paragraph(d, small_left)]
                for p in periods:
                    cls, subj = entry_map.get((d, p), ('', ''))
                    if cls or subj:
                        txt = f'<b>{cls}</b><br/>{subj}' if subj else f'{cls}'
                        row_cells.append(Paragraph(txt, cell_style))
                    else:
                        row_cells.append(Paragraph('', cell_style))
                data.append(row_cells)

            # Create table with reasonable column widths
            usable_w = PAGE_WIDTH - 2 * margin
            day_col = usable_w * 0.12
            period_col = (usable_w - day_col) / max(1, len(periods))
            colWidths = [day_col] + [period_col] * len(periods)

            table = Table(data, colWidths=colWidths, hAlign='LEFT')
            table_style = TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('ALIGN', (0,0), (0,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (1,0), (-1,-1), 'CENTER'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ])
            table.setStyle(table_style)

            elements.append(table)
            # Add page break between teachers except after last
            if idx != len(teacher_id_list) - 1:
                elements.append(PageBreak())

        # Build the PDF
        doc.build(elements)

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

        # If today is not a school day (e.g., Sunday), show a clear message
        today_name = now.strftime('%A')
        if today_name not in getattr(self, 'days', []):
            self.status_var.set('No school today.')
            self.next_var.set('No classes today.')
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
                btn.config(bg=default_bg, fg=self.timetable_text_muted_color)
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

    def stop_blink_animation(self):
        """Stop the blinking animation."""
        # Cancel any scheduled blink callback
        if getattr(self, '_blink_after_id', None):
            try:
                self.after_cancel(self._blink_after_id)
            except Exception:
                pass
            self._blink_after_id = None
        # Restore button's original background/foreground if available
        if hasattr(self, 'current_highlight_btn') and self.current_highlight_btn is not None:
            try:
                btn = self.current_highlight_btn
                orig_bg = getattr(btn, '_orig_bg', None)
                orig_fg = getattr(btn, '_orig_fg', None)
                if orig_bg is not None:
                    try:
                        if orig_fg is not None:
                            btn.config(bg=orig_bg, fg=orig_fg)
                        else:
                            btn.config(bg=orig_bg)
                    except Exception:
                        pass
                try:
                    if hasattr(btn, '_orig_bg'):
                        del btn._orig_bg
                except Exception:
                    pass
                try:
                    if hasattr(btn, '_orig_fg'):
                        del btn._orig_fg
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
        """Toggle blink applied to the inner button (the class text box)."""
        if not hasattr(self, 'current_highlight_btn') or self.current_highlight_btn is None:
            return

        btn = self.current_highlight_btn
        try:
            orig = getattr(btn, '_orig_bg', btn.cget('bg'))
            orig_fg = getattr(btn, '_orig_fg', None)
            # toggle state
            self.blink_state = not getattr(self, 'blink_state', False)
            if self.blink_state:
                try:
                    if orig_fg is not None:
                        btn.config(bg=self.blink_color, fg=self.timetable_text_muted_color)
                    else:
                        btn.config(bg=self.blink_color)
                except Exception:
                    pass
            else:
                try:
                    if orig_fg is not None:
                        btn.config(bg=orig, fg=orig_fg)
                    else:
                        btn.config(bg=orig, fg=self.timetable_text_muted_color)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            self._blink_after_id = self.after(self.blink_interval, self.blink_highlight)
        except Exception:
            self._blink_after_id = None

    def start_auto_update_highlight(self):
        """Start or restart the 1-second auto-update for the highlight area."""
        # Cancel previous
        self.stop_auto_update_highlight()
        # Update immediately
        try:
            self.update_highlight()
        except Exception:
            pass
        # Schedule next update in 1 seconds
        try:
            self._highlight_after_id = self.after(1000, self.start_auto_update_highlight)
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

    def start_blink_animation(self):
        """Initialize blink state for the current highlight button and schedule toggles."""
        # Cancel any existing scheduled blink
        try:
            if getattr(self, '_blink_after_id', None):
                self.after_cancel(self._blink_after_id)
        except Exception:
            pass

        if not hasattr(self, 'current_highlight_btn') or self.current_highlight_btn is None:
            return

        btn = self.current_highlight_btn
        try:
            # Save original bg/fg so we can restore later
            if not hasattr(btn, '_orig_bg'):
                try:
                    btn._orig_bg = btn.cget('bg')
                except Exception:
                    btn._orig_bg = None
            if not hasattr(btn, '_orig_fg'):
                try:
                    btn._orig_fg = btn.cget('fg')
                except Exception:
                    btn._orig_fg = None
        except Exception:
            pass

        # Reset blink state and schedule the first toggle
        try:
            self.blink_state = False
            self._blink_after_id = self.after(self.blink_interval, self.blink_highlight)
        except Exception:
            self._blink_after_id = None

    def edit_period_timings_dialog(self):
        """Open a dialog to edit start/end times for each period (simple design)."""
        dialog = tk.Toplevel(self)
        dialog.title("Edit Period Timings")
        # Larger dialog for better readability
        dialog.geometry("560x520")
        dialog.resizable(False, False)

        main = ttk.Frame(dialog, padding=15)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="Period", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=10)
        ttk.Label(main, text="Start Time", font=("Segoe UI", 12, "bold")).grid(row=0, column=1, sticky="w", padx=8, pady=10)
        ttk.Label(main, text="End Time", font=("Segoe UI", 12, "bold")).grid(row=0, column=2, sticky="w", padx=8, pady=10)

        entries = {}
        for i, pnum in enumerate(sorted(self.periods), start=1):
            ttk.Label(main, text=f"Period {pnum}", font=("Segoe UI", 11)).grid(row=i, column=0, sticky="w", padx=6, pady=8)
            
            start_str = self.period_times.get(pnum, (datetime.time(8, 0), datetime.time(9, 0)))[0].strftime('%H:%M')
            end_str = self.period_times.get(pnum, (datetime.time(8, 0), datetime.time(9, 0)))[1].strftime('%H:%M')
            
            # Use readonly entries and allow picking via a scrollable time-picker
            s_entry = ttk.Entry(main, width=14, font=("Segoe UI", 11))
            s_entry.insert(0, start_str)
            s_entry.grid(row=i, column=1, sticky="w", padx=6, pady=8)
            try:
                s_entry.configure(state='readonly')
            except Exception:
                pass
            # bind click to open wheel-style time picker
            s_entry.bind("<Button-1>", lambda e, ent=s_entry: (lambda v: (ent.configure(state='normal'), ent.delete(0, tk.END), ent.insert(0, v), ent.configure(state='readonly')))(self.show_time_picker(dialog, ent.get()) or ent.get()))

            e_entry = ttk.Entry(main, width=14, font=("Segoe UI", 11))
            e_entry.insert(0, end_str)
            e_entry.grid(row=i, column=2, sticky="w", padx=6, pady=8)
            try:
                e_entry.configure(state='readonly')
            except Exception:
                pass
            e_entry.bind("<Button-1>", lambda e, ent=e_entry: (lambda v: (ent.configure(state='normal'), ent.delete(0, tk.END), ent.insert(0, v), ent.configure(state='readonly')))(self.show_time_picker(dialog, ent.get()) or ent.get()))
            
            entries[pnum] = (s_entry, e_entry)

        button_frame = ttk.Frame(main)
        button_frame.grid(row=len(self.periods)+2, column=0, columnspan=3, pady=18)

        def save_timings():
            """Validate and save period timings."""
            new_map = {}
            for pnum, (s_e, e_e) in entries.items():
                s_val = s_e.get().strip()
                e_val = e_e.get().strip()
                try:
                    s_t = datetime.time.fromisoformat(s_val)
                    e_t = datetime.time.fromisoformat(e_val)
                except Exception:
                    messagebox.showerror("Validation Error", f"Period {pnum}: Use format HH:MM (e.g., 08:30)")
                    return
                if s_t >= e_t:
                    messagebox.showerror("Validation Error", f"Period {pnum}: Start time must be before end time.")
                    return
                new_map[pnum] = (s_t, e_t)

            # Persist to DB
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                for pnum, (s_t, e_t) in new_map.items():
                    cursor.execute("INSERT OR REPLACE INTO period_times (period_number, start, end) VALUES (?, ?, ?)",
                                   (pnum, s_t.strftime('%H:%M'), e_t.strftime('%H:%M')))
                conn.commit()
                conn.close()

                self.period_times.update(new_map)
                try:
                    self.update_current_status()
                except Exception:
                    pass
                messagebox.showinfo("Success", "Period timings saved!")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save:\n{e}")

        tk.Button(button_frame, text="Save", command=save_timings,
              bg=self.color_add, fg=self.text_color, font=("Segoe UI", 10, "bold"), activebackground="#059669", cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=dialog.destroy,
              bg="#6B7280", fg=self.text_color, font=("Segoe UI", 10, "bold"), activebackground="#4B5563", cursor="hand2").pack(side=tk.LEFT, padx=5)

    
    def show_time_picker(self, parent, initial_time=None):
        """Show a wheel-like time picker (hours 00-23, minutes 00-59) and return 'HH:MM' or None.

        The picker is modal and larger for readability. `initial_time` may be in 'HH:MM' 24-hour format.
        """
        try:
            dlg = tk.Toplevel(parent if parent is not None else self)
            dlg.title("Pick Time")
            # Make the picker transient to the parent dialog so stacking is correct
            try:
                dlg.transient(parent if parent is not None else self)
            except Exception:
                try:
                    dlg.transient(self)
                except Exception:
                    pass
            dlg.grab_set()
            dlg.resizable(False, False)
            # Ensure parent and picker are lifted so picker stays above the parent
            try:
                if parent is not None:
                    try:
                        parent.lift()
                    except Exception:
                        pass
                dlg.lift()
                dlg.focus_force()
            except Exception:
                pass

            # geometry: center over parent — make slightly taller so buttons remain visible
            try:
                w, h = 420, 340
                px = (self.winfo_rootx() + max(20, (self.winfo_width() - w) // 2))
                py = (self.winfo_rooty() + max(20, (self.winfo_height() - h) // 2))
                dlg.geometry(f"{w}x{h}+{px}+{py}")
                try:
                    dlg.minsize(w, h)
                except Exception:
                    pass
            except Exception:
                pass

            frame = ttk.Frame(dlg, padding=12)
            frame.pack(fill=tk.BOTH, expand=True)

            lbl = ttk.Label(frame, text="Select time (24-hour)", font=("Segoe UI", 13, "bold"))
            lbl.pack(anchor='w')

            lists_frame = ttk.Frame(frame)
            lists_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 8))

            # Hours (00-23), Minutes (00-59)
            lb_hour = tk.Listbox(lists_frame, exportselection=False, width=6, height=8, font=("Segoe UI", 14), activestyle='none')
            lb_min = tk.Listbox(lists_frame, exportselection=False, width=6, height=8, font=("Segoe UI", 14), activestyle='none')

            # populate
            hours = list(range(0, 24))
            for h_val in hours:
                lb_hour.insert(tk.END, f"{h_val:02d}")
            for m in range(60):
                lb_min.insert(tk.END, f"{m:02d}")


            # layout with arrow buttons
            arrow_frame_hour = ttk.Frame(lists_frame)
            arrow_frame_hour.grid(row=0, column=0, sticky="ns", padx=(0,0))
            lb_hour.grid(row=0, column=1, padx=(0,8))
            arrow_frame_min = ttk.Frame(lists_frame)
            arrow_frame_min.grid(row=0, column=2, sticky="ns")
            lb_min.grid(row=0, column=3)

            # Arrow buttons for hours
            def scroll_hour(delta):
                sel = lb_hour.curselection()
                idx = sel[0] if sel else 0
                new_idx = max(0, min(len(hours)-1, idx+delta))
                lb_hour.selection_clear(0, tk.END)
                lb_hour.selection_set(new_idx)
                lb_hour.see(new_idx)

            up_hour_btn = tk.Button(arrow_frame_hour, text="▲", command=lambda: scroll_hour(-1), font=("Segoe UI", 11), width=2)
            down_hour_btn = tk.Button(arrow_frame_hour, text="▼", command=lambda: scroll_hour(1), font=("Segoe UI", 11), width=2)
            up_hour_btn.pack(side=tk.TOP, pady=(0,2))
            down_hour_btn.pack(side=tk.TOP, pady=(2,0))

            # Arrow buttons for minutes
            def scroll_minute(delta):
                sel = lb_min.curselection()
                idx = sel[0] if sel else 0
                new_idx = max(0, min(59, idx+delta))
                lb_min.selection_clear(0, tk.END)
                lb_min.selection_set(new_idx)
                lb_min.see(new_idx)

            up_min_btn = tk.Button(arrow_frame_min, text="▲", command=lambda: scroll_minute(-1), font=("Segoe UI", 11), width=2)
            down_min_btn = tk.Button(arrow_frame_min, text="▼", command=lambda: scroll_minute(1), font=("Segoe UI", 11), width=2)
            up_min_btn.pack(side=tk.TOP, pady=(0,2))
            down_min_btn.pack(side=tk.TOP, pady=(2,0))

            # helper to scroll with mouse wheel (Windows uses delta multiples of 120)
            def _on_mousewheel(event):
                widget = event.widget
                try:
                    delta = int(-1 * (event.delta / 120))
                except Exception:
                    delta = -1 if getattr(event, 'delta', 0) > 0 else 1
                try:
                    widget.yview_scroll(delta, 'units')
                except Exception:
                    pass

            for lb in (lb_hour, lb_min):
                lb.bind('<MouseWheel>', _on_mousewheel)

            # preselect initial time if provided (expecting 'HH:MM')
            sel_hour_idx = 0
            sel_min_idx = 0
            try:
                if initial_time:
                    parts = initial_time.split(":")
                    if len(parts) >= 2:
                        ih = int(parts[0])
                        im = int(parts[1])
                        sel_hour_idx = max(0, min(23, ih))
                        sel_min_idx = max(0, min(59, im))
            except Exception:
                pass

            try:
                lb_hour.selection_set(sel_hour_idx)
                lb_hour.see(sel_hour_idx)
            except Exception:
                pass
            try:
                lb_min.selection_set(sel_min_idx)
                lb_min.see(sel_min_idx)
            except Exception:
                pass

            result = {'time': None}

            def on_ok():
                try:
                    h_idx = int(lb_hour.curselection()[0])
                    m_idx = int(lb_min.curselection()[0])
                except Exception:
                    # If nothing selected, fallback to first items
                    try:
                        h_idx = 0
                        m_idx = 0
                    except Exception:
                        dlg.destroy()
                        return
                hour = hours[h_idx]
                minute = m_idx
                result['time'] = f"{hour:02d}:{minute:02d}"
                dlg.destroy()

            def on_cancel():
                dlg.destroy()

            btns = ttk.Frame(frame)
            btns.pack(side=tk.BOTTOM, fill=tk.X, pady=(8,0))
            # Use more visible buttons
            try:
                tk.Button(btns, text="OK", command=on_ok, bg=self.color_add, fg=self.text_color, font=("Segoe UI", 11, "bold"), activebackground="#059669").pack(side=tk.LEFT, padx=(0,6))
            except Exception:
                ttk.Button(btns, text="OK", command=on_ok).pack(side=tk.LEFT, padx=(0,6))
            try:
                tk.Button(btns, text="Cancel", command=on_cancel, bg="#6B7280", fg=self.text_color, font=("Segoe UI", 11, "bold"), activebackground="#4B5563").pack(side=tk.LEFT)
            except Exception:
                ttk.Button(btns, text="Cancel", command=on_cancel).pack(side=tk.LEFT)

            # allow Enter/Escape
            dlg.bind('<Return>', lambda e: on_ok())
            dlg.bind('<Escape>', lambda e: on_cancel())

            self.wait_window(dlg)
            return result['time']
        except Exception:
            return None

    def add_teacher_dialog(self):
        """Open add teacher dialog"""
        dialog = tk.Toplevel(self)
        dialog.title("Add Teacher")
        # Set dialog size and center it on the screen (larger)
        dialog_width, dialog_height = 640, 300
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
        
        ttk.Label(main_frame, text="Name:", font=("Segoe UI", 11)).grid(row=0, column=0, sticky="w", pady=6)
        name_entry = ttk.Entry(main_frame, width=30, font=("Segoe UI", 11))
        name_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
        name_entry.focus_set()
        
        ttk.Label(main_frame, text="Degree:", font=("Segoe UI", 11)).grid(row=1, column=0, sticky="w", pady=6)
        degree_entry = ttk.Entry(main_frame, width=30, font=("Segoe UI", 11))
        degree_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
        
        ttk.Label(main_frame, text="Subjects (comma-separated):", font=("Segoe UI", 11)).grid(row=2, column=0, sticky="w", pady=6)
        # Provide a simple Entry + suggestion combobox to build a CSV list of subjects for the teacher
        try:
            all_subj = self.get_all_subjects()
        except Exception:
            all_subj = []
        subjects_entry = ttk.Entry(main_frame, width=30, font=("Segoe UI", 11))
        subjects_entry.grid(row=2, column=1, sticky="ew", pady=5, padx=5)
        # Suggestion combobox + Add button
        subj_suggest = ttk.Combobox(main_frame, width=20, values=all_subj, state='normal')
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
        button_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=18)
        
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
              bg=self.color_add, fg=self.text_color, font=("Segoe UI", 11, "bold"),
              activebackground="#059669").pack(side=tk.LEFT, padx=6)
        tk.Button(button_frame, text="Cancel", command=dialog.destroy,
              bg=self.color_exit, fg=self.text_color, font=("Segoe UI", 11, "bold"),
              activebackground="#1174FD").pack(side=tk.LEFT, padx=6)
    
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
        dialog_width, dialog_height = 640, 300
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
        
        ttk.Label(main_frame, text="Name:", font=("Segoe UI", 11)).grid(row=0, column=0, sticky="w", pady=6)
        name_entry = ttk.Entry(main_frame, width=30, font=("Segoe UI", 11))
        name_entry.insert(0, name)
        name_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
        name_entry.focus_set()
        
        ttk.Label(main_frame, text="Degree:", font=("Segoe UI", 11)).grid(row=1, column=0, sticky="w", pady=6)
        degree_entry = ttk.Entry(main_frame, width=30, font=("Segoe UI", 11))
        degree_entry.insert(0, degree or "")
        degree_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
        
        ttk.Label(main_frame, text="Subjects (comma-separated):", font=("Segoe UI", 11)).grid(row=2, column=0, sticky="w", pady=6)
        try:
            all_subj = self.get_all_subjects()
        except Exception:
            all_subj = []
        subjects_entry = ttk.Entry(main_frame, width=30, font=("Segoe UI", 11))
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
        subj_suggest = ttk.Combobox(main_frame, width=20, values=all_subj, state='normal')
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
        button_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=18)
        
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
          bg=self.color_edit, fg=self.text_color, font=("Segoe UI", 11, "bold"),
          activebackground="#1D4ED8").pack(side=tk.LEFT, padx=6)
        tk.Button(button_frame, text="Cancel", command=dialog.destroy,
            bg=self.color_exit, fg=self.text_color, font=("Segoe UI", 11, "bold"),
            activebackground="#4B5563").pack(side=tk.LEFT, padx=6)
    
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
                btn.config(text="", bg=getattr(self, 'default_btn_bg', btn.cget('bg')), fg=self.timetable_text_muted_color)
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
            # Don't reuse the main Delete button label; we'll show explicit confirm/cancel controls below
            pass
        except Exception:
            pass
        try:
            # Show the Select column and Cancel button by adjusting displaycolumns
            self.teachers_tree.config(displaycolumns=("Select", "Name", "Main Subject"))
            self.teachers_tree.column("Select", width=170)
            self.teachers_tree.heading("Select", text="Select")
        except Exception:
            pass
        try:
            # Hide the regular teacher button area so bulk-confirm buttons appear directly below the list
            try:
                self.teacher_btn_frame.pack_forget()
                self.import_btn_frame.pack_forget()
            except Exception:
                pass
            # Show bulk confirm frame with two buttons: Confirm Delete and Cancel
            self.bulk_confirm_frame.pack(fill=tk.X, pady=(8,6), padx=6)
            self.confirm_bulk_delete_btn.pack(side=tk.LEFT, padx=4)
            self.cancel_bulk_btn.pack(side=tk.LEFT, padx=4)
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
            # Hide bulk confirm frame if visible
            try:
                self.confirm_bulk_delete_btn.pack_forget()
                self.cancel_bulk_btn.pack_forget()
                self.bulk_confirm_frame.pack_forget()
            except Exception:
                pass
            # Restore normal teacher buttons area if layout_mode allows
            if getattr(self, 'layout_mode', 'new') == 'old':
                try:
                    # Pack the three main teacher buttons in the first frame
                    self.teacher_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0), padx=6)
                    self.add_teacher_btn.pack(side=tk.LEFT, padx=3, pady=5)
                    self.edit_teacher_btn.pack(side=tk.LEFT, padx=3, pady=5)
                    self.delete_selected_btn.pack(side=tk.LEFT, padx=3, pady=5)
                    # Pack import button frame below the teacher buttons
                    self.import_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 6), padx=6)
                    self.import_teachers_btn.pack(side=tk.LEFT, padx=3, pady=5)
                except Exception:
                    pass
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
            btn.config(text="", bg=getattr(self, 'default_btn_bg', btn.cget('bg')), fg=self.timetable_text_muted_color)
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
        # larger dialog
        dialog.geometry("560x360")
        dialog.resizable(False, False)

        main_frame = ttk.Frame(dialog, padding=18)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Day of Week:", font=("Segoe UI", 11)).grid(row=0, column=0, sticky="w", pady=10, padx=6)
        day_combo = ttk.Combobox(main_frame, width=28, 
                    values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                    state="readonly", font=("Segoe UI", 11))
        day_combo.grid(row=0, column=1, sticky="ew", pady=10, padx=6)

        ttk.Label(main_frame, text="Period Number:", font=("Segoe UI", 11)).grid(row=1, column=0, sticky="w", pady=10, padx=6)
        period_entry = ttk.Entry(main_frame, width=28, font=("Segoe UI", 11))
        period_entry.grid(row=1, column=1, sticky="ew", pady=10, padx=6)
        # Prefill if provided
        if day:
            day_combo.set(day)
        if period:
            period_entry.insert(0, str(period))
        
        ttk.Label(main_frame, text="Class Name:", font=("Segoe UI", 11)).grid(row=2, column=0, sticky="w", pady=10, padx=6)
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
        class_combo = ttk.Combobox(main_frame, width=28, values=class_values, state='normal', font=("Segoe UI", 11))
        class_combo.grid(row=2, column=1, sticky="ew", pady=10, padx=6)
        # Smart default: if teacher has only one class, auto-select it
        if len(class_values) == 2 and class_values[1] != 'FREE':
            class_combo.set(class_values[1])
        
        ttk.Label(main_frame, text="Subject:", font=("Segoe UI", 11)).grid(row=3, column=0, sticky="w", pady=10, padx=6)
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
        subject_combo = ttk.Combobox(main_frame, width=28, values=subject_values, state='normal', font=("Segoe UI", 11))
        subject_combo.grid(row=3, column=1, sticky="ew", pady=10, padx=6)
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
        button_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=18)
        
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
        
        ttk.Button(button_frame, text="Save", command=save).pack(side=tk.LEFT, padx=8)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=8)
    
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
        # larger dialog
        dialog.geometry("560x360")
        dialog.resizable(False, False)

        main_frame = ttk.Frame(dialog, padding=18)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Day of Week:", font=("Segoe UI", 11)).grid(row=0, column=0, sticky="w", pady=10, padx=6)
        day_combo = ttk.Combobox(main_frame, width=28,
                    values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                    state="readonly", font=("Segoe UI", 11))
        day_combo.set(day)
        day_combo.grid(row=0, column=1, sticky="ew", pady=10, padx=6)

        ttk.Label(main_frame, text="Period Number:", font=("Segoe UI", 11)).grid(row=1, column=0, sticky="w", pady=10, padx=6)
        period_entry = ttk.Entry(main_frame, width=28, font=("Segoe UI", 11))
        period_entry.insert(0, str(period))
        period_entry.grid(row=1, column=1, sticky="ew", pady=10, padx=6)

        ttk.Label(main_frame, text="Class Name:", font=("Segoe UI", 11)).grid(row=2, column=0, sticky="w", pady=10, padx=6)
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
        class_combo = ttk.Combobox(main_frame, width=28, values=class_values, state='normal', font=("Segoe UI", 11))
        class_combo.set(class_name or '')
        class_combo.grid(row=2, column=1, sticky="ew", pady=10, padx=6)
        
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
        subject_combo = ttk.Combobox(main_frame, width=28, values=subject_values, state='normal', font=("Segoe UI", 11))
        subject_combo.set(subject or '')
        subject_combo.grid(row=3, column=1, sticky="ew", pady=10, padx=6)
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
        button_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=18)
        
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
        
        tk.Button(button_frame, text="Update", command=update, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=8)
        tk.Button(button_frame, text="Cancel", command=dialog.destroy, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=8)
    
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

        # Use a larger custom confirmation dialog
        def ask_delete_confirm(title, prompt):
            dlg = tk.Toplevel(self)
            dlg.title(title)
            dlg.geometry("520x180")
            dlg.transient(self)
            try:
                dlg.grab_set()
            except Exception:
                pass
            frm = ttk.Frame(dlg, padding=12)
            frm.pack(fill=tk.BOTH, expand=True)
            ttk.Label(frm, text=prompt, font=("Segoe UI", 12)).pack(anchor='w', pady=(6,10))
            res = {'value': False}
            def on_yes():
                res['value'] = True
                dlg.destroy()
            def on_no():
                dlg.destroy()
            btnf = ttk.Frame(frm)
            btnf.pack(pady=8)
            ttk.Button(btnf, text="Delete", command=on_yes).pack(side=tk.LEFT, padx=8)
            ttk.Button(btnf, text="Cancel", command=on_no).pack(side=tk.LEFT, padx=8)
            try:
                self.wait_window(dlg)
            except Exception:
                pass
            return res['value']

        if ask_delete_confirm("Confirm Delete", "Delete this period?"):
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM timetable WHERE id = ?", (period_id,))
            conn.commit()
            conn.close()
            self.load_timetable_for_teacher()
            # Larger success info
            dlg2 = tk.Toplevel(self)
            dlg2.title("Success")
            dlg2.geometry("420x140")
            dlg2.transient(self)
            try:
                dlg2.grab_set()
            except Exception:
                pass
            f2 = ttk.Frame(dlg2, padding=12)
            f2.pack(fill=tk.BOTH, expand=True)
            ttk.Label(f2, text="Period deleted successfully!", font=("Segoe UI", 12)).pack(pady=8)
            ttk.Button(f2, text="OK", command=dlg2.destroy).pack()

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
        # Simple right-click menu with larger font for readability
        try:
            menu_font = ("Segoe UI", 14)
            menu = tk.Menu(self, tearoff=0, font=menu_font)
            menu.add_command(label="Add / Edit", command=lambda d=day, p=period: self.on_cell_click(d, p))
            menu.add_command(label="Delete", command=lambda d=day, p=period: self.delete_period(day=d, period=p))
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    menu.grab_release()
                except Exception:
                    pass
        except Exception:
            # Fallback: do nothing
            pass

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

    def manage_colors_dialog(self):
        """Open dialog to manage highlight and text colors."""
        dialog = tk.Toplevel(self)
        dialog.title("Manage Colors")
        dialog.geometry("640x480")
        dialog.resizable(False, False)
        # Make dialog modal so the menu closes and the dialog stays on top
        try:
            dialog.transient(self)
            dialog.grab_set()
            dialog.focus_force()
        except Exception:
            pass
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Color Settings", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 20))
        
        # --- Blinking Color Section ---
        blink_label_frame = ttk.Frame(main_frame)
        blink_label_frame.pack(fill=tk.X, pady=(0, 8))
        
        ttk.Label(blink_label_frame, text="Blinking Highlight Color", font=("Segoe UI", 12, "bold")).pack(anchor="w", side=tk.LEFT)
        
        # Color preview box for blink color
        blink_preview = tk.Canvas(blink_label_frame, width=30, height=30, bg=self.blink_color, relief='solid', bd=2, highlightthickness=0)
        blink_preview.pack(anchor="w", side=tk.LEFT, padx=(12, 0))
        
        blink_code_label = ttk.Label(blink_label_frame, text=self.blink_color, font=("Segoe UI", 10, "bold"))
        blink_code_label.pack(anchor="w", side=tk.LEFT, padx=(8, 0))
        
        # Button for blink color
        tk.Button(main_frame, text="Change Blinking Color", 
              command=lambda: self.choose_color("blink_color", "Blinking Color", blink_preview, blink_code_label),
              bg=self.color_edit, fg=self.text_color, font=("Segoe UI", 11, "bold"), activebackground="#1D4ED8", cursor="hand2", 
              padx=12, pady=8).pack(anchor="w", padx=8, pady=(0, 16))
        
        # Divider
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=(0, 16))
        
        # --- Text Color Section ---
        text_label_frame = ttk.Frame(main_frame)
        text_label_frame.pack(fill=tk.X, pady=(0, 8))
        
        ttk.Label(text_label_frame, text="Timetable Text Color", font=("Segoe UI", 12, "bold")).pack(anchor="w", side=tk.LEFT)
        
        # Color preview box for text color
        text_preview = tk.Canvas(text_label_frame, width=30, height=30, bg=self.timetable_text_muted_color, relief='solid', bd=2, highlightthickness=0)
        text_preview.pack(anchor="w", side=tk.LEFT, padx=(12, 0))
        
        text_code_label = ttk.Label(text_label_frame, text=self.timetable_text_muted_color, font=("Segoe UI", 10, "bold"))
        text_code_label.pack(anchor="w", side=tk.LEFT, padx=(8, 0))
        
        # Button for text color
        tk.Button(main_frame, text="Change Text Color",
              command=lambda: self.choose_color("timetable_text_muted_color", "Text Color", text_preview, text_code_label),
              bg=self.color_edit, fg=self.text_color, font=("Segoe UI", 11, "bold"), activebackground="#1D4ED8", cursor="hand2",
              padx=12, pady=8).pack(anchor="w", padx=8, pady=(0, 20))
        
        # Divider
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=(0, 16))
        
        # Action buttons at bottom
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 0))
        
        tk.Button(button_frame, text="Reset to Defaults", command=lambda: self.reset_colors(blink_preview, blink_code_label, text_preview, text_code_label),
              bg="#6B7280", fg=self.text_color, font=("Segoe UI", 10, "bold"), activebackground="#4B5563", cursor="hand2",
              padx=12, pady=8).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(button_frame, text="Close", command=dialog.destroy,
              bg="#6B7280", fg=self.text_color, font=("Segoe UI", 10, "bold"), activebackground="#4B5563", cursor="hand2",
              padx=12, pady=8).pack(side=tk.LEFT)

        # Wait for dialog to be closed before returning to caller (modal)
        try:
            self.wait_window(dialog)
        except Exception:
            pass

    def choose_color(self, attr_name, color_label, preview_canvas=None, code_label=None):
        """Open color picker dialog and update preview/label if provided."""
        from tkinter.colorchooser import askcolor
        current_color = getattr(self, attr_name, "#000000")
        color = askcolor(color=current_color, title=f"Choose {color_label}")
        if color[1]:  # If user didn't cancel
            setattr(self, attr_name, color[1])
            # Update preview box and color code label if provided
            try:
                if preview_canvas:
                    preview_canvas.config(bg=color[1])
                if code_label:
                    code_label.config(text=color[1])
            except Exception:
                pass
            messagebox.showinfo("Color Updated", f"{color_label} has been updated to {color[1]}")
            # Refresh timetable if changing text color
            if attr_name == "timetable_text_muted_color":
                try:
                    self.load_timetable_for_teacher()
                except Exception:
                    pass

    def reset_colors(self, blink_preview=None, blink_code_label=None, text_preview=None, text_code_label=None):
        """Reset colors to default values and update preview boxes if provided."""
        self.blink_color = "#00FF84"
        self.timetable_text_muted_color = "#2B2424"
        # Update preview boxes and labels if provided
        try:
            if blink_preview:
                blink_preview.config(bg=self.blink_color)
            if blink_code_label:
                blink_code_label.config(text=self.blink_color)
            if text_preview:
                text_preview.config(bg=self.timetable_text_muted_color)
            if text_code_label:
                text_code_label.config(text=self.timetable_text_muted_color)
        except Exception:
            pass
        messagebox.showinfo("Colors Reset", "Colors have been reset to default values.")
        try:
            self.load_timetable_for_teacher()
        except Exception:
            pass

    def change_blink_interval_dialog(self):
        """Open dialog to change blink interval."""
        dialog = tk.Toplevel(self)
        dialog.title("Change Blink Interval")
        dialog.geometry("480x220")
        dialog.resizable(False, False)
        
        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Blink Interval (milliseconds)", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(main_frame, text=f"Current: {self.blink_interval}ms", font=("Segoe UI", 11)).pack(anchor="w", pady=(0, 12))
        
        ttk.Label(main_frame, text="New Interval:", font=("Segoe UI", 11)).pack(anchor="w", pady=6)
        interval_entry = ttk.Entry(main_frame, width=28, font=("Segoe UI", 11))
        interval_entry.insert(0, str(self.blink_interval))
        interval_entry.pack(anchor="w", pady=6)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        
        def save_interval():
            try:
                new_interval = int(interval_entry.get())
                if new_interval < 100:
                    messagebox.showerror("Invalid", "Interval must be at least 100ms")
                    return
                self.blink_interval = new_interval
                messagebox.showinfo("Success", f"Blink interval changed to {new_interval}ms")
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Invalid", "Please enter a valid number")
        
        tk.Button(button_frame, text="Save", command=save_interval,
            bg=self.color_add, fg=self.text_color, font=("Segoe UI", 11, "bold"), activebackground="#059669", cursor="hand2").pack(side=tk.LEFT, padx=6)
        tk.Button(button_frame, text="Cancel", command=dialog.destroy,
            bg="#6B7280", fg=self.text_color, font=("Segoe UI", 11, "bold"), activebackground="#4B5563", cursor="hand2").pack(side=tk.LEFT, padx=6)

    def show_about_dialog(self):
        """Show about dialog with app information."""
        version = self.get_app_version()
        about_text = f"""Teacher Timetable App
Version: {version}

A modern timetable management system for teachers.

Features:
• Manage teacher information and subjects
• View and edit timetables
• Period timing management
• Automatic highlighting of current/next class
• Import/export functionality

© 2025 Teacher Timetable App"""
        # Use a larger custom dialog instead of messagebox
        dlg = tk.Toplevel(self)
        dlg.title("About")
        dlg.geometry("640x420")
        dlg.transient(self)
        try:
            dlg.grab_set()
        except Exception:
            pass
        frm = ttk.Frame(dlg, padding=22)
        frm.pack(fill=tk.BOTH, expand=True)
        txt = tk.Text(frm, wrap='word', font=("Segoe UI", 11), height=12)
        txt.insert('1.0', about_text)
        txt.config(state='disabled')
        txt.pack(fill=tk.BOTH, expand=True)
        btn = ttk.Button(frm, text="OK", command=dlg.destroy)
        btn.pack(pady=8)
        try:
            self.wait_window(dlg)
        except Exception:
            pass

    def show_help_dialog(self):
        """Show help dialog with usage instructions."""
        help_text = """How to Use Teacher Timetable App

1. ADDING TEACHERS
   • Click "Add Teacher" to add a new teacher
   • Fill in name, degree, and subjects
   • Click "Save"

2. MANAGING TIMETABLES
   • Select a teacher from the list
   • Click on a timetable cell to add/edit period
   • Right-click for context menu (Edit/Delete)
   • Select class and subject for each period

3. PERIOD TIMINGS
   • Use Settings → Edit Period Timings to set school schedule
   • Set start and end time for each period (8 total)

4. IMPORTING DATA
   • Use File → Import to bulk load teachers or timetables
   • Requires Excel file with proper columns

5. FEATURES
   • Current class automatically highlighted
   • Subject colors are auto-assigned and consistent
   • Single-subject teachers show only class name
   • Status area shows current time and next class"""
        dlg = tk.Toplevel(self)
        dlg.title("How to Use")
        dlg.geometry("680x480")
        dlg.transient(self)
        try:
            dlg.grab_set()
        except Exception:
            pass
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)
        txt = tk.Text(frm, wrap='word', font=("Segoe UI", 11))
        txt.insert('1.0', help_text)
        txt.config(state='disabled')
        sb = ttk.Scrollbar(frm, orient='vertical', command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        txt.pack(fill=tk.BOTH, expand=True)
        ttk.Button(frm, text="Close", command=dlg.destroy).pack(pady=8)
        try:
            self.wait_window(dlg)
        except Exception:
            pass

    def show_shortcuts_dialog(self):
        """Show keyboard shortcuts dialog."""
        shortcuts_text = """Keyboard Shortcuts

Window:
F11 - Toggle fullscreen mode
Esc - Exit fullscreen mode

Global / Keyboard:
Ctrl+F   - Focus search bar 
Ctrl+A   - Add new teacher 
Ctrl+E   - Edit selected teacher 
Ctrl+D   - Delete teacher 
Ctrl+P  - Print timetable 
Ctrl+ +  -Increase timetable font size 
Ctrl+ -  -Decrease timetable font size 
F11      -Toggle fullscreen 
Esc      -Exit fullscreen 
↑ / ↓    -Navigate teachers list 
Alt+F    -Open File menu
Alt+E    -Open Edit menu
Alt+V    -Open View menu 
Alt+T    -Open Tools menu 
Alt+H    -Open Help menu 

Mouse:
• Left-click cell - Add/Edit period
• Right-click cell - Show context menu (Edit/Delete)
• Left-click teacher - Select teacher
• Left-click row - Toggle select checkbox"""
        # Use the simpler messagebox-style layout (older design)
        try:
            messagebox.showinfo("Keyboard Shortcuts", shortcuts_text)
        except Exception:
            pass
    
    
if __name__ == "__main__":
    app = TeacherTimetableApp()
    app.mainloop()