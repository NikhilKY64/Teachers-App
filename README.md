# 📚 Teachers Timetable App

**Version:** v1.5.1

A comprehensive desktop application for managing teacher timetables and scheduling. Built with Python and Tkinter, this app allows schools to efficiently manage teacher assignments, class schedules, and timetables with an intuitive GUI.

---

## ✨ Features

### **Teacher Management**
- ✅ Add, edit, and delete teacher records
- ✅ Store teacher details: name, degree, main subject, and subjects taught
- ✅ Pin/star teachers for quick access
- ✅ Live search functionality to filter teachers by name or subject
- ✅ delete mode for removing multiple teachers at once
- ✅ Import teachers from Excel files

### **Timetable Management**
- ✅ Create and manage class schedules (8 periods per day)
- ✅ Support for 6 days per week (Monday-Saturday)
- ✅ Add, edit, and delete class assignments
- ✅ Import timetables from Excel
- ✅ Automatic period timing configuration (customizable)
- ✅ Live status display showing current and next class for selected teacher

### **Data & Export**
- ✅ Export teachers to Excel
- ✅ Export timetables to Excel
- ✅ Backup database to custom location
- ✅ SQLite database for persistent storage
- ✅ Print single or multiple teacher timetables as PDF

### **UI & Customization**
- ✅ Modern dark mode (OLED) theme support
- ✅ Adjustable timetable font size
- ✅ Toggle between traditional and minimalist layout modes
- ✅ Customizable blink interval for current class highlighting
- ✅ Responsive two-panel layout (Teachers list + Timetable)
- ✅ Color management for visual distinction
- ✅ CustomTkinter support for enhanced UI

### **Keyboard Shortcuts**
- `Ctrl+F` - Focus search bar
- `Ctrl+A` - Add new teacher
- `Ctrl+E` - Edit selected teacher
- `Ctrl+D` - Delete teacher (toggle bulk mode)
- `Ctrl+P` - Print timetable
- `F11` - Toggle fullscreen
- `Escape` - Exit fullscreen
- `Ctrl+` / `Ctrl-` - Adjust timetable size
- `↑` / `↓` - Navigate teachers list

---

## 🚀 Installation

### **Windows (Recommended)**
Download and run the installer:
```
TeacherAppSetup.exe
```

The installer will:
- Install the application to your system
- Create desktop shortcuts
- Configure file associations
- Enable uninstall capability

### **From Source (Python)**

#### Prerequisites
- Python 3.8+
- pip (Python package manager)

#### Installation Steps
1. Clone or download the repository:
   ```bash
   git clone https://github.com/NikhilKY64/Teachers-App.git
   cd Teachers-App
   ```

