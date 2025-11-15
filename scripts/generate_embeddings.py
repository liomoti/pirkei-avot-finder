"""
Script to generate and update embeddings for all Mishna texts in the database.

This script:
1. Loops over all Mishna records in the database
2. Takes the text_raw column
3. Generates 768-dimensional embeddings using AlephBERT model
4. Saves the vector in the embedding column

Usage:
    python scripts/generate_embeddings.py
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sentence_transformers import SentenceTransformer
from app import app
from models import db, Mishna

def generate_embeddings():
    """Loop over mishna table, embed text_raw, and save to embedding column."""
    
    print("Loading AlephBERT model...")
    model = SentenceTransformer('imvladikon/sentence-transformers-alephbert')
    print("Model loaded successfully!")
    
    with app.app_context():
        # Loop over all Mishna records
        mishnaiot = Mishna.query.all()
        total = len(mishnaiot)
        
        if total == 0:
            print("No Mishna records found in database.")
            return
        
        print(f"\nFound {total} Mishna records to process.")
        print("Generating embeddings...\n")
        
        updated_count = 0
        
        for i, mishna in enumerate(mishnaiot, 1):
            try:
                # Take text_raw column and embed it
                embedding_vector = model.encode(mishna.text_raw)
                
                # Save the vector in embedding column
                mishna.embedding = embedding_vector.tolist()
                
                print(f"[{i}/{total}] Mishna {mishna.id}: Embedded and saved")
                updated_count += 1
                
                # Commit every 10 records
                if updated_count % 10 == 0:
                    db.session.commit()
                    print(f"  → Committed {updated_count} updates to database")
                
            except Exception as e:
                print(f"[{i}/{total}] Mishna {mishna.id}: ERROR - {str(e)}")
                continue
        
        # Final commit for remaining records
        db.session.commit()
        print(f"  → Final commit completed")
        
        print(f"\n{'='*60}")
        print(f"Embedding generation complete!")
        print(f"  - Total updated: {updated_count} records")
        print(f"{'='*60}")

if __name__ == "__main__":
    generate_embeddings()
