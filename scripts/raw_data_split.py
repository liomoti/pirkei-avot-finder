import os
import re

# הגדרות שמות קבצים ותיקיות
input_filename = 'pirkei-avot-raw-text.txt'
output_folder = 'mishnayot_files'

# יצירת תיקיית הפלט אם אינה קיימת
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

def process_mishnayot():
    # קריאת תוכן הקובץ
    try:
        with open(input_filename, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"שגיאה: הקובץ {input_filename} לא נמצא בתיקייה.")
        return

    # פיצול לפי 2 שורות רווח (או יותר)
    # ה-Regex הזה תופס רצף של ירידות שורה עם רווחים ביניהן
    chunks = re.split(r'\n\s*\n', content.strip())

    mishnah_counter = 1

    for chunk in chunks:
        # ניקוי רווחים מיותרים בתחילה ובסוף
        clean_chunk = chunk.strip()
        
        if not clean_chunk:
            continue

        # לוגיקה להסרת הכותרת (עד הנקודותיים הראשון)
        # אנו מחפשים את המופע הראשון של ':' ומחזירים את הטקסט שאחריו
        if ':' in clean_chunk:
            # split(..., 1) מבטיח שנפצל רק בנקודותיים הראשונות
            # החלק ה-[0] הוא הכותרת, החלק ה-[1] הוא הטקסט הרצוי
            body_text = clean_chunk.split(':', 1)[1].strip()
        else:
            # במקרה נדיר שאין נקודותיים, משאירים את הטקסט כמו שהוא
            body_text = clean_chunk

        # אם לאחר הניקוי נשאר טקסט ריק, מדלגים
        if not body_text:
            continue

        # הגדרת שם הקובץ (1.txt, 2.txt...)
        output_filename = f"{mishnah_counter}.txt"
        output_path = os.path.join(output_folder, output_filename)

        # כתיבה לקובץ
        with open(output_path, 'w', encoding='utf-8') as out_f:
            out_f.write(body_text)

        print(f"נוצר: {output_filename}")
        mishnah_counter += 1

    print(f"\n✅ התהליך הסתיים. נוצרו {mishnah_counter - 1} קבצים בתיקייה '{output_folder}'.")

if __name__ == "__main__":
    process_mishnayot()