# db_manager.py
import sqlite3
import os
import sys
import shutil
import csv
import re
from datetime import datetime
import pdfplumber


def get_db_path(filename="yomes_enterprise.db"):
    """Anchors database file directly alongside the application executable."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, filename)


DB_NAME = get_db_path("yomes_enterprise.db")


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Storekeeper',
            status TEXT NOT NULL DEFAULT 'Active',
            must_change_password INTEGER DEFAULT 0,
            security_question TEXT,
            security_answer TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    user_cols = [col[1] for col in cursor.execute("PRAGMA table_info(users)").fetchall()]
    if "security_question" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN security_question TEXT")
    if "security_answer" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN security_answer TEXT")
    if "must_change_password" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0")

    # 2. Customers Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            current_debt REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 3. Products Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            cost_price REAL DEFAULT 0.0,
            selling_price REAL NOT NULL,
            stock_quantity REAL NOT NULL DEFAULT 0.0,
            reorder_level REAL NOT NULL DEFAULT 5.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    prod_cols = [col[1] for col in cursor.execute("PRAGMA table_info(products)").fetchall()]
    if "reorder_level" not in prod_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN reorder_level REAL NOT NULL DEFAULT 5.0")
    if "cost_price" not in prod_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN cost_price REAL DEFAULT 0.0")

    # 4. Sales Master Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_no TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            user_id INTEGER,
            payment_method TEXT NOT NULL,
            total_amount REAL NOT NULL,
            amount_paid REAL NOT NULL,
            balance_due REAL NOT NULL,
            sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 5. Sale Items Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            cost_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            unit_price REAL NOT NULL,
            line_total REAL NOT NULL,
            line_profit REAL NOT NULL,
            FOREIGN KEY (sale_id) REFERENCES sales(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # 6. Customer Installment Payments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customer_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            amount_paid REAL NOT NULL,
            payment_method TEXT NOT NULL,
            balance_before REAL NOT NULL,
            balance_after REAL NOT NULL,
            payment_note TEXT,
            received_by INTEGER,
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (received_by) REFERENCES users(id)
        )
    """)

    # 7. Expenses Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            expense_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            logged_by INTEGER,
            FOREIGN KEY (logged_by) REFERENCES users(id)
        )
    """)

    admin = cursor.execute("SELECT * FROM users WHERE LOWER(username) = 'admin'").fetchone()
    if not admin:
        cursor.execute("""
            INSERT INTO users (username, password, full_name, role, status, must_change_password, security_question, security_answer)
            VALUES ('admin', 'admin123', 'System Administrator', 'Admin', 'Active', 0, 'What is your favorite electrical brand?', 'YOMES')
        """)
    else:
        admin_dict = dict(admin)
        if not admin_dict.get('security_question') or not admin_dict.get('security_answer'):
            cursor.execute("""
                UPDATE users 
                SET security_question = 'What is your favorite electrical brand?',
                    security_answer = 'YOMES'
                WHERE LOWER(username) = 'admin'
            """)

    conn.commit()
    conn.close()


# =============================================================================
# EXPENSE MANAGEMENT
# =============================================================================
def record_expense(category, amount, description, logged_by):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO expenses (category, amount, description, logged_by)
            VALUES (?, ?, ?, ?)
        """, (category.strip(), float(amount), description.strip(), logged_by))
        conn.commit()
        return True, "Expense recorded successfully."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def get_expenses_list(limit=100):
    conn = get_connection()
    rows = conn.execute("""
        SELECT e.*, u.full_name as logger_name
        FROM expenses e
        LEFT JOIN users u ON e.logged_by = u.id
        ORDER BY e.expense_date DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_expense(expense_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
        return True, "Expense deleted."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


# =============================================================================
# AUTHENTICATION & ACCESS CONTROL
# =============================================================================
def authenticate_user(username, password):
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE LOWER(username) = LOWER(?) AND password = ? AND status = 'Active'",
        (username.strip(), password)
    ).fetchone()
    conn.close()
    return dict(user) if user else None


def update_user_password(user_id, new_password, sec_q=None, sec_a=None):
    conn = get_connection()
    try:
        if sec_q and sec_a:
            conn.execute("""
                UPDATE users 
                SET password = ?, security_question = ?, security_answer = ?, must_change_password = 0 
                WHERE id = ?
            """, (new_password, sec_q, sec_a, user_id))
        else:
            conn.execute("""
                UPDATE users 
                SET password = ?, must_change_password = 0 
                WHERE id = ?
            """, (new_password, user_id))
        conn.commit()
        return True, "Password updated successfully."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def reset_password_with_security(username, sec_answer, new_password):
    conn = get_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username.strip(),)).fetchone()
        if not user:
            return False, "User account not found."
        if not user['security_answer'] or user['security_answer'].strip().lower() != sec_answer.strip().lower():
            return False, "Security answer does not match records."
        if len(new_password) < 4:
            return False, "Password must be at least 4 characters long."

        conn.execute("UPDATE users SET password = ?, must_change_password = 0 WHERE id = ?", (new_password, user['id']))
        conn.commit()
        return True, "Password successfully reset! You can now sign in."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def create_storekeeper(full_name, username, temp_password):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO users (username, password, full_name, role, status, must_change_password)
            VALUES (?, ?, ?, 'Storekeeper', 'Active', 1)
        """, (username.strip(), temp_password, full_name.strip()))
        conn.commit()
        return True, "Storekeeper created with mandatory first-login setup."
    except sqlite3.IntegrityError:
        return False, "Username is already registered."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def delete_user(user_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM users WHERE id = ? AND role != 'Admin'", (user_id,))
        conn.commit()
        return True, "Staff account deleted."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


# =============================================================================
# INVENTORY, BATCH DELETION & BULK RESTOCKING
# =============================================================================
def update_product_info(product_id, name, category, cost_price, selling_price, stock_quantity, reorder_level):
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE products
            SET name = ?, category = ?, cost_price = ?, selling_price = ?, stock_quantity = ?, reorder_level = ?
            WHERE id = ?
        """, (name.strip(), category.strip(), cost_price, selling_price, stock_quantity, reorder_level, product_id))
        conn.commit()
        return True, "Product details and stock levels updated."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def delete_product(product_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        return True, "Product deleted."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def delete_multiple_products(product_ids):
    """Deletes an arbitrary list of product IDs in a single atomic transaction."""
    if not product_ids:
        return True, "No items selected."
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in product_ids)
        conn.execute(f"DELETE FROM products WHERE id IN ({placeholders})", tuple(product_ids))
        conn.commit()
        return True, f"Successfully removed {len(product_ids)} items."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def get_low_stock_alerts():
    conn = get_connection()
    alerts = conn.execute("""
        SELECT * FROM products 
        WHERE stock_quantity <= reorder_level 
        ORDER BY stock_quantity ASC
    """).fetchall()
    conn.close()
    return [dict(a) for a in alerts]


def bulk_import_products_from_csv(file_path):
    conn = get_connection()
    cursor = conn.cursor()
    inserted_count = 0
    updated_count = 0
    errors = []

    try:
        with open(file_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            reader.fieldnames = [fn.strip().lower().replace(" ", "_") for fn in reader.fieldnames]

            required_cols = {"name", "category", "cost_price", "selling_price", "stock_quantity"}
            if not required_cols.issubset(set(reader.fieldnames)):
                missing = required_cols - set(reader.fieldnames)
                return False, f"Missing required columns in CSV: {', '.join(missing)}"

            cursor.execute("BEGIN TRANSACTION")
            for line_no, row in enumerate(reader, start=2):
                name = row.get("name", "").strip()
                category = row.get("category", "").strip() or "General"

                if not name:
                    continue

                try:
                    cp = float(row.get("cost_price", 0) or 0.0)
                    sp = float(row.get("selling_price", 0) or 0.0)
                    qty = float(row.get("stock_quantity", 0) or 0.0)
                    alert_min = float(row.get("reorder_level", max(1.0, qty * 0.20)) or max(1.0, qty * 0.20))
                except ValueError:
                    errors.append(f"Row {line_no}: Invalid numeric values for '{name}'")
                    continue

                existing = cursor.execute("SELECT id FROM products WHERE LOWER(name) = LOWER(?)", (name,)).fetchone()
                if existing:
                    cursor.execute("""
                        UPDATE products
                        SET category = ?, cost_price = ?, selling_price = ?, stock_quantity = stock_quantity + ?, reorder_level = ?
                        WHERE id = ?
                    """, (category, cp, sp, qty, alert_min, existing['id']))
                    updated_count += 1
                else:
                    cursor.execute("""
                        INSERT INTO products (name, category, cost_price, selling_price, stock_quantity, reorder_level)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (name, category, cp, sp, qty, alert_min))
                    inserted_count += 1

            conn.commit()

        msg = f"Bulk Import Completed!\n\n- New Items Added: {inserted_count}\n- Existing Items Restocked: {updated_count}"
        if errors:
            msg += f"\n\nWarnings:\n" + "\n".join(errors[:5])
        return True, msg

    except Exception as e:
        conn.rollback()
        return False, f"Import Failed: {str(e)}"
    finally:
        conn.close()


