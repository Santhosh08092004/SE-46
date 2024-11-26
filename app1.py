from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file
import uuid
from datetime import datetime
import qrcode
from io import BytesIO
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import os


app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Event venues and their details
VENUES = {
    'conference': {
        'Chennai Trade Centre': {'capacity': 2000, 'cost': 100000},
        'ITC Grand Chola': {'capacity': 1000, 'cost': 150000},
        'Chennai Convention Centre': {'capacity': 1500, 'cost': 120000}
    },
    'cultural': {
        'VGP Golden Beach Resort': {'capacity': 3000, 'cost': 200000},
        'Mayor Ramanathan Centre': {'capacity': 1000, 'cost': 80000},
        'Kamarajar Arangam': {'capacity': 2500, 'cost': 150000}
    },
    'exhibition': {
        'Express Avenue Convention Hall': {'capacity': 1000, 'cost': 100000},
        'Chennai Trade Centre': {'capacity': 5000, 'cost': 250000},
        'Chennai Convention Centre': {'capacity': 2000, 'cost': 120000}
    }
}

def init_db():
    conn = sqlite3.connect('event_management.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL
    )
    ''')
    
    # Create events table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        date TEXT NOT NULL,
        location TEXT NOT NULL,
        capacity INTEGER NOT NULL,
        ticket_price REAL NOT NULL,
        creator_id INTEGER,
        FOREIGN KEY (creator_id) REFERENCES users (id)
    )
    ''')
    
    # Create tickets table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER,
        user_id INTEGER,
        ticket_number TEXT UNIQUE NOT NULL,
        purchase_date TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    conn.commit()
    conn.close()
    
    # Create sample events
    create_sample_events()

