# main.py
import os
import sys
import ctypes
import customtkinter as ctk
from tkinter import messagebox, ttk, filedialog
from datetime import datetime
import calendar
import csv
from PIL import Image, ImageEnhance
import db_manager as db
import printing_engine as pe

# Explicit Windows AppUserModelID so taskbar displays the custom app icon
if sys.platform.startswith("win"):
    myappid = "yomes.electrical.erp.v1"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class MasterShopERP(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YOMES Electrical & Home Solution")
        self.geometry("1280x780")
        self.minsize(1050, 680)

        # Set App Window & Taskbar Icon to YOMES.ico
        icon_file = resource_path("YOMES.ico")
        if os.path.exists(icon_file):
            self.iconbitmap(icon_file)
            self.after(200, lambda: self.iconbitmap(icon_file))

        db.init_db()
        self.current_user = None
        self.cart = []
        self.all_products = []
        self.filtered_products = []
        self.selected_product = None
        self.customer_map = {}

        self.selected_history_date = datetime.now().strftime("%Y-%m-%d")

        self.show_login_screen()

    # =========================================================================
    # THEME TOGGLE
    # =========================================================================
    def toggle_theme(self):
        current = ctk.get_appearance_mode()
        if current == "Dark":
            ctk.set_appearance_mode("Light")
            self.theme_btn.configure(text="Dark Mode")
        else:
            ctk.set_appearance_mode("Dark")
            self.theme_btn.configure(text="Light Mode")

    # =========================================================================
    # 1. LOGIN & AUTH
    # =========================================================================
    def get_low_opacity_logo(self, opacity=0.40, size=(75, 75)):
        for candidate in ["YOMES.png"]:
            path = resource_path(candidate)
            if os.path.exists(path):
                try:
                    pil_img = Image.open(path).convert("RGBA")
                    r, g, b, alpha = pil_img.split()
                    alpha = alpha.point(lambda p: int(p * opacity))
                    pil_img.putalpha(alpha)
                    return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
                except Exception:
                    pass
        return None

    def get_sidebar_logo(self, size=(48, 48)):
        for candidate in ["YOMES.png", "YOMES.ico"]:
            path = resource_path(candidate)
            if os.path.exists(path):
                try:
                    pil_img = Image.open(path).convert("RGBA")
                    return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
                except Exception:
                    pass
        return None

    def show_login_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(self, width=420, height=530, corner_radius=35)
        card.place(relx=0.5, rely=0.5, anchor="center")

        # Low-Opacity Image placed right before the "YOMES ELECTRICAL" header
        logo_img = self.get_low_opacity_logo(opacity=0.40, size=(72, 72))
        if logo_img:
            logo_label = ctk.CTkLabel(card, image=logo_img, text="")
            logo_label.pack(pady=(25, 0))
            title_top_pad = (5, 5)
        else:
            title_top_pad = (35, 5)

        ctk.CTkLabel(card, text="YOMES ELECTRICAL", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color="#3B82F6").pack(pady=title_top_pad)
        ctk.CTkLabel(card, text="Enterprise Shop & Inventory System", font=ctk.CTkFont(size=12),
                     text_color="gray").pack(pady=(0, 20))

        self.ent_user = ctk.CTkEntry(card, placeholder_text="Username", width=240, height=32, corner_radius=15)
        self.ent_user.pack(pady=8)
        self.ent_user.focus_set()

        self.ent_pass = ctk.CTkEntry(card, placeholder_text="Password", show="*", width=240, height=32, corner_radius=15)
        self.ent_pass.pack(pady=8)

        self.ent_user.bind("<Return>", lambda e: self.ent_pass.focus_set())
        self.ent_user.bind("<Down>", lambda e: self.ent_pass.focus_set())
        self.ent_pass.bind("<Up>", lambda e: self.ent_user.focus_set())
        self.ent_pass.bind("<Return>", lambda e: self.handle_login())

        ctk.CTkButton(card, text="Sign In", width=290, height=42, command=self.handle_login).pack(pady=(15, 10))
        ctk.CTkButton(card, text="Forgot Password?", fg_color="transparent", text_color="#60A5FA",
                      command=self.show_forgot_password_dialog).pack()

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
            conn = db.get_connection()
            user = conn.execute("SELECT security_question FROM users WHERE username = ?",
                                (ent_u.get().strip(),)).fetchone()
            conn.close()
            if user and user['security_question']:
                q_lbl.configure(text=f"Question: {user['security_question']}")
                ent_a.focus_set()
            else:
                messagebox.showwarning("Notice", "User not found or no question configured.")

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
        ctk.CTkButton(f, text="Reset Password", width=140, fg_color="green", command=exec_reset).pack(side="left", padx=5)

    # =========================================================================
    # 2. MAIN DASHBOARD SHELL
    # =========================================================================
    def load_main_dashboard(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(11, weight=1)

        # Brand Logo on Sidebar
        side_logo = self.get_sidebar_logo(size=(48, 48))
        if side_logo:
            ctk.CTkLabel(self.sidebar, image=side_logo, text="").grid(row=0, column=0, padx=20, pady=(15, 0))
            store_title_pad = (2, 5)
        else:
            store_title_pad = (20, 5)

        ctk.CTkLabel(self.sidebar, text="YOMES STORE", font=ctk.CTkFont(size=18, weight="bold")).grid(row=1, column=0, padx=20, pady=store_title_pad)
        ctk.CTkLabel(self.sidebar, text=f"{self.current_user['role']}: {self.current_user['full_name']}",
                     font=ctk.CTkFont(size=11), text_color="#60A5FA").grid(row=2, column=0, padx=20, pady=(0, 15))

        self.theme_btn = ctk.CTkButton(self.sidebar,
                                       text="Dark Mode" if ctk.get_appearance_mode() == "Light" else "Light Mode",
                                       fg_color="gray30", height=30, command=self.toggle_theme)
        self.theme_btn.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="ew")

        ctk.CTkButton(self.sidebar, text="Sales / Checkout", command=lambda: self.switch_view("POS")).grid(row=4, column=0, padx=15, pady=5, sticky="ew")
        ctk.CTkButton(self.sidebar, text="Sales History", fg_color="#1E3A8A", hover_color="#1E40AF",
                      command=lambda: self.switch_view("HISTORY")).grid(row=5, column=0, padx=15, pady=5, sticky="ew")
        ctk.CTkButton(self.sidebar, text="Inventory Master", command=lambda: self.switch_view("INV")).grid(row=6, column=0, padx=15, pady=5, sticky="ew")
        ctk.CTkButton(self.sidebar, text="Customers & Debts", command=lambda: self.switch_view("CUST")).grid(row=7, column=0, padx=15, pady=5, sticky="ew")

        if self.current_user['role'] == "Admin":
            ctk.CTkButton(self.sidebar, text="Storekeeper Mgmt", fg_color="#4338CA", hover_color="#3730A3",
                          command=lambda: self.switch_view("USERS")).grid(row=8, column=0, padx=15, pady=5, sticky="ew")
            ctk.CTkButton(self.sidebar, text="Analytics & Profit", fg_color="#0F766E", hover_color="#115E59",
                          command=lambda: self.switch_view("ANALYTICS")).grid(row=9, column=0, padx=15, pady=5, sticky="ew")

        ctk.CTkButton(self.sidebar, text="Logout", fg_color="#991B1B", hover_color="#7F1D1D",
                      command=self.show_login_screen).grid(row=12, column=0, padx=15, pady=20, sticky="ew")

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

    # =========================================================================
    # 3. POS TERMINAL (WITH DYNAMIC CUSTOMER DEBT BALANCE)
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

        ctk.CTkLabel(search_card, text="Search & Select Product:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, columnspan=3, padx=10, pady=(5, 2), sticky="w")

        self.pos_search_entry = ctk.CTkEntry(search_card, placeholder_text="Type product name to search...", height=38, font=ctk.CTkFont(size=13))
        self.pos_search_entry.grid(row=1, column=0, padx=(10, 5), pady=(0, 5), sticky="ew")

        self.pos_q_ent = ctk.CTkEntry(search_card, width=65, placeholder_text="Qty", height=38)
        self.pos_q_ent.insert(0, "1")
        self.pos_q_ent.grid(row=1, column=1, padx=5, pady=(0, 5))

        add_btn = ctk.CTkButton(search_card, text="Add Item", width=85, height=38, command=self.add_pos_item)
        add_btn.grid(row=1, column=2, padx=(5, 10), pady=(0, 5))

        self.suggest_frame = ctk.CTkFrame(left, height=130)
        self.suggest_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))
        self.suggest_frame.grid_remove()

        self.suggest_list = ttk.Treeview(self.suggest_frame, columns=("name", "price", "stock", "status"), show="headings", height=4)
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

        ctk.CTkButton(cart_actions, text="Increase (+ / Up)", width=120, command=self.increase_cart_item).pack(side="left", padx=4)
        ctk.CTkButton(cart_actions, text="Decrease (- / Down)", width=120, fg_color="gray40", command=self.decrease_cart_item).pack(side="left", padx=4)
        ctk.CTkButton(cart_actions, text="Remove (Del)", width=105, fg_color="#DC2626", hover_color="#991B1B", command=self.remove_cart_item).pack(side="left", padx=4)
        ctk.CTkButton(cart_actions, text="Clear Cart", width=80, fg_color="#7F1D1D", command=self.clear_pos_cart).pack(side="right", padx=4)

        right = ctk.CTkFrame(self.content_area)
        right.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        ctk.CTkLabel(right, text="Billing & Finalization", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        # Customer Header & Add Button
        cust_row = ctk.CTkFrame(right, fg_color="transparent")
        cust_row.pack(fill="x", padx=15, pady=(10, 0))

        ctk.CTkLabel(cust_row, text="Customer Account:").pack(side="left")
        ctk.CTkButton(cust_row, text="+ New Customer", width=105, height=24, font=ctk.CTkFont(size=11),
                      fg_color="#2563EB", hover_color="#1D4ED8", command=self.show_quick_add_customer_dialog).pack(side="right")

        self.pos_c_cb = ctk.CTkComboBox(right, width=280, values=["Walk-in (Cash Only)"], command=self.on_pos_customer_changed)
        self.pos_c_cb.pack(fill="x", padx=15, pady=(5, 2))

        # Dynamic Customer Current Debt Display
        self.pos_cust_debt_lbl = ctk.CTkLabel(right, text="Account: Walk-in (No Debt Record)",
                                              font=ctk.CTkFont(size=11, weight="bold"), text_color="gray")
        self.pos_cust_debt_lbl.pack(anchor="w", padx=18, pady=(0, 6))

        ctk.CTkLabel(right, text="Payment Method:").pack(anchor="w", padx=15, pady=(6, 0))
        self.pos_m_cb = ctk.CTkComboBox(right, width=280, values=["CASH", "MOMO", "CREDIT / ON ACCOUNT"])
        self.pos_m_cb.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(right, text="Amount Paid (GHS):").pack(anchor="w", padx=15, pady=(10, 0))
        self.pos_paid_ent = ctk.CTkEntry(right, placeholder_text="0.00", width=280, height=36)
        self.pos_paid_ent.pack(fill="x", padx=15, pady=5)
        self.pos_paid_ent.bind("<Return>", lambda e: self.execute_pos_checkout("THERMAL"))

        self.pos_total_lbl = ctk.CTkLabel(right, text="Total: GHS 0.00", font=ctk.CTkFont(size=22, weight="bold"),
                                          text_color="#10B981")
        self.pos_total_lbl.pack(pady=15)

        ctk.CTkButton(right, text="Checkout & Thermal Slip", height=42,
                      command=lambda: self.execute_pos_checkout("THERMAL")).pack(fill="x", padx=15, pady=6)
        ctk.CTkButton(right, text="Checkout & A4 PDF Invoice", height=42, fg_color="#047857", hover_color="#065F46",
                      command=lambda: self.execute_pos_checkout("A4")).pack(fill="x", padx=15, pady=6)

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

    def show_quick_add_customer_dialog(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Quick Register Customer")
        modal.geometry("380x310")
        modal.grab_set()

        ctk.CTkLabel(modal, text="Quick Register Customer", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 10))

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

                self.populate_pos_data()
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
        self.render_cart_tree()

    def execute_pos_checkout(self, print_type):
        if not self.cart:
            messagebox.showwarning("Empty", "Cart is empty.")
            return
        total = sum(i['line_total'] for i in self.cart)
        try:
            paid = float(self.pos_paid_ent.get().strip() or total)
        except ValueError:
            messagebox.showerror("Error", "Invalid payment amount.")
            return

        cust = self.customer_map.get(self.pos_c_cb.get())
        balance = max(0.0, total - paid)

        if balance > 0 and not cust:
            messagebox.showwarning("Debtor Account Required",
                                   "You must select a registered customer to grant credit / deferred balance.")
            return

        receipt_no = f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        ok, res = db.process_sale_transaction(receipt_no, cust['id'] if cust else None, self.pos_m_cb.get(), self.cart,
                                              total, paid, balance, self.current_user['id'])
        if not ok:
            messagebox.showerror("Error", str(res))
            return

        sale_id, low_stock_warnings = res

        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        if print_type == "THERMAL":
            txt = pe.generate_thermal_slip_text(receipt_no, date_str, self.cart, total, paid, balance,
                                                cust['name'] if cust else "Walk-in")
            with open(f"{receipt_no}.txt", "w") as f:
                f.write(txt)
            messagebox.showinfo("Thermal Slip Generated", f"Slip Generated:\n\n{txt}")
        else:
            pdf_name = f"{receipt_no}.pdf"
            pe.generate_a4_invoice_pdf(pdf_name, receipt_no, date_str, self.cart, total, paid, balance, cust)
            messagebox.showinfo("Invoice Saved", f"A4 PDF saved as: {pdf_name}")

        if low_stock_warnings:
            lines = []
            for w in low_stock_warnings:
                rem = w['stock_quantity']
                thresh = w['reorder_level']
                severity = "CRITICAL DEPLETION" if rem <= thresh / 2 else "LOW STOCK"
                lines.append(f"- {w['name']}: Only {rem} remaining (Alert Limit: {thresh}) [{severity}]")
            messagebox.showwarning("Stock Alert Notice", "The following items have crossed their minimum threshold:\n\n" + "\n".join(lines))

        self.clear_pos_cart()
        self.pos_paid_ent.delete(0, 'end')
        self.populate_pos_data()
        self.pos_search_entry.focus_set()

    # =========================================================================
    # 4. SALES HISTORY & DAY LEDGER (CALENDAR PICKER & EXPORT)
    # =========================================================================
    def render_sales_history_view(self):
        ctk.CTkLabel(self.content_area, text="Daily Sales History & Day Ledger",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(5, 5))

        top_filter_bar = ctk.CTkFrame(self.content_area)
        top_filter_bar.pack(fill="x", pady=5)

        ctk.CTkLabel(top_filter_bar, text="Selected Date:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(10, 5))

        self.cal_btn = ctk.CTkButton(top_filter_bar, text=f"📅 {self.selected_history_date}", width=140, fg_color="#3B82F6", hover_color="#2563EB",
                                     command=lambda: self.open_calendar_picker_dialog(history_tv, stat_lbl))
        self.cal_btn.pack(side="left", padx=5)

        ctk.CTkButton(top_filter_bar, text="Today", width=70, fg_color="gray40", hover_color="gray30",
                      command=lambda: self.set_history_to_today(history_tv, stat_lbl)).pack(side="left", padx=3)

        ctk.CTkButton(top_filter_bar, text="Export CSV", width=100, fg_color="#0F766E", hover_color="#115E59",
                      command=lambda: self.export_sales_to_csv(self.selected_history_date)).pack(side="right", padx=5)
        ctk.CTkButton(top_filter_bar, text="Export PDF Report", width=130, fg_color="#4338CA", hover_color="#3730A3",
                      command=lambda: self.export_sales_to_pdf(self.selected_history_date)).pack(side="right", padx=5)

        stat_bar = ctk.CTkFrame(self.content_area, fg_color="#1E293B", height=38)
        stat_bar.pack(fill="x", pady=5)
        stat_lbl = ctk.CTkLabel(stat_bar, text="Loading Day Metrics...", font=ctk.CTkFont(size=13, weight="bold"), text_color="white")
        stat_lbl.pack(side="left", padx=15, pady=6)

        cols = ("Time", "Receipt No", "Customer", "Payment Method", "Total (GHS)", "Paid (GHS)", "Balance (GHS)", "Cashier")
        history_tv = ttk.Treeview(self.content_area, columns=cols, show="headings", height=13)
        for c in cols:
            history_tv.heading(c, text=c)
            history_tv.column(c, width=120, anchor="center")
        history_tv.column("Customer", width=160, anchor="w")
        history_tv.pack(fill="both", expand=True, pady=8)

        history_tv.bind("<Double-1>", lambda e: self.open_sale_details_modal(history_tv))

        ctrl_bar = ctk.CTkFrame(self.content_area)
        ctrl_bar.pack(fill="x", pady=5)
        ctk.CTkButton(ctrl_bar, text="View Sale Line Items (Double-Click)", width=230, command=lambda: self.open_sale_details_modal(history_tv)).pack(side="left", padx=5)

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
                ctk.CTkLabel(days_frame, text=d_name, font=ctk.CTkFont(size=11, weight="bold"), width=36).grid(row=0, column=idx, pady=2)

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

        stat_lbl.configure(text=f"Date: {query_date}  |  Orders: {len(sales)}  |  Gross Sales: GHS {total_rev:.2f}  |  Collected: GHS {total_paid:.2f}  |  Debt Balance: GHS {total_bal:.2f}")

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
        ctk.CTkLabel(card, text=f"Order Breakdown: {receipt_no}", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=10, pady=(10, 2))
        meta_str = f"Date: {sale['sale_date']} | Cashier: {sale['cashier_name']}\nCustomer: {sale['customer_name'] or 'Walk-in'} | Method: {sale['payment_method']}"
        ctk.CTkLabel(card, text=meta_str, font=ctk.CTkFont(size=11), text_color="gray", justify="left").pack(anchor="w", padx=10, pady=(0, 10))

        cols = ("Item", "Qty", "Unit Price (GHS)", "Total (GHS)")
        item_tv = ttk.Treeview(modal, columns=cols, show="headings", height=7)
        for c in cols:
            item_tv.heading(c, text=c)
            item_tv.column(c, width=110, anchor="center")
        item_tv.column("Item", width=190, anchor="w")
        item_tv.pack(fill="both", expand=True, padx=15, pady=5)

        for it in items:
            item_tv.insert("", "end", values=(it['product_name'] or "Deleted Product", it['quantity'], f"{it['unit_price']:.2f}", f"{it['line_total']:.2f}"))

        sum_bar = ctk.CTkFrame(modal, fg_color="transparent")
        sum_bar.pack(fill="x", padx=15, pady=10)
        ctk.CTkLabel(sum_bar, text=f"Total: GHS {sale['total_amount']:.2f}  |  Paid: GHS {sale['amount_paid']:.2f}  |  Balance: GHS {sale['balance_due']:.2f}",
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
                writer.writerow(["Date Time", "Receipt No", "Customer", "Payment Method", "Total (GHS)", "Amount Paid (GHS)", "Balance Due (GHS)", "Cashier"])
                for s in sales:
                    writer.writerow([s['sale_date'], s['receipt_no'], s['customer'], s['payment_method'], s['total_amount'], s['amount_paid'], s['balance_due'], s['cashier']])
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
            tv.heading(c, text=c)
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

        ctk.CTkLabel(pay_box, text="Debt Payment:", font=ctk.CTkFont(size=13, weight="bold")).pack(
            anchor="w", padx=10, pady=(8, 4))

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

        ctk.CTkLabel(modal, text="Installment Payment History:",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 4))

        p_cols = ("Date & Time", "Amount Paid", "Method", "Before", "Balance Left", "Received By", "Note")
        p_tv = ttk.Treeview(modal, columns=p_cols, show="headings", height=8)
        for c in p_cols:
            p_tv.heading(c, text=c)
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
            tv.heading(c, text=c)
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
    # 7. INVENTORY MASTER (WITH EDIT / RESTOCK SUPPORT)
    # =========================================================================
    def render_inventory_view(self):
        ctk.CTkLabel(self.content_area, text="Inventory Master & Stock Control",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=(5, 5))

        alerts = db.get_low_stock_alerts()
        if alerts:
            crit_count = sum(1 for a in alerts if a['stock_quantity'] <= a['reorder_level'] / 2)
            alert_bar = ctk.CTkFrame(self.content_area, fg_color="#7F1D1D" if crit_count > 0 else "#9A3412", height=32)
            alert_bar.pack(fill="x", pady=(0, 5))
            alert_txt = f"Stock Notice: {len(alerts)} item(s) below alert limit ({crit_count} Critical Low / Depleted)"
            ctk.CTkLabel(alert_bar, text=alert_txt, font=ctk.CTkFont(size=12, weight="bold"), text_color="white").pack(side="left", padx=10)

        top_bar = ctk.CTkFrame(self.content_area)
        top_bar.pack(fill="x", pady=5)

        n_e = ctk.CTkEntry(top_bar, placeholder_text="Product Name", width=160)
        n_e.pack(side="left", padx=3)
        c_e = ctk.CTkEntry(top_bar, placeholder_text="Category", width=110)
        c_e.pack(side="left", padx=3)
        cp_e = ctk.CTkEntry(top_bar, placeholder_text="Cost (GHS)", width=80)
        if self.current_user['role'] == "Admin": cp_e.pack(side="left", padx=3)
        sp_e = ctk.CTkEntry(top_bar, placeholder_text="Selling (GHS)", width=80)
        sp_e.pack(side="left", padx=3)
        st_e = ctk.CTkEntry(top_bar, placeholder_text="Stock Qty", width=70)
        st_e.pack(side="left", padx=3)
        th_e = ctk.CTkEntry(top_bar, placeholder_text="Alert Min", width=70)
        th_e.pack(side="left", padx=3)
        th_e.insert(0, "5")

        n_e.bind("<Return>", lambda e: c_e.focus_set())
        c_e.bind("<Return>", lambda e: (cp_e if self.current_user['role'] == "Admin" else sp_e).focus_set())
        if self.current_user['role'] == "Admin":
            cp_e.bind("<Return>", lambda e: sp_e.focus_set())
        sp_e.bind("<Return>", lambda e: st_e.focus_set())
        st_e.bind("<Return>", lambda e: th_e.focus_set())

        def save_item():
            try:
                cp = float(cp_e.get()) if self.current_user['role'] == "Admin" else 0.0
                sp = float(sp_e.get())
                st = float(st_e.get())
                th = float(th_e.get().strip() or 5)
            except ValueError:
                messagebox.showerror("Error", "Invalid numeric values.")
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
                th_e.delete(0, 'end')
                th_e.insert(0, "5")
                if self.current_user['role'] == "Admin": cp_e.delete(0, 'end')
                n_e.focus_set()
                self.load_inventory_table(tv)
            except Exception as e:
                messagebox.showerror("Error", str(e))
            finally:
                conn.close()

        th_e.bind("<Return>", lambda e: save_item())
        ctk.CTkButton(top_bar, text="+ Add Item", width=90, command=save_item).pack(side="left", padx=4)

        search_ent = ctk.CTkEntry(top_bar, placeholder_text="Search Inventory...", width=180)
        search_ent.pack(side="right", padx=6)
        search_ent.bind("<KeyRelease>", lambda e: self.load_inventory_table(tv, search_ent.get().strip()))

        cols = ("ID", "Name", "Category", "Cost Price", "Selling Price", "Stock Level", "Alert Min", "Status") if self.current_user[
                                                                                               'role'] == "Admin" else (
            "ID", "Name", "Category", "Selling Price", "Stock Level", "Alert Min", "Status")
        tv = ttk.Treeview(self.content_area, columns=cols, show="headings", height=13)
        for c in cols:
            tv.heading(c, text=c)
            tv.column(c, width=105, anchor="center")
        tv.column("Name", width=160, anchor="w")
        tv.pack(fill="both", expand=True, pady=10)

        tv.tag_configure('critical', background='#FEE2E2', foreground='#991B1B')
        tv.tag_configure('warning', background='#FEF3C7', foreground='#92400E')
        tv.tag_configure('normal', background='#F0FDF4', foreground='#166534')

        ctrl_bar = ctk.CTkFrame(self.content_area)
        ctrl_bar.pack(fill="x", pady=5)

        def get_selected_p():
            sel = tv.selection()
            if not sel:
                messagebox.showwarning("Select", "Select a product from the table.")
                return None
            return tv.item(sel[0])['values']

        def open_edit_product_modal():
            row = get_selected_p()
            if not row: return
            pid = row[0]

            conn = db.get_connection()
            p = conn.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
            conn.close()
            if not p: return

            modal = ctk.CTkToplevel(self)
            modal.title(f"Edit / Restock Item #{pid}")
            modal.geometry("420x450")
            modal.grab_set()

            ctk.CTkLabel(modal, text=f"Update Product: {p['name']}", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 8))

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

            ctk.CTkLabel(modal, text="Current Total Stock Quantity:", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=70)
            en_stock = ctk.CTkEntry(modal, placeholder_text="Stock Quantity", width=280)
            en_stock.insert(0, str(p['stock_quantity']))
            en_stock.pack(pady=3)

            ctk.CTkLabel(modal, text="Alert Minimum Limit:", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=70)
            en_alert = ctk.CTkEntry(modal, placeholder_text="Alert Min Limit", width=280)
            en_alert.insert(0, str(p['reorder_level']))
            en_alert.pack(pady=3)

            def save_update():
                try:
                    cp = float(en_cost.get().strip()) if en_cost else p['cost_price']
                    sp = float(en_sell.get().strip())
                    stk = float(en_stock.get().strip())
                    alert_lim = float(en_alert.get().strip() or 5)
                except ValueError:
                    messagebox.showerror("Invalid Input", "Please enter valid numerical values.")
                    return

                ok, msg = db.update_product_info(pid, en_name.get().strip(), en_cat.get().strip(), cp, sp, stk, alert_lim)
                if ok:
                    messagebox.showinfo("Success", msg)
                    modal.destroy()
                    self.load_inventory_table(tv)
                else:
                    messagebox.showerror("Error", msg)

            ctk.CTkButton(modal, text="Save Updates & Stock", width=280, height=38, fg_color="#059669",
                          hover_color="#047857", command=save_update).pack(pady=15)

        tv.bind("<Double-1>", lambda e: open_edit_product_modal())

        def delete_item():
            row = get_selected_p()
            if not row: return
            pid, pname = row[0], row[1]
            if messagebox.askyesno("Delete", f"Permanently delete '{pname}'?"):
                db.delete_product(pid)
                self.load_inventory_table(tv)

        ctk.CTkButton(ctrl_bar, text="Edit / Restock Item", width=140, fg_color="#2563EB", hover_color="#1D4ED8",
                      command=open_edit_product_modal).pack(side="left", padx=5)
        ctk.CTkButton(ctrl_bar, text="Delete Selected Item", fg_color="#DC2626", hover_color="#991B1B",
                      command=delete_item).pack(side="left", padx=5)
        self.load_inventory_table(tv)

    def load_inventory_table(self, tv, query=""):
        for r in tv.get_children(): tv.delete(r)
        conn = db.get_connection()
        if query:
            rows = conn.execute("SELECT * FROM products WHERE name LIKE ? OR category LIKE ? ORDER BY name ASC",
                                (f"%{query}%", f"%{query}%")).fetchall()
        else:
            rows = conn.execute("SELECT * FROM products ORDER BY name ASC").fetchall()
        conn.close()
        for p in rows:
            stk = p['stock_quantity']
            thresh = p['reorder_level']
            if stk <= thresh / 2:
                status = "CRITICAL"
                tag = 'critical'
            elif stk <= thresh:
                status = "LOW STOCK"
                tag = 'warning'
            else:
                status = "NORMAL"
                tag = 'normal'

            if self.current_user['role'] == "Admin":
                tv.insert("", "end", values=(p['id'], p['name'], p['category'], f"GHS {p['cost_price']:.2f}",
                                             f"GHS {p['selling_price']:.2f}", stk, thresh, status), tags=(tag,))
            else:
                tv.insert("", "end", values=(p['id'], p['name'], p['category'], f"GHS {p['selling_price']:.2f}",
                                             stk, thresh, status), tags=(tag,))

    # =========================================================================
    # 8. ANALYTICS (ADMIN ONLY)
    # =========================================================================
    def render_analytics_view(self):
        ctk.CTkLabel(self.content_area, text="Executive Financial Analytics",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", pady=10)
        conn = db.get_connection()
        sales_rev = conn.execute("SELECT COALESCE(SUM(total_amount), 0) as rev FROM sales").fetchone()['rev']
        total_profit = conn.execute("SELECT COALESCE(SUM(line_profit), 0) as profit FROM sale_items").fetchone()[
            'profit']
        total_debt = conn.execute("SELECT COALESCE(SUM(current_debt), 0) as debt FROM customers").fetchone()['debt']
        conn.close()

        cards = ctk.CTkFrame(self.content_area)
        cards.pack(fill="x", pady=20)
        for idx, (title, val, color) in enumerate([
            ("Total Gross Revenue", f"GHS {sales_rev:,.2f}", "#2563EB"),
            ("Gross Estimated Profit", f"GHS {total_profit:,.2f}", "#059669"),
            ("Total Outstanding Debtors", f"GHS {total_debt:,.2f}", "#DC2626")
        ]):
            c = ctk.CTkFrame(cards, fg_color=color, corner_radius=10)
            c.grid(row=0, column=idx, padx=15, pady=10, sticky="nsew")
            cards.grid_columnconfigure(idx, weight=1)
            ctk.CTkLabel(c, text=title, font=ctk.CTkFont(size=14, weight="bold"), text_color="white").pack(pady=(15, 5))
            ctk.CTkLabel(c, text=val, font=ctk.CTkFont(size=20, weight="bold"), text_color="white").pack(pady=(0, 15))


if __name__ == "__main__":
    app = MasterShopERP()
    app.mainloop()