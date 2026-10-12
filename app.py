import os
import logging
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from flask_session import Session
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, db, auth
import json
from datetime import datetime, timezone
import re
from flask_mail import Mail, Message
import urllib.parse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
Session(app)

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_HOST_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_HOST_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('DEFAULT_FROM_EMAIL')

# Initialize Flask-Mail
mail = Mail(app)

# Verify environment variables
required_env_vars = [
    'FIREBASE_PROJECT_ID', 'FIREBASE_PRIVATE_KEY_ID', 'FIREBASE_PRIVATE_KEY',
    'FIREBASE_CLIENT_EMAIL', 'FIREBASE_CLIENT_ID', 'FIREBASE_CLIENT_X509_CERT_URL',
    'FLASK_SECRET_KEY', 'FIREBASE_API_KEY', 'FIREBASE_AUTH_DOMAIN',
    'FIREBASE_STORAGE_BUCKET', 'FIREBASE_MESSAGING_SENDER_ID', 'FIREBASE_APP_ID',
    'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD', 'DEFAULT_FROM_EMAIL',
    'FOURSQUARE_CLIENT_ID', 'FOURSQUARE_CLIENT_SECRET'
]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    logger.error(f"Missing required environment variables: {missing_vars}")
    raise ValueError(f"Missing required environment variables: {missing_vars}")

# Firebase configuration
try:
    firebase_cred = credentials.Certificate({
        "type": "service_account",
        "project_id": os.getenv('FIREBASE_PROJECT_ID'),
        "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
        "private_key": os.getenv('FIREBASE_PRIVATE_KEY').replace('\\n', '\n'),
        "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
        "client_id": os.getenv('FIREBASE_CLIENT_ID'),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_X509_CERT_URL')
    })
    firebase_admin.initialize_app(firebase_cred, {
        'databaseURL': f"https://{os.getenv('FIREBASE_PROJECT_ID')}-default-rtdb.firebaseio.com/"
    })
    logger.info("Firebase Admin SDK initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Firebase Admin SDK: {str(e)}")
    raise

# Configuration for templates
config = {
    'firebase': {
        'apiKey': os.getenv('FIREBASE_API_KEY'),
        'authDomain': os.getenv('FIREBASE_AUTH_DOMAIN'),
        'projectId': os.getenv('FIREBASE_PROJECT_ID'),
        'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET'),
        'messagingSenderId': os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
        'appId': os.getenv('FIREBASE_APP_ID')
    },
    'foursquare': {
        'client_id': os.getenv('FOURSQUARE_CLIENT_ID'),
        'client_secret': os.getenv('FOURSQUARE_CLIENT_SECRET')
    },
    'google_maps': {
        'api_key': os.getenv('GOOGLE_MAPS_API_KEY')
    }
}

# Helper functions
def is_valid_date(date_str):
    try:
        datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False

def is_valid_time(time_str):
    return bool(re.match(r'^\d{2}:\d{2}$', time_str))

def get_user_email(uid):
    """Fetch user email from Firebase Authentication using UID."""
    try:
        user = auth.get_user(uid)
        return user.email
    except Exception as e:
        logger.error(f"Error fetching user email for UID {uid}: {str(e)}")
        return None

def get_notification_count(uid):
    """Fetch the count of unread notifications for a user."""
    try:
        ref = db.reference(f"users/{uid}/notifications")
        notifications = ref.get()
        if not notifications:
            return 0
        return sum(1 for n in notifications.values() if not n.get('dismissed', False))
    except Exception as e:
        logger.error(f"Error fetching notification count for UID {uid}: {str(e)}")
        return 0

# Routes
@app.route('/')
def home():
    if 'user' in session:
        notification_count = get_notification_count(session['user']['uid'])
        return render_template('home.html', config=config, notification_count=notification_count)
    return render_template('home.html', config=config, notification_count=0)

@app.route('/signup')
def signup():
    if 'user' in session:
        notification_count = get_notification_count(session['user']['uid'])
        return redirect(url_for('dashboard', notification_count=notification_count))
    return render_template('signup.html', config=config, notification_count=0)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        notification_count = get_notification_count(session['user']['uid'])
        return redirect(url_for('dashboard', notification_count=notification_count))
    return render_template('login.html', config=config, notification_count=0)

@app.route('/forgot_password')
def forgot_password():
    if 'user' in session:
        notification_count = get_notification_count(session['user']['uid'])
        return redirect(url_for('dashboard', notification_count=notification_count))
    return render_template('forgot_password.html', config=config, notification_count=0)

