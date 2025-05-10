from flask import Flask, render_template, request, redirect, session, flash, url_for
import mysql.connector
import hashlib
from datetime import datetime
from flask import make_response
from io import StringIO
import csv
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this in production

# Database Configuration
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='expense6',
            autocommit=False
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

# Password Hashing
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --------------------------
# HELPER FUNCTIONS
# --------------------------

def ensure_transaction_types(user_id):
    """Ensure default transaction types exist for a user"""
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    try:
        # Check if types exist
        cursor.execute("SELECT COUNT(*) FROM transaction_types WHERE user_id = %s", (user_id,))
        if cursor.fetchone()[0] == 0:
            # Add default types if missing
            cursor.execute("""
                INSERT INTO transaction_types (name, user_id)
                VALUES ('income', %s), ('expense', %s), ('saving', %s)
            """, (user_id, user_id, user_id))
            conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error ensuring transaction types: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

# Default categories (should match your database)
DEFAULT_CATEGORIES = [
    {'id': 1, 'name': 'Food', 'is_default': True},
    {'id': 2, 'name': 'Transportation', 'is_default': True},
    {'id': 3, 'name': 'Housing', 'is_default': True},
    {'id': 4, 'name': 'Utilities', 'is_default': True},
    {'id': 5, 'name': 'Entertainment', 'is_default': True},
    {'id': 6, 'name': 'Healthcare', 'is_default': True},
    {'id': 7, 'name': 'Shopping', 'is_default': True},
    {'id': 8, 'name': 'Education', 'is_default': True},
    {'id': 9, 'name': 'Savings', 'is_default': True},
    {'id': 10, 'name': 'Other', 'is_default': True}
]

def ensure_default_categories():
    """Ensure default categories exist in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create categories table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INT PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                is_default BOOLEAN DEFAULT FALSE,
                user_id INT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Insert default categories
        for cat in DEFAULT_CATEGORIES:
            cursor.execute("""
                INSERT INTO categories (id, name, is_default)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE name=VALUES(name), is_default=VALUES(is_default)
            """, (cat['id'], cat['name'], cat['is_default']))
        
        conn.commit()
    except Exception as e:
        print(f"Error ensuring default categories: {str(e)}")
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

# --------------------------
# AUTH ROUTES
# --------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db_connection()
        if not conn:
            flash("Database connection error", "error")
            return render_template('login.html')

        cursor = conn.cursor(dictionary=True)
        try:
            username = request.form['username']
            password = hash_password(request.form['password'])

            cursor.execute("""
                SELECT id, username FROM users 
                WHERE username = %s AND password_hash = %s
            """, (username, password))
            
            user = cursor.fetchone()
            
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                # Ensure default transaction types exist
                ensure_transaction_types(user['id'])
                return redirect(url_for('dashboard'))
            else:
                flash("Invalid username or password", "error")
                
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "error")
        except Exception as e:
            flash(f"Error: {e}", "error")
        finally:
            cursor.close()
            conn.close()
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        conn = None
        cursor = None
        try:
            # Get form data
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')

            # Validate inputs
            if not all([username, email, password, confirm_password]):
                flash("All fields are required", "error")
                return redirect(url_for('register'))

            if password != confirm_password:
                flash("Passwords do not match", "error")
                return redirect(url_for('register'))

            if len(password) < 8:
                flash("Password must be at least 8 characters", "error")
                return redirect(url_for('register'))

            # Hash password
            hashed_password = hash_password(password)

            # Connect to database
            conn = get_db_connection()
            if not conn:
                flash("Database connection error", "error")
                return redirect(url_for('register'))

            cursor = conn.cursor(dictionary=True)

            # Check if username/email exists
            cursor.execute("""
                SELECT id FROM users 
                WHERE username = %s OR email = %s
            """, (username, email))
            if cursor.fetchone():
                flash("Username or email already exists", "error")
                return redirect(url_for('register'))

            # Insert new user
            cursor.execute("""
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
            """, (username, email, hashed_password))
            
            # Get new user ID
            user_id = cursor.lastrowid

            # Add default transaction types
            cursor.execute("""
                INSERT INTO transaction_types (name, user_id)
                VALUES ('income', %s), ('expense', %s), ('saving', %s)
            """, (user_id, user_id, user_id))

            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))

        except mysql.connector.Error as err:
            if conn:
                conn.rollback()
            if err.errno == 1062:  # Duplicate entry
                flash("Username or email already exists", "error")
            else:
                flash(f"Database error: {err}", "error")
        except Exception as e:
            if conn:
                conn.rollback()
            flash(f"Error: {str(e)}", "error")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        return redirect(url_for('register'))

    # GET request
    return render_template('register.html')

# --------------------------
# DASHBOARD ROUTE
# --------------------------

@app.route('/')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('dashboard.html', 
                            total_income=0,
                            total_expense=0,
                            balance=0,
                            transactions=[])

    cursor = conn.cursor(dictionary=True)
    try:
        # Get financial summary
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN c.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE WHEN c.type = 'expense' THEN t.amount ELSE 0 END), 0) as expense
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.user_id = %s
        """, (session['user_id'],))
        totals = cursor.fetchone()
        
        # Get recent transactions
        cursor.execute("""
            SELECT t.*, c.name as category_name, c.type as category_type
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.user_id = %s
            ORDER BY t.date DESC LIMIT 5
        """, (session['user_id'],))
        recent_transactions = cursor.fetchall()
        
        return render_template('dashboard.html', 
                            total_income=totals['income'],
                            total_expense=totals['expense'],
                            balance=totals['income'] - totals['expense'],
                            transactions=recent_transactions)
        
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
        return render_template('dashboard.html', 
                            total_income=0,
                            total_expense=0,
                            balance=0,
                            transactions=[])
    finally:
        cursor.close()
        conn.close()

