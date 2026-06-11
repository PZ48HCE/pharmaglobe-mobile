import requests
from PIL import Image
import openfda_helper
import med_database

def decode_barcode(pil_image):
    """
    Decodes barcode or QR code from a PIL image using OpenCV.
    Returns: (decoded_value, code_type) or (None, None)
    """
    try:
        import cv2
        import numpy as np
        # Convert PIL Image to BGR numpy array for OpenCV
        img_rgb = np.array(pil_image.convert("RGB"))
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        
        # Try OpenCV Barcode Detector first
        if hasattr(cv2, 'barcode'):
            try:
                detector = cv2.barcode.BarcodeDetector()
                retval, decoded_info, decoded_type, points = detector.detectAndDecode(img_bgr)
                if retval and decoded_info:
                    for info, code_type in zip(decoded_info, decoded_type):
                        if info.strip():
                            return info.strip(), code_type
            except Exception as e:
                print(f"OpenCV BarcodeDetector error: {e}")
                
        # Try standard QR Code Detector as a fallback
        try:
            qr_detector = cv2.QRCodeDetector()
            retval, points, straight_qrcode = qr_detector.detectAndDecode(img_bgr)
            if retval and retval.strip():
                return retval.strip(), "QRCODE"
        except Exception as e:
            print(f"OpenCV QRCodeDetector error: {e}")
            
        # Try generic image processing (grayscale + threshold) to help OpenCV read blurry barcodes
        try:
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            # Resize image to make barcode larger if it's too small
            resized = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            
            if hasattr(cv2, 'barcode'):
                detector = cv2.barcode.BarcodeDetector()
                retval, decoded_info, decoded_type, points = detector.detectAndDecode(resized)
                if retval and decoded_info:
                    for info, code_type in zip(decoded_info, decoded_type):
                        if info.strip():
                            return info.strip(), code_type
        except Exception as e:
            print(f"OpenCV Preprocessing + BarcodeDetector error: {e}")

    except Exception as e:
        print(f"General barcode decoding error: {e}")
        
    return None, None

def lookup_barcode_in_databases(barcode):
    """
    Resolve a barcode number (UPC/EAN) to medicine/product information.
    Pipes search through:
      1. OpenFDA barcode query
      2. Local Database matching
      3. UPCitemdb lookup (global product database)
      4. Fallback search query mapping
    Returns: dict of product details, or None if completely unresolved.
    """
    if not barcode:
        return None
    
    # 1. Search OpenFDA by barcode directly
    fda_result = openfda_helper.search_openfda_by_upc(barcode)
    if fda_result:
        fda_result["resolved_via"] = "OpenFDA Direct Barcode"
        return fda_result
        
    # 2. Query UPCitemdb trial API for product catalog resolution
    upc_clean = barcode.strip().lstrip('0')  # Some databases index without leading zeros
    upc_candidates = [barcode.strip(), upc_clean]
    
    product_name = None
    brand = None
    upc_metadata = None
    
    for u in upc_candidates:
        url = f"https://api.upcitemdb.com/prod/trial/lookup?upc={u}"
        try:
            res = requests.get(url, timeout=8)
            if res.status_code == 200:
                data = res.json()
                items = data.get("items", [])
                if items:
                    item = items[0]
                    product_name = item.get("title")
                    brand = item.get("brand")
                    images = item.get("images", [])
                    image_url = images[0] if images else None
                    upc_metadata = {
                        "brand_name": brand or "Unknown",
                        "generic_name": product_name or "Unknown Product",
                        "manufacturer": item.get("publisher") or brand or "Unknown",
                        "uses": item.get("description") or "Global consumer product registry search.",
                        "warnings": "Always check product packaging for local warnings and guidelines.",
                        "dosage": "Refer to packaging for dosage details.",
                        "active_ingredients": "Not specified in general product registry.",
                        "inactive_ingredients": "Not specified.",
                        "precautions": "Use as directed on the label.",
                        "route": "topical / oral / general",
                        "product_type": item.get("category") or "OTC Product",
                        "price": f"Avg: {item.get('lowest_recorded_price', '')} - {item.get('highest_recorded_price', '')}" if item.get('lowest_recorded_price') else "Price varies",
                        "shop_link": f"https://www.google.com/search?q={urllib.parse.quote(product_name)}" if product_name else "",
                        "image_url": image_url
                    }
                    break
        except Exception as e:
            print(f"Error querying UPCitemdb: {e}")
            
    # 3. Check if the product name resolves to a local medicine in our curated DB
    if product_name:
        # Try to match local medicine database using brand or product title
        local_matches = med_database.search_local_medicines(product_name)
        if not local_matches and brand:
            local_matches = med_database.search_local_medicines(brand)
            
        if local_matches:
            match = local_matches[0]
            match["resolved_via"] = f"Local DB Match (via Barcode Product Name: {product_name})"
            if upc_metadata and upc_metadata.get("image_url"):
                match["image_url"] = upc_metadata["image_url"]
            return match
            
        # 4. If not in local DB, try to search OpenFDA by the resolved brand or title
        fda_label_matches = openfda_helper.search_openfda_by_name(product_name, limit=1)
        if not fda_label_matches and brand:
            fda_label_matches = openfda_helper.search_openfda_by_name(brand, limit=1)
            
        if fda_label_matches:
            res = fda_label_matches[0]
            res["resolved_via"] = f"OpenFDA Label Match (via Barcode Product Name: {product_name})"
            if upc_metadata and upc_metadata.get("price"):
                res["price"] = upc_metadata["price"]
            if upc_metadata and upc_metadata.get("image_url"):
                res["image_url"] = upc_metadata["image_url"]
            return res
            
        # 5. Return general UPC item registry metadata if no FDA/Local match is found
        if upc_metadata:
            upc_metadata["resolved_via"] = "Global Barcode Registry (UPCitemdb)"
            return upc_metadata

            
    return None
import urllib.parse