@app.route('/sync-session', methods=['POST'])
def sync_session():
    if not request.get_json():
        logger.warning("No JSON data in sync-session request")
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    data = request.get_json()
    logger.info(f"Sync-session request: {data}")
    try:
        uid = data.get('uid')
        email = data.get('email')
        id_token = data.get('id_token')
        display_name = data.get('displayName')

        if not all([uid, email, id_token]):
            logger.warning("Missing required fields in sync-session request")
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        try:
            decoded_token = auth.verify_id_token(id_token)
            if decoded_token['uid'] != uid:
                logger.warning(f"UID mismatch in token: {uid} vs {decoded_token['uid']}")
                return jsonify({'success': False, 'error': 'Invalid token'}), 401
        except auth.InvalidIdTokenError:
            logger.warning("Invalid ID token provided")
            return jsonify({'success': False, 'error': 'Invalid token'}), 401
        except auth.ExpiredIdTokenError:
            logger.warning("Expired ID token provided")
            return jsonify({'success': False, 'error': 'Token expired'}), 401
        except auth.RevokedIdTokenError:
            logger.warning("Revoked ID token provided")
            return jsonify({'success': False, 'error': 'Token revoked'}), 401
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            return jsonify({'success': False, 'error': 'Token verification failed'}), 401

        session['user'] = {
            'uid': uid,
            'email': email,
            'displayName': display_name or ''
        }
        session.pop('logging_out', None)
        logger.info(f"Session synced for user: {email} (UID: {uid})")

        # Send welcome email for new users
        if 'is_signup' in data and data['is_signup']:
            welcome_content = f"""
            <h2>Welcome to Smart City Traveller!</h2>
            <p>Hello {display_name or email},</p>
            <p>Thank you for signing up. Start planning your trips today!</p>
            <p>Best,<br>Smart City Traveller Team</p>
            """
            try:
                msg = Message(
                    subject="Welcome to Smart City Traveller",
                    recipients=[email],
                    html=welcome_content
                )
                mail.send(msg)
                logger.info(f"Welcome email sent to {email}")
            except Exception as e:
                logger.error(f"Failed to send welcome email to {email}: {str(e)}")

        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f"Sync session error: {str(e)}")
        return jsonify({'success': False, 'error': 'Session sync failed'}), 500

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        logger.warning("Unauthenticated access attempt to dashboard")
        return redirect(url_for('login'))
    
    try:
        uid = session['user']['uid']
        ref = db.reference(f"users/{uid}/schedules")
        schedules_data = ref.get()
        schedules = []
        
        if schedules_data:
            for schedule_id, schedule in schedules_data.items():
                schedule['id'] = schedule_id
                schedules.append(schedule)
        
        logger.info(f"Loaded {len(schedules)} schedules for user {session['user']['email']}")
        notification_count = get_notification_count(uid)
        return render_template('dashboard.html', config=config, schedules=schedules, notification_count=notification_count)
    except firebase_admin.exceptions.FirebaseError as fe:
        logger.error(f"Firebase error loading schedules for user {session['user']['email']}: {str(fe)}")
        flash('Unable to load schedules due to database error. Please try again.', 'danger')
        notification_count = get_notification_count(session['user']['uid'])
        return render_template('dashboard.html', config=config, schedules=[], notification_count=notification_count)
    except Exception as e:
        logger.error(f"Unexpected error loading schedules for user {session['user']['email']}: {str(e)}")
        flash('Unable to load schedules. Please try again.', 'danger')
        notification_count = get_notification_count(session['user']['uid'])
        return render_template('dashboard.html', config=config, schedules=[], notification_count=notification_count)

