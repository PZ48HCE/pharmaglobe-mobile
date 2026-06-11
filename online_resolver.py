import requests
import urllib.parse

def fetch_wikipedia_summary(query):
    """
    Query Wikipedia API for a summary and image of a medicine/ingredient.
    Returns: dict with keys (name, generic_name, uses, image_url, shop_link) or None
    """
    if not query:
        return None
        
    # Format query (title case is preferred by Wikipedia)
    formatted_query = query.strip().title().replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{formatted_query}"
    
    headers = {
        "User-Agent": "PharmaGlobeMobile/1.0 (contact@pharmaglobe.org; Educational app)"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            # We want pages of type 'standard'
            if data.get("type") in ["standard", "preview"]:
                title = data.get("title")
                extract = data.get("extract")
                
                # Extract image
                image_url = None
                if "originalimage" in data:
                    image_url = data["originalimage"].get("source")
                elif "thumbnail" in data:
                    image_url = data["thumbnail"].get("source")
                    
                page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
                
                return {
                    "name": title,
                    "generic_name": title,
                    "category": "Global Medicine",
                    "uses": extract or "No description available on Wikipedia.",
                    "dosage": "Refer to local clinical guidelines or packaging.",
                    "warnings": "Consult a healthcare professional for side effects and drug interactions.",
                    "precautions": "Use under medical supervision.",
                    "price": "Online Database",
                    "shop_link": page_url or f"https://www.google.com/search?q={urllib.parse.quote(title)}",
                    "image_url": image_url,
                    "resolved_via": "Wikipedia API"
                }
    except Exception as e:
        print(f"Error querying Wikipedia: {e}")
        
    return None

def fetch_duckduckgo_abstract(query):
    """
    Query DuckDuckGo Instant Answer API for quick summaries of brand names.
    """
    if not query:
        return None
        
    escaped_query = urllib.parse.quote(query)
    url = f"https://api.duckduckgo.com/?q={escaped_query}&format=json&no_html=1"
    
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            abstract = data.get("Abstract")
            title = data.get("Heading")
            image = data.get("Image")
            
            # If DDG has a relative image path, expand it
            if image and image.startswith("/"):
                image = "https://duckduckgo.com" + image
                
            if abstract:
                return {
                    "name": title or query,
                    "generic_name": query,
                    "category": "General Health Topic",
                    "uses": abstract,
                    "dosage": "Check packaging for instructions.",
                    "warnings": "Consult a doctor for warnings.",
                    "precautions": "Follow guidelines on label.",
                    "price": "Search Index",
                    "shop_link": f"https://www.google.com/search?q={urllib.parse.quote(title or query)}",
                    "image_url": image,
                    "resolved_via": "DuckDuckGo API"
                }
    except Exception as e:
        print(f"Error querying DuckDuckGo: {e}")
        
    return None

def search_medicine_globally_online(name):
    """
    High-level online resolver pipeline.
    Tries Wikipedia summary, falls back to DuckDuckGo abstract,
    and returns a formatted medication details dict.
    """
    if not name:
        return None
        
    # Clean the name
    clean_name = name.strip()
    
    # Step 1: Try Wikipedia directly
    wiki_res = fetch_wikipedia_summary(clean_name)
    if wiki_res:
        return wiki_res
        
    # Step 2: Try DuckDuckGo
    ddg_res = fetch_duckduckgo_abstract(clean_name)
    if ddg_res:
        return ddg_res
        
    # Step 3: If no instant abstract found, try to resolve generic ingredient via DDG
    # E.g. search DDG for brand, see if it lists active ingredient
    return None