def bulk_import_products_from_pdf(file_path):
    """
    Extracts tabular product data directly from PDF files.
    Applies regex cleaning on '400.00/PCS' and ACCUMULATES onto existing stock.
    """
    conn = get_connection()
    cursor = conn.cursor()
    inserted_count = 0
    updated_count = 0

    try:
        cursor.execute("BEGIN TRANSACTION")
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    header = [str(c).strip().lower().replace(" ", "_") if c else "" for c in table[0]]

                    def find_col(aliases):
                        for alias in aliases:
                            for idx, h in enumerate(header):
                                if alias in h:
                                    return idx
                        return None

                    name_col = find_col(["name", "item", "product", "description"])
                    cat_col = find_col(["cat", "category", "group", "type"])
                    cost_col = find_col(["cost", "buying", "cp"])
                    sell_col = find_col(["unit_price", "sell", "price", "sp", "rate"])
                    qty_col = find_col(["qty", "stock", "quantity", "count"])
                    alert_col = find_col(["alert", "reorder", "min", "threshold"])

                    if name_col is None or (sell_col is None and qty_col is None):
                        continue

                    def clean_num(val, default=0.0):
                        if val is None:
                            return default
                        if isinstance(val, (int, float)):
                            return float(val)
                        s = str(val).replace(",", "").strip()
                        match = re.search(r"[-+]?\d+(?:\.\d+)?", s)
                        if match:
                            try:
                                return float(match.group())
                            except ValueError:
                                return default
                        return default

                    for row in table[1:]:
                        if not row or not any(row):
                            continue

                        raw_name = str(row[name_col]).strip() if name_col < len(row) and row[name_col] else ""
                        if not raw_name or raw_name.lower() in ("total", "subtotal", "name", "item", "description",
                                                                "product name"):
                            continue

                        category = str(row[cat_col]).strip() if (
                                    cat_col is not None and cat_col < len(row) and row[cat_col]) else "General"
                        cp = clean_num(row[cost_col]) if (cost_col is not None and cost_col < len(row)) else 0.0
                        sp = clean_num(row[sell_col]) if (sell_col is not None and sell_col < len(row)) else 0.0
                        qty = clean_num(row[qty_col]) if (qty_col is not None and qty_col < len(row)) else 0.0
                        alert_min = clean_num(row[alert_col], max(1.0, qty * 0.20)) if (
                                    alert_col is not None and alert_col < len(row)) else max(1.0, qty * 0.20)

                        if sp <= 0 and cp <= 0 and qty <= 0:
                            continue

                        existing = cursor.execute("SELECT id FROM products WHERE LOWER(name) = LOWER(?)",
                                                  (raw_name,)).fetchone()
                        if existing:
                            cursor.execute("""
                                UPDATE products
                                SET category = ?, cost_price = ?, selling_price = ?, stock_quantity = stock_quantity + ?, reorder_level = ?
                                WHERE id = ?
                            """, (category, cp, sp, qty, alert_min, existing['id']))
                            updated_count += 1
                        else:
                            cursor.execute("""
                                INSERT INTO products (name, category, cost_price, selling_price, stock_quantity, reorder_level)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (raw_name, category, cp, sp, qty, alert_min))
                            inserted_count += 1

        conn.commit()
        return True, f"PDF Stock Import Completed!\n\n- New Items Added: {inserted_count}\n- Existing Items Restocked: {updated_count}"
    except Exception as e:
        conn.rollback()
        return False, f"PDF Stock Extraction Failed: {str(e)}"
    finally:
        conn.close()


def generate_sample_csv_template(file_path):
    sample_data = [
        ["name", "category", "cost_price", "selling_price", "stock_quantity", "reorder_level"],
        ["1.5mm Single Core Cable (Pure Copper)", "Cables & Wiring", 120.00, 150.00, 200, 40],
        ["2.5mm Twin with Earth Cable 100m", "Cables & Wiring", 310.00, 360.00, 50, 10],
        ["13A Double Switch Socket (White)", "Sockets & Switches", 18.00, 25.00, 100, 20],
        ["18W LED Ceiling Surface Panel Light", "Lighting & Bulbs", 28.00, 40.00, 80, 16],
        ["63A Double Pole Main Breaker", "Distribution & Breakers", 45.00, 65.00, 30, 6]
    ]
    with open(file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(sample_data)


# =============================================================================
# BACKUP & RESTORE
# =============================================================================
def create_database_backup(destination_folder):
    if not os.path.exists(DB_NAME):
        return False, "Active database file not found."
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"YOMES_DB_Backup_{timestamp}.db"
        dest_path = os.path.join(destination_folder, backup_filename)

        conn = get_connection()
        conn.execute("PRAGMA wal_checkpoint(FULL)")
        conn.close()

        shutil.copy2(DB_NAME, dest_path)
        return True, f"Database backup saved successfully to:\n{dest_path}"
    except Exception as e:
        return False, str(e)


def restore_database_backup(backup_file_path):
    if not os.path.exists(backup_file_path):
        return False, "Selected backup file does not exist."
    try:
        test_conn = sqlite3.connect(backup_file_path)
        table_test = test_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
        test_conn.close()

        if not table_test:
            return False, "The selected file is not a valid YOMES ERP backup database."

        if os.path.exists(DB_NAME):
            shutil.copy2(DB_NAME, f"{DB_NAME}.safety_backup")

        shutil.copy2(backup_file_path, DB_NAME)
        return True, "Database successfully restored. Please restart the application."
    except Exception as e:
        return False, f"Restore failed: {str(e)}"


# =============================================================================
# SALES TRANSACTIONS & DEBTORS
# =============================================================================
def process_sale_transaction(receipt_no, customer_id, payment_method, cart_items, total_amount, amount_paid,
                             balance_due, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION")

        cursor.execute("""
            INSERT INTO sales (receipt_no, customer_id, user_id, payment_method, total_amount, amount_paid, balance_due)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (receipt_no, customer_id, user_id, payment_method, total_amount, amount_paid, balance_due))
        sale_id = cursor.lastrowid

        low_stock_warnings = []
        for item in cart_items:
            cursor.execute("""
                INSERT INTO sale_items (sale_id, product_id, quantity, cost_price, selling_price, unit_price, line_total, line_profit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (sale_id, item['id'], item['qty'], item['cost_price'], item['selling_price'], item['selling_price'],
                  item['line_total'], item['line_profit']))

            cursor.execute("""
                UPDATE products
                SET stock_quantity = stock_quantity - ?
                WHERE id = ?
            """, (item['qty'], item['id']))

            prod = cursor.execute("SELECT name, stock_quantity, reorder_level FROM products WHERE id = ?",
                                  (item['id'],)).fetchone()
            if prod and prod['stock_quantity'] <= prod['reorder_level']:
                low_stock_warnings.append(dict(prod))

        if customer_id and balance_due > 0:
            cursor.execute("""
                UPDATE customers
                SET current_debt = current_debt + ?
                WHERE id = ?
            """, (balance_due, customer_id))

        conn.commit()
        return True, (sale_id, low_stock_warnings)
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def update_customer_info(customer_id, name, phone, address):
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE customers
            SET name = ?, phone = ?, address = ?
            WHERE id = ?
        """, (name.strip(), phone.strip(), address.strip(), customer_id))
        conn.commit()
        return True, "Customer details updated."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def delete_customer(customer_id):
    conn = get_connection()
    try:
        cust = conn.execute("SELECT current_debt FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if cust and cust['current_debt'] > 0:
            return False, f"Cannot delete customer with an active debt of GHS {cust['current_debt']:.2f}."
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        conn.commit()
        return True, "Customer deleted."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def record_customer_installment(customer_id, amount_paid, payment_method, note, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION")
        cust = cursor.execute("SELECT current_debt, name FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not cust:
            return False, "Customer not found."

        bal_before = cust['current_debt']
        if bal_before <= 0:
            return False, "Customer has zero debt balance."

        bal_after = max(0.0, bal_before - amount_paid)

        cursor.execute("""
            UPDATE customers
            SET current_debt = ?
            WHERE id = ?
        """, (bal_after, customer_id))

        cursor.execute("""
            INSERT INTO customer_payments (customer_id, amount_paid, payment_method, balance_before, balance_after, payment_note, received_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (customer_id, amount_paid, payment_method, bal_before, bal_after, note, user_id))

        conn.commit()
        return True, f"Recorded GHS {amount_paid:.2f} installment. Remaining debt: GHS {bal_after:.2f}"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def get_customer_payments(customer_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT cp.*, u.full_name as receiver_name
        FROM customer_payments cp
        LEFT JOIN users u ON cp.received_by = u.id
        WHERE cp.customer_id = ?
        ORDER BY cp.payment_date DESC
    """, (customer_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]