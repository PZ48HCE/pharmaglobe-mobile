import requests
import urllib.parse
import os

BASE_URL = "https://api.fda.gov/drug"

# Read FDA_API_KEY from environment or .env if available
# Keep in mind we do not print/log this key
FDA_API_KEY = os.environ.get("FDA_API_KEY", "")

def _build_url(endpoint, search_query, limit=1):
    """Build the OpenFDA API URL with appropriate query parameters."""
    query = f"search={search_query}&limit={limit}"
    if FDA_API_KEY:
        query += f"&api_key={FDA_API_KEY}"
    return f"{BASE_URL}/{endpoint}.json?{query}"

def parse_label_result(result):
    """Safely parse OpenFDA drug label response details."""
    openfda = result.get("openfda", {})
    
    # Extract names
    brand_names = openfda.get("brand_name", [])
    brand_name = brand_names[0] if brand_names else "Unknown Brand"
    
    generic_names = openfda.get("generic_name", [])
    generic_name = generic_names[0] if generic_names else "Unknown Generic"
    
    manufacturers = openfda.get("manufacturer_name", [])
    manufacturer = manufacturers[0] if manufacturers else "Unknown Manufacturer"
    
    # Helper to join text blocks
    def get_field_text(field_name):
        field = result.get(field_name, [])
        if isinstance(field, list):
            return "\n\n".join(field)
        return str(field)
    
    # Extract medical details
    uses = get_field_text("indications_and_usage") or get_field_text("purpose")
    warnings = get_field_text("warnings") or get_field_text("warnings_and_cautions")
    dosage = get_field_text("dosage_and_administration")
    active_ingredients = get_field_text("active_ingredient")
    inactive_ingredients = get_field_text("inactive_ingredient")
    precautions = get_field_text("precautions") or get_field_text("pregnancy_or_breast_feeding")
    
    return {
        "brand_name": brand_name,
        "generic_name": generic_name,
        "manufacturer": manufacturer,
        "uses": uses or "No standard usage information available.",
        "warnings": warnings or "No warnings listed in database.",
        "dosage": dosage or "No specific dosage guidelines listed.",
        "active_ingredients": active_ingredients or generic_name,
        "inactive_ingredients": inactive_ingredients or "Not specified.",
        "precautions": precautions or "No specific precautions listed.",
        "route": ", ".join(openfda.get("route", ["oral"])),
        "product_type": ", ".join(openfda.get("product_type", ["human over the counter drug"]))
    }

def search_openfda_by_name(name, limit=3):
    """Search OpenFDA for drug details by name (brand name, generic, or active ingredient)."""
    if not name:
        return []
    
    # Construct search query
    # E.g. openfda.brand_name:"aspirin" OR openfda.generic_name:"aspirin"
    escaped_name = urllib.parse.quote(f'"{name}"')
    search_query = f'openfda.brand_name:{escaped_name}+OR+openfda.generic_name:{escaped_name}+OR+active_ingredient:{escaped_name}'
    url = _build_url("label", search_query, limit=limit)
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            return [parse_label_result(r) for r in results]
        return []
    except Exception as e:
        print(f"Error querying OpenFDA by name: {e}")
        return []

def search_openfda_by_upc(upc):
    """Search OpenFDA by UPC barcode identifier."""
    if not upc:
        return None
    
    # Strip any spaces or hyphens from UPC
    upc_clean = upc.replace(" ", "").replace("-", "")
    
    # Step 1: Query the label endpoint directly by UPC
    search_query = f'openfda.upc:"{upc_clean}"'
    url = _build_url("label", search_query, limit=1)
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results:
                return parse_label_result(results[0])
    except Exception as e:
        print(f"Error querying OpenFDA label by UPC: {e}")
        
    # Step 2: Fallback query on the NDC (National Drug Code) directory endpoint
    # Sometimes products are indexed in NDC search but label records aren't directly linked by UPC
    url_ndc = _build_url("ndc", search_query, limit=1)
    try:
        response = requests.get(url_ndc, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results:
                ndc_result = results[0]
                # Get brand or generic name from NDC and search label endpoint
                brand_name = ndc_result.get("brand_name")
                generic_name = ndc_result.get("generic_name")
                
                search_term = brand_name or generic_name
                if search_term:
                    label_results = search_openfda_by_name(search_term, limit=1)
                    if label_results:
                        return label_results[0]
    except Exception as e:
        print(f"Error querying OpenFDA NDC by UPC: {e}")
        
    return None
