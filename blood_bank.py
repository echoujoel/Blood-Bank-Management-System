"""Blood Bank Management System

A small desktop application for recording blood donors and viewing the number
of registered donors in each blood group. Donor records are stored in a local
SQLite database beside this script. The chart is a live view of donor records;
it is not a measure of medically screened or physically available blood units.

Run with: python blood_bank.py
Dependencies: Python 3.10+ and Matplotlib (Tkinter is included with most
standard Python installations; on Linux it may need a separate OS package).
"""

from __future__ import annotations

import re
import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


APP_TITLE = "Blood Bank Management System"
BLOOD_GROUPS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")
DATABASE_PATH = Path(__file__).with_name("donors.db")


class DonorStore:
    """Create and query the local donor database."""

    def __init__(self, database_path: Path = DATABASE_PATH) -> None:
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS donors (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT NOT NULL,
                   age INTEGER NOT NULL CHECK (age BETWEEN 1 AND 120),
                   blood_group TEXT NOT NULL,
                   contact TEXT NOT NULL,
                   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        self.connection.commit()

    def add_donor(self, name: str, age: int, blood_group: str, contact: str) -> int:
        """Save one donor and return its database ID."""
        cursor = self.connection.execute(
            "INSERT INTO donors (name, age, blood_group, contact) VALUES (?, ?, ?, ?)",
            (name, age, blood_group, contact),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def list_donors(self) -> list[sqlite3.Row]:
        """Return donor records in most recently added first order."""
        return list(
            self.connection.execute(
                "SELECT id, name, age, blood_group, contact FROM donors ORDER BY id DESC"
            )
        )

    def group_counts(self) -> dict[str, int]:
        """Return donor counts for all eight blood groups, including zeroes."""
        counts = {group: 0 for group in BLOOD_GROUPS}
        rows = self.connection.execute(
            "SELECT blood_group, COUNT(*) AS total FROM donors GROUP BY blood_group"
        )
        counts.update({row["blood_group"]: int(row["total"]) for row in rows})
        return counts

    def close(self) -> None:
        self.connection.close()


def validate_donor(name: str, age_text: str, blood_group: str, contact: str) -> tuple[str, int, str, str]:
    """Normalize and validate user-entered donor details."""
    clean_name = " ".join(name.split())
    clean_contact = contact.strip()
    if not clean_name:
        raise ValueError("Enter the donor's name.")
    if len(clean_name) > 100:
        raise ValueError("Name must be 100 characters or fewer.")
    try:
        age = int(age_text.strip())
    except ValueError as exc:
        raise ValueError("Age must be a whole number.") from exc
    if not 1 <= age <= 120:
        raise ValueError("Age must be between 1 and 120.")
    if blood_group not in BLOOD_GROUPS:
        raise ValueError("Choose a valid blood group.")
    if not clean_contact:
        raise ValueError("Enter a contact number or email address.")
    if len(clean_contact) > 60 or not re.search(r"[A-Za-z0-9]", clean_contact):
        raise ValueError("Enter a valid contact number or email address (60 characters max).")
    return clean_name, age, blood_group, clean_contact


class BloodBankApp:
    """Tkinter interface for donor entry, donor records, and group counts."""

    BG = "#f4f7fb"
    CARD = "#ffffff"
    INK = "#172b4d"
    MUTED = "#718096"
    ACCENT = "#b4233c"
    BORDER = "#e3e9f2"

    def __init__(self, root: tk.Tk, store: DonorStore) -> None:
        self.root = root
        self.store = store
        self.root.title(APP_TITLE)
        self.root.configure(bg=self.BG)
        self.root.minsize(1000, 680)
        self.root.geometry("1280x820")
        self._configure_styles()
        self._build_layout()
        self.refresh_views()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=34,
                        background=self.CARD, fieldbackground=self.CARD, foreground=self.INK)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"),
                        background="#eef2f7", foreground="#53657f", padding=(10, 10))
        style.map("Treeview", background=[("selected", "#fce8ec")],
                  foreground=[("selected", self.INK)])
        style.configure("TCombobox", padding=8, font=("Segoe UI", 10))

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = tk.Frame(self.root, bg=self.CARD, height=86, highlightbackground=self.BORDER,
                          highlightthickness=1)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        tk.Label(header, text="Blood Bank", bg=self.CARD, fg=self.INK,
                 font=("Segoe UI", 21, "bold")).pack(anchor="w", padx=28, pady=(15, 0))
        tk.Label(header, text="Donor records and blood group overview", bg=self.CARD,
                 fg=self.MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=29, pady=(0, 12))

        body = tk.Frame(self.root, bg=self.BG)
        body.grid(row=1, column=0, sticky="nsew", padx=24, pady=22)
        body.columnconfigure(0, weight=0, minsize=310)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)
        self._build_form(body)
        self._build_summary(body)
        self._build_donor_table(body)
        self._build_chart(body)

        footer = tk.Frame(self.root, bg=self.BG)
        footer.grid(row=2, column=0, sticky="ew", padx=26, pady=(0, 12))
        tk.Label(footer, text="Chart counts registered donors; it does not represent screened or stored units.",
                 bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w")

    def _card(self, parent: tk.Widget, row: int, column: int, *, padx: tuple[int, int] = (0, 0),
              pady: tuple[int, int] = (0, 0)) -> tk.Frame:
        frame = tk.Frame(parent, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        frame.grid(row=row, column=column, sticky="nsew", padx=padx, pady=pady)
        return frame

    def _build_form(self, parent: tk.Frame) -> None:
        card = self._card(parent, 0, 0, padx=(0, 16), pady=(0, 16))
        card.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 16), pady=(0, 16))
        card.grid_columnconfigure(0, weight=1)
        tk.Label(card, text="Add a donor", bg=self.CARD, fg=self.INK,
                 font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w", padx=22, pady=(22, 4))
        tk.Label(card, text="Enter the donor details below.", bg=self.CARD, fg=self.MUTED,
                 font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", padx=22, pady=(0, 18))

        self.name_var = tk.StringVar()
        self.age_var = tk.StringVar()
        self.group_var = tk.StringVar()
        self.contact_var = tk.StringVar()
        self._form_field(card, 2, "Full name", self.name_var)
        self._form_field(card, 4, "Age", self.age_var)
        tk.Label(card, text="Blood group", bg=self.CARD, fg="#46566e",
                 font=("Segoe UI", 9, "bold")).grid(row=6, column=0, sticky="w", padx=22, pady=(13, 5))
        group_box = ttk.Combobox(card, textvariable=self.group_var, values=BLOOD_GROUPS,
                                 state="readonly", font=("Segoe UI", 10))
        group_box.grid(row=7, column=0, sticky="ew", padx=22)
        self._form_field(card, 8, "Contact number or email", self.contact_var)

        self.add_button = tk.Button(card, text="Add donor", command=self.add_donor,
                                    bg=self.ACCENT, fg="white", activebackground="#941c31",
                                    activeforeground="white", relief="flat", bd=0,
                                    font=("Segoe UI", 10, "bold"), cursor="hand2", pady=11)
        self.add_button.grid(row=10, column=0, sticky="ew", padx=22, pady=(25, 10))
        self.root.bind("<Return>", lambda _event: self.add_donor())
        self.status_var = tk.StringVar(value="Donor details are stored on this computer.")
        tk.Label(card, textvariable=self.status_var, bg=self.CARD, fg=self.MUTED,
                 font=("Segoe UI", 9), wraplength=255, justify="left").grid(
                     row=11, column=0, sticky="w", padx=22, pady=(4, 20))

    def _form_field(self, parent: tk.Frame, row: int, label: str, variable: tk.StringVar) -> None:
        tk.Label(parent, text=label, bg=self.CARD, fg="#46566e",
                 font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", padx=22, pady=(13, 5))
        entry = tk.Entry(parent, textvariable=variable, relief="flat", bg="#f8fafc", fg=self.INK,
                         insertbackground=self.INK, font=("Segoe UI", 10), highlightthickness=1,
                         highlightbackground=self.BORDER, highlightcolor="#b4233c")
        entry.grid(row=row + 1, column=0, sticky="ew", padx=22, ipady=9)

    def _build_summary(self, parent: tk.Frame) -> None:
        card = self._card(parent, 0, 1, pady=(0, 16))
        card.grid_columnconfigure(1, weight=1)
        tk.Label(card, text="Registered donors", bg=self.CARD, fg=self.MUTED,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 0))
        self.total_var = tk.StringVar(value="0")
        tk.Label(card, textvariable=self.total_var, bg=self.CARD, fg=self.INK,
                 font=("Segoe UI", 23, "bold")).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))
        self.groups_summary = tk.StringVar(value="0 / 8 blood groups represented")
        tk.Label(card, textvariable=self.groups_summary, bg=self.CARD, fg=self.MUTED,
                 font=("Segoe UI", 10)).grid(row=1, column=1, sticky="e", padx=20, pady=(0, 4))

    def _build_donor_table(self, parent: tk.Frame) -> None:
        card = self._card(parent, 1, 1, pady=(0, 16))
        card.grid_rowconfigure(1, weight=1)
        card.grid_columnconfigure(0, weight=1)
        tk.Label(card, text="Donor records", bg=self.CARD, fg=self.INK,
                 font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w", padx=18, pady=(15, 10))
        columns = ("name", "age", "blood_group", "contact")
        self.tree = ttk.Treeview(card, columns=columns, show="headings", selectmode="browse")
        headings = (("name", "DONOR NAME", 190), ("age", "AGE", 65),
                    ("blood_group", "BLOOD GROUP", 110), ("contact", "CONTACT", 210))
        for key, title, width in headings:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=55 if key == "age" else 100,
                             anchor="center" if key in ("age", "blood_group") else "w", stretch=True)
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(16, 0), pady=(0, 16))
        scrollbar = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 12), pady=(0, 16))
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.tag_configure("odd", background="#f8fafc")

    def _build_chart(self, parent: tk.Frame) -> None:
        card = self._card(parent, 2, 1)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)
        tk.Label(card, text="Blood group availability", bg=self.CARD, fg=self.INK,
                 font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w", padx=18, pady=(13, 0))
        self.figure = Figure(figsize=(7.5, 2.7), dpi=100, facecolor=self.CARD, constrained_layout=True)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=card)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 0))
        toolbar = NavigationToolbar2Tk(self.canvas, card, pack_toolbar=False)
        toolbar.update()
        toolbar.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 8))
        self.chart_note = tk.StringVar(value="Select a bar to see its registered donor count.")
        tk.Label(card, textvariable=self.chart_note, bg=self.CARD, fg=self.MUTED,
                 font=("Segoe UI", 9)).grid(row=3, column=0, sticky="w", padx=18, pady=(0, 12))
        self.canvas.mpl_connect("pick_event", self._on_bar_pick)

    def add_donor(self) -> None:
        """Validate the form, save the donor, and refresh both data views."""
        try:
            name, age, blood_group, contact = validate_donor(
                self.name_var.get(), self.age_var.get(), self.group_var.get(), self.contact_var.get()
            )
        except ValueError as exc:
            self.status_var.set(str(exc))
            messagebox.showwarning("Check donor details", str(exc), parent=self.root)
            return

        try:
            donor_id = self.store.add_donor(name, age, blood_group, contact)
        except sqlite3.Error as exc:
            self.status_var.set("The donor record could not be saved.")
            messagebox.showerror("Could not save donor", f"The donor record could not be saved.\n\n{exc}",
                                 parent=self.root)
            return

        # Clear the completed form before refreshing. If a chart/table error
        # occurs, the user can see that the database save succeeded and won't
        # accidentally submit the same donor again by pressing the button.
        self.name_var.set("")
        self.age_var.set("")
        self.group_var.set("")
        self.contact_var.set("")
        try:
            self.refresh_views()
        except Exception as exc:
            self.status_var.set(f"Donor record #{donor_id} was saved, but the display did not refresh.")
            messagebox.showerror(
                "Donor saved; refresh failed",
                f"Donor record #{donor_id} was saved, but the table or chart could not refresh.\n\n{exc}",
                parent=self.root,
            )
            return
        self.status_var.set(f"Donor record #{donor_id} added successfully.")

    def refresh_views(self) -> None:
        """Refresh the donor table, total, and blood group chart from SQLite."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        donors = self.store.list_donors()
        for index, donor in enumerate(donors):
            self.tree.insert("", "end", values=(donor["name"], donor["age"],
                                                  donor["blood_group"], donor["contact"]),
                             tags=("odd",) if index % 2 else ())
        counts = self.store.group_counts()
        total = sum(counts.values())
        self.total_var.set(str(total))
        self.groups_summary.set(f"{sum(value > 0 for value in counts.values())} / 8 blood groups represented")
        self._draw_chart(counts)

    def _draw_chart(self, counts: dict[str, int]) -> None:
        self.axes.clear()
        bars = self.axes.bar(BLOOD_GROUPS, [counts[group] for group in BLOOD_GROUPS],
                             color=["#b4233c" if counts[group] else "#dce3ed" for group in BLOOD_GROUPS],
                             width=0.62, picker=5)
        self.axes.set_ylabel("Registered donors", color=self.MUTED, fontsize=9)
        self.axes.set_ylim(0, max(1, max(counts.values(), default=0) * 1.22))
        self.axes.set_xticks(range(len(BLOOD_GROUPS)), BLOOD_GROUPS)
        self.axes.tick_params(axis="x", colors=self.INK, labelsize=9, length=0, pad=7)
        self.axes.tick_params(axis="y", colors=self.MUTED, labelsize=8, length=0)
        for spine_name in ("top", "right", "left"):
            self.axes.spines[spine_name].set_visible(False)
        self.axes.spines["bottom"].set_color(self.BORDER)
        self.axes.grid(axis="y", color="#e9eef5", linewidth=0.8)
        self.axes.set_axisbelow(True)
        self.axes.set_title("Donor records by blood group", loc="left", color=self.MUTED,
                            fontsize=9, pad=8)
        for bar, group in zip(bars, BLOOD_GROUPS):
            self.axes.annotate(str(counts[group]),
                               (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                               xytext=(0, 4), textcoords="offset points", ha="center",
                               va="bottom", fontsize=8, color=self.MUTED)
        self.canvas.draw_idle()

    def _on_bar_pick(self, event: object) -> None:
        artist = getattr(event, "artist", None)
        index = self.axes.patches.index(artist) if artist in self.axes.patches else None
        if index is not None:
            counts = self.store.group_counts()
            group = BLOOD_GROUPS[index]
            self.chart_note.set(f"{group}: {counts[group]} registered donor(s).")

    def close(self) -> None:
        self.store.close()
        self.root.destroy()


def main() -> None:
    """Start the desktop application."""
    root = tk.Tk()
    store = DonorStore()
    BloodBankApp(root, store)
    root.mainloop()


if __name__ == "__main__":
    main()

