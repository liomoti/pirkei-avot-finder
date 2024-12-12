from flask import Flask
from models import db
from config import Config
from routes import main  # Import the routes blueprint
from logger import setup_logger


def create_app():
    flask_app = Flask(__name__)
    flask_app.config.from_object(Config)

    # Set up logging
    flask_app = setup_logger(flask_app)

    # Initialize the database
    db.init_app(flask_app)

    # Register the blueprint
    flask_app.register_blueprint(main)

    # Optional: Uncomment if you need to create tables on first deployment
    # with app.app_context():
    #     db.create_all()

    return flask_app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
