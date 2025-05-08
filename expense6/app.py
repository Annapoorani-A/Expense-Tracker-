from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
import mysql.connector
import hashlib
from datetime import datetime

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
            autocommit=False  # Explicit transactions
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

# Password Hashing
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

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
            ORDER BY date DESC LIMIT 5
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

    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('transactions'))

    if request.method == 'POST':
        try:
            # Your existing POST handling code
            pass
        except Exception as e:
            flash(f"Error: {str(e)}", "error")

    # For GET requests or if POST fails
    cursor = conn.cursor(dictionary=True)
    try:
        # Get all categories for the current user
        cursor.execute("SELECT id, name, type FROM categories WHERE user_id = %s", 
                      (session['user_id'],))
        categories = cursor.fetchall()

        # Get distinct transaction types from categories
        types = [{'id': 'expense', 'name': 'Expense'}, 
                {'id': 'income', 'name': 'Income'}]

        return render_template('add_transaction.html',
                            categories=categories,
                            types=types,
                            default_date=datetime.now().strftime('%Y-%m-%d'))
    except Exception as e:
        flash(f"Database error: {str(e)}", "error")
        return redirect(url_for('transactions'))
    finally:
        cursor.close()
        conn.close()

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
            # Handle form submission
            amount = float(request.form['amount'])
            category_id = int(request.form['category_id'])
            date = request.form['date']
            notes = request.form.get('notes', '')
            
            cursor.execute("""
                UPDATE transactions 
                SET amount = %s, category_id = %s, date = %s, notes = %s
                WHERE id = %s AND user_id = %s
            """, (amount, category_id, date, notes, transaction_id, session['user_id']))
            
            conn.commit()
            flash("Transaction updated successfully", "success")
            return redirect(url_for('transactions'))
        
        # GET request - show edit form
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
        
        cursor.execute("SELECT id, name FROM categories WHERE user_id = %s", (session['user_id'],))
        categories = cursor.fetchall()
        
        return render_template('edit_transaction.html',
                            transaction=transaction,
                            categories=categories)
        
    except ValueError as ve:
        flash(f"Invalid input: {ve}", "error")
        return redirect(url_for('edit_transaction', transaction_id=transaction_id))
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Database error: {err}", "error")
        return redirect(url_for('transactions'))
    except Exception as e:
        flash(f"Error: {e}", "error")
        return redirect(url_for('transactions'))
    finally:
        cursor.close()
        conn.close()

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
        cursor.execute("SELECT id FROM transactions WHERE id = %s AND user_id = %s", 
                      (transaction_id, session['user_id']))
        if not cursor.fetchone():
            flash("Transaction not found", "error")
            return redirect(url_for('transactions'))
        
        cursor.execute("DELETE FROM transactions WHERE id = %s", (transaction_id,))
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
        cursor.execute("SELECT * FROM categories WHERE user_id = %s", (session['user_id'],))
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
        if err.errno == 1062:  # Duplicate entry
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
            # Handle form submission
            name = request.form['name'].strip()
            category_type = request.form['type']
            
            # Validate
            if not name:
                flash('Category name cannot be empty', 'error')
                return redirect(url_for('edit_category', category_id=category_id))
            
            # Check if name already exists (excluding current category)
            cursor.execute("""
                SELECT id FROM categories 
                WHERE name = %s AND id != %s AND user_id = %s
            """, (name, category_id, session['user_id']))
            
            if cursor.fetchone():
                flash('A category with this name already exists', 'error')
                return redirect(url_for('edit_category', category_id=category_id))
            
            # Update category
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
        
        cursor.execute("DELETE FROM categories WHERE id = %s", (category_id,))
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
        # Get budgets with spending data
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
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('reports.html', 
                            totals=[],
                            spending=[],
                            month=datetime.now().month,
                            year=datetime.now().year)

    cursor = conn.cursor(dictionary=True)
    
    try:
        month = int(request.args.get('month', datetime.now().month))
        year = int(request.args.get('year', datetime.now().year))
        
        cursor.execute("""
            SELECT c.type, SUM(t.amount) as total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.user_id = %s AND MONTH(t.date) = %s AND YEAR(t.date) = %s
            GROUP BY c.type
        """, (session['user_id'], month, year))
        totals = cursor.fetchall()
        
        cursor.execute("""
            SELECT c.name, SUM(t.amount) as total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.user_id = %s AND c.type = 'expense' 
            AND MONTH(t.date) = %s AND YEAR(t.date) = %s
            GROUP BY c.name
        """, (session['user_id'], month, year))
        spending = cursor.fetchall()
        
        return render_template('reports.html', 
                            totals=totals,
                            spending=spending,
                            month=month,
                            year=year)
        
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
        return render_template('reports.html', 
                            totals=[],
                            spending=[],
                            month=datetime.now().month,
                            year=datetime.now().year)
    finally:
        cursor.close()
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
        cursor.execute("SELECT username, email FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        return render_template('profile.html', user=user)
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
        return render_template('profile.html', user={})
    finally:
        cursor.close()
        conn.close()

# --------------------------
# AUTH ROUTES
# --------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            username = request.form['username']
            email = request.form['email']
            password = hash_password(request.form['password'])

            conn = get_db_connection()
            if not conn:
                flash("Database connection error", "error")
                return render_template('register.html')

            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO users (username, email, password_hash) 
                VALUES (%s, %s, %s)
            """, (username, email, password))
            
            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
            
        except mysql.connector.Error as err:
            conn.rollback()
            if err.errno == 1062:  # Duplicate entry
                flash("Username or email already exists", "error")
            else:
                flash(f"Database error: {err}", "error")
        except Exception as e:
            flash(f"Error: {e}", "error")
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals(): conn.close()
    
    return render_template('register.html')

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
                SELECT * FROM users 
                WHERE username = %s AND password_hash = %s
            """, (username, password))
            
            user = cursor.fetchone()
            
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
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

if __name__ == '__main__':
    app.run(debug=True)