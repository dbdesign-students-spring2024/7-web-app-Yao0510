#!/usr/bin/env python3

import os
import sys
import subprocess
import datetime
import time

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    make_response,
    session,
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)

# import logging
import sentry_sdk
from sentry_sdk.integrations.flask import (
    FlaskIntegration,
)  # delete this if not using sentry.io

# from markupsafe import escape
import pymongo
from pymongo.errors import ConnectionFailure
from bson.objectid import ObjectId
from dotenv import load_dotenv

# load credentials and configuration options from .env file
# if you do not yet have a file named .env, make one based on the template in env.example
load_dotenv(override=True)  # take environment variables from .env.

# initialize Sentry for help debugging... this requires an account on sentrio.io
# you will need to set the SENTRY_DSN environment variable to the value provided by Sentry
# delete this if not using sentry.io
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    # enable_tracing=True,
    # Set traces_sample_rate to 1.0 to capture 100% of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100% of sampled transactions.
    # We recommend adjusting this value in production.
    # profiles_sample_rate=1.0,
    integrations=[FlaskIntegration()],
    send_default_pii=True,
)

# instantiate the app using sentry for debugging
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")  # set the secret key for the app

# # turn on debugging if in development mode
# app.debug = True if os.getenv("FLASK_ENV", "development") == "development" else False

# try to connect to the database, and quit if it doesn't work
try:
    cxn = pymongo.MongoClient(os.getenv("MONGO_URI"))
    db = cxn[os.getenv("MONGO_DBNAME")]  # store a reference to the selected database

    # verify the connection works by pinging the database
    cxn.admin.command("ping")  # The ping command is cheap and does not require auth.
    print(" * Connected to MongoDB!")  # if we get here, the connection worked!
except ConnectionFailure as e:
    # catch any database errors
    # the ping command failed, so the connection is not available.
    print(" * MongoDB connection error:", e)  # debug
    sentry_sdk.capture_exception(e)  # send the error to sentry.io. delete if not using
    sys.exit(1)  # this is a catastrophic error, so no reason to continue to live


# set up the login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# create a user class for the login manager
class User(UserMixin):
    def __init__(self, id):
        self.id = id

    def get_id(self):
        return self.id


# create a todo class
class Todo:
    def __init__(self, title, description, created_at):
        self.user = current_user.id
        self.title = title
        self.description = description
        self.created_at = created_at


# set up a user loader function for the login manager
@login_manager.user_loader
def load_user(user_id):
    return User(user_id)


# set up the login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["fusername"]
        password = request.form["fpassword"]

        # check if the user exists in the database
        user = db.users.find_one({"username": username, "password": password})
        if user is not None:
            user_obj = User(user["_id"].__str__())
            login_user(user_obj)
            session["username"] = username
            return redirect(url_for("home"))
        else:
            return show_info("Login failed!")
    return render_template("login.html")


# set up the logout route
@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("username", None)
    return show_info("You are now logged out!")


def show_info(message):
    return render_template("info.html", message=message)


# set up the register route
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["fusername"]
        password = request.form["fpassword"]
        confirm = request.form["fpassword2"]


        # Check for empty fields
        if username == "" or password == "":
            return show_info("Please fill out all fields!")
        
        # Check if the username already exists
        existing_user = db.users.find_one({"username": username})
        if existing_user is not None:
            return show_info("Username already exists!")

        # Check if the passwords match
        if password != confirm:
            return show_info("Passwords do not match!")
        
        # insert the new user into the database
        db.users.insert_one({"username": username, "password": password})
        return redirect(url_for("login"))

    return render_template("register.html")


# set up the routes


@app.route("/")
def home():
    """
    Route for the home page.
    Simply returns to the browser the content of the index.html file located in the templates folder.
    """
    return render_template("index.html")


@app.route("/account")
@login_required
def account():
    """
    Route for the account page.
    Simply returns to the browser the content of the account.html file located in the templates folder.
    """
    return render_template("account.html")


@app.route("/todos")
@login_required
def todos():
    """
    Route for GET requests to the todos page.
    Displays some information for the user with links to other pages.
    """
    # docs = db.exampleapp.find({}).sort(
    #     "created_at", -1
    # )  # sort in descending order of created_at timestamp
    todos = db.todos.find({"user": current_user.id})
    return render_template("todos.html", todos=todos)


@app.route("/add_todo", methods=["POST"])
def add_todo():
    """
    Route for POST requests to the add_todo page.
    Accepts the form submission data for a new document and saves the document to the database.
    """
    title = request.form["title"]
    description = request.form["description"]

    # create a new document with the data the user entered
    todo = Todo(
        title=title,
        description=description,
        created_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    db.todos.insert_one(todo.__dict__)
    return redirect(
        url_for("todos")
    )  # tell the browser to make a request for the /read route


@app.route("/edit/<mongoid>")
def edit(mongoid):
    """
    Route for GET requests to the edit page.
    Displays a form users can fill out to edit an existing record.

    Parameters:
    mongoid (str): The MongoDB ObjectId of the record to be edited.
    """
    todo = db.todos.find_one({"_id": ObjectId(mongoid)})
    return render_template(
        "edit.html", mongoid=mongoid, todo=todo
    )  # render the edit template


@app.route("/edit/<mongoid>", methods=["POST"])
def edit_todo(mongoid):
    """
    Route for POST requests to the edit page.
    Accepts the form submission data for the specified document and updates the document in the database.

    Parameters:
    mongoid (str): The MongoDB ObjectId of the record to be edited.
    """
    title = request.form["ftitle"]
    description = request.form["fdesc"]

    # create a new document with the data the user entered
    todo = Todo(
        title=title,
        description=description,
        created_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    db.todos.update_one({"_id": ObjectId(mongoid)}, {"$set": todo.__dict__})

    return redirect(
        url_for("todos")
    )  # tell the browser to make a request for the /read route


@app.route("/delete/<mongoid>")
def delete(mongoid):
    """
    Route for GET requests to the delete page.
    Deletes the specified record from the database, and then redirects the browser to the read page.

    Parameters:
    mongoid (str): The MongoDB ObjectId of the record to be deleted.
    """
    db.todos.delete_one({"_id": ObjectId(mongoid)})
    return redirect(
        url_for("todos")
    )  # tell the web browser to make a request for the /read route.


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    GitHub can be configured such that each time a push is made to a repository, GitHub will make a request to a particular web URL... this is called a webhook.
    This function is set up such that if the /webhook route is requested, Python will execute a git pull command from the command line to update this app's codebase.
    You will need to configure your own repository to have a webhook that requests this route in GitHub's settings.
    Note that this webhook does do any verification that the request is coming from GitHub... this should be added in a production environment.
    """
    # run a git pull command
    process = subprocess.Popen(["git", "pull"], stdout=subprocess.PIPE)
    pull_output = process.communicate()[0]
    # pull_output = str(pull_output).strip() # remove whitespace
    process = subprocess.Popen(["chmod", "a+x", "flask.cgi"], stdout=subprocess.PIPE)
    chmod_output = process.communicate()[0]
    # send a success response
    response = make_response(f"output: {pull_output}", 200)
    response.mimetype = "text/plain"
    return response


@app.errorhandler(Exception)
def handle_error(e):
    """
    Output any errors - good for debugging.
    """
    return render_template("error.html", error=e)  # render the edit template


# run the app
if __name__ == "__main__":
    # logging.basicConfig(filename="./flask_error.log", level=logging.DEBUG)
    app.run(load_dotenv=True)