# --------------------------
# TRANSACTION ROUTES
# --------------------------

@app.route('/transactions')
def transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get filter parameters
    type_filter = request.args.get('type', '')
    category_filter = request.args.get('category', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('transactions.html', 
                            transactions=[],
                            all_categories=[],
                            type_filter=type_filter,
                            category_filter=category_filter,
                            date_from=date_from,
                            date_to=date_to)

    cursor = conn.cursor(dictionary=True)
    try:
        # Base query
        query = """
            SELECT t.*, c.name as category_name, c.type as category_type
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.user_id = %s
        """
        params = [session['user_id']]
        
        # Add filters
        if type_filter:
            query += " AND c.type = %s"
            params.append(type_filter)
        if category_filter:
            query += " AND c.name = %s"
            params.append(category_filter)
        if date_from:
            query += " AND t.date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND t.date <= %s"
            params.append(date_to)
            
        query += " ORDER BY t.date DESC"
        
        cursor.execute(query, tuple(params))
        transactions = cursor.fetchall()
        
        # Get all categories for filter dropdown
        cursor.execute("SELECT name FROM categories WHERE user_id = %s", (session['user_id'],))
        all_categories = cursor.fetchall()
        
        return render_template('transactions.html', 
                            transactions=transactions,
                            all_categories=all_categories,
                            type_filter=type_filter,
                            category_filter=category_filter,
                            date_from=date_from,
                            date_to=date_to)
        
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
        return render_template('transactions.html', 
                            transactions=[],
                            all_categories=[],
                            type_filter=type_filter,
                            category_filter=category_filter,
                            date_from=date_from,
                            date_to=date_to)
    finally:
        cursor.close()
        conn.close()

@app.route('/transactions/add', methods=['GET', 'POST'])
def add_transaction():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Ensure default categories exist
    ensure_default_categories()

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            flash("Database connection error", "error")
            return redirect(url_for('transactions'))

        if request.method == 'POST':
            # Validate form data
            try:
                transaction_data = {
                    'user_id': session['user_id'],
                    'category_id': int(request.form['category_id']),
                    'type': request.form['type'],
                    'amount': float(request.form['amount']),
                    'date': request.form['date'],
                    'frequency': request.form['frequency'],
                    'notes': request.form.get('notes', '')[:255]
                }

                if transaction_data['amount'] <= 0:
                    raise ValueError("Amount must be positive")
                
                if not re.match(r'^\d{4}-\d{2}-\d{2}$', transaction_data['date']):
                    raise ValueError("Invalid date format")

                # Additional date validation
                transaction_date = datetime.strptime(transaction_data['date'], '%Y-%m-%d').date()
                if transaction_date > datetime.now().date():
                    raise ValueError("Date cannot be in the future")

            except ValueError as e:
                flash(f"Invalid input: {str(e)}", "error")
                return redirect(url_for('add_transaction'))

            cursor = conn.cursor(dictionary=True)
            
            # Check if category exists and is accessible to user
            cursor.execute("""
                SELECT id FROM categories 
                WHERE (id = %s AND (is_default = TRUE OR user_id = %s))
                LIMIT 1
            """, (transaction_data['category_id'], session['user_id']))
            
            if not cursor.fetchone():
                flash("Invalid category selected", "error")
                return redirect(url_for('add_transaction'))

            # Insert transaction with all fields
            cursor.execute("""
                INSERT INTO transactions 
                (user_id, category_id, type, amount, date, frequency, notes)
                VALUES (%(user_id)s, %(category_id)s, %(type)s, %(amount)s, %(date)s, %(frequency)s, %(notes)s)
            """, transaction_data)
            
            conn.commit()
            flash("Transaction added successfully", "success")
            return redirect(url_for('transactions'))

        # GET request - load form with categories
        cursor = conn.cursor(dictionary=True)
        
        # Get both default and user-specific categories
        cursor.execute("""
            (SELECT id, name, TRUE as is_default FROM categories WHERE is_default = TRUE)
            UNION
            (SELECT id, name, FALSE as is_default FROM categories WHERE user_id = %s)
            ORDER BY is_default DESC, name ASC
        """, (session['user_id'],))
        
        categories = cursor.fetchall()

        return render_template('add_transaction.html',
                            categories=categories,
                            default_date=datetime.now().strftime('%Y-%m-%d'),
                            default_type='expense',  # Default transaction type
                            min_date='2000-01-01',
                            max_date=datetime.now().strftime('%Y-%m-%d'))

    except mysql.connector.Error as err:
        if conn: conn.rollback()
        flash(f"Database error: {str(err)}", "error")
        return redirect(url_for('transactions'))
    except Exception as e:
        if conn: conn.rollback()
        flash(f"An unexpected error occurred: {str(e)}", "error")
        return redirect(url_for('transactions'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
@app.route('/transactions/<int:transaction_id>/edit', methods=['GET', 'POST'])
def edit_transaction(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('transactions'))

    cursor = conn.cursor(dictionary=True)
    try:
        if request.method == 'POST':
            # Validate form data
            try:
                category_id = int(request.form['category_id'])
                amount = float(request.form['amount'])
                date = request.form['date']
                notes = request.form.get('notes', '')
            except (KeyError, ValueError) as e:
                flash("Invalid form data submitted", "error")
                return redirect(url_for('edit_transaction', transaction_id=transaction_id))

            # Verify transaction belongs to user
            cursor.execute("""
                SELECT id FROM transactions 
                WHERE id = %s AND user_id = %s
            """, (transaction_id, session['user_id']))
            if not cursor.fetchone():
                flash("Transaction not found", "error")
                return redirect(url_for('transactions'))

            # Verify category exists and belongs to user
            cursor.execute("""
                SELECT id FROM categories 
                WHERE id = %s AND user_id = %s
            """, (category_id, session['user_id']))
            if not cursor.fetchone():
                flash("Invalid category selected", "error")
                return redirect(url_for('edit_transaction', transaction_id=transaction_id))

            # Update transaction
            cursor.execute("""
                UPDATE transactions 
                SET category_id = %s, amount = %s, 
                    date = %s, notes = %s
                WHERE id = %s
            """, (category_id, amount, date, notes, transaction_id))
            
            conn.commit()
            flash("Transaction updated successfully", "success")
            return redirect(url_for('transactions'))
        
        # GET request - show edit form
        # Get current transaction details
        cursor.execute("""
            SELECT t.*, c.name as category_name 
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.id = %s AND t.user_id = %s
        """, (transaction_id, session['user_id']))
        
        transaction = cursor.fetchone()
        if not transaction:
            flash("Transaction not found", "error")
            return redirect(url_for('transactions'))

        # Get available categories
        cursor.execute("""
            SELECT id, name FROM categories 
            WHERE user_id = %s
        """, (session['user_id'],))
        categories = cursor.fetchall()

        return render_template('edit_transaction.html',
                            transaction=transaction,
                            categories=categories,
                            default_date=datetime.now().strftime('%Y-%m-%d'))
        
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Database error: {err}", "error")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('edit_transaction', transaction_id=transaction_id))

@app.route('/transactions/<int:transaction_id>/delete', methods=['POST'])
def delete_transaction(transaction_id):
    if 'user_id' not in session:
        flash("Unauthorized access", "error")
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('transactions'))

    cursor = conn.cursor()
    try:
        # Verify transaction belongs to user
        cursor.execute("""
            SELECT id FROM transactions 
            WHERE id = %s AND user_id = %s
        """, (transaction_id, session['user_id']))
        if not cursor.fetchone():
            flash("Transaction not found", "error")
            return redirect(url_for('transactions'))
        
        cursor.execute("""
            DELETE FROM transactions 
            WHERE id = %s
        """, (transaction_id,))
        conn.commit()
        flash("Transaction deleted successfully", "success")
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Database error: {err}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('transactions'))

# --------------------------
# CATEGORY ROUTES
# --------------------------

@app.route('/categories')
def categories():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('categories.html', categories=[])

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM categories 
            WHERE user_id = %s
        """, (session['user_id'],))
        categories = cursor.fetchall()
        return render_template('categories.html', categories=categories)
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
        return render_template('categories.html', categories=[])
    finally:
        cursor.close()
        conn.close()

@app.route('/categories/add', methods=['POST'])
def add_category():
    if 'user_id' not in session:
        flash("Unauthorized access", "error")
        return redirect(url_for('login'))
    
    name = request.form.get('name')
    category_type = request.form.get('type')
    
    if not name or not category_type:
        flash("Missing required fields", "error")
        return redirect(url_for('categories'))
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('categories'))

    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO categories (name, type, user_id)
            VALUES (%s, %s, %s)
        """, (name, category_type, session['user_id']))
        conn.commit()
        flash("Category added successfully", "success")
    except mysql.connector.Error as err:
        conn.rollback()
        if err.errno == 1062:
            flash("Category already exists", "error")
        else:
            flash(f"Database error: {err}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('categories'))

@app.route('/categories/<int:category_id>/edit', methods=['GET', 'POST'])
def edit_category(category_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('categories'))

    cursor = conn.cursor(dictionary=True)
    try:
        if request.method == 'POST':
            name = request.form['name'].strip()
            category_type = request.form['type']
            
            if not name:
                flash('Category name cannot be empty', 'error')
                return redirect(url_for('edit_category', category_id=category_id))
            
            cursor.execute("""
                SELECT id FROM categories 
                WHERE name = %s AND id != %s AND user_id = %s
            """, (name, category_id, session['user_id']))
            
            if cursor.fetchone():
                flash('A category with this name already exists', 'error')
                return redirect(url_for('edit_category', category_id=category_id))
            
            cursor.execute("""
                UPDATE categories 
                SET name = %s, type = %s
                WHERE id = %s AND user_id = %s
            """, (name, category_type, category_id, session['user_id']))
            
            conn.commit()
            flash("Category updated successfully!", "success")
            return redirect(url_for('categories'))
        
        # GET request - show edit form
        cursor.execute("""
            SELECT * FROM categories 
            WHERE id = %s AND user_id = %s
        """, (category_id, session['user_id']))
        
        category = cursor.fetchone()
        if not category:
            flash("Category not found", "error")
            return redirect(url_for('categories'))
        
        return render_template('edit_category.html', category=category)
        
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Database error: {err}", "error")
        return redirect(url_for('categories'))
    except Exception as e:
        flash(f"Error: {e}", "error")
        return redirect(url_for('categories'))
    finally:
        cursor.close()
        conn.close()

@app.route('/categories/<int:category_id>/delete', methods=['POST'])
def delete_category(category_id):
    if 'user_id' not in session:
        flash("Unauthorized access", "error")
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('categories'))

    cursor = conn.cursor()
    try:
        # Verify category belongs to user
        cursor.execute("""
            SELECT id FROM categories 
            WHERE id = %s AND user_id = %s
        """, (category_id, session['user_id']))
        
        if not cursor.fetchone():
            flash("Category not found", "error")
            return redirect(url_for('categories'))
        
        # Check if category is used in transactions
        cursor.execute("""
            SELECT id FROM transactions 
            WHERE category_id = %s AND user_id = %s LIMIT 1
        """, (category_id, session['user_id']))
        
        if cursor.fetchone():
            flash("Cannot delete category with existing transactions", "error")
            return redirect(url_for('categories'))
        
        cursor.execute("""
            DELETE FROM categories 
            WHERE id = %s
        """, (category_id,))
        conn.commit()
        flash("Category deleted successfully", "success")
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Database error: {err}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('categories'))

