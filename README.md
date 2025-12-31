!(https://img.shields.io/github/downloads/NikhilKY64/Teachers-App/v2.0/TeacherAppSetup.exe?label=Teacher%20App%20Setup&color=blue&style=for-the-badge)
!(https://img.shields.io/github/downloads/NikhilKY64/Teachers-App/v2.0/ClassStatusSetup.exe?label=Class%20Status%20Setup&color=orange&style=for-the-badge)


![TeacherAppSetup Downloads](https://img.shields.io/github/downloads/NikhilKY64/Teachers-App/v2.0/TeacherAppSetup.exe)
![ClassStatusSetup Downloads](https://img.shields.io/github/downloads/NikhilKY64/Teachers-App/v2.0/ClassStatusSetup.exe)
![v1.5.4](https://img.shields.io/github/downloads/NikhilKY64/Teachers-App/v1.5.4/total)
![v1.5.2](https://img.shields.io/github/downloads/NikhilKY64/Teachers-App/v1.5.2/total)
![v1.5.1](https://img.shields.io/github/downloads/NikhilKY64/Teachers-App/v1.5.1/total)
![v1.4.2](https://img.shields.io/github/downloads/NikhilKY64/Teachers-App/v1.4.2/total)
![v1.0](https://img.shields.io/github/downloads/NikhilKY64/Teachers-App/v1.0/total)



# Teachers App

The Teachers App is a desktop application built using Python and Tkinter to help schools manage and view teacher timetables. The app includes features such as timetable viewing, searching, data import/export, blinking highlight for ongoing classes, and database backup/restore.

---

## Features

- View teacher timetables
- Search teachers instantly
- Highlight current teaching period
- Blinking effect for active time slot
- Toggle between Old UI and New UI
- Add, edit, delete teacher information
- Import and export data via Excel
- Backup (database_bkp_YYYY-MM-DD_HH-MM.db)
- Pin teachers (priority display)

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl + S | Focus search bar |
| Ctrl + P | Print timetable |
| Ctrl + Plus / Minus | Increase or decrease timetable text size |
| F11 | Toggle fullscreen |
| ESC | Exit fullscreen |

---
## Installation

### 1. Install AppSetup-v1.x.x.exe

Run the setup and save the app in Readable/Writable location.

## Run the Application

Open the "Teachers App.exe" , shotcut created on desktop.

---

## How It Works

- The application loads timetable and teacher records from the SQLite database.
- Users can select a teacher to view their schedule.
- A timed check runs every seconds to detect the current class and highlight that cell.
- Excel files can be imported or exported to update teacher data.
- Backup features help prevent data loss.

---

## Project Structure

```
Teachers-App/
|
├── Teachers App.py                                  # App code
└── database.db -OR- School.db (In Old verson)       # SQLite database
```

---
## How to Use

1. Start the app  
2. Select a teacher from the left panel  
3. The timetable will appear on the right  
4. Use the menu bar to:
   - Import / Export Excel files  
   - Adjust timetable size  
   - Change theme  
   - Backup database  

Tip: Use the search box to quickly find teachers.

---

## Backup Information

When using the backup option, the app will generate files formatted as:

```
database_bkp_YYYY-MM-DD_HH-MM.db
```

---

## Author

Created by **Nikhil**.

Feedback, feature requests, or improvements are welcome.
