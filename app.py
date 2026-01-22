from flask import Flask, render_template, request, redirect, session, flash
from datetime import datetime
import json
import os
import random

app = Flask(__name__)
app.secret_key = "secure_banking_key"

DB_FILE = "banking_data.json"

# --- CONFIGURATION: SPENDING LIMITS ---
TIER_LIMITS = {
    "Tier 1": 50000,    # Max daily transfer: 50k
    "Tier 2": 200000,   # Max daily transfer: 200k
    "Tier 3": 5000000   # Max daily transfer: 5m
}

# --- HELPER FUNCTIONS ---

def load_data():
    """Reads the database file."""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, 'r') as file:
            return json.load(file)
    except (json.JSONDecodeError, IOError):
        return {}

def save_data(data):
    """Writes data to file."""
    with open(DB_FILE, 'w') as file:
        json.dump(data, file, indent=4)

def generate_ref():
    """Generates a unique transaction reference."""
    return f"REF{random.randint(1000000000, 9999999999)}"

def check_daily_limit(user, amount):
    """Resets daily limit if date changed, checks if amount allowed."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Reset if it's a new day
    if user.get("last_txn_date") != today_str:
        user["daily_used"] = 0
        user["last_txn_date"] = today_str
    
    tier = user.get("tier", "Tier 1")
    limit = TIER_LIMITS.get(tier, 50000)
    
    if (user.get("daily_used", 0) + amount) > limit:
        return False, limit
    
    return True, limit

# --- PAGE ROUTES (LINKING THE HTML FILES) ---

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].lower().strip()
        pin = request.form["pin"]
        customers = load_data()

        if username in customers and customers[username]["pin"] == pin:
            session["user"] = username
            session["last_login"] = datetime.now().strftime("%d %b %Y, %I:%M %p")
            return redirect("/dashboard")
        else:
            return render_template("login.html", error="Invalid username or PIN")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        username = request.form["username"].lower().strip()
        pin = request.form["pin"]
        customers = load_data()

        if username in customers:
            return render_template("register.html", error="Username taken")
        
        customers[username] = {
            "pin": pin,
            "name": name,
            "account_no": str(random.randint(2000000000, 2999999999)), # Realistic Acc No
            "account_type": "Savings",
            "tier": "Tier 1",
            "daily_used": 0,
            "last_txn_date": datetime.now().strftime("%Y-%m-%d"),
            "balance": 0,
            "status": "Active",
            "transactions": []
        }
        save_data(customers)
        return redirect("/")
    return render_template("register.html")

# 1. DASHBOARD PAGE
@app.route("/dashboard")
def dashboard():
    if "user" not in session: return redirect("/")
    
    customers = load_data()
    user = customers.get(session["user"])
    
    # If user doesn't exist (server reset), clear session and logout
    if not user:
        session.clear()
        return redirect("/")

    # Calculate Limits for Progress Bar
    tier = user.get("tier", "Tier 1")
    limit = TIER_LIMITS.get(tier, 50000)
    daily_used = user.get("daily_used", 0)
    
    # Visual reset if date changed (without saving yet)
    if user.get("last_txn_date") != datetime.now().strftime("%Y-%m-%d"):
        daily_used = 0

    progress = min((daily_used / limit) * 100, 100) if limit > 0 else 0

    return render_template("dashboard.html", user=user, limit=limit, daily_used=daily_used, progress=progress)

# 2. TRANSACTIONS PAGE
@app.route("/transactions")
def transactions():
    if "user" not in session: return redirect("/")
    
    customers = load_data()
    user = customers.get(session["user"])
    
    # If user doesn't exist (server reset), clear session and logout
    if not user:
        session.clear()
        return redirect("/")

    # Pass full transaction list
    return render_template("transactions.html", user=user, transactions=user.get("transactions", []))

# 3. CARDS PAGE
@app.route("/cards")
def cards():
    if "user" not in session: return redirect("/")
    
    customers = load_data()
    user = customers.get(session["user"])
    
    # If user doesn't exist (server reset), clear session and logout
    if not user:
        session.clear()
        return redirect("/")

    return render_template("cards.html", user=user)

# 4. ANALYTICS PAGE
@app.route("/analytics")
def analytics():
    if "user" not in session: return redirect("/")
    
    customers = load_data()
    user = customers.get(session["user"])
    
    # If user doesn't exist (server reset), clear session and logout
    if not user:
        session.clear()
        return redirect("/")

    txns = user.get("transactions", [])

    # Calculate Totals
    total_in = sum(t["amount"] for t in txns if t["type"] == "Credit")
    total_out = sum(t["amount"] for t in txns if t["type"] == "Debit")

    return render_template("analytics.html", user=user, total_in=total_in, total_out=total_out)

# 5. SETTINGS PAGE
@app.route("/settings")
def settings():
    if "user" not in session: return redirect("/")
    
    customers = load_data()
    user = customers.get(session["user"])
    
    # If user doesn't exist (server reset), clear session and logout
    if not user:
        session.clear()
        return redirect("/")

    return render_template("settings.html", user=user)

# --- ACTION ROUTES (Processing Money) ---

@app.route("/deposit", methods=["POST"])
def deposit():
    if "user" not in session: return redirect("/")
    try:
        amount = int(request.form["amount"])
    except ValueError: return redirect("/dashboard")

    customers = load_data()
    user = customers.get(session["user"])
    
    if not user:
        session.clear()
        return redirect("/")

    if amount > 0:
        user["balance"] += amount
        txn = {
            "date": datetime.now().strftime('%d-%m-%Y %H:%M'),
            "desc": "Cash Deposit",
            "type": "Credit",
            "amount": amount,
            "ref": generate_ref(),
            "status": "Success"
        }
        user["transactions"].insert(0, txn)
        save_data(customers)

    return redirect("/dashboard")

@app.route("/withdraw", methods=["POST"])
def withdraw():
    if "user" not in session: return redirect("/")
    try:
        amount = int(request.form["amount"])
    except ValueError: return redirect("/dashboard")

    customers = load_data()
    user = customers.get(session["user"])
    
    if not user:
        session.clear()
        return redirect("/")

    if amount > 0 and amount <= user["balance"]:
        user["balance"] -= amount
        txn = {
            "date": datetime.now().strftime('%d-%m-%Y %H:%M'),
            "desc": "Cash Withdrawal",
            "type": "Debit",
            "amount": amount,
            "ref": generate_ref(),
            "status": "Success"
        }
        user["transactions"].insert(0, txn)
        save_data(customers)

    return redirect("/dashboard")

@app.route("/transfer", methods=["POST"])
def transfer():
    if "user" not in session: return redirect("/")
    
    try:
        amount = float(request.form["amount"])
        recipient_acc = request.form["account_number"].strip()
    except ValueError: return redirect("/dashboard")

    customers = load_data()
    sender_username = session["user"]
    
    # --- FIX START: Check if user still exists after server restart ---
    sender = customers.get(sender_username)
    if not sender:
        session.clear() # Clear the old cookie
        flash("Session expired or server reset. Please login again.", "error")
        return redirect("/")
    # --- FIX END ---

    # 1. Check Daily Limit & Balance
    allowed, limit = check_daily_limit(sender, amount)
    if not allowed or sender["balance"] < amount:
        flash("Insufficient funds or daily limit exceeded!", "error") 
        return redirect("/dashboard") 

    # 2. Find Recipient
    recipient = None
    recipient_username = None
    
    for uname, data in customers.items():
        if data["account_no"] == recipient_acc:
            recipient = data
            recipient_username = uname
            break
    
    # 3. Validation Checks
    if not recipient:
        flash("Recipient account not found!", "error") 
        return redirect("/dashboard") 
    
    if recipient_username == sender_username:
        flash("You cannot transfer money to yourself!", "error") 
        return redirect("/dashboard") 

    # 4. Execute Transfer
    ref = generate_ref()
    sender["balance"] -= amount
    sender["daily_used"] += amount
    recipient["balance"] += amount

    # Log for Sender
    sender["transactions"].insert(0, {
        "date": datetime.now().strftime('%d-%m-%Y %H:%M'),
        "desc": f"Transfer to {recipient['name']}",
        "type": "Debit", 
        "amount": amount, 
        "ref": ref, 
        "status": "Success"
    })

    # Log for Recipient
    recipient["transactions"].insert(0, {
        "date": datetime.now().strftime('%d-%m-%Y %H:%M'),
        "desc": f"Received from {sender['name']}",
        "type": "Credit", 
        "amount": amount, 
        "ref": ref, 
        "status": "Success"
    })

    save_data(customers)
    return redirect(f"/receipt/{ref}")

@app.route("/pay_bills", methods=["POST"])
def pay_bills():
    # You can hook this up to the dashboard form later
    return redirect("/dashboard")

@app.route("/receipt/<ref>")
def receipt(ref):
    if "user" not in session: return redirect("/")
    customers = load_data()
    user = customers.get(session["user"])
    
    if not user:
        session.clear()
        return redirect("/")
    
    # Find the specific transaction
    txn = next((t for t in user["transactions"] if t["ref"] == ref), None)
    if not txn: return redirect("/dashboard")
    
    return render_template("receipt.html", t=txn, user=user)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)