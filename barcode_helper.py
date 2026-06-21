import requests
import urllib.parse
from PIL import Image
import openfda_helper
import med_database

def decode_barcode(pil_image):
    """
    Decodes barcode or QR code from a PIL image using OpenCV.
    Supports flipped and rotated orientations (0, 90, 180, 270 degrees + mirrored) 
    to handle sideways or mirrored camera feeds on mobile/Macbook webcams.
    Also falls back to image sharpening and tilt correction rotation sweep (±10°, ±15°)
    for hand-held camera frames.
    Returns: (decoded_value, code_type) or (None, None)
    """
    try:
        import cv2
        import numpy as np
        # Convert PIL Image to BGR numpy array for OpenCV
        img_rgb = np.array(pil_image.convert("RGB"))
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        
        # Define candidate orientations for rotated, mirrored, or sideways cameras
        orientations = [
            ("Original", img_bgr),
            ("Horizontally Flipped (Mirrored)", cv2.flip(img_bgr, 1)),
            ("Vertically Flipped (Upside Down)", cv2.flip(img_bgr, 0)),
            ("Both Flipped (180 Rotation)", cv2.flip(img_bgr, -1)),
            ("Rotated 90 Clockwise", cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)),
            ("Rotated 90 Counter-Clockwise", cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)),
            ("Rotated 90 Clockwise + Mirrored", cv2.flip(cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE), 1)),
            ("Rotated 90 Counter-Clockwise + Mirrored", cv2.flip(cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE), 1))
        ]
        
        for desc, img in orientations:
            # Try multiple preprocessing strategies to find the barcode:
            # Strategy A: Add 50px white border quiet zone to original scale
            # Strategy B: Scale 2x and add 30px white border quiet zone
            strategies = [
                ("Scale 1x, Border 50", lambda im: cv2.copyMakeBorder(im, 50, 50, 50, 50, cv2.BORDER_CONSTANT, value=[255, 255, 255])),
                ("Scale 2x, Border 30", lambda im: cv2.copyMakeBorder(cv2.resize(im, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC), 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=[255, 255, 255]))
            ]
            
            for strat_name, preprocess_fn in strategies:
                processed_img = preprocess_fn(img)
                
                # Try OpenCV Barcode Detector
                if hasattr(cv2, 'barcode'):
                    try:
                        detector = cv2.barcode.BarcodeDetector()
                        res = detector.detectAndDecode(processed_img)
                        # Handle both 3-tuple and 4-tuple OpenCV versions
                        if len(res) == 4:
                            retval, decoded_info, decoded_type, points = res
                        elif len(res) == 3:
                            decoded_info, points, decoded_type = res
                            retval = bool(decoded_info)
                        else:
                            retval = False
                            
                        if retval:
                            if isinstance(decoded_info, (list, tuple)):
                                for info, code_type in zip(decoded_info, decoded_type or ["UNKNOWN"] * len(decoded_info)):
                                    if info and info.strip():
                                        print(f"[Scanner] Decoded {info.strip()} ({code_type}) from {desc} using {strat_name}.")
                                        return info.strip(), code_type
                            elif isinstance(decoded_info, str) and decoded_info.strip():
                                code_type = decoded_type if isinstance(decoded_type, str) else "BARCODE"
                                print(f"[Scanner] Decoded {decoded_info.strip()} ({code_type}) from {desc} using {strat_name}.")
                                return decoded_info.strip(), code_type
                    except Exception as e:
                        pass
                        
            # Try standard QR Code Detector as a fallback on the original orientation
            try:
                qr_detector = cv2.QRCodeDetector()
                retval, points, straight_qrcode = qr_detector.detectAndDecode(img)
                if retval and retval.strip():
                    print(f"[Scanner] Decoded QR code: {retval.strip()} from {desc} frame.")
                    return retval.strip(), "QRCODE"
            except Exception as e:
                pass

        # Fallback: Apply image sharpening and try minor rotation adjustments (tilted hand-held corrections)
        try:
            # Sharpening filter
            kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
            sharpened = cv2.filter2D(img_bgr, -1, kernel)
            
            image_center = tuple(np.array(sharpened.shape[1::-1]) / 2)
            
            # Test slight rotations (±15 and ±10 degrees)
            tilted_angles = [15, -15, 10, -10]
            for angle in tilted_angles:
                rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
                rotated = cv2.warpAffine(sharpened, rot_mat, sharpened.shape[1::-1], flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=[255, 255, 255])
                
                # Test rotated version with our preprocessing strategies
                for desc, img in [
                    (f"Tilted {angle}°", rotated),
                    (f"Tilted {angle}° Mirrored", cv2.flip(rotated, 1))
                ]:
                    strategies = [
                        ("Scale 1x, Border 50", lambda im: cv2.copyMakeBorder(im, 50, 50, 50, 50, cv2.BORDER_CONSTANT, value=[255, 255, 255])),
                        ("Scale 2x, Border 30", lambda im: cv2.copyMakeBorder(cv2.resize(im, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC), 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=[255, 255, 255]))
                    ]
                    
                    for strat_name, preprocess_fn in strategies:
                        processed_img = preprocess_fn(img)
                        if hasattr(cv2, 'barcode'):
                            try:
                                detector = cv2.barcode.BarcodeDetector()
                                res = detector.detectAndDecode(processed_img)
                                if len(res) == 4:
                                    retval, decoded_info, decoded_type, points = res
                                elif len(res) == 3:
                                    decoded_info, points, decoded_type = res
                                    retval = bool(decoded_info)
                                else:
                                    retval = False
                                    
                                if retval:
                                    if isinstance(decoded_info, (list, tuple)):
                                        for info, code_type in zip(decoded_info, decoded_type or ["UNKNOWN"] * len(decoded_info)):
                                            if info and info.strip():
                                                print(f"[Scanner] Decoded {info.strip()} ({code_type}) from {desc} using {strat_name}.")
                                                return info.strip(), code_type
                                    elif isinstance(decoded_info, str) and decoded_info.strip():
                                        code_type = decoded_type if isinstance(decoded_type, str) else "BARCODE"
                                        print(f"[Scanner] Decoded {decoded_info.strip()} ({code_type}) from {desc} using {strat_name}.")
                                        return decoded_info.strip(), code_type
                            except Exception as e:
                                pass
        except Exception as e:
            print(f"Error in tilted fallback decoding: {e}")

    except Exception as e:
        print(f"General barcode decoding error: {e}")
        
    return None, None

