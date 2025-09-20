import sqlite3
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

DB_PATH = "words.db"
REFRESH_INTERVAL = 5000
ACTIVE_THRESHOLD_MINUTES = 5

class AdminApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Адмін-перегляд бази")
        self.geometry("950x600")

        # Користувачі
        tk.Label(self, text="Користувачі").pack()
        self.users_tree = ttk.Treeview(self, columns=("user_id", "username", "start_date", "last_active"), show="headings")
        for col in ("user_id", "username", "start_date", "last_active"):
            self.users_tree.heading(col, text=col, command=lambda c=col: self.sort_by_column(c))
            self.users_tree.column(col, width=200)
        self.users_tree.pack(fill=tk.X)
        self.users_tree.bind("<<TreeviewSelect>>", self.on_user_select)

        # Label для поточного користувача
        self.current_user_label = tk.Label(self, text="Слова користувача: ")
        self.current_user_label.pack()

        # Слова користувача
        self.words_tree = ttk.Treeview(self, columns=("word", "translation", "usage_count"), show="headings")
        for col in ("word", "translation", "usage_count"):
            self.words_tree.heading(col, text=col)
            self.words_tree.column(col, width=200)
        self.words_tree.pack(fill=tk.BOTH, expand=True)

        self.selected_user_id = None
        self.sort_column = None
        self.sort_reverse = False

        self.update_users_table()

    def update_users_table(self):
        for row in self.users_tree.get_children():
            self.users_tree.delete(row)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, start_date, last_active FROM users")
        users = cursor.fetchall()
        conn.close()

        now = datetime.now()
        active_users = []
        inactive_users = []

        for u in users:
            user_id, username, start_date, last_active = u
            active = False
            if last_active:
                try:
                    last_active_dt = datetime.fromisoformat(last_active)
                    if now - last_active_dt < timedelta(minutes=ACTIVE_THRESHOLD_MINUTES):
                        active = True
                except:
                    pass
            if active:
                active_users.append(u)
            else:
                inactive_users.append(u)

        def sort_key(user):
            if not self.sort_column:
                return user[0]
            col_index = ("user_id", "username", "start_date", "last_active").index(self.sort_column)
            value = user[col_index]
            if self.sort_column == "user_id":
                return int(value)
            elif self.sort_column in ("start_date", "last_active"):
                try:
                    return datetime.fromisoformat(value)
                except:
                    return datetime.min
            else:
                return value

        active_users.sort(key=sort_key, reverse=self.sort_reverse)
        inactive_users.sort(key=sort_key, reverse=self.sort_reverse)

        for u in active_users:
            self.users_tree.insert("", tk.END, values=u, tags=("active",))
        for u in inactive_users:
            self.users_tree.insert("", tk.END, values=u)

        self.users_tree.tag_configure("active", background="lightgreen")

        if self.selected_user_id:
            self.update_words_table(self.selected_user_id)

        self.after(REFRESH_INTERVAL, self.update_users_table)

    def update_words_table(self, user_id):
        # Оновлюємо лейбл з поточним користувачем
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        username = result[0] if result else str(user_id)
        self.current_user_label.config(text=f"Слова користувача: {username}")

        for row in self.words_tree.get_children():
            self.words_tree.delete(row)

        cursor.execute("""
            SELECT word, translation, usage_count
            FROM user_words
            WHERE user_id=?
        """, (user_id,))
        for w in cursor.fetchall():
            self.words_tree.insert("", tk.END, values=w)
        conn.close()

    def on_user_select(self, event):
        selected = self.users_tree.selection()
        if selected:
            user_id = self.users_tree.item(selected[0])["values"][0]
            self.selected_user_id = user_id
            self.update_words_table(user_id)

    def sort_by_column(self, col):
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        self.update_users_table()


if __name__ == "__main__":
    app = AdminApp()
    app.mainloop()
