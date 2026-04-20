from flask import Flask
from database import db
import my_routes  # 🚀 NAYA NAAM (ताकि कोई टकराव न हो)

app = Flask(__name__)

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///btm_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Data & Routes
db.init_app(app)
my_routes.init_app(app)  # 🚀 NAYA NAAM

if __name__ == '__main__':
    with app.app_context():
        # Creates database tables if they don't exist
        db.create_all()
        
    print("🚀 BTM Pro Server Started! Running Modulated Architecture.")
    app.run(host='0.0.0.0', port=5000)
