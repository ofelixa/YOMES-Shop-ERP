# main.py
import os
import sys
import ctypes
import re
import customtkinter as ctk
from tkinter import messagebox, ttk, filedialog
from datetime import datetime, timedelta
import calendar
import csv
from PIL import Image, ImageTk
import db_manager as db
import printing_engine as pe

# Matplotlib for Analytics Dashboard
import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

if sys.platform.startswith("win"):
    myappid = "yomes.electrical.erp.v1"
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, relative_path)


def find_highres_image_file():
    """Finds image files (JPEG/PNG) strictly for inside visuals and watermarks."""
    extensions = ["jpeg", "jpg", "png", "JPEG", "JPG", "PNG"]
    base_names = ["YOMES", "yomes", "logo", "icon", "Logo", "Icon"]

    for ext in extensions:
        for name in base_names:
            candidate = f"{name}.{ext}"
            path = resource_path(candidate)
            if os.path.exists(path):
                return path

    base_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        for file in os.listdir(base_dir):
            if any(file.lower().endswith(f".{ext.lower()}") for ext in extensions):
                return os.path.join(base_dir, file)
    except Exception:
        pass
    return None


def find_ico_file():
    """Finds .ico strictly for Windows binary taskbar/window icon."""
    for candidate in ["YOMES.ico", "icon.ico", "yomes.ico"]:
        p = resource_path(candidate)
        if os.path.exists(p):
            return p
    return None


