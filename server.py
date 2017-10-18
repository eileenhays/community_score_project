"""BLOCK PARTY Server File"""

from jinja2 import StrictUndefined
from flask import (Flask, jsonify, render_template, redirect, request,
                   flash, session, abort, url_for)
from flask_debugtoolbar import DebugToolbarExtension

#libraries for API requests
from sys import argv
from pprint import pprint, pformat

from model import db, connect_to_db, User, Address, Saved_event
import os
from meetup_handler import Meetup_API
from passlib.hash import bcrypt

from flask_login import LoginManager, login_user, login_required, logout_user, current_user 


app = Flask(__name__)
app.secret_key = "ABC"

MEETUP_API_KEY = os.environ.get('MEETUP_API_KEY')
EVENTBRITE_TOKEN = os.environ.get('EVENTBRITE_OAUTH_TOKEN')
EVENTBRITE_URL = "https://www.eventbriteapi.com/v3/"

# Raises an error in Jinja
app.jinja_env.undefined = StrictUndefined

######################################
#For Registration and Login
######################################

login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = 'render_login_page'


@app.route('/')
def index():
    """Homepage with map."""

    return render_template("map.html")


@app.route('/search-events')
def search_for_events():
    """Request events from Meetup API and returns a JSON with local events."""

    address = request.args.get('address')
    lat = request.args.get('lat')
    lng = request.args.get('lng')

    session["address"] = address
    session["lat"] = lat
    session["lng"] = lng
    print session

    raw_data = Meetup_API.find_events(lat, lng, MEETUP_API_KEY)
    clean_data = Meetup_API.sanitize_data(raw_data)
    # print pprint(clean_data)

    return jsonify(clean_data)


@app.route('/registration')
def render_registration_page():
    """Shows registration page"""

    return render_template("registration.html")


@app.route('/handle-regis', methods=['POST'])
def save_user_in_database():
    """Register new user and save info in database"""

    name = request.form.get("name")
    email = request.form.get("email") 
    regis_pw_input = request.form.get("password")

    # Check if user is already registered
    if User.query.filter_by(email=email).first() is not None:
        flash("There is already an account registered with this email.")
        return redirect("/registration")

    # Hash password to save in database
    hashed_pw = bcrypt.hash(regis_pw_input)
    del regis_pw_input    

    # Add address record in DB 
    if session != None:
        new_address = Address(lat=session["lat"], lng=session["lng"], formatted_addy=session["address"])
        db.session.add(new_address)
        db.session.flush()

    # Add user record in DB 
    if new_address.addy_id:
        new_user = User(name=name, email=email, password=hashed_pw, addy_id=new_address.addy_id)
    else:
        new_user = User(name=name, email=email, password=hashed_pw)

    db.session.add(new_user)
    db.session.commit() 

    login_user(new_user)

    print "registration was successful and user logged in"
    flash("registration was successful<br> user logged in")

    return redirect("/") 


@login_manager.user_loader
def load_user(user_id):

    return User.query.get(user_id)


@app.route('/login')
def render_login_page():
    """Shows the registration and login page. Gives user access to profile."""

    return render_template("login.html")


@app.route('/handle-login', methods=['POST'])
def check_login():
    """Verify login credentials"""

    email = request.form.get("email")
    user = User.query.filter_by(email=email).first()
    password = user.password

    if bcrypt.verify(request.form.get("password"), password):
        # Login and validate the user.
        # user should be an instance of your `User` class
        login_user(user)

        flash('Logged in successfully.')

        next = request.args.get('next')
        # is_safe_url should check if the url is safe for redirects.
        # See http://flask.pocoo.org/snippets/62/ for an example.
        # if not is_safe_url(next):
        #     return abort(400)

        return redirect(next or url_for('index'))
    return render_template('login.html', form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    print session
    flash("Logout successful!")
    return redirect('/')


@app.route('/add-fave', methods=['POST'])
@login_required
def save_event_in_database():
    """Saves event information in database when user favorites""" 

    evt_name = request.form.get("name")
    time = request.form.get("time")
    url = request.form.get("url")
    lat = request.form.get("lat")
    lng = request.form.get("lng")
    address = request.form.get("address")

    # add event address 
    new_address = Address(lat=lat, lng=lng, formatted_addy=address)
    db.session.add(new_address)
    db.session.flush()

    new_evt = Saved_event(name=evt_name, datetime=time, url=url, user_id=session['user_id'], addy_id=new_address.addy_id)

    db.session.add(new_evt)
    db.session.commit() 

    print "New event was added to favorites"
    return evt_name


@app.route('/favorites')
@login_required
def render_favorites_page():
    """Shows user's favorites""" 

    user_id = current_user.user_id
    saved_events = Saved_event.query.filter_by(user_id=user_id).all()

    return render_template("favorites.html", saved_events=saved_events)


@app.route('/eventbrite-events')
def find_eb_events(lat, lng):
    """Search for event details on Eventbrite"""

    location_lat = lat
    location_lng = lng
    distance = 2
    measurement = 'mi'
    sort_by = 'date'

    if location and distance and measurement:
        distance = distance + measurement

        payload = {'location.latitude': lat,
                   'location.longitude': lng,
                   'location.within': distance,
                   'sort_by': sort_by,
                   }

        # For GET requests to Eventbrite's API, the token could also be sent as a
        # URL parameter with the key 'token'
        headers = {'Authorization': 'Bearer ' + EVENTBRITE_TOKEN}

        response = requests.get(EVENTBRITE_URL + "events/search/",
                                params=payload,
                                headers=headers)
        data = response.json()

        if response.ok:
            events = data['events']
        else:
            flash(":( No parties: " + data['error_description'])
            events = []

        return render_template("evt_analysis.html",
                               data=pformat(data),
                               results=events)

    # If the required info isn't in the request, redirect to the search form
    else:
        flash("Please provide all the required information!")
        return redirect("/afterparty-search")




if __name__ == "__main__":
    # We have to set debug=True here, since it has to be True at the
    # point that we invoke the DebugToolbarExtension
    app.debug = True
    app.jinja_env.auto_reload = app.debug  # make sure templates, etc. are not cached in debug mode

    connect_to_db(app)

    # Use the DebugToolbar
    # DebugToolbarExtension(app)



    app.run(port=5000, host='0.0.0.0')