# --------------------------
# BUDGET ROUTES
# --------------------------

@app.route('/budgets')
def budgets():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('budgets.html', budgets=[])

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT b.*, c.name as category_name, 
                   COALESCE(SUM(t.amount), 0) as spent
            FROM budgets b
            JOIN categories c ON b.category_id = c.id
            LEFT JOIN transactions t ON t.category_id = c.id 
                AND t.user_id = %s 
                AND MONTH(t.date) = MONTH(CURRENT_DATE())
                AND YEAR(t.date) = YEAR(CURRENT_DATE())
            WHERE b.user_id = %s
            GROUP BY b.id
        """, (session['user_id'], session['user_id']))
        budgets = cursor.fetchall()
        return render_template('budgets.html', budgets=budgets)
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
        return render_template('budgets.html', budgets=[])
    finally:
        cursor.close()
        conn.close()

# --------------------------
# REPORT ROUTES
# --------------------------

@app.route('/reports')
def reports():
    # Ensure user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        # Get month/year parameters with defaults
        month = request.args.get('month', default=datetime.now().month, type=int)
        year = request.args.get('year', default=datetime.now().year, type=int)
        
        # Debug print
        print(f"Generating report for user {session['user_id']}, month {month}, year {year}")
        
        # Get database connection
        conn = get_db_connection()
        if not conn:
            flash("Database connection failed", "error")
            return render_template('reports.html',
                                income_data=[],
                                expense_data=[],
                                savings_data=0,
                                month=month,
                                year=year,
                                months=list(range(1, 13)),
                                years=list(range(2020, datetime.now().year + 1)))

        cursor = conn.cursor(dictionary=True)

        # Income Query
        income_query = """
            SELECT c.name, SUM(t.amount) as total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            JOIN transaction_types tt ON t.type_id = tt.id
            WHERE t.user_id = %s AND tt.name = 'income'
            AND MONTH(t.date) = %s AND YEAR(t.date) = %s
            GROUP BY c.name
        """
        cursor.execute(income_query, (session['user_id'], month, year))
        income_data = cursor.fetchall() or []  # Ensure empty list if None

        # Expense Query
        expense_query = """
            SELECT c.name, SUM(t.amount) as total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            JOIN transaction_types tt ON t.type_id = tt.id
            WHERE t.user_id = %s AND tt.name = 'expense'
            AND MONTH(t.date) = %s AND YEAR(t.date) = %s
            GROUP BY c.name
        """
        cursor.execute(expense_query, (session['user_id'], month, year))
        expense_data = cursor.fetchall() or []

        # Savings Query
        savings_query = """
            SELECT COALESCE(SUM(t.amount), 0) as total_saved
            FROM transactions t
            JOIN transaction_types tt ON t.type_id = tt.id
            WHERE t.user_id = %s AND tt.name = 'saving'
            AND MONTH(t.date) = %s AND YEAR(t.date) = %s
        """
        cursor.execute(savings_query, (session['user_id'], month, year))
        savings_result = cursor.fetchone()
        savings_data = savings_result['total_saved'] if savings_result else 0

        return render_template('reports.html',
                            income_data=income_data,
                            expense_data=expense_data,
                            savings_data=savings_data,
                            month=month,
                            year=year,
                            months=list(range(1, 13)),
                            years=list(range(2020, datetime.now().year + 1)))

    except Exception as e:
        print(f"Error generating report: {str(e)}")
        flash("Error generating report", "error")
        return render_template('reports.html',
                            income_data=[],
                            expense_data=[],
                            savings_data=0,
                            month=month,
                            year=year,
                            months=list(range(1, 13)),
                            years=list(range(2020, datetime.now().year + 1)))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
# --------------------------
# PROFILE ROUTES
# --------------------------

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        conn = get_db_connection()
        if not conn:
            flash("Database connection error", "error")
            return redirect(url_for('profile'))
        
        cursor = conn.cursor()
        try:
            username = request.form['username']
            email = request.form['email']
            password = request.form.get('password')
            
            if password:
                hashed_pw = hash_password(password)
                cursor.execute("""
                    UPDATE users 
                    SET username = %s, email = %s, password_hash = %s
                    WHERE id = %s
                """, (username, email, hashed_pw, session['user_id']))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET username = %s, email = %s
                    WHERE id = %s
                """, (username, email, session['user_id']))
            
            conn.commit()
            session['username'] = username
            flash("Profile updated successfully!", "success")
        except mysql.connector.Error as err:
            conn.rollback()
            flash(f"Database error: {err}", "error")
        except Exception as e:
            flash(f"Error: {e}", "error")
        finally:
            cursor.close()
            conn.close()
    
    # GET request - show profile
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('profile.html', user={})

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT username, email FROM users 
            WHERE id = %s
        """, (session['user_id'],))
        user = cursor.fetchone()
        return render_template('profile.html', user=user)
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
        return render_template('profile.html', user={})
    finally:
        cursor.close()
        conn.close()
@app.route('/download_report')
def download_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get parameters
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    # Fetch data (same as your reports route)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get income data
    cursor.execute("""
        SELECT c.name as category, SUM(t.amount) as total 
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        JOIN transaction_types tt ON t.type_id = tt.id
        WHERE t.user_id = %s AND tt.name = 'income'
        AND MONTH(t.date) = %s AND YEAR(t.date) = %s
        GROUP BY c.name
        ORDER BY total DESC
    """, (session['user_id'], month, year))
    income_data = cursor.fetchall()
    
    # Get expense data
    cursor.execute("""
        SELECT c.name as category, SUM(t.amount) as total 
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        JOIN transaction_types tt ON t.type_id = tt.id
        WHERE t.user_id = %s AND tt.name = 'expense'
        AND MONTH(t.date) = %s AND YEAR(t.date) = %s
        GROUP BY c.name
        ORDER BY total DESC
    """, (session['user_id'], month, year))
    expense_data = cursor.fetchall()
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Financial Report', f'{month}/{year}'])
    writer.writerow([])
    
    # Write income data
    writer.writerow(['Income'])
    writer.writerow(['Category', 'Amount'])
    for item in income_data:
        writer.writerow([item['category'], item['total']])
    writer.writerow(['Total Income', sum(item['total'] for item in income_data)])
    writer.writerow([])
    
    # Write expense data
    writer.writerow(['Expenses'])
    writer.writerow(['Category', 'Amount'])
    for item in expense_data:
        writer.writerow([item['category'], item['total']])
    writer.writerow(['Total Expenses', sum(item['total'] for item in expense_data)])
    writer.writerow([])
    
    # Write summary
    total_income = sum(item['total'] for item in income_data)
    total_expenses = sum(item['total'] for item in expense_data)
    writer.writerow(['Summary'])
    writer.writerow(['Net Savings', total_income - total_expenses])
    
    # Prepare response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=financial_report_{month}_{year}.csv'
    response.headers['Content-type'] = 'text/csv'
    
    cursor.close()
    conn.close()
    
    return response
if __name__ == '__main__':
    app.run(debug=True)