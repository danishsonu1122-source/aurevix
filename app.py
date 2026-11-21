import os
import sqlite3
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "aurevix.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this-secret-before-deploying")

ROLE_PAGES = {
    "customer": ["Home", "QR Menu", "Cart", "My Orders", "Live Tracking", "Rewards Wallet", "Games & Offers", "Profile"],
    "owner": ["Dashboard", "Orders", "Menu Management", "Staff & Roles", "Tables", "Rewards & Games", "Subscription", "Cafe Settings"],
    "chef": ["Kitchen Dashboard", "New Orders", "Preparing Orders", "Ready Orders", "Completed Orders"],
    "waiter": ["Waiter Dashboard", "Ready to Serve", "Active Orders", "Served Orders", "Tables Overview"],
    "admin": ["Admin Dashboard", "All Cafes", "Subscription Plans", "Payments", "Platform Settings"]
}
ROLE_TITLES = {"customer":"Customer Portal","owner":"Cafe Owner","chef":"Chef Workspace","waiter":"Waiter Workspace","admin":"Super Admin"}

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL, role TEXT NOT NULL, cafe_id INTEGER, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS cafes(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, owner_id INTEGER,
      plan TEXT DEFAULT 'Starter', status TEXT DEFAULT 'Active'
    );
    CREATE TABLE IF NOT EXISTS menu_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT, cafe_id INTEGER NOT NULL, name TEXT NOT NULL,
      category TEXT NOT NULL, price INTEGER NOT NULL, emoji TEXT DEFAULT '🍽️',
      available INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS orders(
      id INTEGER PRIMARY KEY AUTOINCREMENT, cafe_id INTEGER NOT NULL, customer_id INTEGER NOT NULL,
      table_name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'New', total INTEGER NOT NULL,
      created_at TEXT NOT NULL, prep_minutes INTEGER DEFAULT 20
    );
    CREATE TABLE IF NOT EXISTS order_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, menu_item_id INTEGER,
      item_name TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS rewards(
      user_id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 120
    );
    """)
    if not con.execute("SELECT id FROM cafes LIMIT 1").fetchone():
        con.execute("INSERT INTO cafes(name,plan,status) VALUES(?,?,?)", ("Aurevix Demo Cafe","Growth","Active"))
        cafe_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        demo_users = [
            ("Demo Customer","customer@demo.com","customer",cafe_id),
            ("Cafe Owner","owner@demo.com","owner",cafe_id),
            ("Kitchen Chef","chef@demo.com","chef",cafe_id),
            ("Cafe Waiter","waiter@demo.com","waiter",cafe_id),
            ("Platform Admin","admin@demo.com","admin",None),
        ]
        for name,email,role,cid in demo_users:
            con.execute("INSERT INTO users(name,email,password_hash,role,cafe_id,created_at) VALUES(?,?,?,?,?,?)",
                        (name,email,generate_password_hash("demo1234"),role,cid,datetime.now().isoformat(timespec="minutes")))
        con.execute("UPDATE cafes SET owner_id=(SELECT id FROM users WHERE role='owner' LIMIT 1)")
        items = [
            ("Classic Beef Burger","Burgers",950,"🍔"),("Creamy Alfredo Pasta","Pasta",1250,"🍝"),
            ("Crispy Chicken Wrap","Wraps",780,"🌯"),("Loaded Fries","Sides",550,"🍟"),
            ("Iced Caramel Latte","Drinks",480,"🥤"),("Chocolate Brownie","Desserts",420,"🍫")
        ]
        for n,c,p,e in items:
            con.execute("INSERT INTO menu_items(cafe_id,name,category,price,emoji) VALUES(?,?,?,?,?)",(cafe_id,n,c,p,e))
        customer_id = con.execute("SELECT id FROM users WHERE role='customer'").fetchone()["id"]
        con.execute("INSERT OR IGNORE INTO rewards(user_id,coins) VALUES(?,120)",(customer_id,))
    con.commit()
    con.close()

def current_user():
    if "user_id" not in session:
        return None
    con=db()
    user=con.execute("SELECT * FROM users WHERE id=?",(session["user_id"],)).fetchone()
    con.close()
    return user

def login_required(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return fn(*args,**kwargs)
    return wrapped

def roles_required(*roles):
    def deco(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args,**kwargs):
            u=current_user()
            if u["role"] not in roles:
                abort(403)
            return fn(*args,**kwargs)
        return wrapped
    return deco

@app.context_processor
def inject():
    u=current_user()
    return {"user":u,"role_pages":ROLE_PAGES,"role_titles":ROLE_TITLES}

@app.route("/")
def index():
    if current_user():
        return redirect(url_for("workspace", page=ROLE_PAGES[current_user()["role"]][0]))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        con=db(); u=con.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone(); con.close()
        if u and check_password_hash(u["password_hash"],password):
            session.clear(); session["user_id"]=u["id"]
            return redirect(url_for("workspace",page=ROLE_PAGES[u["role"]][0]))
        flash("Email or password is incorrect.","error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/workspace/<path:page>", methods=["GET","POST"])
@login_required
def workspace(page):
    u=current_user(); role=u["role"]
    if page not in ROLE_PAGES[role]:
        abort(403)
    con=db()
    cafe_id=u["cafe_id"]
    if role=="admin":
        orders=con.execute("""SELECT o.*,u.name customer_name FROM orders o JOIN users u ON u.id=o.customer_id ORDER BY o.id DESC""").fetchall()
        cafes=con.execute("SELECT c.*,u.email owner_email FROM cafes c LEFT JOIN users u ON u.id=c.owner_id ORDER BY c.id").fetchall()
        items=[]; staff=[]
    else:
        orders=con.execute("""SELECT o.*,u.name customer_name FROM orders o JOIN users u ON u.id=o.customer_id
                              WHERE o.cafe_id=? ORDER BY o.id DESC""",(cafe_id,)).fetchall()
        items=con.execute("SELECT * FROM menu_items WHERE cafe_id=? ORDER BY category,name",(cafe_id,)).fetchall()
        staff=con.execute("SELECT name,email,role FROM users WHERE cafe_id=? AND role IN ('chef','waiter')",(cafe_id,)).fetchall()
        cafes=[]
    rewards=con.execute("SELECT coins FROM rewards WHERE user_id=?",(u["id"],)).fetchone()
    coins=rewards["coins"] if rewards else 0
    if request.method=="POST":
        action=request.form.get("action")
        if action=="place_order" and role=="customer":
            ids=request.form.getlist("item_id")
            qtys=request.form.getlist("quantity")
            chosen=[]; total=0
            for iid,q in zip(ids,qtys):
                try: q=max(0,min(20,int(q)))
                except: q=0
                item=con.execute("SELECT * FROM menu_items WHERE id=? AND cafe_id=? AND available=1",(iid,cafe_id)).fetchone()
                if item and q:
                    chosen.append((item,q)); total+=item["price"]*q
            if chosen:
                table_name=request.form.get("table_name","Table 01")
                con.execute("INSERT INTO orders(cafe_id,customer_id,table_name,status,total,created_at) VALUES(?,?,?,?,?,?)",
                            (cafe_id,u["id"],table_name,"New",total,datetime.now().strftime("%Y-%m-%d %H:%M")))
                oid=con.execute("SELECT last_insert_rowid()").fetchone()[0]
                for item,q in chosen:
                    con.execute("INSERT INTO order_items(order_id,menu_item_id,item_name,quantity,unit_price) VALUES(?,?,?,?,?)",
                                (oid,item["id"],item["name"],q,item["price"]))
                con.commit(); flash(f"Order #{oid} placed successfully.","success")
                con.close(); return redirect(url_for("workspace",page="My Orders"))
            flash("Choose at least one available menu item.","error")
        elif action=="update_status" and role in ("chef","waiter"):
            oid=request.form.get("order_id"); status=request.form.get("status")
            allowed={"chef":{"New":"Preparing","Preparing":"Ready"},"waiter":{"Ready":"Served"}}
            order=con.execute("SELECT * FROM orders WHERE id=? AND cafe_id=?",(oid,cafe_id)).fetchone()
            if order and allowed.get(role,{}).get(order["status"])==status:
                prep=int(request.form.get("prep_minutes",20) or 20)
                con.execute("UPDATE orders SET status=?,prep_minutes=? WHERE id=?",(status,prep,oid))
                if status=="Served":
                    con.execute("INSERT INTO rewards(user_id,coins) VALUES(?,20) ON CONFLICT(user_id) DO UPDATE SET coins=coins+20",(order["customer_id"],))
                con.commit(); flash("Order status updated.","success")
            else: flash("This order action is not allowed.","error")
        elif action=="add_menu" and role=="owner":
            name=request.form.get("name","").strip(); cat=request.form.get("category","General").strip()
            try: price=int(request.form.get("price","0"))
            except: price=0
            if name and 0<price<10000000:
                con.execute("INSERT INTO menu_items(cafe_id,name,category,price,emoji) VALUES(?,?,?,?,?)",(cafe_id,name,cat,price,request.form.get("emoji","🍽️")))
                con.commit(); flash("Menu item added.","success")
            else: flash("Enter a name and valid price.","error")
        elif action=="toggle_menu" and role=="owner":
            iid=request.form.get("item_id")
            con.execute("UPDATE menu_items SET available=1-available WHERE id=? AND cafe_id=?",(iid,cafe_id)); con.commit()
            flash("Menu availability updated.","success")
        elif action=="create_staff" and role=="owner":
            name=request.form.get("name","").strip(); email=request.form.get("email","").strip().lower()
            staff_role=request.form.get("staff_role")
            if name and email and staff_role in ("chef","waiter"):
                try:
                    con.execute("INSERT INTO users(name,email,password_hash,role,cafe_id,created_at) VALUES(?,?,?,?,?,?)",
                                (name,email,generate_password_hash("ChangeMe123!"),staff_role,cafe_id,datetime.now().isoformat(timespec="minutes")))
                    con.commit(); flash("Staff account created. Temporary password: ChangeMe123! Change it before production.","success")
                except sqlite3.IntegrityError: flash("That email is already registered.","error")
            else: flash("Enter valid staff details.","error")
        elif action=="redeem" and role=="customer":
            cost=int(request.form.get("cost",0))
            reward=con.execute("SELECT coins FROM rewards WHERE user_id=?",(u["id"],)).fetchone()
            if reward and reward["coins"]>=cost and cost>0:
                con.execute("UPDATE rewards SET coins=coins-? WHERE user_id=?",(cost,u["id"])); con.commit(); flash("Reward redeemed in demo.","success")
            else: flash("Not enough coins.","error")
        con.close()
        return redirect(url_for("workspace",page=page))
    # Fetch line items for all orders
    order_data=[]
    for o in orders:
        if role=="customer" and o["customer_id"]!=u["id"]: continue
        lines=con.execute("SELECT * FROM order_items WHERE order_id=?",(o["id"],)).fetchall()
        order_data.append({"row":o,"lines":lines})
    if role=="customer":
        items=con.execute("SELECT * FROM menu_items WHERE cafe_id=? AND available=1 ORDER BY category,name",(cafe_id,)).fetchall()
    cafe=con.execute("SELECT * FROM cafes WHERE id=?",(cafe_id,)).fetchone() if cafe_id else None
    con.close()
    return render_template("workspace.html", page=page, orders=order_data, items=items, staff=staff,
                           cafes=cafes, coins=coins, cafe=cafe, role=role)

@app.errorhandler(403)
def forbidden(e):
    return render_template("message.html",title="Access restricted",message="This page is not available for your account role."),403

@app.errorhandler(404)
def missing(e):
    return render_template("message.html",title="Page not found",message="The page you requested does not exist."),404

if __name__=="__main__":
    init_db()
    app.run(debug=True,host="127.0.0.1",port=5000)