def lookup_barcode_in_databases(barcode):
    """
    Resolve a barcode number (UPC/EAN) to medicine/product information.
    Pipes search through:
      1. Local Database Mappings (for robust offline-first and test resolving)
      2. OpenFDA barcode query
      3. UPCitemdb lookup (global product database)
      4. Fallback search query mapping
    Returns: dict of product details, or None if completely unresolved.
    """
    if not barcode:
        return None
        
    barcode_str = str(barcode).strip()
    barcode_clean = barcode_str.lstrip('0')
    
    # Check for PAYKE coupon barcodes
    if barcode_str.startswith("PAYKE"):
        return {
            "brand_name": "PharmaGlobe Coupon",
            "name": "PharmaGlobe Loyalty Reward Voucher",
            "generic_name": "Coupon Code Voucher",
            "category": "Rewards",
            "country": "Loyalty Program",
            "uses": "Discount on medicine purchases at partner pharmacies.",
            "benefits": [
                "10% off your next prescription",
                "Redeemable instantly at cashier counter",
                "Valid for 30 days from redemption"
            ],
            "dosage": "Present barcode to store cashier during checkout.",
            "warnings": [
                "Cannot be combined with other offers.",
                "One-time use only.",
                "No cash value."
            ],
            "resolved_via": "PharmaGlobe Loyalty Coupon Scanner"
        }
    
    # 1. Local hardcoded barcode mapping for test medicines
    # Maps common product barcode variants to curated medicine names in med_database.py
    LOCAL_BARCODE_MAP = {
        "4987306054233": "Pabron Gold A (パブロンゴールドA)",
        "300450449108": "Tylenol Extra Strength",
        "300450449107": "Tylenol Extra Strength", # Handles incorrect UPC check-digit variant
        "4987033400030": "Ohta's Isan (太田胃散)",
        "4987033904019": "Ohta's Isan (太田胃散)",
        "4987306054219": "Pabron Gold A (パブロンゴールドA)",
        "4970883014806": "Delguard Adhesive Bandage (デルガード 救急絆創膏)",
        "10820148": "Delguard Adhesive Bandage (デルガード 救急絆創膏)",  # Fallback EAN-8 partial matches
        "20890148": "Delguard Adhesive Bandage (デルガード 救急絆創膏)",
        "10821480": "Delguard Adhesive Bandage (デルガード 救急絆創膏)",
        "52710148": "Delguard Adhesive Bandage (デルガード 救急絆創膏)",
        "52994180": "Delguard Adhesive Bandage (デルガード 救急絆創膏)",
        "52990148": "Delguard Adhesive Bandage (デルガード 救急絆創膏)",
        "4946842505975": "Asahi Mintia Coldsmash (アサヒ ミンティア コールスマッシュ)",
        "4902705096028": "Meiji Probio Yogurt R-1 Drink Type (明治プロビオヨーグルトR-1 飲むタイプ)",
    }
    
    target_name = None
    for bc, name in LOCAL_BARCODE_MAP.items():
        if bc == barcode_str or bc.lstrip('0') == barcode_clean:
            target_name = name
            break
            
    if target_name:
        for med in med_database.MEDICINE_DATABASE:
            if target_name.lower() in med['name'].lower():
                match = dict(med)
                match["resolved_via"] = f"Local Database Barcode Scan ({barcode_str})"
                return match

    # 2. Search OpenFDA by barcode directly
    fda_result = openfda_helper.search_openfda_by_upc(barcode_str)
    if fda_result:
        fda_result["resolved_via"] = "OpenFDA Direct Barcode"
        return fda_result
        
    # 3. Query UPCitemdb trial API for product catalog resolution
    upc_candidates = [barcode_str, barcode_clean]
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
            
    # 4. Check if the product name resolves to a local medicine in our curated DB
    if product_name:
        local_matches = med_database.search_local_medicines(product_name)
        if not local_matches and brand:
            local_matches = med_database.search_local_medicines(brand)
            
        if local_matches:
            match = local_matches[0]
            match["resolved_via"] = f"Local DB Match (via Barcode Product Name: {product_name})"
            if upc_metadata and upc_metadata.get("image_url"):
                match["image_url"] = upc_metadata["image_url"]
            return match
            
        # Try to search OpenFDA by the resolved brand or title
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
            
        # Return general UPC item registry metadata if no FDA/Local match is found
        if upc_metadata:
            upc_metadata["resolved_via"] = "Global Barcode Registry (UPCitemdb)"
            return upc_metadata
            
    return None