2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python "Teachers App.py"
   ```

#### Required Packages
- `tkinter` - GUI framework (usually bundled with Python)
- `customtkinter` - Modern themed widgets (optional)
- `pandas` - Excel/CSV data manipulation
- `openpyxl` - Excel file creation
- `reportlab` - PDF generation
- `pillow` - Image processing

---

## 📖 Usage Guide

### **Getting Started**

1. **Launch the application** - Open Teachers App from your desktop or Start menu
2. **Add Teachers** - Click "➕ Add Teacher" to create teacher records
3. **Create Timetable** - Select a teacher and click "➕ Add Period" to schedule classes
4. **Save & Backup** - Database is auto-saved; use File → Backup Database for manual backups

### **Working with Teachers**

#### Adding a Teacher
1. Click **Edit → Add Teacher** or use `Ctrl+A`
2. Enter teacher details:
   - **Name** - Teacher's full name
   - **Degree** - Qualification (e.g., B.Ed, M.Ed)
   - **Main Subject** - Primary teaching subject
   - **Subjects** - Comma-separated list of all subjects taught
3. Click **Save**

#### Searching Teachers
- Type in the **Search teacher...** box to filter by name or subject
- Results update in real-time
- Clear search to see all teachers

#### Editing a Teacher
1. Select the teacher from the list
2. Click **Edit Teacher** or use `Ctrl+E`
3. Modify details and click **Save**

#### Pinning Teachers
- Click the **☆** (star) icon next to a teacher's name to pin them
- Pinned teachers appear at the top of the list
- Useful for frequently accessed teachers

#### Deleting Teachers
- delete: ***Edit(Top of the App) → Click checkboxe(s) → Confirm Delete***
- **OR**
- delete: ***delete → Click checkboxe(s) → Confirm Delete***

### **Managing Timetables**

#### Adding Classes
1. Select a **teacher** from the list
2. Timetable appears in the right panel
3. Click **➕ Add Period** to add a class:
   - Select **Day** and **Period**
   - Enter **Class Name** (e.g., 10-A, 12-B)
   - Select **Subject**
4. Click **Save**

#### Editing Classes
- Click on any cell in the timetable to modify or delete that class

#### Importing Timetable from Excel
1. Prepare an Excel file with columns: **Day**, **Period**, **Class**, **Subject**
2. Select a teacher
3. Click **File → Import Timetable from Excel**
4. Select your file
5. Review the preview and confirm import

#### Period Timings
1. Go to **File → Edit Period Timings** (or menu)
2. Set start and end times for each period (8 periods by default)
3. Changes apply immediately

### **Viewing Status**

The **Selected Teacher** panel displays:
- 📝 **Teacher Name** with pin option
- 🎓 **Degree** - Qualification
- 📚 **Main Subject** - Primary subject taught
- 🕐 **Current Time** - System time and day
- 🏫 **Current Class** - Class being taught (if any)
- ⏭️ **Next Class** - Upcoming class with time remaining

The current class **highlights in green** and blinks to draw attention.

### **Export & Backup**

#### Export Teachers
- **File → Export Teachers** - Saves all teacher records as Excel file

#### Export Timetable
- Select teacher → **File → Export Timetable** - Saves that teacher's schedule

#### Backup Database
- **File → Backup Database** - Save a backup copy of the database
- Choose location and filename
- Useful before major changes or regular maintenance

#### Print Timetable
- Select teacher → **Tools → Print Timetable** - Generates PDF and prints/saves
- **Tools → Print Multiple Timetables** - Print all teachers' timetables in one PDF

### **Customization**

#### Theme (Dark Mode)
- **View → Dark mode (OLED)** - Switch to dark theme optimized for OLED screens

#### Layout Mode
- **View → Layout Mode (Old/New)** - Toggle between button-visible and menu-only layouts

#### Timetable Size
- **View → Adjust Timetable size** - Dialog to increase/decrease font size
- Use `Ctrl+` (plus) and `Ctrl-` (minus) for quick adjustment
- Size preference is saved

#### Blink Interval
- **Tools → Change Blink Interval** - Adjust how fast the current class cell blinks (in milliseconds)

#### Manage Colors
- **Tools → Manage Colors** - Customize:
  - Blink highlight color (for current class)
  - Text color for timetable cells

---

## 📊 Data Format

### **Excel Import Format - Teachers**
| Name | Degree | Main Subject | Subjects |
|------|--------|--------------|----------|
| John Doe | B.Ed | Mathematics | Mathematics, Physics |
| Jane Smith | M.Ed | English | English, Literature |

### **Excel Import Format - Timetable**
| Day | Period | Class | Subject |
|-----|--------|-------|---------|
| Monday | 1 | 10-A | Mathematics |
| Monday | 2 | 10-B | Physics |
| Tuesday | 3 | 11-A | English |

---

## 🗄️ Database

The app uses **SQLite** (`database.db`) to store:
- **Teachers** - Name, degree, subjects, pin status
- **Timetable** - Teacher assignments, days, periods, classes
- **Period Times** - Start and end times for each period
- **Settings** - User preferences (layout mode, font size, theme)

### Database Location
- **Windows Installer:** `C:\Users\[YourUsername]\AppData\Local\Teachers App\database.db`
- **Portable/Source:** Same directory as the application

### Backup
Always maintain a backup of `database.db`:
1. Use **File → Backup Database** within the app
2. Or manually copy the file to a safe location

---

## ⌨️ Complete Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+F` | Focus search bar |
| `Ctrl+A` | Add new teacher |
| `Ctrl+E` | Edit selected teacher |
| `Ctrl+D` | Delete teacher |
| `Ctrl+P` | Print timetable |
| `Ctrl+ +` | Increase timetable font size |
| `Ctrl+ -` | Decrease timetable font size |
| `F11` | Toggle fullscreen |
| `Esc` | Exit fullscreen |
| `↑` / `↓` | Navigate teachers list |
| `Alt+F` | Open File menu |
| `Alt+E` | Open Edit menu |
| `Alt+V` | Open View menu |
| `Alt+T` | Open Tools menu |
| `Alt+H` | Open Help menu |

