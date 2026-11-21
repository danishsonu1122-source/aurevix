import os, sqlite3, secrets, io
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(BASE, 'aurevix.db'))
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'development-key-change-before-deploying')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1', PERMANENT_SESSION_LIFETIME=timedelta(hours=12), MAX_CONTENT_LENGTH=2*1024*1024)

NAV = {
 'customer':['Cafe Menu','My Orders','Live Tracking','Rewards Wallet','Games & Offers','My Profile'],
 'owner':['Dashboard','Orders','Menu Management','Staff & Roles','Tables & QR','Rewards & Games','Reports','Subscription','Cafe Settings'],
 'chef':['Kitchen Dashboard','New Orders','Preparing Orders','Ready Orders','Order History'],
 'waiter':['Waiter Dashboard','Ready to Serve','Active Orders','Served Orders','Tables Overview'],
 'admin':['Admin Dashboard','All Cafes','Subscription Plans','Payments','Platform Settings']}
TITLES={'customer':'Customer Portal','owner':'Cafe Owner','chef':'Chef Workspace','waiter':'Waiter Workspace','admin':'Super Admin'}
PLANS={'Starter':(0, 'Digital menu and basic order management'), 'Growth':(2499,'QR ordering, kitchen and waiter workflow'), 'Pro':(4999,'Reports, loyalty and advanced cafe tools'), 'Enterprise':(0,'Custom multi-branch solution')}
STATUSES=['New','Accepted','Preparing','Ready','Served','Cancelled']

def db():
 c=sqlite3.connect(DB_PATH, timeout=20); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA journal_mode=WAL'); return c

def now(): return datetime.now().isoformat(timespec='seconds')
def money(n): return f"Rs {int(n):,}"
app.jinja_env.filters['money']=money

