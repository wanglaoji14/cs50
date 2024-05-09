import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    #确认现在有的股票和份额
    stocks = db.execute("SELECT symbol,sum(shares) as total_shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0 ",session["user_id"])
    #确认现在有的账户余额
    cash = db.execute("SELECT cash FROM users WHERE id = ?",session["user_id"])[0]["cash"]
    #初始化总价值
    total_value = cash

    #计算每个股票的情况
    for stock in stocks:
        quote = lookup(stock["symbol"])
        stock["price"] = quote["price"]
        stock["value"] = stock["total_shares"]*stock["price"]
        total_value += stock["value"]
    return  render_template("index.html",stocks = stocks,total_value= total_value)




@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        #初始化
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        check = lookup(symbol)

        #确认是否提交了 symbol
        if not symbol:
            return apology("must provide symbol ")

        #确保symbol是正整数
        if not shares or not shares.isdigit() or int(shares) < 0:
            return apology("must provide a positive integer number of shares ")
        #确保symbol存在
        if check is None:
            return apology("symbol not exists")
        #计算购买成本
        price = check["price"]
        total_cost = int(shares)*price
        cash = db.execute("SELECT cash FROM users WHERE id = ?",session["user_id"])[0]["cash"]
        #比较成本和现金
        if cash < total_cost:
            return apology("not enough cash")
        #update table
        balance = cash - total_cost
        db.execute("UPDATE users SET cash = ? WHERE id = ?",balance,session["user_id"])
        db.execute("INSERT INTO transactions(user_id,symbol,shares,price) VALUES (?,?,?,?)",session["user_id"],symbol, shares,price)
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    #抽取数据
    transactions = db.execute("SELECT *FROM transactions WHERE user_id = ? ORDER by timestamp DESC",session["user_id"])

    return render_template("history.html",transactions =transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        #确认是否提供了symbol
        if not symbol :
            return apology("must provide symbol")
        #获取symbol的row
        quote = lookup(symbol)
        #确认symbol是否存在
        if not quote:
            return apology("symbol not exists")
        price = quote['price']
        symbols = quote['symbol']

        return render_template("quoted.html",price = price,symbol = symbols)
    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    #清除所有session
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        #确 认有没有输入用户名
        if not username:
            return apology("must provide username")
        #确认这个账户有没有注册过
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if rows:
            return apology("username already exists")
        #确认密码有没有输入
        if not request.form.get("password"):
            return apology("must provide password")
        #确认密码和“确认密码”是否一致
        if confirmation != password:
            return apology("passwords do not match")
        #hash 密码并储存
        hash_password = generate_password_hash(password)
        db.execute("INSERT INTO users (username,hash) VALUES (?, ?)", username, hash_password)
        #记住session
        rows2 = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        session["user_id"] = rows2[0]["id"]
        return redirect("/")
    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method =="POST":
        #初始化
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        #确认symbol和shares是正整数
        if not symbol:
            return apology("must provide symbol")
        elif not shares or not shares.isdigit() or int(shares) <= 0:
            return apology (" must provide a positive number of shares")
        else:
            shares = int(shares)

        #获取现在的交易记录，为了保证过去有购买过股票
        stocks = db.execute("SELECT symbol,SUM(shares) as total_shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0",session["user_id"])

        for stock in stocks:
            #确认symbol以前买过
            if stock["symbol"] == symbol:
                #确认足够的shares
                if stock["total_shares"] < shares:
                    return apology("no enough shares")
                else:
                    #查看现在的股票的价格
                    quote = lookup(symbol)
                    price = quote["price"]

                    #计算卖出多少钱
                    sell = price * shares

                    #查看现金
                    cash = db.execute("SELECT cash FROM users WHERE id = ?",session["user_id"])

                    #计算卖出股票后，有多少钱
                    cash_update = cash[0]["cash"]+sell
                    #更新现金
                    db.execute("UPDATE users SET cash = ? WHERE id = ?",cash_update,session["user_id"])

                    #更新交易记录
                    db.execute("INSERT INTO transactions (user_id,symbol,shares,price) VALUES (?,?,?,?)",session["user_id"],symbol,-shares,price)
                    return redirect("/")
        return apology("symbol not found")

    else:
     return render_template("sell.html")


