# db_manager.py
import sqlite3
import hashlib
import os
from datetime import datetime

DB_NAME = "yomes_enterprise.db"


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if not salt:
        salt = os.urandom(16).hex()
    hashed = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
    return hashed, salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest() == hashed


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Users / Staff Accounts
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT CHECK(role IN ('Admin', 'Storekeeper')) NOT NULL,
        status TEXT DEFAULT 'Active' CHECK(status IN ('Active', 'Disabled')),
        must_change_password INTEGER DEFAULT 1,
        security_question TEXT,
        security_answer_hash TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Inventory / Products
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        cost_price REAL NOT NULL,
        selling_price REAL NOT NULL,
        stock_quantity REAL DEFAULT 0,
        reorder_level REAL DEFAULT 5,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Debtors / Customers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        address TEXT,
        credit_limit REAL DEFAULT 0.00,
        current_debt REAL DEFAULT 0.00,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Sales Header
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_no TEXT UNIQUE NOT NULL,
        customer_id INTEGER,
        payment_method TEXT NOT NULL,
        subtotal REAL NOT NULL,
        discount REAL DEFAULT 0.00,
        total_amount REAL NOT NULL,
        amount_paid REAL NOT NULL,
        balance_due REAL DEFAULT 0.00,
        user_id INTEGER NOT NULL,
        sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    # 5. Sale Line Items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        product_id INTEGER,
        quantity REAL NOT NULL,
        unit_cost REAL NOT NULL,
        unit_price REAL NOT NULL,
        line_total REAL NOT NULL,
        line_profit REAL NOT NULL,
        FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
    );
    """)

    # 6. Debt Audit Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS debt_adjustments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        old_debt REAL NOT NULL,
        new_debt REAL NOT NULL,
        adjustment_type TEXT NOT NULL,
        reason TEXT,
        adjusted_by INTEGER NOT NULL,
        adjustment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
        FOREIGN KEY (adjusted_by) REFERENCES users(id)
    );
    """)

    # 7. Customer Installment Payments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customer_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        amount_paid REAL NOT NULL,
        payment_method TEXT NOT NULL,
        payment_note TEXT,
        balance_before REAL NOT NULL,
        balance_after REAL NOT NULL,
        received_by INTEGER NOT NULL,
        payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
        FOREIGN KEY (received_by) REFERENCES users(id)
    );
    """)

    # Create Default Admin
    cursor.execute("SELECT COUNT(*) as count FROM users")
    if cursor.fetchone()['count'] == 0:
        h, s = hash_password("admin123")
        ans_h, _ = hash_password("accra", s)
        cursor.execute("""
            INSERT INTO users (full_name, username, password_hash, salt, role, status, must_change_password, security_question, security_answer_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("System Administrator", "admin", h, s, "Admin", "Active", 0, "What is your default company city?", ans_h))

    conn.commit()
    conn.close()


# --- Auth Operations ---

def authenticate_user(username, password):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND status = 'Active'", (username,)).fetchone()
    conn.close()
    if user and verify_password(password, user['password_hash'], user['salt']):
        return dict(user)
    return None


def update_user_password(user_id, new_password, security_q=None, security_ans=None):
    h, s = hash_password(new_password)
    conn = get_connection()
    cursor = conn.cursor()
    if security_q and security_ans:
        ans_h, _ = hash_password(security_ans.strip().lower(), s)
        cursor.execute("""
            UPDATE users 
            SET password_hash = ?, salt = ?, must_change_password = 0, security_question = ?, security_answer_hash = ?
            WHERE id = ?
        """, (h, s, security_q, ans_h, user_id))
    else:
        cursor.execute("""
            UPDATE users 
            SET password_hash = ?, salt = ?, must_change_password = 0 
            WHERE id = ?
        """, (h, s, user_id))
    conn.commit()
    conn.close()


