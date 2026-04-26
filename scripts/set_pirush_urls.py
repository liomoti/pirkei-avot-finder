"""
One-time script: set pirush_url for mishna numbers 3–32
using S3 bucket URLs (https://pirkei-avot-pirush.s3.us-east-2.amazonaws.com/{number}.pdf).

Run from project root:
    source venv/bin/activate
    python scripts/set_pirush_urls.py
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

S3_BASE = 'https://pirkei-avot-pirush.s3.us-east-2.amazonaws.com'
MISHNA_RANGE = range(3, 33)  # 3 to 32 inclusive

def main():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print('ERROR: DATABASE_URL not set in .env')
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    updated = 0
    for number in MISHNA_RANGE:
        url = f'{S3_BASE}/{number}.pdf'
        cur.execute(
            'UPDATE mishna SET pirush_url = %s WHERE number = %s',
            (url, number)
        )
        if cur.rowcount:
            print(f'  mishna {number:>3} → {url}')
            updated += cur.rowcount
        else:
            print(f'  mishna {number:>3} → NOT FOUND (skipped)')

    conn.commit()
    cur.close()
    conn.close()
    print(f'\nDone. {updated} rows updated.')

if __name__ == '__main__':
    main()