def create_sample_events():
    conn = sqlite3.connect('event_management.db')
    cursor = conn.cursor()
    
    # Sample events data
    sample_events = [
        ('Tech Summit 2024', 'conference', '2024-12-15', 'Chennai Trade Centre', 500, 1500, 1),
        ('Music Festival', 'cultural', '2024-12-20', 'VGP Golden Beach Resort', 2000, 999, 1),
        ('Art Exhibition', 'exhibition', '2024-12-25', 'Express Avenue Convention Hall', 300, 750, 1),
        ('Gaming Convention', 'conference', '2024-12-28', 'ITC Grand Chola', 1000, 1200, 1),
        ('Dance Festival', 'cultural', '2024-12-30', 'Mayor Ramanathan Centre', 800, 850, 1),
        ('Science Expo', 'exhibition', '2025-01-05', 'Chennai Convention Centre', 600, 500, 1)
    ]
    
    # Check if events exist
    cursor.execute('SELECT COUNT(*) FROM events')
    if cursor.fetchone()[0] == 0:
        # Create default admin user if not exists
        cursor.execute('SELECT id FROM users WHERE username = ?', ('admin',))
        admin = cursor.fetchone()
        if not admin:
            hashed_password = generate_password_hash('admin123')
            cursor.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)',
                         ('admin', hashed_password, 'admin@example.com'))
            admin_id = cursor.lastrowid
        else:
            admin_id = admin[0]
        
        # Insert sample events
        for event in sample_events:
            cursor.execute('''
                INSERT INTO events (name, type, date, location, capacity, ticket_price, creator_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', event)
            
        conn.commit()
    conn.close()

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('event_management.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, password FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['username'] = username
            # Reset chat session
            session.pop('chat_history', None)
            session.pop('chat_step', None)
            session.pop('event_list', None)
            session.pop('selected_event', None)
            session.pop('event_data', None)
            session.pop('suggested_venue', None)
            flash('Login successful!')
            return redirect(url_for('home'))
        
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        if not all([username, password, email]):
            flash('Please fill all fields')
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password)
        
        conn = sqlite3.connect('event_management.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)',
                         (username, hashed_password, email))
            conn.commit()
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists')
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('event_management.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM events ORDER BY date ASC')
    events = cursor.fetchall()
    conn.close()
    
    return render_template('home.html', events=events)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('event_management.db')
    cursor = conn.cursor()
    
    # Get user's tickets with all necessary information
    cursor.execute('''
        SELECT t.id, t.ticket_number, t.purchase_date, e.name, e.date, e.location
        FROM tickets t
        JOIN events e ON t.event_id = e.id
        WHERE t.user_id = ?
        ORDER BY t.purchase_date DESC
    ''', (session['user_id'],))
    tickets = cursor.fetchall()
    
    # Get event counts
    cursor.execute('SELECT COUNT(*) FROM tickets WHERE user_id = ?', (session['user_id'],))
    registered_events = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM events WHERE creator_id = ?', (session['user_id'],))
    created_events = cursor.fetchone()[0]
    
    conn.close()
    
    user_events = {
        'registered': registered_events,
        'created': created_events
    }
    
    return render_template('profile.html', 
                         user_events=user_events, 
                         tickets=tickets)

@app.route('/download_ticket/<int:ticket_id>')
def download_ticket(ticket_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = sqlite3.connect('event_management.db')
        cursor = conn.cursor()
        
        # Get ticket and event details
        cursor.execute('''
            SELECT t.ticket_number, t.purchase_date, e.name, e.date, e.location, e.ticket_price
            FROM tickets t
            JOIN events e ON t.event_id = e.id
            WHERE t.id = ? AND t.user_id = ?
        ''', (ticket_id, session['user_id']))
        
        ticket = cursor.fetchone()
        conn.close()
        
        if not ticket:
            flash('Ticket not found')
            return redirect(url_for('profile'))

        # Create PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        # Add fancy header
        p.setFont("Helvetica-Bold", 24)
        p.drawString(100, 750, "EVENT TICKET")
        
        # Add event details
        p.setFont("Helvetica", 14)
        y_position = 700
        
        details = [
            ("Event Name", ticket[2]),
            ("Event Date", ticket[3]),
            ("Location", ticket[4]),
            ("Ticket Number", ticket[0]),
            ("Purchase Date", ticket[1]),
            ("Price", f"₹{ticket[5]}")
        ]
        
        for label, value in details:
            p.drawString(100, y_position, f"{label}:")
            p.drawString(250, y_position, str(value))
            y_position -= 30
        
        # Add QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(f"Ticket: {ticket[0]}\nEvent: {ticket[2]}")
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white")
        # Save QR code to a temporary file
        qr_img_path = f"temp_qr_{ticket_id}.png"
        qr_img.save(qr_img_path)
        
        # Add QR code to PDF
        p.drawImage(qr_img_path, 100, 350, width=200, height=200)
        
        # Remove temporary QR code file
        os.remove(qr_img_path)
        
        # Add footer
        p.setFont("Helvetica-Italic", 10)
        p.drawString(100, 200, "This ticket is valid for one-time entry only.")
        p.drawString(100, 180, "Please present this ticket at the venue entrance.")
        
        # Add border
        p.rect(50, 50, 500, 750)
        
        p.save()
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'Ticket_{ticket[0]}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error generating ticket: {str(e)}")  # For debugging
        flash('Error generating ticket. Please try again.')
        return redirect(url_for('profile'))

@app.route('/create_event', methods=['POST'])
def create_event():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'})
    
    data = request.json
    name = data.get('name')
    event_type = data.get('type')
    date = data.get('date')
    location = data.get('location')
    capacity = data.get('capacity')
    ticket_price = data.get('ticket_price')
    
    if not all([name, event_type, date, location, capacity, ticket_price]):
        return jsonify({'error': 'All fields are required'})
    
    conn = sqlite3.connect('event_management.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO events (name, type, date, location, capacity, ticket_price, creator_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, event_type, date, location, capacity, ticket_price, session['user_id']))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Event created successfully!'})
    except sqlite3.Error as e:
        return jsonify({'error': f'Database error: {str(e)}'})
    finally:
        conn.close()

def calculate_event_cost(event_type, capacity):
    if event_type not in VENUES:
        return None
    
    suitable_venues = []
    for venue, details in VENUES[event_type].items():
        if details['capacity'] >= capacity:
            suitable_venues.append((venue, details))
    
    if not suitable_venues:
        return None
    
    # Sort venues by cost and get the cheapest suitable venue
    venue, details = sorted(suitable_venues, key=lambda x: x[1]['cost'])[0]
    
    # Calculate costs
    venue_cost = details['cost']
    setup_cost = 50000  # Base setup cost
    staff_cost = (capacity // 50) * 2000  # One staff per 50 attendees
    
    return {
        'venue': venue,
        'venue_cost': venue_cost,
        'setup_cost': setup_cost,
        'staff_cost': staff_cost,
        'total_cost': venue_cost + setup_cost + staff_cost
    }

@app.route('/logout')
def logout():
    # Clear all session data
    session.clear()
    flash('You have been logged out successfully.')
    return redirect(url_for('login'))

# Error handlers

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# Optional: Add a catch-all error handler
@app.errorhandler(Exception)
def handle_exception(e):
    # Log the error if you have logging configured
    app.logger.error(f"Unhandled exception: {str(e)}")
    return render_template('500.html'), 500

@app.route('/chatbot')
def chatbot():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Reset chat session when starting new chat
    session.pop('chat_history', None)
    session.pop('chat_step', None)
    session.pop('event_list', None)
    session.pop('selected_event', None)
    session.pop('event_data', None)
    session.pop('suggested_venue', None)
    
    session['chat_history'] = []
    session['chat_step'] = 0
    
    return render_template('chatbot.html', 
                         chat_history=session['chat_history'],
                         buttons=['Participate', 'Arrange'])

@app.route('/restart_chat')  # Using a different name to avoid confusion
def restart_chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('chatbot')) 

@app.route('/reset_chat')
def reset_chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Reset all chat-related session data
    session.pop('chat_history', None)
    session.pop('chat_step', None)
    session.pop('event_list', None)
    session.pop('selected_event', None)
    session.pop('event_data', None)
    session.pop('suggested_venue', None)
    
    # Start fresh chat session
    session['chat_history'] = []
    session['chat_step'] = 0
    
    return redirect(url_for('chatbot'))

@app.route('/chatbot_response', methods=['POST'])
def chatbot_response():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    message = request.form.get('message', '').strip()
    step = session.get('chat_step', 0)
    
    # Store user message in chat history
    if 'chat_history' not in session:
        session['chat_history'] = []
    session['chat_history'].append(('user', message))

    response = ""
    buttons = []

    if step == 0:  # Initial choice
        if message.lower() == 'participate':
            conn = sqlite3.connect('event_management.db')
            cursor = conn.cursor()
            cursor.execute('SELECT id, name, date, location, ticket_price FROM events')
            events = cursor.fetchall()
            conn.close()
            
            response = "Here are the available events:"
            buttons = [f"{event[1]} - ₹{event[4]}" for event in events]
            session['event_list'] = events
            session['chat_step'] = 1
            
        elif message.lower() == 'arrange':
            response = "Please enter the name of your event:"
            session['chat_step'] = 10
            session['event_data'] = {}
            
        else:
            response = "Welcome! Would you like to participate in an event or arrange one?"
            buttons = ['Participate', 'Arrange']

    elif step == 1:  # Event selection for participation
        events = session.get('event_list', [])
        selected_event = None
        for event in events:
            if message.startswith(event[1]):  # Match event name
                selected_event = event
                break
                
        if selected_event:
            session['selected_event'] = selected_event
            response = f"""Event Details:
Name: {selected_event[1]}
Location: {selected_event[3]}
Date: {selected_event[2]}
Price: ₹{selected_event[4]}

Would you like to book tickets for this event?"""
            buttons = ['Yes', 'No']
            session['chat_step'] = 2
        else:
            response = "Please select a valid event:"
            buttons = [f"{event[1]} - ₹{event[4]}" for event in events]

    elif step == 2:  # Booking confirmation
        if message.lower() == 'yes':
            response = "How many tickets would you like to book?"
            session['chat_step'] = 3
        else:
            response = "No problem! Would you like to check other events?"
            buttons = ['Participate', 'Arrange']
            session['chat_step'] = 0

    elif step == 3:  # Number of tickets
        try:
            num_tickets = int(message)
            if num_tickets <= 0:
                response = "Please enter a valid number of tickets."
            else:
                event = session['selected_event']
                total_price = num_tickets * event[4]
                session['num_tickets'] = num_tickets
                session['total_price'] = total_price
                response = f"Total amount for {num_tickets} tickets: ₹{total_price}\nWould you like to proceed with payment?"
                buttons = ['Proceed to Payment', 'Cancel']
                session['chat_step'] = 4
        except ValueError:
            response = "Please enter a valid number."

    elif step == 4:  # Payment processing
        if message.lower() == 'proceed to payment' or message.lower() == 'proceed':
            event = session['selected_event']
            num_tickets = session['num_tickets']
            
            conn = sqlite3.connect('event_management.db')
            cursor = conn.cursor()
            
            try:
                # Check if enough tickets are available
                cursor.execute('SELECT capacity FROM events WHERE id = ?', (event[0],))
                capacity = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM tickets WHERE event_id = ?', (event[0],))
                sold_tickets = cursor.fetchone()[0]
                
                if sold_tickets + num_tickets > capacity:
                    response = "Sorry, not enough tickets available for this event."
                    buttons = ['Check Other Events', 'Exit']
                    session['chat_step'] = 0
                else:
                    # Generate tickets
                    for _ in range(num_tickets):
                        ticket_number = f"TICKET-{uuid.uuid4().hex[:8]}"
                        cursor.execute('''
                            INSERT INTO tickets (event_id, user_id, ticket_number, purchase_date)
                            VALUES (?, ?, ?, ?)
                        ''', (event[0], session['user_id'], ticket_number, 
                             datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    
                    conn.commit()
                    response = "Payment successful! Your tickets have been generated."
                    buttons = ['View Tickets in Profile', 'Book Another Event']
                    session['chat_step'] = 5
            except sqlite3.Error as e:
                response = "There was an error processing your payment. Please try again."
                buttons = ['Try Again', 'Cancel']
            finally:
                conn.close()
        else:
            response = "Booking cancelled. What would you like to do?"
            buttons = ['Participate', 'Arrange']
            session['chat_step'] = 0

    elif step == 5:  # Post-payment options
        if message == 'View Tickets in Profile':
            return redirect(url_for('profile'))
        elif message == 'Book Another Event':
            response = "Would you like to participate in an event or arrange one?"
            buttons = ['Participate', 'Arrange']
            session['chat_step'] = 0

    # Arrange event flow
    elif step == 10:  # Event name input
        session['event_data']['name'] = message
        response = "Please enter the date of the event (YYYY-MM-DD):"
        session['chat_step'] = 11

    elif step == 11:  # Event date input
        if validate_date(message):
            session['event_data']['date'] = message
            response = "Please select the event type:"
            buttons = ['conference', 'cultural', 'exhibition']
            session['chat_step'] = 12
        else:
            response = "Please enter a valid future date in YYYY-MM-DD format:"

    elif step == 12:  # Event type selection
        if message.lower() in ['conference', 'cultural', 'exhibition']:
            session['event_data']['type'] = message.lower()
            response = "Please enter the expected number of people:"
            session['chat_step'] = 13
        else:
            response = "Please select a valid event type:"
            buttons = ['conference', 'cultural', 'exhibition']

    elif step == 13:  # Capacity input
        try:
            capacity = int(message)
            if capacity > 0:
                session['event_data']['capacity'] = capacity
                response = "Please enter the ticket price per person:"
                session['chat_step'] = 14
            else:
                response = "Please enter a valid number greater than 0:"
        except ValueError:
            response = "Please enter a valid number:"

    elif step == 14:  # Ticket price input
        try:
            price = float(message)
            if price > 0:
                session['event_data']['ticket_price'] = price
                suggested_venue = suggest_venue(session['event_data'])
                session['suggested_venue'] = suggested_venue
                response = f"""Based on your requirements:
Venue: {suggested_venue['name']}
Setup Cost: ₹{suggested_venue['setup_cost']}
Total Cost: ₹{suggested_venue['total_cost']}

Would you like to proceed with these arrangements?"""
                buttons = ['Accept', 'Negotiate']
                session['chat_step'] = 15
            else:
                response = "Please enter a valid price greater than 0:"
        except ValueError:
            response = "Please enter a valid price:"

    elif step == 15:  # Venue confirmation
        if message.lower() == 'accept':
            data = session['event_data']
            venue = session['suggested_venue']
            
            conn = sqlite3.connect('event_management.db')
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO events (name, type, date, location, capacity, ticket_price, creator_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (data['name'], data['type'], data['date'], venue['name'], 
                     data['capacity'], data['ticket_price'], session['user_id']))
                conn.commit()
                response = "Great! Your event has been created successfully! You can view it on the home page."
                buttons = ['Create Another Event', 'Exit']
                session['chat_step'] = 0
            except:
                response = "There was an error creating your event. Please try again."
            finally:
                conn.close()
        
        elif message.lower() == 'negotiate':
            venue = session['suggested_venue']
            reduced_cost = venue['total_cost'] * 0.95  # 5% reduction
            venue['total_cost'] = reduced_cost
            venue['name'] = get_alternate_venue(session['event_data']['type'])
            session['suggested_venue'] = venue
            
            response = f"""Revised offer:
Venue: {venue['name']}
Total Cost: ₹{reduced_cost}

Would you like to proceed with these arrangements?"""
            buttons = ['Accept', 'Exit']

    # Store bot response in chat history
    session['chat_history'].append(('bot', response))
    session.modified = True

    return render_template(
        'chatbot.html',
        chat_history=session['chat_history'],
        buttons=buttons
    )

def validate_date(date_str):
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        return date > datetime.now()
    except:
        return False

def suggest_venue(event_data):
    event_type = event_data['type']
    capacity = event_data['capacity']
    
    base_cost = {
        'conference': 100000,
        'cultural': 150000,
        'exhibition': 200000
    }
    
    setup_cost = base_cost[event_type]
    total_cost = setup_cost + (capacity * 100)  # ₹100 per person
    
    venues = {
        'conference': ['Chennai Trade Centre', 'ITC Grand Chola', 'Chennai Convention Centre'],
        'cultural': ['VGP Golden Beach Resort', 'Mayor Ramanathan Centre', 'Kamarajar Arangam'],
        'exhibition': ['Express Avenue Convention Hall', 'Chennai Trade Centre', 'Chennai Convention Centre']
    }
    
    return {
        'name': venues[event_type][0],
        'setup_cost': setup_cost,
        'total_cost': total_cost
    }

def get_alternate_venue(event_type):
    venues = {
        'conference': ['ITC Grand Chola', 'Chennai Convention Centre'],
        'cultural': ['Mayor Ramanathan Centre', 'Kamarajar Arangam'],
        'exhibition': ['Chennai Trade Centre', 'Chennai Convention Centre']
    }
    return venues[event_type][0]

# Initialize the database when the app starts
if __name__ == '__main__':
    # Create the database file if it doesn't exist
    if not os.path.exists('event_management.db'):
        init_db()
    app.run(debug=True)