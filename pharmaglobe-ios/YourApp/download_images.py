import os
import sys
import requests
from io import BytesIO
from PIL import Image, ImageDraw

# Add current directory to path to import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import med_database

# Create images folder if not exists
os.makedirs("images", exist_ok=True)

print(f"Loaded {len(med_database.MEDICINE_DATABASE)} medicines from database.")

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def generate_placeholder(filename, name, category):
    cat_lower = category.lower()
    if "pain" in cat_lower:
        bg_color = (255, 235, 235)  # Soft red
        text_color = (255, 107, 107)
    elif "cold" in cat_lower or "cough" in cat_lower or "flu" in cat_lower:
        bg_color = (235, 245, 255)  # Soft blue
        text_color = (74, 144, 226)
    elif "digest" in cat_lower or "stomach" in cat_lower:
        bg_color = (235, 255, 235)  # Soft green
        text_color = (46, 204, 113)
    else:
        bg_color = (255, 250, 230)  # Soft yellow
        text_color = (241, 196, 15)
        
    img = Image.new('RGB', (200, 200), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Draw pill capsule shape in center
    draw.rounded_rectangle([60, 85, 140, 115], radius=15, fill=text_color)
    draw.line([100, 85, 100, 115], fill=bg_color, width=2)
    
    img.save(filename, "PNG")
    print(f"Generated pill placeholder for: {name}")

# Iterate and download
for idx, med in enumerate(med_database.MEDICINE_DATABASE):
    url = med.get("image_url", "")
    name = med.get("name", f"Medicine {idx}")
    cat = med.get("category", "General")
    
    local_filename = f"images/med_{idx}.png"
    
    downloaded = False
    if url and url.startswith("http"):
        print(f"[{idx+1}/{len(med_database.MEDICINE_DATABASE)}] Downloading {name} image...")
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                # Open with Pillow and convert/save as PNG
                img = Image.open(BytesIO(r.content))
                img.save(local_filename, "PNG")
                print(f"Success: Saved {name} image to {local_filename}")
                downloaded = True
            else:
                print(f"Warning: HTTP {r.status_code} for {name}")
        except Exception as e:
            print(f"Error downloading {name}: {e}")
            
    if not downloaded:
        generate_placeholder(local_filename, name, cat)
        
    # Update image_url in-memory to the local path
    med["image_url"] = local_filename

# Rewrite med_database.py
print("\nRewriting med_database.py with local image URLs...")

import pprint

database_str = pprint.pformat(med_database.MEDICINE_DATABASE, indent=2, width=120)

file_content = f"""# Curated Local Medicine Database for PharmaGlobe

MEDICINE_DATABASE = {database_str}

def get_countries():
    \"\"\"Returns unique list of countries in the database.\"\"\"
    return sorted(list(set(med["country"] for med in MEDICINE_DATABASE)))

def get_categories(country=None):
    \"\"\"Returns unique list of categories, optionally filtered by country.\"\"\"
    if country:
        return sorted(list(set(med["category"] for med in MEDICINE_DATABASE if med["country"] == country)))
    return sorted(list(set(med["category"] for med in MEDICINE_DATABASE)))

def get_medicines_by_filters(country=None, category=None):
    \"\"\"Filter medicines by country and/or category.\"\"\"
    results = MEDICINE_DATABASE
    if country:
        results = [med for med in results if med["country"].lower() == country.lower()]
    if category:
        results = [med for med in results if med["category"].lower() == category.lower()]
    return results

def search_local_medicines(query):
    \"\"\"Search local database for medicine matching query in name, generic_name, uses, or category.\"\"\"
    if not query:
        return []
    query = query.lower()
    results = []
    for med in MEDICINE_DATABASE:
        if (query in med["name"].lower() or 
            query in med["generic_name"].lower() or 
            query in med["category"].lower() or 
            any(query in use.lower() for use in med["uses"])):
            results.append(med)
    return results
"""

with open("med_database.py", "w", encoding="utf-8") as f:
    f.write(file_content)

print("med_database.py updated successfully!")
