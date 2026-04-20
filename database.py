from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10))
    state = db.Column(db.String(50))         
    dob = db.Column(db.String(20))           
    category = db.Column(db.String(50))      
    partner_name = db.Column(db.String(100)) 
    rank = db.Column(db.Integer, default=0)         
    seed = db.Column(db.Integer, default=0)         
    draw_type = db.Column(db.String(20), default="Main") 
    is_playing = db.Column(db.Boolean, default=False)
    rest_until = db.Column(db.DateTime, nullable=True)

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player1_id = db.Column(db.Integer, db.ForeignKey('player.id'))

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_no = db.Column(db.Integer, default=0)
    round_no = db.Column(db.Integer, default=1)
    category = db.Column(db.String(50))
    draw_type = db.Column(db.String(50), default="Main")
    team1_id = db.Column(db.Integer, db.ForeignKey('team.id'))
    team2_id = db.Column(db.Integer, db.ForeignKey('team.id'))
    team1_score = db.Column(db.Integer, default=0)
    team2_score = db.Column(db.Integer, default=0)
    score_history = db.Column(db.String(200), default="")
    court_number = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default="Pending")
    winner_id = db.Column(db.Integer, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True) # 🚀 NAYA COLUMN: Time track karne ke liye

class Ranking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    category = db.Column(db.String(50))
    points = db.Column(db.Integer, default=0)
    tournaments_played = db.Column(db.Integer, default=0)
    
    # Player ke sath relationship taaki hum ranking table me player ka naam dikha sakein
    player = db.relationship('Player', backref=db.backref('rankings', lazy=True))