def init_db():
 c=db(); c.executescript('''
 CREATE TABLE IF NOT EXISTS cafes(id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL, owner_id INTEGER, plan TEXT NOT NULL DEFAULT 'Starter', status TEXT NOT NULL DEFAULT 'Active', phone TEXT DEFAULT '', address TEXT DEFAULT '', currency TEXT DEFAULT 'PKR', created_at TEXT NOT NULL, qr_token TEXT UNIQUE NOT NULL);
 CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, cafe_id INTEGER, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, FOREIGN KEY(cafe_id) REFERENCES cafes(id));
 CREATE TABLE IF NOT EXISTS cafe_tables(id INTEGER PRIMARY KEY, cafe_id INTEGER NOT NULL, name TEXT NOT NULL, token TEXT UNIQUE NOT NULL, active INTEGER DEFAULT 1, UNIQUE(cafe_id,name), FOREIGN KEY(cafe_id) REFERENCES cafes(id));
 CREATE TABLE IF NOT EXISTS menu_items(id INTEGER PRIMARY KEY, cafe_id INTEGER NOT NULL, name TEXT NOT NULL, description TEXT DEFAULT '', category TEXT NOT NULL, price INTEGER NOT NULL, emoji TEXT DEFAULT '🍽️', available INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0, FOREIGN KEY(cafe_id) REFERENCES cafes(id));
 CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, cafe_id INTEGER NOT NULL, customer_id INTEGER NOT NULL, table_id INTEGER, table_name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'New', total INTEGER NOT NULL, payment_status TEXT NOT NULL DEFAULT 'Unpaid', payment_method TEXT DEFAULT 'Pay at counter', prep_minutes INTEGER DEFAULT 20, note TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(cafe_id) REFERENCES cafes(id), FOREIGN KEY(customer_id) REFERENCES users(id), FOREIGN KEY(table_id) REFERENCES cafe_tables(id));
 CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, menu_item_id INTEGER, item_name TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price INTEGER NOT NULL, FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE);
 CREATE TABLE IF NOT EXISTS rewards(user_id INTEGER PRIMARY KEY, coins INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(user_id) REFERENCES users(id));
 CREATE TABLE IF NOT EXISTS reward_rules(cafe_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 1, coins_per_order INTEGER DEFAULT 20, daily_cap INTEGER DEFAULT 100, redeem_cost INTEGER DEFAULT 60, discount_percent INTEGER DEFAULT 10, FOREIGN KEY(cafe_id) REFERENCES cafes(id));
 CREATE TABLE IF NOT EXISTS reward_ledger(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, cafe_id INTEGER NOT NULL, delta INTEGER NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS game_plays(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, cafe_id INTEGER NOT NULL, game TEXT NOT NULL, reward INTEGER NOT NULL, played_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS subscriptions(id INTEGER PRIMARY KEY, cafe_id INTEGER NOT NULL, plan TEXT NOT NULL, amount INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'Pending', starts_at TEXT, ends_at TEXT, created_at TEXT NOT NULL, FOREIGN KEY(cafe_id) REFERENCES cafes(id));
 CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, cafe_id INTEGER NOT NULL, subscription_id INTEGER, amount INTEGER NOT NULL, method TEXT NOT NULL, reference TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'Pending', created_at TEXT NOT NULL, FOREIGN KEY(cafe_id) REFERENCES cafes(id));
 CREATE TABLE IF NOT EXISTS settings(cafe_id INTEGER NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(cafe_id,key));
 ''')
 if not c.execute('SELECT id FROM cafes LIMIT 1').fetchone():
  slug='demo-cafe'; token=secrets.token_urlsafe(18)
  c.execute('INSERT INTO cafes(name,slug,plan,status,created_at,qr_token) VALUES(?,?,?,?,?,?)',('AUREVIX Demo Cafe',slug,'Growth','Active',now(),token)); cid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
  demo=[('Demo Customer','customer@demo.com','customer',cid),('Cafe Owner','owner@demo.com','owner',cid),('Kitchen Chef','chef@demo.com','chef',cid),('Cafe Waiter','waiter@demo.com','waiter',cid),('Platform Admin','admin@demo.com','admin',None)]
  for n,e,r,fc in demo: c.execute('INSERT INTO users(cafe_id,name,email,password_hash,role,created_at) VALUES(?,?,?,?,?,?)',(fc,n,e,generate_password_hash('demo1234'),r,now()))
  owner=c.execute("SELECT id FROM users WHERE email='owner@demo.com'").fetchone()['id']; c.execute('UPDATE cafes SET owner_id=? WHERE id=?',(owner,cid))
  for i in range(1,7): c.execute('INSERT INTO cafe_tables(cafe_id,name,token) VALUES(?,?,?)',(cid,f'Table {i:02}',secrets.token_urlsafe(16)))
  for n,cat,p,e in [('Classic Beef Burger','Burgers',950,'🍔'),('Creamy Alfredo Pasta','Pasta',1250,'🍝'),('Crispy Chicken Wrap','Wraps',780,'🌯'),('Loaded Fries','Sides',550,'🍟'),('Iced Caramel Latte','Drinks',480,'🥤'),('Chocolate Brownie','Desserts',420,'🍫')]: c.execute('INSERT INTO menu_items(cafe_id,name,category,price,emoji) VALUES(?,?,?,?,?)',(cid,n,cat,p,e))
  cust=c.execute("SELECT id FROM users WHERE role='customer'").fetchone()['id']; c.execute('INSERT INTO rewards(user_id,coins) VALUES(?,120)',(cust,)); c.execute('INSERT INTO reward_rules(cafe_id) VALUES(?)',(cid,))
 c.commit(); c.close()

def get_user():
 if not session.get('uid'): return None
 c=db(); u=c.execute('SELECT * FROM users WHERE id=? AND active=1',(session['uid'],)).fetchone(); c.close(); return u

def login_required(fn):
 @wraps(fn)
 def w(*a,**kw):
  if not get_user(): return redirect(url_for('login'))
  return fn(*a,**kw)
 return w

def roles(*allowed):
 def deco(fn):
  @wraps(fn)
  @login_required
  def w(*a,**kw):
   if get_user()['role'] not in allowed: abort(403)
   return fn(*a,**kw)
  return w
 return deco

def owner_cafe(u):
 if u['role']=='admin': return None
 return u['cafe_id']

@app.context_processor
def ctx():
 u=get_user(); return {'user':u,'nav':NAV,'titles':TITLES,'plans':PLANS,'now_iso':now()}

@app.route('/')
def index():
 u=get_user()
 if u: return redirect(url_for('workspace',page=NAV[u['role']][0]))
 return redirect(url_for('login'))

@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  email=request.form.get('email','').strip().lower(); pw=request.form.get('password','')
  c=db(); u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); c.close()
  if u and u['active'] and check_password_hash(u['password_hash'],pw):
   session.clear(); session['uid']=u['id']; session.permanent=True; return redirect(url_for('workspace',page=NAV[u['role']][0]))
  flash('Email ya password ghalat hai, dobara check karein.','error')
 return render_template('login.html')