---

## 🛠️ Technical Details

### **Architecture**
- **GUI Framework:** Tkinter (Python's standard GUI library)
- **Database:** SQLite 3
- **Data Processing:** Pandas for Excel/CSV operations
- **PDF Generation:** ReportLab
- **Packaging:** PyInstaller (for Windows executable)

### **File Structure**
```
Teachers-App/
├── Teachers App.py          # Main application file
├── database.db              # SQLite database (auto-created)
├── VERSION.txt              # Version information
├── Setup.iss                # Inno Setup installer script
├── version_info.txt         # Version info for PyInstaller
├── App_icon.ico             # Application icon
├── Icon-Setup.ico           # Installer icon
├── README.md                # This file
└── Samples/                 # Sample data directory
```

### **System Requirements**
- **OS:** Windows 7 or later
- **RAM:** 512 MB minimum
- **Disk Space:** 100 MB for installation
- **Python:** 3.8+ (if running from source)

---

## 📝 Configuration

### **Period Timings (Default)**
| Period | Start | End |
|--------|-------|-----|
| 1 | 08:30 | 09:15 |
| 2 | 09:15 | 10:00 |
| 3 | 10:00 | 10:45 |
| 4 | 10:45 | 11:30 |
| 5 | 11:30 | 12:15 |
| 6 | 12:15 | 13:00 |
| 7 | 13:00 | 13:45 |
| 8 | 13:45 | 14:30 |

Edit via **Edit → Add Period** or **File → Edit Period Timings**.

---

## ⚠️ Troubleshooting

### **App won't start**
- Ensure Python 3.8+ is installed (if running from source)
- Reinstall the application or required packages
- Check that `database.db` file isn't corrupted

### **Database errors**
- **Solution:** Backup current database, delete it, and restart app (it will recreate)
- Use **File → Backup Database** first to preserve data

### **Search not working**
- Click in the search box and clear any placeholder text
- Try searching with partial names

### **Print/PDF issues**
- Ensure a teacher is selected before printing
- Check disk space for PDF file saving

### **Import fails**
- Verify Excel file has correct column names (case-insensitive)
- Ensure no blank rows in data
- Try converting XLS to XLSX format

---

## 📋 Version History

### **v1.5.1** (Current)
- Enhanced UI with modern styling
- Keyboard shortcut system
- Blink animation for current class
- Dark mode (OLED) support
- Bulk delete functionality
- Teacher pinning feature
- Improved search with real-time filtering
- Database backup feature

---

## 👨‍💻 Author

**Nikhil KY**  
GitHub: [@NikhilKY64](https://github.com/NikhilKY64)

---

## 📞 Support

For issues, questions, or suggestions:
1. Check this README first
2. Review the Help menu within the app (**Help → How to Use**)
3. Contact the developer via GitHub or gmail

---

## Quick Links
- 🏠 [Home](https://github.com/NikhilKY64/Teachers-App)
- 🐛 [Report Bug](https://github.com/NikhilKY64/Teachers-App/issues)
- ⭐ [Star this project](https://github.com/NikhilKY64/Teachers-App)

---

*Teachers Timetable App - Simplifying School Scheduling* 📚✏️
