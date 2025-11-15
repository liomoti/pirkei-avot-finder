import os

from flask import Flask
from flask_wtf.csrf import CSRFProtect
from models import db
from config import Config
from routes import main  # Import the routes blueprint
from logger import setup_logger

app = Flask(__name__)
app.config.from_object(Config)

# Set up logging
app = setup_logger(app)

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize the database
db.init_app(app)

# Register the blueprint
app.register_blueprint(main)

# Create database tables manually in the app context
# with app.app_context():
#     db.create_all()


if __name__ == '__main__':
    # app.run(debug=True)
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