def create_storekeeper(full_name, username, temp_password):
    h, s = hash_password(temp_password)
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO users (full_name, username, password_hash, salt, role, status, must_change_password)
            VALUES (?, ?, ?, ?, 'Storekeeper', 'Active', 1)
        """, (full_name, username, h, s))
        conn.commit()
        return True, "Storekeeper account created successfully."
    except sqlite3.IntegrityError:
        return False, "Username is already in use."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def delete_user(user_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return True, "User account deleted."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def reset_password_with_security(username, security_answer, new_password):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user:
        conn.close()
        return False, "User not found."

    ans_h, _ = hash_password(security_answer.strip().lower(), user['salt'])
    if ans_h != user['security_answer_hash']:
        conn.close()
        return False, "Incorrect answer to security question."

    new_h, new_s = hash_password(new_password)
    conn.execute("UPDATE users SET password_hash = ?, salt = ?, must_change_password = 0 WHERE id = ?",
                 (new_h, new_s, user['id']))
    conn.commit()
    conn.close()
    return True, "Password reset successfully."


# --- Customer & Debt Operations ---

def update_customer_info(cust_id, name, phone, address):
    conn = get_connection()
    try:
        conn.execute("UPDATE customers SET name = ?, phone = ?, address = ? WHERE id = ?",
                     (name, phone, address, cust_id))
        conn.commit()
        return True, "Customer details updated."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def adjust_customer_debt(cust_id, new_debt, reason, user_id, adj_type="MANUAL_EDIT"):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION;")
        old_debt = cursor.execute("SELECT current_debt FROM customers WHERE id = ?", (cust_id,)).fetchone()[
            'current_debt']
        cursor.execute("UPDATE customers SET current_debt = ? WHERE id = ?", (new_debt, cust_id))
        cursor.execute("""
            INSERT INTO debt_adjustments (customer_id, old_debt, new_debt, adjustment_type, reason, adjusted_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cust_id, old_debt, new_debt, adj_type, reason, user_id))
        conn.commit()
        return True, "Debt updated successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def record_customer_installment(customer_id, amount_paid, payment_method, note, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION;")
        cust = cursor.execute("SELECT current_debt FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not cust:
            return False, "Customer not found."

        balance_before = cust['current_debt']
        if amount_paid <= 0:
            return False, "Payment amount must be greater than zero."

        balance_after = max(0.0, balance_before - amount_paid)

        cursor.execute("UPDATE customers SET current_debt = ? WHERE id = ?", (balance_after, customer_id))

        cursor.execute("""
            INSERT INTO customer_payments (customer_id, amount_paid, payment_method, payment_note, balance_before, balance_after, received_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (customer_id, amount_paid, payment_method, note, balance_before, balance_after, user_id))

        conn.commit()
        return True, "Payment recorded and debt deducted successfully."
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
        JOIN users u ON cp.received_by = u.id
        WHERE cp.customer_id = ?
        ORDER BY cp.payment_date DESC
    """, (customer_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_customer(cust_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM customers WHERE id = ?", (cust_id,))
        conn.commit()
        return True, "Customer record deleted."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


# --- Product & Stock Operations ---

def update_product_info(prod_id, name, category, cost_price, selling_price, stock_quantity, reorder_level):
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE products 
            SET name = ?, category = ?, cost_price = ?, selling_price = ?, stock_quantity = ?, reorder_level = ?
            WHERE id = ?
        """, (name, category, cost_price, selling_price, stock_quantity, reorder_level, prod_id))
        conn.commit()
        return True, "Product updated successfully."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def delete_product(prod_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM products WHERE id = ?", (prod_id,))
        conn.commit()
        return True, "Product deleted."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def get_low_stock_alerts():
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, name, stock_quantity, reorder_level 
        FROM products 
        WHERE stock_quantity <= reorder_level 
        ORDER BY stock_quantity ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def process_sale_transaction(receipt_no, customer_id, payment_method, cart_items, total_amount, amount_paid,
                             balance_due, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    low_stock_warnings = []
    try:
        cursor.execute("BEGIN TRANSACTION;")

        cursor.execute("""
            INSERT INTO sales (receipt_no, customer_id, payment_method, subtotal, discount, total_amount, amount_paid, balance_due, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (receipt_no, customer_id, payment_method, total_amount, 0.0, total_amount, amount_paid, balance_due,
              user_id))

        sale_id = cursor.lastrowid

        for item in cart_items:
            cursor.execute("""
                INSERT INTO sale_items (sale_id, product_id, quantity, unit_cost, unit_price, line_total, line_profit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sale_id, item['id'], item['qty'], item['cost_price'], item['selling_price'], item['line_total'],
                  item['line_profit']))

            cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?",
                           (item['qty'], item['id']))

            # Recheck stock level vs alert threshold
            p_data = cursor.execute("SELECT name, stock_quantity, reorder_level FROM products WHERE id = ?",
                                    (item['id'],)).fetchone()
            if p_data and p_data['stock_quantity'] <= p_data['reorder_level']:
                low_stock_warnings.append(dict(p_data))

        if customer_id and balance_due > 0:
            cursor.execute("UPDATE customers SET current_debt = current_debt + ? WHERE id = ?",
                           (balance_due, customer_id))

        conn.commit()
        return True, (sale_id, low_stock_warnings)
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()