class MasterShopERP(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YOMES Electrical & Home Solution")
        self.geometry("1180x720")
        self.minsize(980, 600)

        try:
            self.after(50, lambda: self.state('zoomed'))
        except Exception:
            pass

        self.ico_path = find_ico_file()
        self.visual_image_path = find_highres_image_file()
        self._cached_images = {}
        self._window_icon_photo = None

        self.apply_window_icon()

        db.init_db()
        self.current_user = None
        self.cart = []
        self.all_products = []
        self.filtered_products = []
        self.selected_product = None
        self.customer_map = {}

        self.selected_history_date = datetime.now().strftime("%Y-%m-%d")
        self.analytics_timeframe = "Last 7 Days"

        self.show_login_screen()

    def apply_window_icon(self):
        if self.ico_path and os.path.exists(self.ico_path):
            try:
                self.iconbitmap(self.ico_path)
                self.after(200, lambda: self.iconbitmap(self.ico_path))
            except Exception:
                pass

        img_source = self.visual_image_path or self.ico_path
        if img_source and os.path.exists(img_source):
            try:
                pil_img = Image.open(img_source).convert("RGBA")
                self._window_icon_photo = ImageTk.PhotoImage(pil_img.resize((32, 32)))
                self.iconphoto(False, self._window_icon_photo)
            except Exception:
                pass

    def toggle_theme(self):
        current = ctk.get_appearance_mode()
        if current == "Dark":
            ctk.set_appearance_mode("Light")
            self.theme_btn.configure(text="Dark Mode")
        else:
            ctk.set_appearance_mode("Dark")
            self.theme_btn.configure(text="Light Mode")

    def load_ctk_image(self, size=(60, 60), opacity=1.0):
        target_path = self.visual_image_path or self.ico_path
        if not target_path or not os.path.exists(target_path):
            return None

        cache_key = f"{size}_{opacity}"
        if cache_key in self._cached_images:
            return self._cached_images[cache_key]

        try:
            pil_img = Image.open(target_path).convert("RGBA")
            if opacity < 1.0:
                r, g, b, alpha = pil_img.split()
                alpha = alpha.point(lambda p: int(p * opacity))
                pil_img.putalpha(alpha)

            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
            self._cached_images[cache_key] = ctk_img
            return ctk_img
        except Exception:
            return None

    def attach_page_watermark(self):
        wm_img = self.load_ctk_image(size=(360, 360), opacity=0.08)
        if wm_img:
            lbl = ctk.CTkLabel(self.content_area, image=wm_img, text="")
            lbl.place(relx=0.5, rely=0.52, anchor="center")
            lbl.lower()

    # =========================================================================
    # REUSABLE COLUMN SORTING ENGINE
    # =========================================================================
    def sort_treeview_column(self, tv, col, reverse):
        clean_col_name = col.replace(" ▲", "").replace(" ▼", "")

        def extract_sort_key(element):
            val = element[0]
            if val is None:
                return (0, 0.0)
            s = str(val).strip()
            s_clean = s.replace("GHS", "").replace("GH¢", "").replace("%", "").replace(",", "").strip()
            match = re.search(r"^[-+]?\d+(?:\.\d+)?", s_clean)
            if match:
                try:
                    return (0, float(match.group()))
                except ValueError:
                    pass
            return (1, s.lower())

        data = [(tv.set(k, clean_col_name), k) for k in tv.get_children("")]
        data.sort(key=extract_sort_key, reverse=reverse)

        for index, (val, k) in enumerate(data):
            tv.move(k, "", index)

        for c in tv["columns"]:
            raw = c.replace(" ▲", "").replace(" ▼", "")
            tv.heading(c, text=raw)

        arrow = " ▼" if reverse else " ▲"
        tv.heading(clean_col_name, text=f"{clean_col_name}{arrow}",
                   command=lambda: self.sort_treeview_column(tv, clean_col_name, not reverse))

    # =========================================================================
    # 1. LOGIN & AUTH
    # =========================================================================
    def show_login_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(self, width=420, height=530, corner_radius=35)
        card.place(relx=0.5, rely=0.5, anchor="center")

        logo_img = self.load_ctk_image(size=(80, 80), opacity=0.95)
        if logo_img:
            self.login_logo_label = ctk.CTkLabel(card, image=logo_img, text="")
            self.login_logo_label.pack(pady=(25, 0))
            title_top_pad = (5, 5)
        else:
            title_top_pad = (35, 5)

        ctk.CTkLabel(card, text="YOMES ELECTRICAL", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color="#3B82F6").pack(pady=title_top_pad)
        ctk.CTkLabel(card, text="Enterprise Shop & Inventory System", font=ctk.CTkFont(size=12),
                     text_color="gray").pack(pady=(0, 20))

        self.ent_user = ctk.CTkEntry(card, placeholder_text="Username", width=240, height=32, corner_radius=15)
        self.ent_user.pack(pady=8)

        self.ent_pass = ctk.CTkEntry(card, placeholder_text="Password", show="*", width=240, height=32,
                                     corner_radius=15)
        self.ent_pass.pack(pady=8)

        self.ent_user.bind("<Return>", lambda e: self.ent_pass.focus_set())
        self.ent_user.bind("<Down>", lambda e: self.ent_pass.focus_set())
        self.ent_user.bind("<Up>", lambda e: self.ent_user.focus_set())
        self.ent_pass.bind("<Return>", lambda e: self.handle_login())

        ctk.CTkButton(card, text="Sign In", width=290, height=42, command=self.handle_login).pack(pady=(15, 10))
        ctk.CTkButton(card, text="Forgot Password?", fg_color="transparent", text_color="#60A5FA",
                      command=self.show_forgot_password_dialog).pack()

        self.after(100, lambda: self.ent_user.focus_force())

    def handle_login(self):
        u = self.ent_user.get().strip()
        p = self.ent_pass.get()
        if not u or not p:
            messagebox.showwarning("Missing", "Please provide both username and password.")
            return

        user = db.authenticate_user(u, p)
        if not user:
            messagebox.showerror("Auth Error", "Invalid username or password.")
            return

        self.current_user = user
        if user['must_change_password'] == 1:
            self.show_first_time_password_dialog()
        else:
            self.load_main_dashboard()

    def show_first_time_password_dialog(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Security Setup")
        modal.geometry("460x420")
        modal.grab_set()

        ctk.CTkLabel(modal, text="Mandatory Password Update", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=15)
        p1 = ctk.CTkEntry(modal, placeholder_text="New Password", show="*", width=300)
        p1.pack(pady=8)
        p1.focus_set()

        p2 = ctk.CTkEntry(modal, placeholder_text="Confirm New Password", show="*", width=300)
        p2.pack(pady=8)

        sec_q = ctk.CTkComboBox(modal, width=300, values=[
            "What is your mother's maiden name?",
            "What was the name of your first school?",
            "What city were you born in?",
            "What is your favorite electrical brand?"
        ])
        sec_q.pack(pady=8)
        sec_a = ctk.CTkEntry(modal, placeholder_text="Security Answer", width=300)
        sec_a.pack(pady=8)

        def save():
            np = p1.get()
            if len(np) < 4 or np != p2.get() or not sec_a.get().strip():
                messagebox.showerror("Invalid", "Please check that passwords match and all fields are complete.")
                return
            db.update_user_password(self.current_user['id'], np, sec_q.get(), sec_a.get())
            modal.destroy()
            self.load_main_dashboard()

        p1.bind("<Return>", lambda e: p2.focus_set())
        p1.bind("<Down>", lambda e: p2.focus_set())
        p2.bind("<Return>", lambda e: sec_a.focus_set())
        p2.bind("<Down>", lambda e: sec_a.focus_set())
        p2.bind("<Up>", lambda e: p1.focus_set())
        sec_a.bind("<Up>", lambda e: p2.focus_set())
        sec_a.bind("<Return>", lambda e: save())

        ctk.CTkButton(modal, text="Save Credentials", width=300, height=40, command=save).pack(pady=15)

    def show_forgot_password_dialog(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Account Recovery")
        modal.geometry("450x380")
        modal.grab_set()

        ctk.CTkLabel(modal, text="Self-Service Password Reset", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=15)
        ent_u = ctk.CTkEntry(modal, placeholder_text="Enter Username", width=300)
        ent_u.pack(pady=8)
        ent_u.focus_set()

        q_lbl = ctk.CTkLabel(modal, text="Question: [Click Load Question]", text_color="#93C5FD")
        q_lbl.pack(pady=4)
        ent_a = ctk.CTkEntry(modal, placeholder_text="Security Answer", width=300)
        ent_a.pack(pady=8)
        ent_np = ctk.CTkEntry(modal, placeholder_text="New Password", show="*", width=300)
        ent_np.pack(pady=8)

        def load_q():
            target_user = ent_u.get().strip()
            if not target_user:
                messagebox.showwarning("Notice", "Please enter your username first.")
                return

            conn = db.get_connection()
            user = conn.execute("SELECT security_question FROM users WHERE LOWER(username) = LOWER(?)",
                                (target_user,)).fetchone()
            conn.close()

            if user and user['security_question']:
                q_lbl.configure(text=f"Question: {user['security_question']}", text_color="#93C5FD")
                ent_a.focus_set()
            else:
                q_lbl.configure(text="No recovery question found for this account.", text_color="#EF4444")
                messagebox.showwarning("Notice", "User not found or no recovery question configured.")

        def exec_reset():
            ok, msg = db.reset_password_with_security(ent_u.get().strip(), ent_a.get().strip(), ent_np.get())
            if ok:
                messagebox.showinfo("Success", msg)
                modal.destroy()
            else:
                messagebox.showerror("Error", msg)

        ent_u.bind("<Return>", lambda e: load_q())
        ent_a.bind("<Return>", lambda e: ent_np.focus_set())
        ent_np.bind("<Return>", lambda e: exec_reset())

        f = ctk.CTkFrame(modal, fg_color="transparent")
        f.pack(pady=10)
        ctk.CTkButton(f, text="Load Question", width=140, command=load_q).pack(side="left", padx=5)
        ctk.CTkButton(f, text="Reset Password", width=140, fg_color="green", command=exec_reset).pack(side="left",
                                                                                                      padx=5)

    def show_change_password_dialog(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Change Account Password")
        modal.geometry("400x380")
        modal.grab_set()

        ctk.CTkLabel(modal, text=f"Change Password: @{self.current_user['username']}",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 10))

        old_p = ctk.CTkEntry(modal, placeholder_text="Current Password", show="*", width=280)
        old_p.pack(pady=8)
        old_p.focus_set()

        new_p = ctk.CTkEntry(modal, placeholder_text="New Password", show="*", width=280)
        new_p.pack(pady=8)

        confirm_p = ctk.CTkEntry(modal, placeholder_text="Confirm New Password", show="*", width=280)
        confirm_p.pack(pady=8)

        def execute_update():
            cur = old_p.get()
            np = new_p.get()
            cp = confirm_p.get()

            if not cur or not np:
                messagebox.showwarning("Missing Info", "Please fill in all password fields.")
                return

            if cur != self.current_user['password']:
                messagebox.showerror("Auth Error", "Current password does not match.")
                return

            if len(np) < 4:
                messagebox.showerror("Too Short", "New password must be at least 4 characters long.")
                return

            if np != cp:
                messagebox.showerror("Mismatch", "New password and confirmation do not match.")
                return

            ok, msg = db.update_user_password(self.current_user['id'], np)
            if ok:
                self.current_user['password'] = np
                messagebox.showinfo("Success", "Password updated successfully!")
                modal.destroy()
            else:
                messagebox.showerror("Error", f"Failed to update: {msg}")

        old_p.bind("<Return>", lambda e: new_p.focus_set())
        new_p.bind("<Return>", lambda e: confirm_p.focus_set())
        confirm_p.bind("<Return>", lambda e: execute_update())

        ctk.CTkButton(modal, text="Update Password", width=280, height=38,
                      fg_color="#2563EB", hover_color="#1D4ED8", command=execute_update).pack(pady=20)

    # =========================================================================
    # 2. MAIN DASHBOARD SHELL
    # =========================================================================
    def load_main_dashboard(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=190)
        self.grid_columnconfigure(1, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=190, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(13, weight=1)

        side_logo = self.load_ctk_image(size=(55, 55), opacity=1.0)
        if side_logo:
            self.sidebar_logo_lbl = ctk.CTkLabel(self.sidebar, image=side_logo, text="")
            self.sidebar_logo_lbl.grid(row=0, column=0, padx=20, pady=(15, 0))
            store_title_pad = (2, 5)
        else:
            store_title_pad = (20, 5)

        ctk.CTkLabel(self.sidebar, text="YOMES STORE", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=1, column=0, padx=20, pady=store_title_pad)
        ctk.CTkLabel(self.sidebar, text=f"{self.current_user['role']}: {self.current_user['full_name']}",
                     font=ctk.CTkFont(size=11), text_color="#60A5FA").grid(row=2, column=0, padx=20, pady=(0, 15))

        self.theme_btn = ctk.CTkButton(self.sidebar,
                                       text="Dark Mode" if ctk.get_appearance_mode() == "Light" else "Light Mode",
                                       fg_color="gray30", height=30, command=self.toggle_theme)
        self.theme_btn.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="ew")

        ctk.CTkButton(self.sidebar, text="Sales / Checkout", command=lambda: self.switch_view("POS")).grid(
            row=4, column=0, padx=15, pady=5, sticky="ew")
        ctk.CTkButton(self.sidebar, text="Sales History", fg_color="#1E3A8A", hover_color="#1E40AF",
                      command=lambda: self.switch_view("HISTORY")).grid(row=5, column=0, padx=15, pady=5, sticky="ew")
        ctk.CTkButton(self.sidebar, text="Inventory Master", command=lambda: self.switch_view("INV")).grid(
            row=6, column=0, padx=15, pady=5, sticky="ew")
        ctk.CTkButton(self.sidebar, text="Customers & Debts", command=lambda: self.switch_view("CUST")).grid(
            row=7, column=0, padx=15, pady=5, sticky="ew")

        if self.current_user['role'] == "Admin":
            ctk.CTkButton(self.sidebar, text="Storekeeper Mgmt", fg_color="#4338CA", hover_color="#3730A3",
                          command=lambda: self.switch_view("USERS")).grid(row=8, column=0, padx=15, pady=5, sticky="ew")
            ctk.CTkButton(self.sidebar, text="Analytics & Profit", fg_color="#0F766E", hover_color="#115E59",
                          command=lambda: self.switch_view("ANALYTICS")).grid(row=9, column=0, padx=15, pady=5,
                                                                              sticky="ew")
            ctk.CTkButton(self.sidebar, text="Backup & Restore", fg_color="#7C3AED", hover_color="#6D28D9",
                          command=self.show_backup_restore_modal).grid(row=10, column=0, padx=15, pady=5, sticky="ew")

        ctk.CTkButton(self.sidebar, text="Change Password", fg_color="#334155", hover_color="#475569",
                      command=self.show_change_password_dialog).grid(row=12, column=0, padx=15, pady=(0, 5),
                                                                     sticky="ew")

        ctk.CTkButton(self.sidebar, text="Logout", fg_color="#991B1B", hover_color="#7F1D1D",
                      command=self.show_login_screen).grid(row=14, column=0, padx=15, pady=15, sticky="ew")

        self.content_area = ctk.CTkFrame(self)
        self.content_area.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)

        self.switch_view("POS")

    def switch_view(self, view_name):
        for widget in self.content_area.winfo_children():
            widget.destroy()

        if view_name == "POS":
            self.render_pos_view()
        elif view_name == "HISTORY":
            self.render_sales_history_view()
        elif view_name == "INV":
            self.render_inventory_view()
        elif view_name == "CUST":
            self.render_debtor_view()
        elif view_name == "USERS" and self.current_user['role'] == "Admin":
            self.render_storekeeper_management()
        elif view_name == "ANALYTICS" and self.current_user['role'] == "Admin":
            self.render_analytics_view()

        self.attach_page_watermark()

    # =========================================================================
    # 3. POS TERMINAL
    # =========================================================================
    def render_pos_view(self):
        self.content_area.grid_columnconfigure(0, weight=3)
        self.content_area.grid_columnconfigure(1, weight=2)
        self.content_area.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self.content_area)
        left.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)

        search_card = ctk.CTkFrame(left)
        search_card.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        search_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(search_card, text="Search & Select Product:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, columnspan=3, padx=10, pady=(5, 2), sticky="w")

        self.pos_search_entry = ctk.CTkEntry(search_card, placeholder_text="Type product name to search...", height=38,
                                             font=ctk.CTkFont(size=13))
        self.pos_search_entry.grid(row=1, column=0, padx=(10, 5), pady=(0, 5), sticky="ew")

        self.pos_q_ent = ctk.CTkEntry(search_card, width=65, placeholder_text="Qty", height=38)
        self.pos_q_ent.insert(0, "1")
        self.pos_q_ent.grid(row=1, column=1, padx=5, pady=(0, 5))

        add_btn = ctk.CTkButton(search_card, text="Add Item", width=85, height=38, command=self.add_pos_item)
        add_btn.grid(row=1, column=2, padx=(5, 10), pady=(0, 5))

        self.suggest_frame = ctk.CTkFrame(left, height=130)
        self.suggest_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))
        self.suggest_frame.grid_remove()

        self.suggest_list = ttk.Treeview(self.suggest_frame, columns=("name", "price", "stock", "status"),
                                         show="headings", height=4)
        self.suggest_list.heading("name", text="Product Name")
        self.suggest_list.heading("price", text="Selling Price (GHS)")
        self.suggest_list.heading("stock", text="Stock Available")
        self.suggest_list.heading("status", text="Stock Status")

        self.suggest_list.column("name", width=210, anchor="w")
        self.suggest_list.column("price", width=95, anchor="center")
        self.suggest_list.column("stock", width=90, anchor="center")
        self.suggest_list.column("status", width=110, anchor="center")
        self.suggest_list.pack(fill="both", expand=True, padx=5, pady=5)

        self.pos_search_entry.bind("<KeyRelease>", self.on_search_typing)
        self.pos_search_entry.bind("<Down>", lambda e: self.focus_suggest_list())
        self.pos_search_entry.bind("<Return>", self.on_search_entry_enter)

        self.suggest_list.bind("<Return>", lambda e: self.select_from_suggest_list())
        self.suggest_list.bind("<Double-1>", lambda e: self.select_from_suggest_list())

        self.pos_q_ent.bind("<Up>", lambda e: self.increment_qty_entry(1))
        self.pos_q_ent.bind("<Down>", lambda e: self.increment_qty_entry(-1))
        self.pos_q_ent.bind("<Return>", lambda e: self.add_pos_item())

        cart_frame = ctk.CTkFrame(left)
        cart_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        cart_frame.grid_rowconfigure(0, weight=1)
        cart_frame.grid_columnconfigure(0, weight=1)

        cart_cols = ("name", "qty", "price", "total")
        self.cart_tree = ttk.Treeview(cart_frame, columns=cart_cols, show="headings", selectmode="browse")
        self.cart_tree.heading("name", text="Product Description")
        self.cart_tree.heading("qty", text="Qty")
        self.cart_tree.heading("price", text="Unit Price (GHS)")
        self.cart_tree.heading("total", text="Total (GHS)")

        self.cart_tree.column("name", width=220, anchor="w")
        self.cart_tree.column("qty", width=60, anchor="center")
        self.cart_tree.column("price", width=90, anchor="center")
        self.cart_tree.column("total", width=90, anchor="center")
        self.cart_tree.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.cart_tree.bind("<Up>", lambda e: self.increase_cart_item())
        self.cart_tree.bind("<Down>", lambda e: self.decrease_cart_item())
        self.cart_tree.bind("+", lambda e: self.increase_cart_item())
        self.cart_tree.bind("-", lambda e: self.decrease_cart_item())
        self.cart_tree.bind("<Delete>", lambda e: self.remove_cart_item())
        self.cart_tree.bind("<BackSpace>", lambda e: self.remove_cart_item())

        cart_actions = ctk.CTkFrame(left, fg_color="transparent")
        cart_actions.grid(row=3, column=0, sticky="ew", padx=10, pady=8)

        ctk.CTkButton(cart_actions, text="Increase (+ / Up)", width=120, command=self.increase_cart_item).pack(
            side="left", padx=4)
        ctk.CTkButton(cart_actions, text="Decrease (- / Down)", width=120, fg_color="gray40",
                      command=self.decrease_cart_item).pack(side="left", padx=4)
        ctk.CTkButton(cart_actions, text="Remove (Del)", width=105, fg_color="#DC2626", hover_color="#991B1B",
                      command=self.remove_cart_item).pack(side="left", padx=4)
        ctk.CTkButton(cart_actions, text="Clear Cart", width=90, fg_color="#7F1D1D", hover_color="#581C1C",
                      command=self.clear_pos_cart).pack(side="right", padx=4)

        right = ctk.CTkFrame(self.content_area)
        right.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        header_frame = ctk.CTkFrame(right, fg_color="transparent")
        header_frame.pack(fill="x", pady=(10, 5))
        pos_badge = self.load_ctk_image(size=(32, 32), opacity=1.0)
        if pos_badge:
            ctk.CTkLabel(header_frame, image=pos_badge, text="").pack(side="left", padx=(15, 5))
        ctk.CTkLabel(header_frame, text="Billing & Printing Options", font=ctk.CTkFont(size=16, weight="bold")).pack(
            side="left")

        cust_row = ctk.CTkFrame(right, fg_color="transparent")
        cust_row.pack(fill="x", padx=15, pady=(5, 0))

        ctk.CTkLabel(cust_row, text="Customer Account:").pack(side="left")
        ctk.CTkButton(cust_row, text="+ New Customer", width=105, height=24, font=ctk.CTkFont(size=11),
                      fg_color="#2563EB", hover_color="#1D4ED8", command=self.show_quick_add_customer_dialog).pack(
            side="right")

        self.pos_c_cb = ctk.CTkComboBox(right, width=280, values=["Walk-in (Cash Only)"],
                                        command=self.on_pos_customer_changed)
        self.pos_c_cb.pack(fill="x", padx=15, pady=(5, 2))

        self.pos_cust_debt_lbl = ctk.CTkLabel(right, text="Account: Walk-in (No Debt Record)",
                                              font=ctk.CTkFont(size=11, weight="bold"), text_color="gray")
        self.pos_cust_debt_lbl.pack(anchor="w", padx=18, pady=(0, 4))

        ctk.CTkLabel(right, text="Payment Method:").pack(anchor="w", padx=15, pady=(4, 0))
        self.pos_m_cb = ctk.CTkComboBox(right, width=280, values=["CASH", "MOMO", "CREDIT / ON ACCOUNT"])
        self.pos_m_cb.pack(fill="x", padx=15, pady=3)

        ctk.CTkLabel(right, text="Amount Paid (GHS):").pack(anchor="w", padx=15, pady=(6, 0))
        self.pos_paid_ent = ctk.CTkEntry(right, placeholder_text="0.00", width=280, height=36)
        self.pos_paid_ent.pack(fill="x", padx=15, pady=3)
        self.pos_paid_ent.bind("<KeyRelease>", lambda e: self.update_change_calculation())
        self.pos_paid_ent.bind("<Return>", lambda e: self.execute_pos_checkout("THERMAL"))

        self.pos_total_lbl = ctk.CTkLabel(right, text="Total: GHS 0.00", font=ctk.CTkFont(size=20, weight="bold"),
                                          text_color="#10B981")
        self.pos_total_lbl.pack(pady=(8, 2))

        self.pos_change_lbl = ctk.CTkLabel(right, text="Change to Return: GHS 0.00",
                                           font=ctk.CTkFont(size=13, weight="bold"),
                                           text_color="gray")
        self.pos_change_lbl.pack(pady=(0, 10))

        ctk.CTkButton(right, text="Checkout (Thermal POS Slip)", height=42, fg_color="#2563EB", hover_color="#1D4ED8",
                      command=lambda: self.execute_pos_checkout("THERMAL")).pack(fill="x", padx=15, pady=5)
        ctk.CTkButton(right, text="Generate A4 Official Invoice", height=42, fg_color="#047857",
                      hover_color="#065F46", command=lambda: self.execute_pos_checkout("A4")).pack(fill="x", padx=15,
                                                                                                   pady=5)

        self.populate_pos_data()
        self.render_cart_tree()
        self.pos_search_entry.focus_set()

    def on_pos_customer_changed(self, choice=None):
        choice = choice or self.pos_c_cb.get()
        cust = self.customer_map.get(choice)
        if cust:
            debt = cust.get('current_debt', 0.0)
            if debt > 0:
                self.pos_cust_debt_lbl.configure(text=f"Current Debt Balance: GHS {debt:.2f}", text_color="#EF4444")
            else:
                self.pos_cust_debt_lbl.configure(text="Current Debt Balance: GHS 0.00 (Clear)", text_color="#10B981")
        else:
            self.pos_cust_debt_lbl.configure(text="Account: Walk-in (No Debt Record)", text_color="gray")
        self.update_change_calculation()

    def update_change_calculation(self):
        total = sum(i['line_total'] for i in self.cart)
        paid_str = self.pos_paid_ent.get().strip()

        if total == 0:
            self.pos_change_lbl.configure(text="Change to Return: GHS 0.00", text_color="gray")
            return

        if not paid_str:
            self.pos_change_lbl.configure(text=f"Invoice Balance: GHS {total:.2f}", text_color="gray")
            return

        try:
            paid = float(paid_str)
        except ValueError:
            self.pos_change_lbl.configure(text="Invalid amount", text_color="#EF4444")
            return

        cust = self.customer_map.get(self.pos_c_cb.get())
        if paid >= total:
            change = paid - total
            self.pos_change_lbl.configure(text=f"Change to Give: GHS {change:.2f}", text_color="#10B981")
        else:
            deficit = total - paid
            if cust:
                self.pos_change_lbl.configure(text=f"Deferred Debt to Add: GHS {deficit:.2f}", text_color="#EF4444")
            else:
                self.pos_change_lbl.configure(text=f"Invoice Unpaid Bal: GHS {deficit:.2f}", text_color="#F59E0B")

    def show_quick_add_customer_dialog(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Quick Register Customer")
        modal.geometry("380x310")
        modal.grab_set()

        ctk.CTkLabel(modal, text="Quick Register Customer", font=ctk.CTkFont(size=16, weight="bold")).pack(
            pady=(15, 10))

        n_ent = ctk.CTkEntry(modal, placeholder_text="Full Name", width=280, height=36)
        n_ent.pack(pady=6)
        n_ent.focus_set()

        p_ent = ctk.CTkEntry(modal, placeholder_text="Phone Number", width=280, height=36)
        p_ent.pack(pady=6)

        a_ent = ctk.CTkEntry(modal, placeholder_text="Address (Optional)", width=280, height=36)
        a_ent.pack(pady=6)

        def save_quick_cust():
            name = n_ent.get().strip()
            phone = p_ent.get().strip()
            addr = a_ent.get().strip()

            if not name or not phone:
                messagebox.showwarning("Missing Details", "Name and Phone Number are required.")
                return

            conn = db.get_connection()
            try:
                conn.execute("INSERT INTO customers (name, phone, address) VALUES (?, ?, ?)", (name, phone, addr))
                conn.commit()
                conn.close()

                self.populate_pos_data_keep_cart()
                new_key = f"{name} ({phone}) - Debt: GHS 0.00"
                if new_key in self.customer_map:
                    self.pos_c_cb.set(new_key)
                    self.on_pos_customer_changed(new_key)

                modal.destroy()
            except Exception as e:
                conn.close()
                messagebox.showerror("Error", f"Failed to add customer: {str(e)}")

        n_ent.bind("<Return>", lambda e: p_ent.focus_set())
        p_ent.bind("<Return>", lambda e: a_ent.focus_set())
        a_ent.bind("<Return>", lambda e: save_quick_cust())

        ctk.CTkButton(modal, text="Create & Select", width=280, height=38, fg_color="#2563EB",
                      hover_color="#1D4ED8", command=save_quick_cust).pack(pady=15)

    def increment_qty_entry(self, delta):
        try:
            val = float(self.pos_q_ent.get().strip() or 0)
        except ValueError:
            val = 1
        new_val = max(1, val + delta)
        display_val = int(new_val) if new_val.is_integer() else new_val
        self.pos_q_ent.delete(0, 'end')
        self.pos_q_ent.insert(0, str(display_val))
        return "break"

    def populate_pos_data(self):
        conn = db.get_connection()
        self.all_products = [dict(p) for p in conn.execute(
            "SELECT * FROM products WHERE stock_quantity > 0 ORDER BY name ASC").fetchall()]
        custs = conn.execute("SELECT * FROM customers ORDER BY name ASC").fetchall()
        conn.close()

        self.selected_product = None
        self.filtered_products = []

        self.customer_map = {"Walk-in (Cash Only)": None}
        for c in custs:
            self.customer_map[f"{c['name']} ({c['phone']}) - Debt: GHS {c['current_debt']:.2f}"] = dict(c)
        self.pos_c_cb.configure(values=list(self.customer_map.keys()))
        self.on_pos_customer_changed()

    def populate_pos_data_keep_cart(self):
        conn = db.get_connection()
        self.all_products = [dict(p) for p in conn.execute(
            "SELECT * FROM products WHERE stock_quantity > 0 ORDER BY name ASC").fetchall()]
        custs = conn.execute("SELECT * FROM customers ORDER BY name ASC").fetchall()
        conn.close()

        for item in self.cart:
            current_p = next((p for p in self.all_products if p['id'] == item['id']), None)
            if current_p:
                item['max_stock'] = current_p['stock_quantity']

        current_selection = self.pos_c_cb.get()
        self.customer_map = {"Walk-in (Cash Only)": None}
        matched_selection = None
        for c in custs:
            key = f"{c['name']} ({c['phone']}) - Debt: GHS {c['current_debt']:.2f}"
            self.customer_map[key] = dict(c)
            if current_selection.startswith(f"{c['name']} ({c['phone']})"):
                matched_selection = key

        self.pos_c_cb.configure(values=list(self.customer_map.keys()))
        if matched_selection:
            self.pos_c_cb.set(matched_selection)
            self.on_pos_customer_changed(matched_selection)

    def on_search_typing(self, event):
        if event.keysym in ("Down", "Up", "Return"):
            return

        query = self.pos_search_entry.get().strip().lower()
        for r in self.suggest_list.get_children():
            self.suggest_list.delete(r)

        if not query:
            self.suggest_frame.grid_remove()
            self.filtered_products = []
            self.selected_product = None
            return

        self.filtered_products = [p for p in self.all_products if
                                  query in p['name'].lower() or query in p['category'].lower()]

        if self.filtered_products:
            self.suggest_frame.grid()
            for p in self.filtered_products[:6]:
                stk = p['stock_quantity']
                thresh = p['reorder_level']
                if stk <= thresh / 2:
                    status_text = "CRITICAL LOW"
                elif stk <= thresh:
                    status_text = "LOW STOCK"
                else:
                    status_text = "NORMAL"

                self.suggest_list.insert("", "end", values=(
                    p['name'],
                    f"{p['selling_price']:.2f}",
                    p['stock_quantity'],
                    status_text
                ))
        else:
            self.suggest_frame.grid_remove()

    def focus_suggest_list(self):
        children = self.suggest_list.get_children()
        if children:
            self.suggest_list.focus_set()
            self.suggest_list.selection_set(children[0])

    def select_from_suggest_list(self):
        sel = self.suggest_list.selection()
        if not sel:
            return
        idx = self.suggest_list.index(sel[0])
        if idx < len(self.filtered_products):
            self.selected_product = self.filtered_products[idx]
            self.pos_search_entry.delete(0, 'end')
            self.pos_search_entry.insert(0, self.selected_product['name'])
            self.suggest_frame.grid_remove()
            self.pos_q_ent.focus_set()
            self.pos_q_ent.select_range(0, 'end')

    def on_search_entry_enter(self, event):
        query = self.pos_search_entry.get().strip()
        if not query:
            return

        if self.filtered_products:
            self.selected_product = self.filtered_products[0]
            self.pos_search_entry.delete(0, 'end')
            self.pos_search_entry.insert(0, self.selected_product['name'])
            self.suggest_frame.grid_remove()
            self.pos_q_ent.focus_set()
            self.pos_q_ent.select_range(0, 'end')
        else:
            messagebox.showwarning("Not Found", f"No available product matching '{query}'.")

    def add_pos_item(self):
        prod_name = self.pos_search_entry.get().strip()

        if not prod_name:
            messagebox.showwarning("Selection Missing", "Please type or select a product before adding.")
            return

        prod = None
        if self.selected_product and self.selected_product['name'].lower() == prod_name.lower():
            prod = self.selected_product
        else:
            matches = [p for p in self.all_products if prod_name.lower() in p['name'].lower()]
            if matches:
                prod = matches[0]

        if not prod:
            messagebox.showwarning("Selection Missing", "Please search and select a valid product from the list.")
            return

        try:
            qty = float(self.pos_q_ent.get().strip() or 1)
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid Qty", "Please enter a valid quantity.")
            return

        existing = next((i for i in self.cart if i['id'] == prod['id']), None)
        current_qty = existing['qty'] if existing else 0

        if current_qty + qty > prod['stock_quantity']:
            messagebox.showwarning("Stock Limit", f"Only {prod['stock_quantity']} units available in stock.")
            return

        if existing:
            existing['qty'] += qty
            existing['line_total'] = existing['qty'] * existing['selling_price']
            existing['line_profit'] = existing['line_total'] - (existing['qty'] * existing['cost_price'])
        else:
            line_total = qty * prod['selling_price']
            profit = line_total - (qty * prod['cost_price'])
            self.cart.append({
                'id': prod['id'], 'name': prod['name'], 'qty': qty,
                'max_stock': prod['stock_quantity'],
                'cost_price': prod['cost_price'], 'selling_price': prod['selling_price'],
                'line_total': line_total, 'line_profit': profit
            })

        self.pos_search_entry.delete(0, 'end')
        self.pos_q_ent.delete(0, 'end')
        self.pos_q_ent.insert(0, "1")
        self.suggest_frame.grid_remove()
        self.selected_product = None
        self.pos_search_entry.focus_set()
        self.render_cart_tree()

    def render_cart_tree(self, selected_index=None):
        for r in self.cart_tree.get_children():
            self.cart_tree.delete(r)

        total = sum(i['line_total'] for i in self.cart)
        row_ids = []
        for i in self.cart:
            item_id = self.cart_tree.insert("", "end", values=(
                i['name'],
                i['qty'],
                f"{i['selling_price']:.2f}",
                f"{i['line_total']:.2f}"
            ))
            row_ids.append(item_id)

        self.pos_total_lbl.configure(text=f"Total: GHS {total:.2f}")

        if selected_index is not None and row_ids:
            target_idx = min(selected_index, len(row_ids) - 1)
            self.cart_tree.selection_set(row_ids[target_idx])
            self.cart_tree.focus(row_ids[target_idx])

        self.update_change_calculation()

    def increase_cart_item(self):
        sel = self.cart_tree.selection()
        if not sel:
            return "break"
        idx = self.cart_tree.index(sel[0])
        item = self.cart[idx]
        if item['qty'] + 1 > item['max_stock']:
            messagebox.showwarning("Stock Limit", f"Only {item['max_stock']} units available.")
            return "break"
        item['qty'] += 1
        item['line_total'] = item['qty'] * item['selling_price']
        item['line_profit'] = item['line_total'] - (item['qty'] * item['cost_price'])
        self.render_cart_tree(selected_index=idx)
        return "break"

    def decrease_cart_item(self):
        sel = self.cart_tree.selection()
        if not sel:
            return "break"
        idx = self.cart_tree.index(sel[0])
        item = self.cart[idx]
        if item['qty'] - 1 <= 0:
            self.cart.pop(idx)
            next_idx = min(idx, len(self.cart) - 1) if self.cart else None
            self.render_cart_tree(selected_index=next_idx)
        else:
            item['qty'] -= 1
            item['line_total'] = item['qty'] * item['selling_price']
            item['line_profit'] = item['line_total'] - (item['qty'] * item['cost_price'])
            self.render_cart_tree(selected_index=idx)
        return "break"

    def remove_cart_item(self):
        sel = self.cart_tree.selection()
        if not sel:
            return
        idx = self.cart_tree.index(sel[0])
        self.cart.pop(idx)
        next_idx = min(idx, len(self.cart) - 1) if self.cart else None
        self.render_cart_tree(selected_index=next_idx)

    def clear_pos_cart(self):
        self.cart = []
        self.pos_paid_ent.delete(0, 'end')

        if "Walk-in (Cash Only)" in self.customer_map:
            self.pos_c_cb.set("Walk-in (Cash Only)")
        self.on_pos_customer_changed("Walk-in (Cash Only)")

        self.render_cart_tree()
        self.update_change_calculation()
        self.pos_search_entry.focus_set()

    def execute_pos_checkout(self, print_type):
        if not self.cart:
            messagebox.showwarning("Empty Cart", "Cart is empty. Please add products first.")
            return
        total = sum(i['line_total'] for i in self.cart)
        paid_str = self.pos_paid_ent.get().strip()

        cust = self.customer_map.get(self.pos_c_cb.get())

        if print_type == "THERMAL":
            if not cust and not paid_str:
                messagebox.showwarning("Payment Required", "Walk-in cash sales must be paid in full before checkout.")
                self.pos_paid_ent.focus_set()
                return

        try:
            paid = float(paid_str) if paid_str else 0.0
            if paid < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Amount", "Please enter a valid payment amount.")
            return

        if paid >= total:
            actual_paid = total
            change = paid - total
            balance = 0.0
        else:
            actual_paid = paid
            change = 0.0
            balance = total - paid

        if print_type == "THERMAL" and balance > 0 and not cust:
            messagebox.showerror(
                "Credit Prohibited for Walk-ins",
                f"Walk-in sales cannot carry an unpaid balance of GHS {balance:.2f}.\n\n"
                "Please collect full payment or switch to a registered Customer Account."
            )
            return

        receipt_no = f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        ok, res = db.process_sale_transaction(
            receipt_no,
            cust['id'] if cust else None,
            self.pos_m_cb.get(),
            self.cart,
            total,
            actual_paid,
            balance,
            self.current_user['id']
        )
        if not ok:
            messagebox.showerror("Error", str(res))
            return

        sale_id, low_stock_warnings = res
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        if print_type == "THERMAL":
            try:
                pe.print_thermal_receipt_direct(
                    receipt_no,
                    date_str,
                    self.cart,
                    total,
                    paid,
                    balance,
                    cust['name'] if cust else "Walk-in",
                    change=change
                )
            except Exception as e:
                messagebox.showerror("Printer Error",
                                     f"Could not print receipt: {str(e)}\nEnsure printer is powered on and set as default.")

            msg = f"Thermal Slip #{receipt_no} sent to printer.\n\nTotal: GHS {total:.2f}\nPaid: GHS {paid:.2f}"
            if change > 0:
                msg += f"\nChange: GHS {change:.2f}"
            if balance > 0:
                msg += f"\nDebt Added: GHS {balance:.2f}"
            messagebox.showinfo("Receipt Completed", msg)

        else:
            pdf_name = f"{receipt_no}_A4_Invoice.pdf"
            pe.generate_a4_invoice_pdf(
                pdf_name,
                receipt_no,
                date_str,
                self.cart,
                total,
                paid,
                balance,
                cust,
                change=change
            )

            try:
                if sys.platform.startswith("win"):
                    os.startfile(pdf_name)
            except Exception:
                pass

            inv_msg = f"Official A4 Invoice saved as:\n{pdf_name}\n\nTotal: GHS {total:.2f} | Paid: GHS {paid:.2f}"
            if balance > 0:
                inv_msg += f" | Balance: GHS {balance:.2f}"
            messagebox.showinfo("Invoice Generated", inv_msg)

        if low_stock_warnings:
            lines = []
            for w in low_stock_warnings:
                rem = w['stock_quantity']
                thresh = w['reorder_level']
                pct = (rem / (thresh * 5)) * 100 if thresh > 0 else 0
                severity = f"CRITICAL DEPLETION ({pct:.0f}% Left)" if rem <= thresh / 2 else f"LOW STOCK ({pct:.0f}% Left)"
                lines.append(
                    f"- {w['name']}: Only {rem} remaining [{pct:.0f}% Left] (Alert Limit: {thresh}) [{severity}]")
            messagebox.showwarning("Stock Alert Notice",
                                   "The following items have crossed their minimum threshold:\n\n" + "\n".join(lines))

        self.populate_pos_data_keep_cart()
        self.pos_search_entry.focus_set()

    # =========================================================================
    # 4. SALES HISTORY & DAY LEDGER
    # =========================================================================
    def render_sales_history_view(self):
        ctk.CTkLabel(self.content_area, text="Daily Sales History & Day Ledger",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(2, 4), padx=5)

        top_filter_bar = ctk.CTkFrame(self.content_area)
        top_filter_bar.pack(fill="x", pady=3, padx=5)

        ctk.CTkLabel(top_filter_bar, text="Date:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left",
                                                                                                  padx=(6, 2))

        self.cal_btn = ctk.CTkButton(top_filter_bar, text=f"📅 {self.selected_history_date}", width=120, height=30,
                                     fg_color="#3B82F6", hover_color="#2563EB",
                                     command=lambda: self.open_calendar_picker_dialog(history_tv, stat_lbl))
        self.cal_btn.pack(side="left", padx=3)

        ctk.CTkButton(top_filter_bar, text="Today", width=60, height=30, fg_color="gray40", hover_color="gray30",
                      command=lambda: self.set_history_to_today(history_tv, stat_lbl)).pack(side="left", padx=2)

        ctk.CTkButton(top_filter_bar, text="Export CSV", width=90, height=30, fg_color="#0F766E", hover_color="#115E59",
                      command=lambda: self.export_sales_to_csv(self.selected_history_date)).pack(side="right", padx=3)
        ctk.CTkButton(top_filter_bar, text="Export PDF", width=95, height=30, fg_color="#4338CA", hover_color="#3730A3",
                      command=lambda: self.export_sales_to_pdf(self.selected_history_date)).pack(side="right", padx=3)

        stat_bar = ctk.CTkFrame(self.content_area, fg_color="#1E293B", height=32)
        stat_bar.pack(fill="x", pady=3, padx=5)
        stat_lbl = ctk.CTkLabel(stat_bar, text="Loading Day Metrics...", font=ctk.CTkFont(size=11, weight="bold"),
                                text_color="white")
        stat_lbl.pack(side="left", padx=10, pady=4)

        tree_frame = ctk.CTkFrame(self.content_area)
        tree_frame.pack(fill="both", expand=True, pady=4, padx=5)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        cols = ("Time", "Receipt No", "Customer", "Payment Method", "Total (GHS)", "Paid (GHS)", "Balance (GHS)",
                "Cashier")
        history_tv = ttk.Treeview(tree_frame, columns=cols, show="headings", height=10)

        col_widths = {
            "Time": 50, "Receipt No": 130, "Customer": 120, "Payment Method": 75,
            "Total (GHS)": 75, "Paid (GHS)": 75, "Balance (GHS)": 75, "Cashier": 65
        }
        for c in cols:
            history_tv.heading(c, text=c, command=lambda _col=c: self.sort_treeview_column(history_tv, _col, False))
            history_tv.column(c, width=col_widths.get(c, 80), anchor="center")
        history_tv.column("Customer", anchor="w")
        history_tv.grid(row=0, column=0, sticky="nsew")

        sb_y = ttk.Scrollbar(tree_frame, orient="vertical", command=history_tv.yview)
        history_tv.configure(yscrollcommand=sb_y.set)
        sb_y.grid(row=0, column=1, sticky="ns")

        history_tv.bind("<Double-1>", lambda e: self.open_sale_details_modal(history_tv))

        ctrl_bar = ctk.CTkFrame(self.content_area)
        ctrl_bar.pack(fill="x", pady=4, padx=5)
        ctk.CTkButton(ctrl_bar, text="View Sale Line Items (Double-Click)", width=210, height=32,
                      command=lambda: self.open_sale_details_modal(history_tv)).pack(side="left", padx=5)

        self.load_sales_history_table(history_tv, stat_lbl, self.selected_history_date)

    def set_history_to_today(self, history_tv, stat_lbl):
        self.selected_history_date = datetime.now().strftime("%Y-%m-%d")
        self.cal_btn.configure(text=f"📅 {self.selected_history_date}")
        self.load_sales_history_table(history_tv, stat_lbl, self.selected_history_date)

    def open_calendar_picker_dialog(self, history_tv, stat_lbl):
        modal = ctk.CTkToplevel(self)
        modal.title("Select Date")
        modal.geometry("320x330")
        modal.resizable(False, False)
        modal.grab_set()

        try:
            cur_dt = datetime.strptime(self.selected_history_date, "%Y-%m-%d")
        except Exception:
            cur_dt = datetime.now()

        cal_state = {'year': cur_dt.year, 'month': cur_dt.month}

        header = ctk.CTkFrame(modal, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))

        month_lbl = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=14, weight="bold"))

        def refresh_calendar_view():
            month_lbl.configure(text=f"{calendar.month_name[cal_state['month']]} {cal_state['year']}")
            for w in days_frame.winfo_children():
                w.destroy()

            for idx, d_name in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
                ctk.CTkLabel(days_frame, text=d_name, font=ctk.CTkFont(size=11, weight="bold"), width=36).grid(row=0,
                                                                                                               column=idx,
                                                                                                               pady=2)

            month_matrix = calendar.monthcalendar(cal_state['year'], cal_state['month'])
            for r_idx, week in enumerate(month_matrix, start=1):
                for c_idx, day in enumerate(week):
                    if day != 0:
                        is_current = (
                                cal_state['year'] == cur_dt.year and
                                cal_state['month'] == cur_dt.month and
                                day == cur_dt.day
                        )
                        btn = ctk.CTkButton(
                            days_frame,
                            text=str(day),
                            width=36,
                            height=28,
                            fg_color="#2563EB" if is_current else "gray25",
                            hover_color="#1D4ED8",
                            command=lambda d=day: on_day_picked(d)
                        )
                        btn.grid(row=r_idx, column=c_idx, padx=2, pady=2)

        def on_day_picked(day):
            picked_date_str = f"{cal_state['year']:04d}-{cal_state['month']:02d}-{day:02d}"
            self.selected_history_date = picked_date_str
            self.cal_btn.configure(text=f"📅 {self.selected_history_date}")
            modal.destroy()
            self.load_sales_history_table(history_tv, stat_lbl, self.selected_history_date)

        def prev_month():
            if cal_state['month'] == 1:
                cal_state['month'] = 12
                cal_state['year'] -= 1
            else:
                cal_state['month'] -= 1
            refresh_calendar_view()

        def next_month():
            if cal_state['month'] == 12:
                cal_state['month'] = 1
                cal_state['year'] += 1
            else:
                cal_state['month'] += 1
            refresh_calendar_view()

        ctk.CTkButton(header, text="<", width=30, height=26, command=prev_month).pack(side="left")
        month_lbl.pack(side="left", expand=True)
        ctk.CTkButton(header, text=">", width=30, height=26, command=next_month).pack(side="right")

        days_frame = ctk.CTkFrame(modal, fg_color="transparent")
        days_frame.pack(padx=10, pady=5)

        refresh_calendar_view()

    def load_sales_history_table(self, tv, stat_lbl, query_date):
        for r in tv.get_children():
            tv.delete(r)

        conn = db.get_connection()
        sales = conn.execute("""
            SELECT s.*, c.name as customer_name, u.full_name as cashier_name
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            LEFT JOIN users u ON s.user_id = u.id
            WHERE DATE(s.sale_date) = DATE(?)
            ORDER BY s.sale_date DESC
        """, (query_date,)).fetchall()
        conn.close()

        total_rev = 0.0
        total_paid = 0.0
        total_bal = 0.0

        for s in sales:
            total_rev += s['total_amount']
            total_paid += s['amount_paid']
            total_bal += s['balance_due']

            time_str = s['sale_date'].split()[1][:5] if ' ' in s['sale_date'] else s['sale_date']
            tv.insert("", "end", values=(
                time_str,
                s['receipt_no'],
                s['customer_name'] or "Walk-in (Cash)",
                s['payment_method'],
                f"{s['total_amount']:.2f}",
                f"{s['amount_paid']:.2f}",
                f"{s['balance_due']:.2f}",
                s['cashier_name'] or "System"
            ), tags=(s['id'],))

        stat_lbl.configure(
            text=f"Date: {query_date}  |  Orders: {len(sales)}  |  Gross Sales: GHS {total_rev:.2f}  |  Collected: GHS {total_paid:.2f}  |  Debt Balance: GHS {total_bal:.2f}")

    def open_sale_details_modal(self, tv):
        sel = tv.selection()
        if not sel:
            messagebox.showwarning("Select Order", "Please select a sale transaction from the table.")
            return

        rec_vals = tv.item(sel[0])['values']
        receipt_no = rec_vals[1]

        conn = db.get_connection()
        sale = conn.execute("""
            SELECT s.*, c.name as customer_name, c.phone as customer_phone, u.full_name as cashier_name
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.receipt_no = ?
        """, (receipt_no,)).fetchone()

        if not sale:
            conn.close()
            return

        items = conn.execute("""
            SELECT si.*, p.name as product_name
            FROM sale_items si
            LEFT JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = ?
        """, (sale['id'],)).fetchall()
        conn.close()

        modal = ctk.CTkToplevel(self)
        modal.title(f"Receipt Breakdown - {receipt_no}")
        modal.geometry("580x480")
        modal.grab_set()

        card = ctk.CTkFrame(modal)
        card.pack(fill="x", padx=15, pady=10)
        ctk.CTkLabel(card, text=f"Order Breakdown: {receipt_no}", font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 2))
        meta_str = f"Date: {sale['sale_date']} | Cashier: {sale['cashier_name']}\nCustomer: {sale['customer_name'] or 'Walk-in'} | Method: {sale['payment_method']}"
        ctk.CTkLabel(card, text=meta_str, font=ctk.CTkFont(size=11), text_color="gray", justify="left").pack(anchor="w",
                                                                                                             padx=10,
                                                                                                             pady=(0,
                                                                                                                   10))

        cols = ("Item", "Qty", "Unit Price (GHS)", "Total (GHS)")
        item_tv = ttk.Treeview(modal, columns=cols, show="headings", height=7)
        for c in cols:
            item_tv.heading(c, text=c, command=lambda _col=c: self.sort_treeview_column(item_tv, _col, False))
            item_tv.column(c, width=110, anchor="center")
        item_tv.column("Item", width=190, anchor="w")
        item_tv.pack(fill="both", expand=True, padx=15, pady=5)

        for it in items:
            item_tv.insert("", "end",
                           values=(it['product_name'] or "Deleted Product", it['quantity'], f"{it['unit_price']:.2f}",
                                   f"{it['line_total']:.2f}"))

        sum_bar = ctk.CTkFrame(modal, fg_color="transparent")
        sum_bar.pack(fill="x", padx=15, pady=10)
        ctk.CTkLabel(sum_bar,
                     text=f"Total: GHS {sale['total_amount']:.2f}  |  Paid: GHS {sale['amount_paid']:.2f}  |  Balance: GHS {sale['balance_due']:.2f}",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color="#10B981").pack(side="right")

    def export_sales_to_csv(self, query_date):
        conn = db.get_connection()
        sales = conn.execute("""
            SELECT s.sale_date, s.receipt_no, COALESCE(c.name, 'Walk-in') as customer, s.payment_method,
                   s.total_amount, s.amount_paid, s.balance_due, u.full_name as cashier
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            LEFT JOIN users u ON s.user_id = u.id
            WHERE DATE(s.sale_date) = DATE(?)
            ORDER BY s.sale_date ASC
        """, (query_date,)).fetchall()
        conn.close()

        if not sales:
            messagebox.showinfo("Notice", f"No sales found on {query_date} to export.")
            return

        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")],
                                                 initialfile=f"Sales_Report_{query_date}.csv")
        if not file_path:
            return

        try:
            with open(file_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["Date Time", "Receipt No", "Customer", "Payment Method", "Total (GHS)", "Amount Paid (GHS)",
                     "Balance Due (GHS)", "Cashier"])
                for s in sales:
                    writer.writerow(
                        [s['sale_date'], s['receipt_no'], s['customer'], s['payment_method'], s['total_amount'],
                         s['amount_paid'], s['balance_due'], s['cashier']])
            messagebox.showinfo("Export Successful", f"Sales successfully exported to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def export_sales_to_pdf(self, query_date):
        conn = db.get_connection()
        sales = conn.execute("""
            SELECT s.sale_date, s.receipt_no, COALESCE(c.name, 'Walk-in') as customer_name, s.payment_method,
                   s.total_amount, s.amount_paid, s.balance_due, COALESCE(u.full_name, 'System') as cashier_name
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            LEFT JOIN users u ON s.user_id = u.id
            WHERE DATE(s.sale_date) = DATE(?)
            ORDER BY s.sale_date ASC
        """, (query_date,)).fetchall()
        conn.close()

        if not sales:
            messagebox.showinfo("Notice", f"No sales found on {query_date} to export.")
            return

        file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Documents", "*.pdf")],
                                                 initialfile=f"Sales_Audit_{query_date}.pdf")
        if not file_path:
            return

        sales_dicts = [dict(s) for s in sales]
        summary_stats = {
            'count': len(sales_dicts),
            'total_revenue': sum(s['total_amount'] for s in sales_dicts),
            'total_paid': sum(s['amount_paid'] for s in sales_dicts),
            'total_balance': sum(s['balance_due'] for s in sales_dicts)
        }

        try:
            pe.generate_daily_sales_pdf_report(file_path, query_date, sales_dicts, summary_stats)
            messagebox.showinfo("Export Successful", f"Sales Audit PDF successfully saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    # =========================================================================
    # 5. CUSTOMER PROFILE, DEBTS & INSTALLMENTS
    # =========================================================================
    def render_debtor_view(self):
        ctk.CTkLabel(self.content_area, text="Customer Accounts & Debtor Ledger",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(5, 10))

        top_bar = ctk.CTkFrame(self.content_area)
        top_bar.pack(fill="x", pady=5)

        n_e = ctk.CTkEntry(top_bar, placeholder_text="Full Name", width=160)
        n_e.pack(side="left", padx=4)
        p_e = ctk.CTkEntry(top_bar, placeholder_text="Phone", width=120)
        p_e.pack(side="left", padx=4)
        a_e = ctk.CTkEntry(top_bar, placeholder_text="Address", width=140)
        a_e.pack(side="left", padx=4)

        n_e.bind("<Return>", lambda e: p_e.focus_set())
        p_e.bind("<Return>", lambda e: a_e.focus_set())

        def add_c():
            if not n_e.get().strip() or not p_e.get().strip():
                messagebox.showwarning("Missing", "Name and Phone required.")
                return
            conn = db.get_connection()
            try:
                conn.execute("INSERT INTO customers (name, phone, address) VALUES (?,?,?)",
                             (n_e.get().strip(), p_e.get().strip(), a_e.get().strip()))
                conn.commit()
                messagebox.showinfo("Saved", "Customer added.")
                n_e.delete(0, 'end')
                p_e.delete(0, 'end')
                a_e.delete(0, 'end')
                n_e.focus_set()
                self.load_customers_table(tv)
            except Exception as e:
                messagebox.showerror("Error", str(e))
            finally:
                conn.close()

        a_e.bind("<Return>", lambda e: add_c())
        ctk.CTkButton(top_bar, text="+ Add Customer", width=110, command=add_c).pack(side="left", padx=5)

        search_ent = ctk.CTkEntry(top_bar, placeholder_text="Search Name or Phone...", width=220)
        search_ent.pack(side="right", padx=6)
        search_ent.bind("<KeyRelease>", lambda event: self.load_customers_table(tv, search_ent.get().strip()))

        cols = ("ID", "Customer Name", "Phone", "Address", "Current Debt")
        tv = ttk.Treeview(self.content_area, columns=cols, show="headings", height=14)
        for c in cols:
            tv.heading(c, text=c, command=lambda _col=c: self.sort_treeview_column(tv, _col, False))
            tv.column(c, width=130, anchor="center")
        tv.pack(fill="both", expand=True, pady=10)

        tv.bind("<Double-1>", lambda e: open_customer_profile_modal())

        ctrl_bar = ctk.CTkFrame(self.content_area)
        ctrl_bar.pack(fill="x", pady=5)

        def get_selected():
            sel = tv.selection()
            if not sel:
                messagebox.showwarning("Select Row", "Please select a customer from the table.")
                return None
            return tv.item(sel[0])['values']

        def open_customer_profile_modal():
            row = get_selected()
            if not row: return
            cid = row[0]
            self.show_customer_profile_dialog(cid, tv)

        def open_edit_modal():
            row = get_selected()
            if not row: return
            cid, cname, cphone, caddr, _ = row

            modal = ctk.CTkToplevel(self)
            modal.title(f"Edit Customer #{cid}")
            modal.geometry("400x320")
            modal.grab_set()

            ctk.CTkLabel(modal, text="Update Customer Details", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
            en_name = ctk.CTkEntry(modal, width=280)
            en_name.insert(0, cname)
            en_name.pack(pady=6)
            en_name.focus_set()
            en_phone = ctk.CTkEntry(modal, width=280)
            en_phone.insert(0, cphone)
            en_phone.pack(pady=6)
            en_addr = ctk.CTkEntry(modal, width=280)
            en_addr.insert(0, caddr)
            en_addr.pack(pady=6)

            def save_edit():
                ok, msg = db.update_customer_info(cid, en_name.get(), en_phone.get(), en_addr.get())
                if ok:
                    messagebox.showinfo("Saved", msg)
                    modal.destroy()
                    self.load_customers_table(tv)
                else:
                    messagebox.showerror("Error", msg)

            en_name.bind("<Return>", lambda e: en_phone.focus_set())
            en_phone.bind("<Return>", lambda e: en_addr.focus_set())
            en_addr.bind("<Return>", lambda e: save_edit())

            ctk.CTkButton(modal, text="Save Changes", width=280, command=save_edit).pack(pady=15)

        def delete_cust():
            row = get_selected()
            if not row: return
            cid, cname, _, _, _ = row
            if messagebox.askyesno("Delete Confirmation", f"Permanently delete customer '{cname}'?"):
                ok, msg = db.delete_customer(cid)
                if ok:
                    messagebox.showinfo("Deleted", msg)
                    self.load_customers_table(tv)
                else:
                    messagebox.showerror("Error", msg)

        ctk.CTkButton(ctrl_bar, text="View Profile & Installments", width=180, fg_color="#2563EB",
                      command=open_customer_profile_modal).pack(side="left", padx=5)
        ctk.CTkButton(ctrl_bar, text="Edit Details", width=110, command=open_edit_modal).pack(side="left", padx=5)
        ctk.CTkButton(ctrl_bar, text="Delete Customer", width=130, fg_color="#DC2626", hover_color="#991B1B",
                      command=delete_cust).pack(side="left", padx=5)

        self.load_customers_table(tv)

    def load_customers_table(self, tv, query=""):
        for r in tv.get_children(): tv.delete(r)
        conn = db.get_connection()
        if query:
            rows = conn.execute("SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY name ASC",
                                (f"%{query}%", f"%{query}%")).fetchall()
        else:
            rows = conn.execute("SELECT * FROM customers ORDER BY name ASC").fetchall()
        conn.close()
        for c in rows:
            tv.insert("", "end", values=(c['id'], c['name'], c['phone'], c['address'], f"GHS {c['current_debt']:.2f}"))

    def show_customer_profile_dialog(self, customer_id, parent_table):
        modal = ctk.CTkToplevel(self)
        modal.title("Customer Profile & Installment Ledger")
        modal.geometry("780x620")
        modal.minsize(700, 550)
        modal.grab_set()

        conn = db.get_connection()
        cust = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        conn.close()

        if not cust:
            modal.destroy()
            return

        card = ctk.CTkFrame(modal)
        card.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(card, text=f"Customer Account: {cust['name']}", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=15, pady=(10, 2))
        info_str = f"Phone: {cust['phone']}   |   Address: {cust['address'] or 'N/A'}   |   Member Since: {cust['created_at'][:10]}"
        ctk.CTkLabel(card, text=info_str, font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", padx=15,
                                                                                             pady=(0, 10))

        debt_lbl = ctk.CTkLabel(card, text=f"Outstanding Debt Balance: GHS {cust['current_debt']:.2f}",
                                font=ctk.CTkFont(size=16, weight="bold"),
                                text_color="#EF4444" if cust['current_debt'] > 0 else "#10B981")
        debt_lbl.pack(anchor="w", padx=15, pady=(0, 10))

        pay_box = ctk.CTkFrame(modal)
        pay_box.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(pay_box, text="Debt Payment:", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=10,
                                                                                                   pady=(8, 4))

        form_row = ctk.CTkFrame(pay_box, fg_color="transparent")
        form_row.pack(fill="x", padx=10, pady=(0, 8))

        amt_e = ctk.CTkEntry(form_row, placeholder_text="Amount (GHS)", width=130)
        amt_e.pack(side="left", padx=4)
        amt_e.focus_set()

        mth_cb = ctk.CTkComboBox(form_row, width=140, values=["CASH", "MOMO", "BANK / TRANSFER"])
        mth_cb.pack(side="left", padx=4)

        note_e = ctk.CTkEntry(form_row, placeholder_text="Payment Note", width=180)
        note_e.pack(side="left", padx=4)

        def submit_installment():
            try:
                amt = float(amt_e.get().strip())
                if amt <= 0: raise ValueError
            except ValueError:
                messagebox.showerror("Invalid Amount", "Please enter a valid positive payment amount.")
                return

            ok, msg = db.record_customer_installment(customer_id, amt, mth_cb.get(), note_e.get().strip(),
                                                     self.current_user['id'])
            if ok:
                messagebox.showinfo("Payment Successful", msg)
                amt_e.delete(0, 'end')
                note_e.delete(0, 'end')

                conn_ref = db.get_connection()
                updated_cust = conn_ref.execute("SELECT current_debt FROM customers WHERE id = ?",
                                                (customer_id,)).fetchone()
                conn_ref.close()
                new_debt = updated_cust['current_debt']
                debt_lbl.configure(text=f"Outstanding Debt Balance: GHS {new_debt:.2f}",
                                   text_color="#EF4444" if new_debt > 0 else "#10B981")

                self.load_customer_installments_table(p_tv, customer_id)
                self.load_customers_table(parent_table)
            else:
                messagebox.showerror("Error", msg)

        amt_e.bind("<Return>", lambda e: note_e.focus_set())
        note_e.bind("<Return>", lambda e: submit_installment())

        ctk.CTkButton(form_row, text="Pay", width=110, fg_color="#059669", hover_color="#047857",
                      command=submit_installment).pack(side="left", padx=6)

        ctk.CTkLabel(modal, text="Installment Payment History:", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=15, pady=(10, 4))

        p_cols = ("Date & Time", "Amount Paid", "Method", "Before", "Balance Left", "Received By", "Note")
        p_tv = ttk.Treeview(modal, columns=p_cols, show="headings", height=8)
        for c in p_cols:
            p_tv.heading(c, text=c, command=lambda _col=c: self.sort_treeview_column(p_tv, _col, False))
            p_tv.column(c, width=105, anchor="center")
        p_tv.column("Date & Time", width=130, anchor="center")
        p_tv.column("Note", width=120, anchor="w")
        p_tv.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.load_customer_installments_table(p_tv, customer_id)

    def load_customer_installments_table(self, tv, customer_id):
        for r in tv.get_children():
            tv.delete(r)
        history = db.get_customer_payments(customer_id)
        for p in history:
            tv.insert("", "end", values=(
                p['payment_date'],
                f"GHS {p['amount_paid']:.2f}",
                p['payment_method'],
                f"GHS {p['balance_before']:.2f}",
                f"GHS {p['balance_after']:.2f}",
                p['receiver_name'],
                p['payment_note'] or "-"
            ))

    # =========================================================================
    # 6. STOREKEEPER MANAGEMENT
    # =========================================================================
    def render_storekeeper_management(self):
        ctk.CTkLabel(self.content_area, text="Storekeeper Accounts & Access Control",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(5, 10))

        f = ctk.CTkFrame(self.content_area)
        f.pack(fill="x", pady=5)

        n_e = ctk.CTkEntry(f, placeholder_text="Full Name", width=160)
        n_e.pack(side="left", padx=4)
        u_e = ctk.CTkEntry(f, placeholder_text="Username", width=130)
        u_e.pack(side="left", padx=4)
        p_e = ctk.CTkEntry(f, placeholder_text="Temp Password", width=140)
        p_e.pack(side="left", padx=4)

        n_e.bind("<Return>", lambda e: u_e.focus_set())
        u_e.bind("<Return>", lambda e: p_e.focus_set())

        def add_keeper():
            if not n_e.get().strip() or not u_e.get().strip() or not p_e.get():
                messagebox.showwarning("Missing", "All fields required.")
                return
            ok, msg = db.create_storekeeper(n_e.get().strip(), u_e.get().strip(), p_e.get())
            if ok:
                messagebox.showinfo("Success", msg)
                n_e.delete(0, 'end')
                u_e.delete(0, 'end')
                p_e.delete(0, 'end')
                n_e.focus_set()
                self.load_users_table(tv)
            else:
                messagebox.showerror("Error", msg)

        p_e.bind("<Return>", lambda e: add_keeper())
        ctk.CTkButton(f, text="+ Add Storekeeper", width=130, command=add_keeper).pack(side="left", padx=5)

        search_ent = ctk.CTkEntry(f, placeholder_text="Search Staff...", width=200)
        search_ent.pack(side="right", padx=6)
        search_ent.bind("<KeyRelease>", lambda e: self.load_users_table(tv, search_ent.get().strip()))

        cols = ("ID", "Full Name", "Username", "Role", "Status", "Must Reset Password", "Date Added")
        tv = ttk.Treeview(self.content_area, columns=cols, show="headings", height=14)
        for c in cols:
            tv.heading(c, text=c, command=lambda _col=c: self.sort_treeview_column(tv, _col, False))
            tv.column(c, width=120, anchor="center")
        tv.pack(fill="both", expand=True, pady=10)

        ctrl_bar = ctk.CTkFrame(self.content_area)
        ctrl_bar.pack(fill="x", pady=5)

        def delete_staff():
            sel = tv.selection()
            if not sel:
                messagebox.showwarning("Select", "Select a staff member.")
                return
            uid, name, uname, role, _, _, _ = tv.item(sel[0])['values']
            if role == "Admin":
                messagebox.showerror("Restricted", "Cannot delete the Administrator account.")
                return
            if messagebox.askyesno("Confirm Dismissal / Deletion",
                                   f"Permanently delete storekeeper '{name}' (@{uname})?"):
                ok, msg = db.delete_user(uid)
                if ok:
                    messagebox.showinfo("Success", msg)
                    self.load_users_table(tv)
                else:
                    messagebox.showerror("Error", msg)

        ctk.CTkButton(ctrl_bar, text="Delete Storekeeper Account", fg_color="#DC2626", hover_color="#991B1B",
                      command=delete_staff).pack(side="left", padx=5)
        self.load_users_table(tv)

    def load_users_table(self, tv, query=""):
        for r in tv.get_children(): tv.delete(r)
        conn = db.get_connection()
        if query:
            users = conn.execute(
                "SELECT id, full_name, username, role, status, must_change_password, created_at FROM users WHERE full_name LIKE ? OR username LIKE ?",
                (f"%{query}%", f"%{query}%")).fetchall()
        else:
            users = conn.execute(
                "SELECT id, full_name, username, role, status, must_change_password, created_at FROM users").fetchall()
        conn.close()
        for u in users:
            tv.insert("", "end", values=(u['id'], u['full_name'], u['username'], u['role'], u['status'],
                                         "Yes" if u['must_change_password'] else "No", u['created_at']))

    # =========================================================================
    # 7. INVENTORY MASTER (WITH MOUSE-DRAG HOVER MULTI-SELECT & CTRL+A)
    # =========================================================================
    def render_inventory_view(self):
        header_row = ctk.CTkFrame(self.content_area, fg_color="transparent")
        header_row.pack(fill="x", pady=(5, 6), padx=5)

        ctk.CTkLabel(header_row, text="Inventory Master & Stock Control",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")

        if self.current_user['role'] == "Admin":
            ctk.CTkButton(header_row, text="Bulk Import (CSV/PDF)", width=170, fg_color="#0F766E",
                          hover_color="#115E59",
                          command=self.handle_bulk_import_csv).pack(side="right", padx=(5, 0))
            ctk.CTkButton(header_row, text="Sample CSV Template", width=150, fg_color="#4338CA", hover_color="#3730A3",
                          command=self.handle_download_csv_template).pack(side="right", padx=5)

        alerts = db.get_low_stock_alerts()
        if alerts:
            crit_count = sum(1 for a in alerts if a['stock_quantity'] <= a['reorder_level'] / 2)
            alert_bar = ctk.CTkFrame(self.content_area, fg_color="#7F1D1D" if crit_count > 0 else "#9A3412", height=32)
            alert_bar.pack(fill="x", pady=(0, 6), padx=5)
            alert_txt = f"⚠ Stock Notice: {len(alerts)} item(s) below 20% Alert Limit ({crit_count} Critical Low / Depleted)"
            ctk.CTkLabel(alert_bar, text=alert_txt, font=ctk.CTkFont(size=12, weight="bold"), text_color="white").pack(
                side="left", padx=10)

        form_card = ctk.CTkFrame(self.content_area)
        form_card.pack(fill="x", pady=(0, 6), padx=5)

        n_e = ctk.CTkEntry(form_card, placeholder_text="Product Name", width=180)
        n_e.pack(side="left", padx=4, pady=6)

        c_e = ctk.CTkEntry(form_card, placeholder_text="Category", width=120)
        c_e.pack(side="left", padx=4, pady=6)

        cp_e = ctk.CTkEntry(form_card, placeholder_text="Cost (GHS)", width=85)
        if self.current_user['role'] == "Admin":
            cp_e.pack(side="left", padx=4, pady=6)

        sp_e = ctk.CTkEntry(form_card, placeholder_text="Selling (GHS)", width=85)
        sp_e.pack(side="left", padx=4, pady=6)

        st_e = ctk.CTkEntry(form_card, placeholder_text="Stock Qty", width=85)
        st_e.pack(side="left", padx=4, pady=6)

        n_e.bind("<Return>", lambda e: c_e.focus_set())
        c_e.bind("<Return>", lambda e: (cp_e if self.current_user['role'] == "Admin" else sp_e).focus_set())
        if self.current_user['role'] == "Admin":
            cp_e.bind("<Return>", lambda e: sp_e.focus_set())
        sp_e.bind("<Return>", lambda e: st_e.focus_set())

        def save_item():
            try:
                cp = float(cp_e.get()) if self.current_user['role'] == "Admin" else 0.0
                sp = float(sp_e.get())
                st = float(st_e.get())
                th = max(1.0, st * 0.20)
            except ValueError:
                messagebox.showerror("Error", "Please provide valid numerical values.")
                return
            conn = db.get_connection()
            try:
                conn.execute(
                    "INSERT INTO products (name, category, cost_price, selling_price, stock_quantity, reorder_level) VALUES (?,?,?,?,?,?)",
                    (n_e.get().strip(), c_e.get().strip(), cp, sp, st, th))
                conn.commit()
                n_e.delete(0, 'end')
                c_e.delete(0, 'end')
                sp_e.delete(0, 'end')
                st_e.delete(0, 'end')
                if self.current_user['role'] == "Admin":
                    cp_e.delete(0, 'end')
                n_e.focus_set()
                self.load_inventory_table(tv)
            except Exception as e:
                messagebox.showerror("Error", str(e))
            finally:
                conn.close()

        st_e.bind("<Return>", lambda e: save_item())
        ctk.CTkButton(form_card, text="+ Add Product", width=110, command=save_item).pack(side="left", padx=6, pady=6)

        search_bar = ctk.CTkFrame(self.content_area, fg_color="transparent")
        search_bar.pack(fill="x", pady=(2, 4), padx=5)

        search_ent = ctk.CTkEntry(search_bar, placeholder_text="Search inventory by name or category...", height=34)
        search_ent.pack(fill="x")
        search_ent.bind("<KeyRelease>", lambda e: self.load_inventory_table(tv, search_ent.get().strip()))

        cols = ("ID", "Name", "Category", "Cost Price", "Selling Price", "Stock Level", "% Left", "Alert Min (20%)",
                "Status") if self.current_user['role'] == "Admin" else (
            "ID", "Name", "Category", "Selling Price", "Stock Level", "% Left", "Alert Min (20%)", "Status")

        tree_frame = ctk.CTkFrame(self.content_area)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=4)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        tv = ttk.Treeview(tree_frame, columns=cols, show="headings", height=12, selectmode="extended")
        for c in cols:
            tv.heading(c, text=c, command=lambda _col=c: self.sort_treeview_column(tv, _col, False))
            tv.column(c, width=105, anchor="center")

        tv.column("ID", width=45, anchor="center")
        tv.column("Name", width=220, anchor="w")
        tv.column("Category", width=130, anchor="w")
        tv.column("% Left", width=85, anchor="center")
        tv.grid(row=0, column=0, sticky="nsew")

        # -------------------------------------------------------------
        # HOVER / CLICK-AND-DRAG MULTI-SELECTION & KEYBOARD SHORTCUTS
        # -------------------------------------------------------------
        def on_tree_drag(event):
            """Accumulates selections as the user holds the left button and drags across items."""
            row_id = tv.identify_row(event.y)
            if row_id:
                cur_sel = set(tv.selection())
                cur_sel.add(row_id)
                tv.selection_set(list(cur_sel))

        def select_all_items(event=None):
            """Selects all items across the table on Ctrl+A."""
            all_ids = tv.get_children()
            if all_ids:
                tv.selection_set(all_ids)
            return "break"

        tv.bind("<B1-Motion>", on_tree_drag)
        tv.bind("<Control-a>", select_all_items)
        tv.bind("<Control-A>", select_all_items)

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

        tv.tag_configure('critical', background='#FEE2E2', foreground='#991B1B')
        tv.tag_configure('warning', background='#FEF3C7', foreground='#92400E')
        tv.tag_configure('normal', background='#F0FDF4', foreground='#166534')

        ctrl_bar = ctk.CTkFrame(self.content_area)
        ctrl_bar.pack(fill="x", pady=(4, 5), padx=5)

        def get_single_selected_p():
            sel = tv.selection()
            if not sel:
                messagebox.showwarning("Select Row", "Please select a product from the table.")
                return None
            return tv.item(sel[0])['values']

        def open_edit_product_modal():
            row = get_single_selected_p()
            if not row: return
            pid = row[0]

            conn = db.get_connection()
            p = conn.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
            conn.close()
            if not p: return

            modal = ctk.CTkToplevel(self)
            modal.title(f"Edit / Restock Item #{pid}")
            modal.geometry("420x460")
            modal.grab_set()

            ctk.CTkLabel(modal, text=f"Update Product: {p['name']}", font=ctk.CTkFont(size=16, weight="bold")).pack(
                pady=(15, 8))

            en_name = ctk.CTkEntry(modal, placeholder_text="Product Name", width=280)
            en_name.insert(0, p['name'])
            en_name.pack(pady=5)
            en_name.focus_set()

            en_cat = ctk.CTkEntry(modal, placeholder_text="Category", width=280)
            en_cat.insert(0, p['category'])
            en_cat.pack(pady=5)

            en_cost = None
            if self.current_user['role'] == "Admin":
                ctk.CTkLabel(modal, text="Cost Price (GHS):", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=70)
                en_cost = ctk.CTkEntry(modal, placeholder_text="Cost Price (GHS)", width=280)
                en_cost.insert(0, f"{p['cost_price']:.2f}")
                en_cost.pack(pady=3)

            ctk.CTkLabel(modal, text="Selling Price (GHS):", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=70)
            en_sell = ctk.CTkEntry(modal, placeholder_text="Selling Price (GHS)", width=280)
            en_sell.insert(0, f"{p['selling_price']:.2f}")
            en_sell.pack(pady=3)

            ctk.CTkLabel(modal, text="Stock Quantity (100% Base):", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=70)
            en_stock = ctk.CTkEntry(modal, placeholder_text="Stock Quantity", width=280)
            en_stock.insert(0, str(p['stock_quantity']))
            en_stock.pack(pady=3)

            def save_update():
                try:
                    cp = float(en_cost.get().strip()) if en_cost else p['cost_price']
                    sp = float(en_sell.get().strip())
                    stk = float(en_stock.get().strip())
                    alert_lim = max(1.0, stk * 0.20)
                except ValueError:
                    messagebox.showerror("Invalid Input", "Please enter valid numerical values.")
                    return

                ok, msg = db.update_product_info(pid, en_name.get().strip(), en_cat.get().strip(), cp, sp, stk,
                                                 alert_lim)
                if ok:
                    messagebox.showinfo("Success", msg)
                    modal.destroy()
                    self.load_inventory_table(tv)
                else:
                    messagebox.showerror("Error", msg)

            ctk.CTkButton(modal, text="Save Updates", width=280, height=38, fg_color="#059669",
                          hover_color="#047857", command=save_update).pack(pady=15)

        tv.bind("<Double-1>", lambda e: open_edit_product_modal())

        def delete_selected_items():
            sel = tv.selection()
            if not sel:
                messagebox.showwarning("Select Items",
                                       "Please select one or more items to delete.\n(Tip: Click and drag, or press Ctrl+A to select all)")
                return

            ids_to_delete = []
            names_to_delete = []
            for item in sel:
                vals = tv.item(item)['values']
                ids_to_delete.append(vals[0])
                names_to_delete.append(str(vals[1]))

            count = len(ids_to_delete)
            if count == 1:
                confirm_msg = f"Permanently delete '{names_to_delete[0]}' from inventory?"
            else:
                confirm_msg = f"Permanently delete all {count} selected products from inventory?\n\nThis cannot be undone."

            if messagebox.askyesno("Confirm Batch Deletion", confirm_msg):
                ok, msg = db.delete_multiple_products(ids_to_delete)
                if ok:
                    messagebox.showinfo("Success", msg)
                    self.load_inventory_table(tv)
                else:
                    messagebox.showerror("Error", msg)

        ctk.CTkButton(ctrl_bar, text="Edit Selected Item", width=150, fg_color="#2563EB", hover_color="#1D4ED8",
                      command=open_edit_product_modal).pack(side="left", padx=5)
        ctk.CTkButton(ctrl_bar, text="Select All (Ctrl+A)", width=130, fg_color="gray40", hover_color="gray30",
                      command=select_all_items).pack(side="left", padx=5)
        ctk.CTkButton(ctrl_bar, text="Delete Selected Items (Batch)", width=210, fg_color="#DC2626",
                      hover_color="#991B1B",
                      command=delete_selected_items).pack(side="left", padx=5)

        self.load_inventory_table(tv)

    def load_inventory_table(self, tv, query=""):
        for r in tv.get_children():
            tv.delete(r)
        conn = db.get_connection()
        if query:
            rows = conn.execute("SELECT * FROM products WHERE name LIKE ? OR category LIKE ? ORDER BY name ASC",
                                (f"%{query}%", f"%{query}%")).fetchall()
        else:
            rows = conn.execute("SELECT * FROM products ORDER BY name ASC").fetchall()
        conn.close()

        for p in rows:
            stk = p['stock_quantity']
            thresh = p['reorder_level'] if p['reorder_level'] > 0 else 1.0

            base_capacity = thresh * 5.0
            percent_left = min(100.0, (stk / base_capacity) * 100) if base_capacity > 0 else 0.0

            if percent_left <= 10.0 or stk <= thresh / 2:
                status = "CRITICAL LOW"
                tag = 'critical'
            elif percent_left <= 20.0 or stk <= thresh:
                status = "LOW STOCK (ALERT)"
                tag = 'warning'
            else:
                status = "HEALTHY"
                tag = 'normal'

            stock_lvl_display = f"{stk:.0f}" if stk.is_integer() else f"{stk:.1f}"
            pct_left_display = f"{percent_left:.0f}%"
            alert_min_display = f"{thresh:.0f} (20%)"

            if self.current_user['role'] == "Admin":
                tv.insert("", "end", values=(
                    p['id'],
                    p['name'],
                    p['category'],
                    f"GHS {p['cost_price']:.2f}",
                    f"GHS {p['selling_price']:.2f}",
                    stock_lvl_display,
                    pct_left_display,
                    alert_min_display,
                    status
                ), tags=(tag,))
            else:
                tv.insert("", "end", values=(
                    p['id'],
                    p['name'],
                    p['category'],
                    f"GHS {p['selling_price']:.2f}",
                    stock_lvl_display,
                    pct_left_display,
                    alert_min_display,
                    status
                ), tags=(tag,))

    def handle_bulk_import_csv(self):
        file_path = filedialog.askopenfilename(
            title="Select Products File (CSV or PDF)",
            filetypes=[("Supported Files", "*.csv;*.pdf"), ("CSV Files", "*.csv"), ("PDF Files", "*.pdf")]
        )
        if not file_path:
            return

        if file_path.lower().endswith(".pdf"):
            ok, msg = db.bulk_import_products_from_pdf(file_path)
        else:
            ok, msg = db.bulk_import_products_from_csv(file_path)

        if ok:
            messagebox.showinfo("Import Success", msg)
            self.switch_view("INV")
        else:
            messagebox.showerror("Import Error", msg)

    def handle_download_csv_template(self):
        file_path = filedialog.asksaveasfilename(
            title="Save Sample CSV Template",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile="YOMES_Inventory_Import_Template.csv"
        )
        if not file_path:
            return
        try:
            db.generate_sample_csv_template(file_path)
            messagebox.showinfo("Template Saved",
                                f"Sample template saved successfully to:\n{file_path}\n\nYou can fill it in Excel or Notepad and import it directly!")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # =========================================================================
    # 8. BACKUP & RESTORE MODAL (ADMIN ONLY)
    # =========================================================================
    def show_backup_restore_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Database Backup & Safety Center")
        modal.geometry("520x400")
        modal.grab_set()

        ctk.CTkLabel(modal, text="Enterprise Database Backup & Restore",
                     font=ctk.CTkFont(size=17, weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(modal, text="Create instant offline snapshots or restore previous database archives.",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(0, 20))

        b_box = ctk.CTkFrame(modal)
        b_box.pack(fill="x", padx=25, pady=8)
        ctk.CTkLabel(b_box, text="Backup Database Snapshot", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=15, pady=(10, 2))
        ctk.CTkLabel(b_box, text="Saves a complete timestamped copy of all inventory, sales, and debt ledgers.",
                     font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", padx=15, pady=(0, 10))

        def execute_backup():
            folder = filedialog.askdirectory(title="Select Folder or USB Drive to Save Backup")
            if not folder:
                return
            ok, msg = db.create_database_backup(folder)
            if ok:
                messagebox.showinfo("Backup Successful", msg)
            else:
                messagebox.showerror("Backup Error", msg)

        ctk.CTkButton(b_box, text="Create Backup Snapshot Now", height=36, fg_color="#0F766E", hover_color="#115E59",
                      command=execute_backup).pack(fill="x", padx=15, pady=(0, 15))

        r_box = ctk.CTkFrame(modal)
        r_box.pack(fill="x", padx=25, pady=8)
        ctk.CTkLabel(r_box, text="Restore Database From Archive", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#EF4444").pack(anchor="w", padx=15, pady=(10, 2))
        ctk.CTkLabel(r_box, text="Restores all shop records from a previously generated .db backup file.",
                     font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", padx=15, pady=(0, 10))

        def execute_restore():
            file_path = filedialog.askopenfilename(
                title="Select Backup Database File (.db)",
                filetypes=[("Database Files", "*.db")]
            )
            if not file_path:
                return

            if messagebox.askyesno("Restore Warning",
                                   "Are you sure you want to replace current shop records with this backup?\n\n(A safety copy of your current database will be saved automatically)."):
                ok, msg = db.restore_database_backup(file_path)
                if ok:
                    messagebox.showinfo("Restore Successful", msg)
                    modal.destroy()
                    self.load_main_dashboard()
                else:
                    messagebox.showerror("Restore Error", msg)

        ctk.CTkButton(r_box, text="Select & Restore Backup (.db)", height=36, fg_color="#DC2626", hover_color="#991B1B",
                      command=execute_restore).pack(fill="x", padx=15, pady=(0, 15))

    # =========================================================================
    # 9. ADVANCED ANALYTICS, MULTI-YEAR EXPANDED & EXPENDITURE TRACKING
    # =========================================================================
    def render_analytics_view(self):
        header_bar = ctk.CTkFrame(self.content_area, fg_color="transparent")
        header_bar.pack(fill="x", pady=(2, 6))

        ctk.CTkLabel(header_bar, text="Executive Financial Analytics & Profit Ledger",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")

        ctk.CTkButton(header_bar, text="+ Add Store Expenditure", width=170, fg_color="#DC2626", hover_color="#B91C1C",
                      command=self.show_record_expense_modal).pack(side="right", padx=(5, 0))

        filter_cb = ctk.CTkComboBox(header_bar, width=170,
                                    values=["Last 7 Days", "This Month (Daily)", "Past 12 Months",
                                            "All Years (Annual)"],
                                    command=self.on_analytics_timeframe_changed)
        filter_cb.set(self.analytics_timeframe)
        filter_cb.pack(side="right", padx=5)

        ctk.CTkLabel(header_bar, text="Period:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="right",
                                                                                                padx=(10, 3))

        conn = db.get_connection()

        where_sale = ""
        where_exp = ""
        now = datetime.now()

        if self.analytics_timeframe == "Last 7 Days":
            seven_days_ago = (now - timedelta(days=6)).strftime("%Y-%m-%d")
            where_sale = f"WHERE DATE(sale_date) >= '{seven_days_ago}'"
            where_exp = f"WHERE DATE(expense_date) >= '{seven_days_ago}'"
        elif self.analytics_timeframe == "This Month (Daily)":
            first_day = now.strftime("%Y-%m-01")
            where_sale = f"WHERE DATE(sale_date) >= '{first_day}'"
            where_exp = f"WHERE DATE(expense_date) >= '{first_day}'"
        elif self.analytics_timeframe == "Past 12 Months":
            one_year_ago = (now - timedelta(days=365)).strftime("%Y-%m-01")
            where_sale = f"WHERE DATE(sale_date) >= '{one_year_ago}'"
            where_exp = f"WHERE DATE(expense_date) >= '{one_year_ago}'"
        else:
            where_sale = ""
            where_exp = ""

        sales_rev = conn.execute(f"SELECT COALESCE(SUM(total_amount), 0) as rev FROM sales {where_sale}").fetchone()[
            'rev']

        if where_sale:
            profit_query = f"""
                SELECT COALESCE(SUM(si.line_profit), 0) as profit 
                FROM sale_items si
                INNER JOIN sales s ON si.sale_id = s.id
                {where_sale}
            """
        else:
            profit_query = "SELECT COALESCE(SUM(line_profit), 0) as profit FROM sale_items"
        gross_profit = conn.execute(profit_query).fetchone()['profit']

        total_expenses = conn.execute(f"SELECT COALESCE(SUM(amount), 0) as exp FROM expenses {where_exp}").fetchone()[
            'exp']
        net_profit = gross_profit - total_expenses
        total_debt = conn.execute("SELECT COALESCE(SUM(current_debt), 0) as debt FROM customers").fetchone()['debt']

        labels = []
        rev_values = []
        net_values = []

        if self.analytics_timeframe == "Last 7 Days":
            for i in range(6, -1, -1):
                day_target = (now - timedelta(days=i)).strftime("%Y-%m-%d")
                labels.append((now - timedelta(days=i)).strftime("%b %d"))
                day_sales = conn.execute(
                    "SELECT COALESCE(SUM(total_amount), 0) as total FROM sales WHERE DATE(sale_date) = DATE(?)",
                    (day_target,)).fetchone()['total']
                day_gross = conn.execute("""
                    SELECT COALESCE(SUM(si.line_profit), 0) as p 
                    FROM sale_items si 
                    JOIN sales s ON si.sale_id = s.id 
                    WHERE DATE(s.sale_date) = DATE(?)
                """, (day_target,)).fetchone()['p']
                day_exp = \
                conn.execute("SELECT COALESCE(SUM(amount), 0) as e FROM expenses WHERE DATE(expense_date) = DATE(?)",
                             (day_target,)).fetchone()['e']
                rev_values.append(day_sales)
                net_values.append(day_gross - day_exp)

        elif self.analytics_timeframe == "This Month (Daily)":
            days_in_month = calendar.monthrange(now.year, now.month)[1]
            for d in range(1, days_in_month + 1):
                day_target = f"{now.year:04d}-{now.month:02d}-{d:02d}"
                labels.append(str(d))
                d_sales = conn.execute(
                    "SELECT COALESCE(SUM(total_amount), 0) as total FROM sales WHERE DATE(sale_date) = DATE(?)",
                    (day_target,)).fetchone()['total']
                d_gross = conn.execute("""
                    SELECT COALESCE(SUM(si.line_profit), 0) as p 
                    FROM sale_items si 
                    JOIN sales s ON si.sale_id = s.id 
                    WHERE DATE(s.sale_date) = DATE(?)
                """, (day_target,)).fetchone()['p']
                d_exp = \
                conn.execute("SELECT COALESCE(SUM(amount), 0) as e FROM expenses WHERE DATE(expense_date) = DATE(?)",
                             (day_target,)).fetchone()['e']
                rev_values.append(d_sales)
                net_values.append(d_gross - d_exp)

        elif self.analytics_timeframe == "Past 12 Months":
            for i in range(11, -1, -1):
                m_target_dt = now - timedelta(days=i * 30)
                ym_target = m_target_dt.strftime("%Y-%m")
                labels.append(m_target_dt.strftime("%b %y"))

                m_sales = conn.execute(
                    "SELECT COALESCE(SUM(total_amount), 0) as total FROM sales WHERE strftime('%Y-%m', sale_date) = ?",
                    (ym_target,)).fetchone()['total']
                m_gross = conn.execute("""
                    SELECT COALESCE(SUM(si.line_profit), 0) as p 
                    FROM sale_items si 
                    JOIN sales s ON si.sale_id = s.id 
                    WHERE strftime('%Y-%m', s.sale_date) = ?
                """, (ym_target,)).fetchone()['p']
                m_exp = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) as e FROM expenses WHERE strftime('%Y-%m', expense_date) = ?",
                    (ym_target,)).fetchone()['e']
                rev_values.append(m_sales)
                net_values.append(m_gross - m_exp)

        else:
            years_rows = conn.execute(
                "SELECT DISTINCT strftime('%Y', sale_date) as y FROM sales UNION SELECT DISTINCT strftime('%Y', expense_date) as y FROM expenses ORDER BY y ASC").fetchall()
            years = [r['y'] for r in years_rows if r['y']]
            if not years:
                years = [str(now.year)]

            for yr in years:
                labels.append(yr)
                y_sales = conn.execute(
                    "SELECT COALESCE(SUM(total_amount), 0) as total FROM sales WHERE strftime('%Y', sale_date) = ?",
                    (yr,)).fetchone()['total']
                y_gross = conn.execute("""
                    SELECT COALESCE(SUM(si.line_profit), 0) as p 
                    FROM sale_items si 
                    JOIN sales s ON si.sale_id = s.id 
                    WHERE strftime('%Y', s.sale_date) = ?
                """, (yr,)).fetchone()['p']
                y_exp = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) as e FROM expenses WHERE strftime('%Y', expense_date) = ?",
                    (yr,)).fetchone()['e']
                rev_values.append(y_sales)
                net_values.append(y_gross - y_exp)

        conn.close()

        cards = ctk.CTkFrame(self.content_area, fg_color="transparent")
        cards.pack(fill="x", pady=(2, 6))

        metric_cards = [
            ("Sales Revenue", f"GHS {sales_rev:,.2f}", "#2563EB"),
            ("Gross Profit", f"GHS {gross_profit:,.2f}", "#059669"),
            ("Expenses / Costs", f"GHS {total_expenses:,.2f}", "#DC2626"),
            ("Net Clean Profit", f"GHS {net_profit:,.2f}", "#0D9488" if net_profit >= 0 else "#991B1B"),
            ("Customer Debtors", f"GHS {total_debt:,.2f}", "#7C3AED")
        ]

        for idx, (title, val, color) in enumerate(metric_cards):
            c = ctk.CTkFrame(cards, fg_color=color, corner_radius=10)
            c.grid(row=0, column=idx, padx=4, pady=2, sticky="nsew")
            cards.grid_columnconfigure(idx, weight=1)
            ctk.CTkLabel(c, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color="white").pack(pady=(8, 2))
            ctk.CTkLabel(c, text=val, font=ctk.CTkFont(size=14, weight="bold"), text_color="white").pack(pady=(0, 8))

        main_split = ctk.CTkFrame(self.content_area, fg_color="transparent")
        main_split.pack(fill="both", expand=True, pady=4)
        main_split.grid_rowconfigure(0, weight=1)
        main_split.grid_columnconfigure(0, weight=3)
        main_split.grid_columnconfigure(1, weight=2)

        graph_card = ctk.CTkFrame(main_split)
        graph_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        chart_title = f"Revenue vs Net Profit Velocity ({self.analytics_timeframe})"
        ctk.CTkLabel(graph_card, text=chart_title, font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=12,
                                                                                                  pady=(8, 0))

        is_dark = ctk.get_appearance_mode() == "Dark"
        bg_color = "#2A2D2E" if is_dark else "#F8FAFC"
        text_color = "white" if is_dark else "#1E293B"

        fig = Figure(figsize=(6, 3.2), dpi=100, facecolor=bg_color)
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg_color)

        import numpy as np
        x = np.arange(len(labels))
        width = 0.38

        ax.bar(x - width / 2, rev_values, width, label="Sales Revenue", color="#3B82F6", edgecolor="#1D4ED8")
        ax.bar(x + width / 2, net_values, width, label="Net Profit", color="#10B981", edgecolor="#047857")

        if self.analytics_timeframe == "This Month (Daily)":
            step = 3 if len(labels) > 25 else 2
            visible_ticks = list(range(0, len(labels), step))
            if (len(labels) - 1) not in visible_ticks:
                visible_ticks.append(len(labels) - 1)
            ax.set_xticks(visible_ticks)
            ax.set_xticklabels([labels[i] for i in visible_ticks], rotation=0)
        elif self.analytics_timeframe in ("Past 12 Months", "All Years (Annual)"):
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=35, ha='right')
        else:
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=0)

        ax.tick_params(colors=text_color, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(text_color)
        ax.grid(axis='y', linestyle='--', alpha=0.3, color=text_color)
        ax.legend(facecolor=bg_color, edgecolor=text_color, labelcolor=text_color, fontsize=8)

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=graph_card)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=6)

        exp_card = ctk.CTkFrame(main_split)
        exp_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        exp_card.grid_rowconfigure(1, weight=1)
        exp_card.grid_columnconfigure(0, weight=1)

        exp_header = ctk.CTkFrame(exp_card, fg_color="transparent")
        exp_header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        ctk.CTkLabel(exp_header, text="Recent Expenditures Ledger", font=ctk.CTkFont(size=13, weight="bold")).pack(
            side="left")

        cols = ("ID", "Date", "Category", "Amount (GHS)", "Details")
        exp_tv = ttk.Treeview(exp_card, columns=cols, show="headings", height=8)
        for c in cols:
            exp_tv.heading(c, text=c, command=lambda _col=c: self.sort_treeview_column(exp_tv, _col, False))
            exp_tv.column(c, width=70, anchor="center")
        exp_tv.column("ID", width=35)
        exp_tv.column("Details", width=110, anchor="w")
        exp_tv.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)

        exp_sb = ttk.Scrollbar(exp_card, orient="vertical", command=exp_tv.yview)
        exp_tv.configure(yscrollcommand=exp_sb.set)
        exp_sb.grid(row=1, column=1, sticky="ns")

        exp_actions = ctk.CTkFrame(exp_card, fg_color="transparent")
        exp_actions.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))

        def delete_selected_expense():
            sel = exp_tv.selection()
            if not sel:
                messagebox.showwarning("Select", "Please select an expense entry to delete.")
                return
            eid, edate, ecat, eamt, _ = exp_tv.item(sel[0])['values']
            if messagebox.askyesno("Confirm Delete", f"Delete {ecat} expense of {eamt}?"):
                ok, msg = db.delete_expense(eid)
                if ok:
                    messagebox.showinfo("Success", msg)
                    self.switch_view("ANALYTICS")
                else:
                    messagebox.showerror("Error", msg)

        ctk.CTkButton(exp_actions, text="Delete Selected Expense", height=28, fg_color="#DC2626", hover_color="#991B1B",
                      command=delete_selected_expense).pack(side="left")

        for r in exp_tv.get_children(): exp_tv.delete(r)
        expenses_list = db.get_expenses_list(limit=80)
        for e in expenses_list:
            d_str = e['expense_date'][:10]
            exp_tv.insert("", "end",
                          values=(e['id'], d_str, e['category'], f"{e['amount']:.2f}", e['description'] or "-"))

    def on_analytics_timeframe_changed(self, choice):
        self.analytics_timeframe = choice
        self.switch_view("ANALYTICS")

    def show_record_expense_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Record Store Expenditure")
        modal.geometry("420x420")
        modal.grab_set()

        ctk.CTkLabel(modal, text="Log Business Expenditure", font=ctk.CTkFont(size=16, weight="bold")).pack(
            pady=(15, 6))
        ctk.CTkLabel(modal, text="Expenses are subtracted from sales profit to give your exact Net Profit.",
                     font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(0, 15))

        cat_cb = ctk.CTkComboBox(modal, width=280, values=[
            "Shop Rent", "Electricity & Utilities", "Staff Wages / Salaries",
            "Transportation & Delivery", "Shop Maintenance / Repairs",
            "New Stock Purchase / Haulage", "Food / Refreshments", "Miscellaneous"
        ])
        cat_cb.pack(pady=8)

        amt_ent = ctk.CTkEntry(modal, placeholder_text="Expense Amount (GHS)", width=280, height=36)
        amt_ent.pack(pady=8)
        amt_ent.focus_set()

        desc_ent = ctk.CTkEntry(modal, placeholder_text="Description / Reason (e.g. ECG Meter credit)", width=280,
                                height=36)
        desc_ent.pack(pady=8)

        def save_exp():
            cat = cat_cb.get().strip()
            amt_str = amt_ent.get().strip()
            desc = desc_ent.get().strip()

            if not amt_str:
                messagebox.showwarning("Missing Amount", "Please enter the amount paid.")
                return

            try:
                amt = float(amt_str)
                if amt <= 0: raise ValueError
            except ValueError:
                messagebox.showerror("Invalid Amount", "Please enter a valid positive numerical amount.")
                return

            ok, msg = db.record_expense(cat, amt, desc, self.current_user['id'])
            if ok:
                messagebox.showinfo("Expense Logged", msg)
                modal.destroy()
                self.switch_view("ANALYTICS")
            else:
                messagebox.showerror("Error", msg)

        amt_ent.bind("<Return>", lambda e: desc_ent.focus_set())
        desc_ent.bind("<Return>", lambda e: save_exp())

        ctk.CTkButton(modal, text="Save Expense Entry", width=280, height=38, fg_color="#DC2626", hover_color="#991B1B",
                      command=save_exp).pack(pady=20)


if __name__ == "__main__":
    app = MasterShopERP()
    app.mainloop()