@app.route('/create_schedule', methods=['GET', 'POST'])
def create_schedule():
    if 'user' not in session:
        logger.warning("Unauthenticated access attempt to create_schedule")
        return redirect(url_for('login'))
    
    schedule_id = request.args.get('schedule_id')
    schedule = None
    if schedule_id:
        try:
            ref = db.reference(f"users/{session['user']['uid']}/schedules/{schedule_id}")
            schedule = ref.get()
            if not schedule:
                logger.warning(f"Schedule not found: {schedule_id}")
                flash('Schedule not found.', 'danger')
                notification_count = get_notification_count(session['user']['uid'])
                return redirect(url_for('dashboard', notification_count=notification_count))
            schedule['id'] = schedule_id
        except firebase_admin.exceptions.FirebaseError as fe:
            logger.error(f"Firebase error loading schedule {schedule_id}: {str(fe)}")
            flash('Unable to load schedule due to database error. Please try again.', 'danger')
            notification_count = get_notification_count(session['user']['uid'])
            return redirect(url_for('dashboard', notification_count=notification_count))
        except Exception as e:
            logger.error(f"Unexpected error loading schedule {schedule_id}: {str(e)}")
            flash('Unable to load schedule. Please try again.', 'danger')
            notification_count = get_notification_count(session['user']['uid'])
            return redirect(url_for('dashboard', notification_count=notification_count))

    if request.method == 'POST':
        try:
            data = request.form
            interests = data.getlist('interests')
            city = data.get('city', '').strip()
            date = data.get('date', '').strip()
            start_time = data.get('start_time', '').strip()
            end_time = data.get('end_time', '').strip()
            selected_venues = json.loads(data.get('selected_venues', '[]'))

            if not all([interests, city, date, start_time, end_time]):
                logger.warning("Missing required fields in create_schedule")
                flash('All fields are required.', 'danger')
                notification_count = get_notification_count(session['user']['uid'])
                return redirect(url_for('create_schedule', schedule_id=schedule_id, notification_count=notification_count))

            if not is_valid_date(date):
                logger.warning(f"Invalid date format: {date}")
                flash('Invalid date format.', 'danger')
                notification_count = get_notification_count(session['user']['uid'])
                return redirect(url_for('create_schedule', schedule_id=schedule_id, notification_count=notification_count))

            if not is_valid_time(start_time) or not is_valid_time(end_time):
                logger.warning(f"Invalid time format: start_time={start_time}, end_time={end_time}")
                flash('Invalid time format (use HH:MM).', 'danger')
                notification_count = get_notification_count(session['user']['uid'])
                return redirect(url_for('create_schedule', schedule_id=schedule_id, notification_count=notification_count))

            # Validate time window
            start_h, start_m = map(int, start_time.split(':'))
            end_h, end_m = map(int, end_time.split(':'))
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m
            if end_minutes <= start_minutes:
                logger.warning(f"End time {end_time} is not after start time {start_time}")
                flash('End time must be after start time.', 'danger')
                notification_count = get_notification_count(session['user']['uid'])
                return redirect(url_for('create_schedule', schedule_id=schedule_id, notification_count=notification_count))

            # Validate venues
            for venue in selected_venues:
                if not all(key in venue for key in ['name', 'category', 'location']):
                    logger.warning(f"Invalid venue data: {venue}")
                    flash('Invalid venue data.', 'danger')
                    notification_count = get_notification_count(session['user']['uid'])
                    return redirect(url_for('create_schedule', schedule_id=schedule_id, notification_count=notification_count))
                if not all(key in venue['location'] for key in ['lat', 'lng', 'formattedAddress']):
                    logger.warning(f"Invalid venue location: {venue['location']}")
                    flash('Invalid venue location data.', 'danger')
                    notification_count = get_notification_count(session['user']['uid'])
                    return redirect(url_for('create_schedule', schedule_id=schedule_id, notification_count=notification_count))

            # Calculate time slots
            time_slots = len([v for v in selected_venues if v.get('id') != 'your-location'])
            if time_slots == 0:
                logger.warning("No venues selected for scheduling")
                flash('Please select at least one venue.', 'danger')
                notification_count = get_notification_count(session['user']['uid'])
                return redirect(url_for('create_schedule', schedule_id=schedule_id, notification_count=notification_count))

            # Enforce minimum slot duration (30 minutes)
            total_minutes = end_minutes - start_minutes
            min_slot_duration = 30  # Minimum 30 minutes per slot
            if total_minutes < time_slots * min_slot_duration:
                logger.warning(f"Time window too short: {total_minutes} minutes for {time_slots} slots")
                flash(f'Time window must be at least {time_slots * min_slot_duration} minutes for {time_slots} venues.', 'danger')
                notification_count = get_notification_count(session['user']['uid'])
                return redirect(url_for('create_schedule', schedule_id=schedule_id, notification_count=notification_count))

            slot_duration = max(min_slot_duration, total_minutes // time_slots)
            logger.debug(f"Calculated slot duration: {slot_duration} minutes for {time_slots} slots")

            for i, venue in enumerate(v for v in selected_venues if v.get('id') != 'your-location'):
                slot_start = start_minutes + i * slot_duration
                slot_end = min(slot_start + slot_duration, end_minutes)  # Ensure slot_end doesn't exceed end_time
                venue['time'] = f"{slot_start // 60:02d}:{slot_start % 60:02d} - {slot_end // 60:02d}:{slot_end % 60:02d}"
                logger.debug(f"Assigned time for {venue['name']}: {venue['time']}")

            schedule_data = {
                'interests': interests,
                'city': city,
                'date': date,
                'start_time': start_time,
                'end_time': end_time,
                'venues': selected_venues,
                'created_at': datetime.now(timezone.utc).isoformat()
            }

            ref = db.reference(f"users/{session['user']['uid']}/schedules")
            if schedule_id:
                ref.child(schedule_id).set(schedule_data)
                flash('Schedule updated successfully!', 'success')
                logger.info(f"Schedule updated: {schedule_id} for user {session['user']['email']}")
            else:
                new_schedule_ref = ref.push(schedule_data)
                schedule_id = new_schedule_ref.key
                flash('Schedule created successfully!', 'success')
                logger.info(f"Schedule created: {schedule_id} for user {session['user']['email']}")

                # Create trip reminder notification
                notification_data = {
                    'title': 'Trip Reminder',
                    'message': f'Your trip to {city} is scheduled for {date} from {start_time} to {end_time}.',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'dismissed': False
                }
                db.reference(f"users/{session['user']['uid']}/notifications").push(notification_data)
                logger.info(f"Trip reminder notification created for schedule {schedule_id}")

            return redirect(url_for('results', schedule_id=schedule_id))
        except firebase_admin.exceptions.FirebaseError as fe:
            logger.error(f"Firebase error saving schedule: {str(fe)}")
            flash('Unable to save schedule due to database error. Please try again.', 'danger')
            notification_count = get_notification_count(session['user']['uid'])
            return redirect(url_for('create_schedule', schedule_id=schedule_id, notification_count=notification_count))
        except Exception as e:
            logger.error(f"Unexpected error saving schedule: {str(e)}")
            flash('Unable to save schedule. Please try again.', 'danger')
            notification_count = get_notification_count(session['user']['uid'])
            return redirect(url_for('create_schedule', schedule_id=schedule_id, notification_count=notification_count))

    notification_count = get_notification_count(session['user']['uid'])
    return render_template('create_schedule.html', config=config, schedule=schedule, notification_count=notification_count)

@app.route('/fetch_venue_details/<venue_id>')
def fetch_venue_details(venue_id):
    try:
        url = f"https://api.foursquare.com/v2/venues/{venue_id}?client_id={config['foursquare']['client_id']}&client_secret={config['foursquare']['client_secret']}&v=20250519"
        response = requests.get(url)
        data = response.json()

        if data['meta']['code'] != 200:
            logger.error(f"Foursquare API error for venue {venue_id}: {data['meta']['errorDetail']}")
            return jsonify({'success': False, 'error': data['meta']['errorDetail']}), 500

        venue = data['response']['venue']
        formatted_venue = {
            'id': venue['id'],
            'name': venue.get('name', 'Unknown'),
            'category': venue['categories'][0]['name'] if venue.get('categories') else 'Unknown',
            'location': {
                'lat': venue['location'].get('lat', 0.0),
                'lng': venue['location'].get('lng', 0.0),
                'formattedAddress': venue['location'].get('formattedAddress', ['N/A'])
            },
            'rating': venue.get('rating', None),  # Foursquare rating (0-10)
            'phone': venue.get('contact', {}).get('formattedPhone', 'N/A'),
            'website': venue.get('url', 'N/A'),
            'hours': venue.get('hours', {}).get('status', 'N/A'),
            'price': venue.get('price', {}).get('tier', None),  # Price tier (1-4)
            'description': venue.get('description', 'N/A'),
            'categories': [cat['name'] for cat in venue.get('categories', [])],
            'photos': [{'url': photo['prefix'] + 'original' + photo['suffix']} for photo in venue.get('photos', {}).get('groups', [{}])[0].get('items', [])] if venue.get('photos') else []
        }
        logger.info(f"Fetched details for venue {venue_id}")
        return jsonify({'success': True, 'venue': formatted_venue}), 200
    except Exception as e:
        logger.error(f"Error fetching venue details for {venue_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/results')
def results():
    if 'user' not in session or 'uid' not in session['user']:
        logger.warning("Unauthenticated access attempt to results or missing UID")
        flash('Please log in to view results.', 'danger')
        return redirect(url_for('login'))
    
    schedule_id = request.args.get('schedule_id')
    logger.info(f"Received schedule_id: {schedule_id}")
    if not schedule_id:
        logger.warning("No schedule_id provided for results")
        flash('No schedule selected.', 'danger')
        notification_count = get_notification_count(session['user']['uid'])
        return redirect(url_for('dashboard', notification_count=notification_count))
    
    try:
        uid = session['user']['uid']
        email = session['user']['email']
        logger.info(f"Fetching schedule for user: {email} (UID: {uid}), Schedule ID: {schedule_id}")

        ref = db.reference(f"users/{uid}/schedules/{schedule_id}")
        schedule = ref.get()
        logger.info(f"Schedule data: {schedule}")
        if not schedule:
            logger.warning(f"Schedule not found: {schedule_id}")
            flash('Schedule not found.', 'danger')
            notification_count = get_notification_count(session['user']['uid'])
            return redirect(url_for('dashboard', notification_count=notification_count))

        required_keys = ['city', 'date', 'start_time', 'end_time', 'interests', 'venues']
        if not all(key in schedule for key in required_keys):
            logger.error(f"Invalid schedule data, missing keys: {set(required_keys) - set(schedule.keys())}")
            flash('Invalid schedule data.', 'danger')
            notification_count = get_notification_count(session['user']['uid'])
            return redirect(url_for('dashboard', notification_count=notification_count))

        venues = schedule.get('venues', [])
        if not isinstance(venues, list):
            logger.error(f"Invalid venues format: {venues}")
            flash('Invalid venues data.', 'danger')
            notification_count = get_notification_count(session['user']['uid'])
            return redirect(url_for('dashboard', notification_count=notification_count))

        for venue in venues:
            if not all(key in venue for key in ['name', 'category', 'location']):
                logger.error(f"Invalid venue data: {venue}")
                flash('Invalid venue data.', 'danger')
                notification_count = get_notification_count(session['user']['uid'])
                return redirect(url_for('dashboard', notification_count=notification_count))
            if not all(key in venue['location'] for key in ['lat', 'lng', 'formattedAddress']):
                logger.error(f"Invalid venue location data: {venue['location']}")
                flash('Invalid venue location data.', 'danger')
                notification_count = get_notification_count(session['user']['uid'])
                return redirect(url_for('dashboard', notification_count=notification_count))

        schedule['id'] = schedule_id
        logger.info(f"Loaded results for schedule {schedule_id} for user {email}")

        venues_html = ''.join([f"<li>{venue['name']} ({venue['category']}) at {venue.get('time', 'N/A')}</li>" for venue in venues])
        email_content = f"""
        <h2>Your Travel Schedule</h2>
        <p><strong>City:</strong> {schedule['city'].capitalize()}</p>
        <p><strong>Date:</strong> {schedule['date']}</p>
        <p><strong>Time:</strong> {schedule['start_time']} - {schedule['end_time']}</p>
        <p><strong>Interests:</strong> {', '.join(schedule['interests']).capitalize()}</p>
        <h3>Locations:</h3>
        <ul>{venues_html}</ul>
        <p>Enjoy your trip!</p>
        """
        try:
            msg = Message(
                subject=f"Schedule for {schedule['city'].capitalize()}",
                recipients=[email],
                html=email_content
            )
            mail.send(msg)
            logger.info(f"Results email sent to {email}")
        except Exception as e:
            logger.error(f"Failed to send results email to {email}: {str(e)}")

        notification_count = get_notification_count(uid)
        return render_template('results.html', config=config, schedule=schedule, venues=venues, notification_count=notification_count)
    except firebase_admin.exceptions.FirebaseError as fe:
        logger.error(f"Firebase error loading results: {str(fe)}")
        flash('Unable to load results due to database error. Please try again.', 'danger')
        notification_count = get_notification_count(session['user']['uid'])
        return redirect(url_for('dashboard', notification_count=notification_count))
    except Exception as e:
        logger.error(f"Unexpected error loading results: {str(e)}")
        flash('Unable to load results. Please try again.', 'danger')
        notification_count = get_notification_count(session['user']['uid'])
        return redirect(url_for('dashboard', notification_count=notification_count))

@app.route('/map_view')
def map_view():
    if 'user' not in session:
        logger.warning("Unauthenticated access attempt to map_view")
        return redirect(url_for('login'))
    
    schedule_id = request.args.get('schedule_id')
    if not schedule_id:
        logger.warning("No schedule_id provided for map_view")
        flash('No schedule selected.', 'danger')
        notification_count = get_notification_count(session['user']['uid'])
        return redirect(url_for('dashboard', notification_count=notification_count))
    
    try:
        ref = db.reference(f"users/{session['user']['uid']}/schedules/{schedule_id}")
        schedule = ref.get()
        if not schedule:
            logger.warning(f"Schedule not found: {schedule_id}")
            flash('Schedule not found.', 'danger')
            notification_count = get_notification_count(session['user']['uid'])
            return redirect(url_for('dashboard', notification_count=notification_count))
        
        venues = schedule.get('venues', [])
        schedule['id'] = schedule_id
        logger.info(f"Loaded map view for schedule {schedule_id} for user {session['user']['email']}")
        notification_count = get_notification_count(session['user']['uid'])
        return render_template('map_view.html', config=config, schedule=schedule, venues=venues, notification_count=notification_count)
    except firebase_admin.exceptions.FirebaseError as fe:
        logger.error(f"Firebase error loading map view: {str(fe)}")
        flash('Unable to load map view due to database error. Please try again.', 'danger')
        notification_count = get_notification_count(session['user']['uid'])
        return redirect(url_for('dashboard', notification_count=notification_count))
    except Exception as e:
        logger.error(f"Unexpected error loading map view: {str(e)}")
        flash('Unable to load map view. Please try again.', 'danger')
        notification_count = get_notification_count(session['user']['uid'])
        return redirect(url_for('dashboard', notification_count=notification_count))

@app.route('/notifications')
def notifications():
    if 'user' not in session:
        logger.warning("Unauthenticated access attempt to notifications")
        return redirect(url_for('login'))
    
    try:
        uid = session['user']['uid']
        ref = db.reference(f"users/{uid}/notifications")
        notifications_data = ref.get()
        notifications = []
        
        if notifications_data:
            for notification_id, notification in notifications_data.items():
                if not notification.get('dismissed', False):
                    notification['id'] = notification_id
                    notifications.append(notification)
        
        logger.info(f"Loaded {len(notifications)} notifications for user {session['user']['email']}")
        notification_count = get_notification_count(uid)
        return render_template('notifications.html', config=config, notifications=notifications, notification_count=notification_count)
    except firebase_admin.exceptions.FirebaseError as fe:
        logger.error(f"Firebase error loading notifications for user {session['user']['email']}: {str(fe)}")
        flash('Unable to load notifications due to database error. Please try again.', 'danger')
        notification_count = get_notification_count(session['user']['uid'])
        return render_template('notifications.html', config=config, notifications=[], notification_count=notification_count)
    except Exception as e:
        logger.error(f"Unexpected error loading notifications for user {session['user']['email']}: {str(e)}")
        flash('Unable to load notifications. Please try again.', 'danger')
        notification_count = get_notification_count(session['user']['uid'])
        return render_template('notifications.html', config=config, notifications=[], notification_count=notification_count)

@app.route('/dismiss_notification/<notification_id>', methods=['POST'])
def dismiss_notification(notification_id):
    if 'user' not in session:
        logger.warning("Unauthenticated access attempt to dismiss_notification")
        return redirect(url_for('login'))
    
    try:
        uid = session['user']['uid']
        ref = db.reference(f"users/{uid}/notifications/{notification_id}")
        ref.update({'dismissed': True})
        logger.info(f"Notification {notification_id} dismissed for user {session['user']['email']}")
        flash('Notification dismissed.', 'success')
        notification_count = get_notification_count(uid)
        return redirect(url_for('notifications', notification_count=notification_count))
    except firebase_admin.exceptions.FirebaseError as fe:
        logger.error(f"Firebase error dismissing notification {notification_id}: {str(fe)}")
        flash('Unable to dismiss notification due to database error. Please try again.', 'danger')
        notification_count = get_notification_count(session['user']['uid'])
        return redirect(url_for('notifications', notification_count=notification_count))
    except Exception as e:
        logger.error(f"Unexpected error dismissing notification {notification_id}: {str(e)}")
        flash('Unable to dismiss notification. Please try again.', 'danger')
        notification_count = get_notification_count(session['user']['uid'])
        return redirect(url_for('notifications', notification_count=notification_count))

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if 'user' not in session:
        logger.warning("Unauthenticated access attempt to feedback")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            feedback_type = request.form.get('type')
            message = request.form.get('message').strip()
            
            if not feedback_type or not message:
                logger.warning("Missing required fields in feedback submission")
                flash('All fields are required.', 'danger')
                notification_count = get_notification_count(session['user']['uid'])
                return redirect(url_for('feedback', notification_count=notification_count))
            
            feedback_data = {
                'type': feedback_type,
                'message': message,
                'user_id': session['user']['uid'],
                'user_email': session['user']['email'],
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            db.reference('feedback').push(feedback_data)
            logger.info(f"Feedback submitted by user {session['user']['email']}: {feedback_type}")
            flash('Thank you for your feedback!', 'success')
            
            email_content = f"""
            <h2>Thank You for Your Feedback!</h2>
            <p>Hello {session['user']['displayName'] or session['user']['email']},</p>
            <p>We have received your {feedback_type} feedback:</p>
            <p><strong>Message:</strong> {message}</p>
            <p>We appreciate your input and will review it soon.</p>
            <p>Best,<br>Smart City Traveller Team</p>
            """
            try:
                msg = Message(
                    subject="Feedback Confirmation",
                    recipients=[session['user']['email']],
                    html=email_content
                )
                mail.send(msg)
                logger.info(f"Feedback confirmation email sent to {session['user']['email']}")
            except Exception as e:
                logger.error(f"Failed to send feedback confirmation email to {session['user']['email']}: {str(e)}")
            
            notification_count = get_notification_count(session['user']['uid'])
            return redirect(url_for('dashboard', notification_count=notification_count))
        except firebase_admin.exceptions.FirebaseError as fe:
            logger.error(f"Firebase error saving feedback: {str(fe)}")
            flash('Unable to submit feedback due to database error. Please try again.', 'danger')
            notification_count = get_notification_count(session['user']['uid'])
            return redirect(url_for('feedback', notification_count=notification_count))
        except Exception as e:
            logger.error(f"Unexpected error saving feedback: {str(e)}")
            flash('Unable to submit feedback. Please try again.', 'danger')
            notification_count = get_notification_count(session['user']['uid'])
            return redirect(url_for('feedback', notification_count=notification_count))
    
    notification_count = get_notification_count(session['user']['uid'])
    return render_template('feedback.html', config=config, notification_count=notification_count)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        logger.warning("Unauthenticated access attempt to profile")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            display_name = data.get('displayName', '').strip()
            travel_preferences = data.get('travelPreferences', [])
            
            if not display_name:
                logger.warning("Missing displayName in profile update")
                return jsonify({'success': False, 'error': 'Display name is required'}), 400

            ref = db.reference(f"users/{session['user']['uid']}")
            ref.update({
                'displayName': display_name,
                'travelPreferences': travel_preferences
            })
            
            session['user']['displayName'] = display_name
            logger.info(f"Profile updated for user {session['user']['email']}")
            return jsonify({'success': True}), 200
        except firebase_admin.exceptions.FirebaseError as fe:
            logger.error(f"Firebase error updating profile: {str(fe)}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        except Exception as e:
            logger.error(f"Unexpected error updating profile: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    notification_count = get_notification_count(session['user']['uid'])
    return render_template('profile.html', config=config, notification_count=notification_count)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user' not in session:
        logger.warning("Unauthenticated access attempt to update_profile")
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        display_name = data.get('displayName', '').strip()
        travel_preferences = data.get('travelPreferences', [])
        
        if not display_name:
            logger.warning("Missing displayName in update_profile")
            return jsonify({'success': False, 'error': 'Display name is required'}), 400

        ref = db.reference(f"users/{session['user']['uid']}")
        ref.update({
            'displayName': display_name,
            'travelPreferences': travel_preferences
        })
        
        session['user']['displayName'] = display_name
        logger.info(f"Profile updated for user {session['user']['email']}")
        return jsonify({'success': True}), 200
    except firebase_admin.exceptions.FirebaseError as fe:
        logger.error(f"Firebase error updating profile: {str(fe)}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    except Exception as e:
        logger.error(f"Unexpected error updating profile: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/delete_schedule/<schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    if 'user' not in session:
        logger.warning("Unauthenticated access attempt to delete_schedule")
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        ref = db.reference(f"users/{session['user']['uid']}/schedules/{schedule_id}")
        ref.delete()
        logger.info(f"Schedule {schedule_id} deleted for user {session['user']['email']}")
        return jsonify({'success': True}), 200
    except firebase_admin.exceptions.FirebaseError as fe:
        logger.error(f"Firebase error deleting schedule {schedule_id}: {str(fe)}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    except Exception as e:
        logger.error(f"Unexpected error deleting schedule {schedule_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/email_schedule/<schedule_id>', methods=['POST'])
def email_schedule(schedule_id):
    if 'user' not in session:
        logger.warning("Unauthenticated access attempt to email_schedule")
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        uid = session['user']['uid']
        email = session['user']['email']
        ref = db.reference(f"users/{uid}/schedules/{schedule_id}")
        schedule = ref.get()
        if not schedule:
            logger.warning(f"Schedule not found: {schedule_id}")
            return jsonify({'success': False, 'error': 'Schedule not found'}), 404

        venues = schedule.get('venues', [])
        venues_html = ''
        for venue in venues:
            formatted_address = venue['location'].get('formattedAddress', ['N/A'])
            if isinstance(formatted_address, list):
                formatted_address = ', '.join(formatted_address)
            lat = venue['location'].get('lat')
            lng = venue['location'].get('lng')
            
            if formatted_address and isinstance(formatted_address, str) and formatted_address != 'N/A':
                maps_query = formatted_address
            elif lat is not None and lng is not None and isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                maps_query = f"{lat},{lng}"
            else:
                maps_query = venue.get('name', 'Unknown Location')
            try:
                maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(maps_query)}"
            except Exception as e:
                logger.warning(f"Failed to generate Maps URL for venue {venue.get('name', 'Unknown')}: {str(e)}")
                maps_url = "https://www.google.com/maps"

            rating = venue.get('rating', 'N/A')
            if rating != 'N/A' and isinstance(rating, (int, float)):
                rating = f"{rating:.1f}/10"

            price = venue.get('price', 'N/A')
            if price != 'N/A' and isinstance(price, int):
                price = '💲' * price

            website = venue.get('website', 'N/A')
            website_html = f'<a href="{website}" target="_blank">Visit Website</a>' if website != 'N/A' and isinstance(website, str) else 'N/A'

            venues_html += f"""
            <li style="margin-bottom: 20px;">
                <strong>{venue.get('name', 'Unknown')}</strong> ({venue.get('category', 'N/A')})<br>
                <strong>Address:</strong> {formatted_address}<br>
                <strong>Google Maps:</strong> <a href="{maps_url}" target="_blank">View on Google Maps</a><br>
                <strong>Coordinates:</strong> Lat: {lat if lat is not None else 'N/A'}, Lng: {lng if lng is not None else 'N/A'}<br>
                <strong>Scheduled Time:</strong> {venue.get('time', 'N/A')}<br>
                <strong>Rating:</strong> {rating}<br>
                <strong>Price:</strong> {price}<br>
                <strong>Website:</strong> {website_html}<br>
                <strong>Phone:</strong> {venue.get('phone', 'N/A')}<br>
                <strong>Hours:</strong> {venue.get('hours', 'N/A')}<br>
                <strong>Description:</strong> {venue.get('description', 'N/A')}<br>
            </li>
            """

        email_content = f"""
        <h2 style="color: #007bff;">Your Travel Schedule for {schedule['city'].capitalize()}</h2>
        <p><strong>City:</strong> {schedule['city'].capitalize()}</p>
        <p><strong>Date:</strong> {schedule['date']}</p>
        <p><strong>Time:</strong> {schedule['start_time']} - {schedule['end_time']}</p>
        <p><strong>Interests:</strong> {', '.join(schedule['interests']).capitalize()}</p>
        <h3>Locations:</h3>
        <ul style="list-style-type: none; padding-left: 0;">{venues_html}</ul>
        <p>Plan your trip with <strong>Smart City Traveller</strong>! For more details, visit your <a href="{url_for('dashboard', _external=True)}" style="color: #007bff;">dashboard</a>.</p>
        <p style="font-style: italic;">Best regards,<br>Smart City Traveller Team</p>
        """

        msg = Message(
            subject=f"Your Travel Schedule for {schedule['city'].capitalize()}",
            recipients=[email],
            html=email_content
        )
        mail.send(msg)
        logger.info(f"Schedule {schedule_id} emailed to {email} with detailed venue information")
        return jsonify({'success': True}), 200
    except firebase_admin.exceptions.FirebaseError as fe:
        logger.error(f"Firebase error emailing schedule {schedule_id}: {str(fe)}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    except Exception as e:
        logger.error(f"Unexpected error emailing schedule {schedule_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/delete_account', methods=['DELETE'])
def delete_account():
    if 'user' not in session:
        logger.warning("Unauthenticated arty to delete_account")
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        uid = session['user']['uid']
        email = session['user']['email']
        ref = db.reference(f"users/{uid}")
        ref.delete()
        try:
            auth.delete_user(uid)
            logger.info(f"Firebase Auth user deleted: {uid}")
        except Exception as auth_e:
            logger.warning(f"Failed to delete Firebase Auth user {uid}: {str(auth_e)}")
        session.clear()
        logger.info(f"Account deleted for user {email} (UID: {uid})")
        response = jsonify({'success': True})
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.set_cookie('session', '', expires=0)
        return response
    except firebase_admin.exceptions.FirebaseError as fe:
        logger.error(f"Firebase error deleting account: {str(fe)}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    except Exception as e:
        logger.error(f"Unexpected error deleting account: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to delete account. Please try again.'}), 500

@app.route('/logout')
def logout():
    user_email = session.get('user', {}).get('email', 'unknown')
    session.clear()
    flash('You have been logged out.', 'success')
    logger.info(f"User logged out: {user_email}")
    response = make_response(redirect(url_for('login')))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.set_cookie('session', '', expires=0)
    return response

@app.route('/send-email/<uid>')
def send_email(uid):
    if 'user' not in session:
        logger.warning("Unauthenticated access attempt to send-email")
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        recipient_email = get_user_email(uid)
        if not recipient_email:
            logger.warning(f"No email found for UID: {uid}")
            return jsonify({'success': False, 'error': 'No email found for user'}), 400

        msg = Message(
            subject='Hello from Smart City Traveller',
            recipients=[recipient_email],
            body='This is a test email sent from your Flask application!'
        )
        mail.send(msg)
        logger.info(f"Test email sent to {recipient_email} (UID: {uid})")
        return jsonify({'success': True, 'message': f'Email sent successfully to {recipient_email}!'}), 200
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/send-email')
def send_email_session():
    if 'user' not in session:
        logger.warning("Unauthenticated access attempt to send-email")
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        recipient_email = session['user']['email']
        if not recipient_email:
            logger.warning("No email found in session")
            return jsonify({'success': False, 'error': 'No email found for user'}), 400

        msg = Message(
            subject='Hello from Smart City Traveller',
            recipients=[recipient_email],
            body='This is a test email sent from your Flask application!'
        )
        mail.send(msg)
        logger.info(f"Test email sent to {recipient_email}")
        return jsonify({'success': True, 'message': f'Email sent successfully to {recipient_email}!'}), 200
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_ENV') == 'development')