@app.route('/logout',methods=['POST'])
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/register',methods=['GET','POST'])
def register():
 if request.method=='POST':
  name=request.form.get('owner_name','').strip(); cafe=request.form.get('cafe_name','').strip(); email=request.form.get('email','').strip().lower(); pw=request.form.get('password','')
  slug=''.join(ch.lower() if ch.isalnum() else '-' for ch in cafe).strip('-')[:35] or 'cafe'; slug += '-'+secrets.token_hex(3)
  if not all([name,cafe,email]) or len(pw)<10: flash('Tamam fields bharein aur password kam az kam 10 characters ka rakhein.','error')
  else:
   c=db()
   try:
    c.execute('INSERT INTO cafes(name,slug,plan,status,created_at,qr_token) VALUES(?,?,?,?,?,?)',(cafe,slug,'Starter','Active',now(),secrets.token_urlsafe(18))); cid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.execute('INSERT INTO users(cafe_id,name,email,password_hash,role,created_at) VALUES(?,?,?,?,?,?)',(cid,name,email,generate_password_hash(pw),'owner',now())); uid=c.execute('SELECT last_insert_rowid()').fetchone()[0]; c.execute('UPDATE cafes SET owner_id=? WHERE id=?',(uid,cid)); c.execute('INSERT INTO reward_rules(cafe_id) VALUES(?)',(cid,))
    for i in range(1,6): c.execute('INSERT INTO cafe_tables(cafe_id,name,token) VALUES(?,?,?)',(cid,f'Table {i:02}',secrets.token_urlsafe(16)))
    c.commit(); session['uid']=uid; session.permanent=True; c.close(); return redirect(url_for('workspace',page='Dashboard'))
   except sqlite3.IntegrityError: c.rollback(); c.close(); flash('Ye email pehle se registered hai.','error')
 return render_template('register.html')

