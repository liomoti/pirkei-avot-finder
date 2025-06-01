from flask import Flask
from models import Mishna, db
from config import Config
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# Use the same configuration as the main app
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app

# Load the model
model = SentenceTransformer('imvladikon/sentence-transformers-alephbert')

app = create_app()

with app.app_context():
    # Fetch mishnaiot without embeddings
    mishnayot = Mishna.query.filter(Mishna.embedding == None).all()
    # mishnayot = Mishna.query.all()
    print(f"Found {len(mishnayot)} mishnaiot without embedding")

    for mishna in tqdm(mishnayot, desc="Generating embeddings"):
        embedding = model.encode(mishna.text_raw).tolist()
        mishna.embedding = embedding

    db.session.commit()
    print("✅ Finished successfully")