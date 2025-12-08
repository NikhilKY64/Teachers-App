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

## Technologies Used

| Component | Technology |
|----------|------------|
| Language | Python 3.10.10 |
| UI Library | Tkinter / ttk |
| Optional UI | CustomTkinter |
| Database | SQLite (database.db) |
| Excel Support | pandas + openpyxl |

---

## Installation

### 1. Install AppSetup-v1.x.x.exe

```sh
Run the setup and save the app in Readable/Writable location.
```

## Run the Application

```sh
Open the "Teachers App" shotcut created on desktop.
```

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

## Backup

- Clicking the backup option generates a file with this format:

```
database_bkp_YYYY-MM-DD_HH-MM.db
```

---

## Etc.

---

## Author

Created by **Nikhil**.

Feedback, feature requests, or improvements are welcome.