@app.route('/c/<slug>/table/<token>',methods=['GET','POST'])
def public_menu(slug,token):
 c=db(); cafe=c.execute("SELECT * FROM cafes WHERE slug=? AND status='Active'",(slug,)).fetchone(); table=c.execute('SELECT * FROM cafe_tables WHERE token=? AND active=1',(token,)).fetchone() if cafe else None
 if not cafe or not table or table['cafe_id']!=cafe['id']: c.close(); abort(404)
 items=c.execute('SELECT * FROM menu_items WHERE cafe_id=? AND available=1 ORDER BY category,name',(cafe['id'],)).fetchall()
 if request.method=='POST':
  name=request.form.get('customer_name','Guest').strip()[:80] or 'Guest'; phone=request.form.get('phone','').strip()[:30]; email=f"guest-{secrets.token_hex(8)}@guest.aurevix.local"; c.execute('INSERT INTO users(cafe_id,name,email,password_hash,role,created_at) VALUES(?,?,?,?,?,?)',(cafe['id'],name,email,generate_password_hash(secrets.token_urlsafe(24)),'customer',now())); uid=c.execute('SELECT last_insert_rowid()').fetchone()['last_insert_rowid()']
  ids=request.form.getlist('item_id'); qtys=request.form.getlist('quantity'); chosen=[]; total=0
  for iid,qv in zip(ids,qtys):
   try:q=max(0,min(30,int(qv)))
   except:q=0
   it=c.execute('SELECT * FROM menu_items WHERE id=? AND cafe_id=? AND available=1',(iid,cafe['id'])).fetchone()
   if it and q: chosen.append((it,q)); total+=it['price']*q
  if not chosen: c.close(); flash('Kam az kam aik item select karein.','error'); return redirect(request.url)
  note=request.form.get('note','').strip()[:300]
  c.execute('INSERT INTO orders(cafe_id,customer_id,table_id,table_name,total,note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(cafe['id'],uid,table['id'],table['name'],total,note,now(),now())); oid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
  for it,q in chosen:c.execute('INSERT INTO order_items(order_id,menu_item_id,item_name,quantity,unit_price) VALUES(?,?,?,?,?)',(oid,it['id'],it['name'],q,it['price']))
  c.execute('INSERT OR IGNORE INTO rewards(user_id,coins) VALUES(?,0)',(uid,)); c.commit(); c.close(); session['guest_order']=oid; session['guest_cafe']=cafe['id']; return redirect(url_for('track_order',oid=oid,token=token))
 c.close(); return render_template('public_menu.html',cafe=cafe,table=table,items=items)

@app.route('/track/<int:oid>/<token>')
def track_order(oid,token):
 c=db(); t=c.execute('SELECT t.*,ca.name cafe_name,ca.slug FROM cafe_tables t JOIN cafes ca ON ca.id=t.cafe_id WHERE t.token=?',(token,)).fetchone(); o=c.execute('SELECT * FROM orders WHERE id=? AND table_id=?',(oid,t['id'] if t else -1)).fetchone(); lines=c.execute('SELECT * FROM order_items WHERE order_id=?',(oid,)).fetchall() if o else []; c.close()
 if not o: abort(404)
 return render_template('tracking.html',order=o,lines=lines,table=t)

@app.route('/api/order/<int:oid>/<token>')
def order_api(oid,token):
 c=db(); o=c.execute('SELECT o.status,o.prep_minutes,o.updated_at,o.payment_status FROM orders o JOIN cafe_tables t ON t.id=o.table_id WHERE o.id=? AND t.token=?',(oid,token)).fetchone(); c.close()
 if not o: return jsonify({'error':'not found'}),404
 return jsonify(dict(o))

@app.route('/workspace/<path:page>',methods=['GET','POST'])
@login_required
def workspace(page):
 u=get_user(); role=u['role']
 if page not in NAV[role]: abort(403)
 c=db(); cid=u['cafe_id']; is_admin=role=='admin'
 if request.method=='POST':
  action=request.form.get('action','')
  try:
   if action=='add_menu' and role=='owner':
    name=request.form.get('name','').strip(); cat=request.form.get('category','General').strip() or 'General'; desc=request.form.get('description','').strip()[:250]; price=int(request.form.get('price','0')); emoji=request.form.get('emoji','🍽️')[:8]
    if not name or price<1: raise ValueError()
    c.execute('INSERT INTO menu_items(cafe_id,name,description,category,price,emoji) VALUES(?,?,?,?,?,?)',(cid,name,desc,cat,price,emoji)); flash('Menu item add ho gaya.','success')
   elif action=='edit_menu' and role=='owner':
    iid=int(request.form['item_id']); name=request.form['name'].strip(); price=int(request.form['price']); cat=request.form['category'].strip(); desc=request.form.get('description','').strip()[:250]
    c.execute('UPDATE menu_items SET name=?,price=?,category=?,description=? WHERE id=? AND cafe_id=?',(name,price,cat,desc,iid,cid)); flash('Menu item update ho gaya.','success')
   elif action=='toggle_menu' and role=='owner': c.execute('UPDATE menu_items SET available=1-available WHERE id=? AND cafe_id=?',(int(request.form['item_id']),cid)); flash('Availability update ho gayi.','success')
   elif action=='create_staff' and role=='owner':
    nm=request.form['name'].strip(); em=request.form['email'].strip().lower(); rr=request.form['staff_role']; pw=request.form.get('password','')
    if rr not in ('chef','waiter') or len(pw)<10: raise ValueError()
    c.execute('INSERT INTO users(cafe_id,name,email,password_hash,role,created_at) VALUES(?,?,?,?,?,?)',(cid,nm,em,generate_password_hash(pw),rr,now())); flash('Staff account create ho gaya.','success')
   elif action=='toggle_staff' and role=='owner': c.execute("UPDATE users SET active=1-active WHERE id=? AND cafe_id=? AND role IN ('chef','waiter')",(int(request.form['staff_id']),cid)); flash('Staff access update ho gaya.','success')
   elif action=='add_table' and role=='owner':
    nm=request.form['name'].strip(); c.execute('INSERT INTO cafe_tables(cafe_id,name,token) VALUES(?,?,?)',(cid,nm,secrets.token_urlsafe(18))); flash('Table aur QR link create ho gaya.','success')
   elif action=='toggle_table' and role=='owner': c.execute('UPDATE cafe_tables SET active=1-active WHERE id=? AND cafe_id=?',(int(request.form['table_id']),cid)); flash('Table status update ho gaya.','success')
   elif action=='update_order' and role in ('chef','waiter','owner'):
    oid=int(request.form['order_id']); status=request.form['status']; prep=max(1,min(180,int(request.form.get('prep_minutes',20))))
    o=c.execute('SELECT * FROM orders WHERE id=? AND cafe_id=?',(oid,cid)).fetchone()
    allowed={'chef':{'New':'Accepted','Accepted':'Preparing','Preparing':'Ready'},'waiter':{'Ready':'Served'},'owner':{'New':'Cancelled','Accepted':'Cancelled','Preparing':'Cancelled','Ready':'Cancelled','Served':'Served'}}
    if not o or allowed.get(role,{}).get(o['status'])!=status: abort(403)
    c.execute('UPDATE orders SET status=?,prep_minutes=?,updated_at=? WHERE id=?',(status,prep,now(),oid))
    if status=='Served': award_coins(c,o['customer_id'],cid)
    flash(f'Order #{oid}: {status}.','success')
   elif action=='payment_status' and role in ('owner','waiter'):
    oid=int(request.form['order_id']); ps=request.form['payment_status']
    if ps not in ('Paid','Unpaid','Refunded'): raise ValueError()
    c.execute('UPDATE orders SET payment_status=?,updated_at=? WHERE id=? AND cafe_id=?',(ps,now(),oid,cid)); flash('Payment status update ho gaya.','success')
   elif action=='save_rewards' and role=='owner':
    en=1 if request.form.get('enabled') else 0; coins=max(0,min(100,int(request.form['coins_per_order']))); cap=max(0,min(1000,int(request.form['daily_cap']))); cost=max(1,min(10000,int(request.form['redeem_cost']))); disc=max(1,min(50,int(request.form['discount_percent'])))
    c.execute('INSERT INTO reward_rules(cafe_id,enabled,coins_per_order,daily_cap,redeem_cost,discount_percent) VALUES(?,?,?,?,?,?) ON CONFLICT(cafe_id) DO UPDATE SET enabled=excluded.enabled,coins_per_order=excluded.coins_per_order,daily_cap=excluded.daily_cap,redeem_cost=excluded.redeem_cost,discount_percent=excluded.discount_percent',(cid,en,coins,cap,cost,disc)); flash('Rewards settings save ho gayi.','success')
   elif action=='play_game' and role=='customer':
    rules=c.execute('SELECT * FROM reward_rules WHERE cafe_id=?',(cid,)).fetchone()
    if not rules or not rules['enabled']: flash('Is cafe mein games filhal band hain.','error')
    else:
     today=datetime.now().strftime('%Y-%m-%d'); played=c.execute('SELECT COUNT(*) n FROM game_plays WHERE user_id=? AND cafe_id=? AND substr(played_at,1,10)=?',(u['id'],cid,today)).fetchone()['n']
     if played>=3: flash('Aaj ke 3 game attempts use ho chuke hain.','error')
     else:
      import random
      reward=random.choice([0,0,2,5,10]); c.execute('INSERT INTO game_plays(user_id,cafe_id,game,reward,played_at) VALUES(?,?,?,?,?)',(u['id'],cid,request.form.get('game','Lucky Box')[:30],reward,now()))
      if reward: add_coins(c,u['id'],cid,reward,'Game reward')
      flash(f'Game complete! Aap ne {reward} coins jeete.' if reward else 'Is dafa coins nahi mile—dobara kal try karein.', 'success')
   elif action=='redeem' and role=='customer':
    rules=c.execute('SELECT * FROM reward_rules WHERE cafe_id=?',(cid,)).fetchone(); cost=rules['redeem_cost'] if rules else 60; bal=c.execute('SELECT coins FROM rewards WHERE user_id=?',(u['id'],)).fetchone(); bal=bal['coins'] if bal else 0
    if bal>=cost:
     c.execute('UPDATE rewards SET coins=coins-? WHERE user_id=?',(cost,u['id'])); c.execute('INSERT INTO reward_ledger(user_id,cafe_id,delta,reason,created_at) VALUES(?,?,?,?,?)',(u['id'],cid,-cost,'Redeemed discount',now())); flash(f'{cost} coins redeem ho gaye. Discount counter par show karein.','success')
    else: flash('Aap ke coins kam hain.','error')
   elif action=='cafe_settings' and role=='owner':
    nm=request.form['name'].strip(); phone=request.form.get('phone','').strip(); address=request.form.get('address','').strip(); c.execute('UPDATE cafes SET name=?,phone=?,address=? WHERE id=?',(nm,phone,address,cid)); flash('Cafe details save ho gayi.','success')
   elif action=='request_plan' and role=='owner':
    plan=request.form.get('plan'); method=request.form.get('method','Bank transfer'); ref=request.form.get('reference','').strip()[:80]
    if plan not in PLANS: raise ValueError()
    amount=PLANS[plan][0]; c.execute('INSERT INTO subscriptions(cafe_id,plan,amount,status,created_at) VALUES(?,?,?,?,?)',(cid,plan,amount,'Pending',now())); sid=c.execute('SELECT last_insert_rowid()').fetchone()[0]; c.execute('INSERT INTO payments(cafe_id,subscription_id,amount,method,reference,status,created_at) VALUES(?,?,?,?,?,?,?)',(cid,sid,amount,method,ref,'Pending',now())); flash('Plan request submit ho gayi. Admin payment verify karega.','success')
   elif action=='admin_cafe' and role=='admin':
    cafe_id=int(request.form['cafe_id']); status=request.form['status']; plan=request.form['plan']
    if status not in ('Active','Suspended') or plan not in PLANS: raise ValueError()
    c.execute('UPDATE cafes SET status=?,plan=? WHERE id=?',(status,plan,cafe_id)); flash('Cafe account update ho gaya.','success')
   elif action=='payment_review' and role=='admin':
    pid=int(request.form['payment_id']); status=request.form['status']
    if status not in ('Paid','Rejected','Pending'): raise ValueError()
    p=c.execute('SELECT * FROM payments WHERE id=?',(pid,)).fetchone(); c.execute('UPDATE payments SET status=? WHERE id=?',(status,pid))
    if p and status=='Paid':
     c.execute('UPDATE subscriptions SET status="Active",starts_at=?,ends_at=? WHERE id=?',(now(),(datetime.now()+timedelta(days=30)).isoformat(timespec='seconds'),p['subscription_id'])); sub=c.execute('SELECT plan,cafe_id FROM subscriptions WHERE id=?',(p['subscription_id'],)).fetchone(); c.execute('UPDATE cafes SET plan=? WHERE id=?',(sub['plan'],sub['cafe_id']))
    flash('Payment review save ho gaya.','success')
   elif action=='save_plan' and role=='admin':
    flash('Plan prices source config mein managed hain; production mein editable billing catalogue add karein.','success')
   else: abort(403)
   c.commit()
  except (ValueError,KeyError,sqlite3.IntegrityError): c.rollback(); flash('Details check karein. Email duplicate ho sakti hai ya koi value invalid hai.','error')
  finally: c.close()
  return redirect(url_for('workspace',page=page))
 # shared data scoped to tenant
 if is_admin:
  cafes=c.execute('SELECT ca.*,u.email owner_email FROM cafes ca LEFT JOIN users u ON u.id=ca.owner_id ORDER BY ca.id DESC').fetchall(); orders=c.execute('SELECT o.*,u.name customer_name,ca.name cafe_name FROM orders o JOIN users u ON u.id=o.customer_id JOIN cafes ca ON ca.id=o.cafe_id ORDER BY o.id DESC LIMIT 100').fetchall(); payments=c.execute('SELECT p.*,ca.name cafe_name FROM payments p JOIN cafes ca ON ca.id=p.cafe_id ORDER BY p.id DESC').fetchall(); items=[]; staff=[]; tables=[]; cafe=None
 else:
  cafe=c.execute('SELECT * FROM cafes WHERE id=?',(cid,)).fetchone(); cafes=[]; payments=[]
  cond='WHERE o.cafe_id=?'; params=(cid,)
  if role=='customer': cond+=' AND o.customer_id=?'; params=(cid,u['id'])
  if role=='chef':
   if page=='New Orders': cond+=" AND o.status='New'"
   elif page=='Preparing Orders': cond+=" AND o.status IN ('Accepted','Preparing')"
   elif page=='Ready Orders': cond+=" AND o.status='Ready'"
   elif page=='Order History': cond+=" AND o.status IN ('Served','Cancelled')"
   else: cond+=" AND o.status IN ('New','Accepted','Preparing','Ready')"
  if role=='waiter':
   if page=='Ready to Serve': cond+=" AND o.status='Ready'"
   elif page=='Served Orders': cond+=" AND o.status='Served'"
   elif page=='Active Orders': cond+=" AND o.status NOT IN ('Served','Cancelled')"
   else: cond+=" AND o.status IN ('Ready','Served')"
  orders=c.execute(f'SELECT o.*,u.name customer_name FROM orders o JOIN users u ON u.id=o.customer_id {cond} ORDER BY o.id DESC LIMIT 100',params).fetchall()
  items=c.execute('SELECT * FROM menu_items WHERE cafe_id=? ORDER BY category,name',(cid,)).fetchall(); staff=c.execute('SELECT * FROM users WHERE cafe_id=? AND role IN (\'chef\',\'waiter\') ORDER BY role,name',(cid,)).fetchall(); tables=c.execute('SELECT * FROM cafe_tables WHERE cafe_id=? ORDER BY name',(cid,)) .fetchall()
 lines={}
 for o in orders: lines[o['id']]=c.execute('SELECT * FROM order_items WHERE order_id=?',(o['id'],)).fetchall()
 rules=c.execute('SELECT * FROM reward_rules WHERE cafe_id=?',(cid,)).fetchone() if cid else None
 reward=c.execute('SELECT coins FROM rewards WHERE user_id=?',(u['id'],)).fetchone() if role=='customer' else None; coins=reward['coins'] if reward else 0
 ledger=c.execute('SELECT * FROM reward_ledger WHERE user_id=? ORDER BY id DESC LIMIT 20',(u['id'],)).fetchall() if role=='customer' else []
 subs=c.execute('SELECT * FROM subscriptions WHERE cafe_id=? ORDER BY id DESC',(cid,)).fetchall() if role=='owner' else []
 report=c.execute("SELECT COUNT(*) orders,COALESCE(SUM(total),0) revenue,COALESCE(AVG(total),0) avg_order FROM orders WHERE cafe_id=? AND status!='Cancelled'",(cid,)).fetchone() if cid else None
 c.close()
 return render_template('workspace.html',page=page,role=role,cafe=cafe,cafes=cafes,orders=orders,lines=lines,items=items,staff=staff,tables=tables,coins=coins,ledger=ledger,rules=rules,subs=subs,payments=payments,report=report)

def add_coins(c,uid,cid,amount,reason):
 c.execute('INSERT INTO rewards(user_id,coins) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET coins=coins+excluded.coins',(uid,amount)); c.execute('INSERT INTO reward_ledger(user_id,cafe_id,delta,reason,created_at) VALUES(?,?,?,?,?)',(uid,cid,amount,reason,now()))
def award_coins(c,uid,cid):
 r=c.execute('SELECT * FROM reward_rules WHERE cafe_id=?',(cid,)).fetchone()
 if not r or not r['enabled'] or r['coins_per_order']<=0:return
 today=datetime.now().strftime('%Y-%m-%d'); earned=c.execute("SELECT COALESCE(SUM(delta),0) n FROM reward_ledger WHERE user_id=? AND cafe_id=? AND delta>0 AND substr(created_at,1,10)=?",(uid,cid,today)).fetchone()['n']; amount=max(0,min(r['coins_per_order'],r['daily_cap']-earned))
 if amount:add_coins(c,uid,cid,amount,'Completed order reward')

@app.route('/qr/<int:table_id>.png')
@roles('owner')
def qr_image(table_id):
 c=db(); t=c.execute('SELECT t.*,ca.slug FROM cafe_tables t JOIN cafes ca ON ca.id=t.cafe_id WHERE t.id=? AND t.cafe_id=?',(table_id,get_user()['cafe_id'])).fetchone(); c.close()
 if not t: abort(404)
 try:
  import qrcode
  img=qrcode.make(url_for('public_menu',slug=t['slug'],token=t['token'],_external=True)); b=io.BytesIO(); img.save(b,format='PNG'); b.seek(0); return send_file(b,mimetype='image/png')
 except ImportError: return 'Install qrcode[pil] to generate QR images.',501

@app.route('/health')
def health(): return jsonify({'service':'AUREVIX','status':'ok'})

@app.errorhandler(403)
def forbidden(e): return render_template('message.html',title='Access restricted',message='Is page ka access aap ke role ko nahi diya gaya.'),403
@app.errorhandler(404)
def missing(e): return render_template('message.html',title='Page not found',message='Requested page available nahi.'),404

if __name__=='__main__':
 init_db(); app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=False)
