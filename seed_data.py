from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///btm_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 1. Tournament Table 
class Tournament(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(100))
    status = db.Column(db.String(20), default="Upcoming") 

# 2. Player Table (सिर्फ खिलाड़ियों की बेसिक डिटेल्स और रेस्ट टाइम)
class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    state_or_college = db.Column(db.String(100)) 
    rest_until = db.Column(db.DateTime, nullable=True) 

# 3. NEW: Team / Entry Table (सिंगल्स और डबल्स दोनों को हैंडल करने के लिए)
class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=False)
    event_category = db.Column(db.String(50)) # e.g., "Men's Singles", "Men's Doubles"
    
    # सिंगल्स में सिर्फ player1_id में डेटा होगा, player2_id खाली (NULL) रहेगा
    # डबल्स में दोनों में डेटा होगा
    player1_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    player2_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=True)

# 4. Match Table (अब यह Player की जगह सीधे Team से जुड़ेगी)
class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=False)
    category = db.Column(db.String(50)) 
    stage = db.Column(db.String(50)) 
    match_number = db.Column(db.Integer) 
    
    # अब खिलाड़ियों की जगह टीम्स आपस में भिड़ेंगी
    team1_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    team2_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    
    court_number = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default="Pending") 
    
    scheduled_time = db.Column(db.DateTime, nullable=True)
    actual_start_time = db.Column(db.DateTime, nullable=True)
    actual_end_time = db.Column(db.DateTime, nullable=True)
    
    # रिज़ल्ट्स भी अब सीधे टीम के नाम सेव होंगे
    winner_team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    final_score = db.Column(db.String(50)) 

if __name__ == '__main__':
    with app.app_context():
        db.create_all() 
        print("BTM 2.0 Database Created: Singles & Doubles Logic Updated! 🏸🔥")
