# Blood Bank Management System

A desktop donor registry built with Python, Tkinter/ttk, SQLite, and Matplotlib. Add donor details, browse saved records in a table, and click the chart bars to inspect the donor count for each blood group. Adding a record refreshes the table, summary, and chart immediately.

## Run

1. Install Python 3.10 or newer. Tkinter is included with most Windows and macOS Python distributions. On Linux, install the distribution's `python3-tk` package if needed.
2. Install Matplotlib:

   ```bash
   python -m pip install matplotlib
   ```

3. From this folder, start the app:

   ```bash
   python blood_bank.py
   ```

The app creates `donors.db` beside `blood_bank.py` on first launch. Donor records remain on that computer between runs.

## Features

- Add a donor's name, age, blood group, and contact number or email.
- Validate required fields and accepted blood groups before saving.
- View all saved donors in a sortable-looking, scrollable `ttk.Treeview` table (newest first).
- View counts across A+, A-, B+, B-, AB+, AB-, O+, and O- in a Matplotlib bar chart.
- Select a chart bar to see that group's current registered donor count.
- Keep donor records in a local SQLite database.

## Data note

The chart counts registered donor records by blood group. It does not track donation dates, screening results, blood components, expiry dates, or physical stock, so its counts should not be interpreted as medically cleared or available units of blood.

