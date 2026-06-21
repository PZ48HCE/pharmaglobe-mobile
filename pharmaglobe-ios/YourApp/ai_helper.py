import os
import med_database

# Helper to check if API key exists in environment
def get_env_api_key():
    return os.environ.get("GEMINI_API_KEY", "")

class GeminiRestClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def generate_content(self, prompt):
        import requests
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        if res.status_code == 200:
            data = res.json()
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    text = parts[0].get("text", "")
                    
                    class GeminiResponse:
                        def __init__(self, text_val):
                            self.text = text_val
                            
                    return GeminiResponse(text)
            raise Exception(f"Empty or invalid response from Gemini API: {data}")
        else:
            raise Exception(f"Gemini API returned HTTP {res.status_code}: {res.text}")

def get_gemini_client(api_key=None):
    """Initializes and returns the generative model REST client if a valid key is provided."""
    key = api_key or get_env_api_key()
    if not key:
        return None
    return GeminiRestClient(key)

# ==================== PERSONA SYSTEM PROMPTS ====================

HEALTH_SYSTEM_PROMPT = """
You are "Aegis", a professional AI Health Consultant for the PharmaGlobe Mobile app.
Your goal is to help users discuss general health problems, understand mild symptoms, suggest appropriate daily-use over-the-counter (OTC) medicines, and offer health guidelines.

Strict Guidelines:
1. ALWAYS start or end your response with a clear medical disclaimer:
   "Disclaimer: I am an AI, not a doctor. This advice is for informational purposes only. Please consult a qualified healthcare provider or pharmacist before taking any medication, especially if you have pre-existing conditions, are pregnant, or experience severe symptoms."
2. Suggest appropriate OTC medicines based on standard medical guidelines. If the user mentions a location (e.g. Japan, USA, India, UK), try to recommend the corresponding local brand names from the PharmaGlobe curated database (e.g., Loxonin S or EVE Quick in Japan, Tylenol or Advil in the US, Dolo 650 in India, Panadol in the UK).
3. Always ask clarifying questions if the symptoms are vague, and list common warnings (e.g., drowsiness, stomach irritation).
4. Emphasize when symptoms require immediate medical attention (e.g., high fever, severe chest pain, shortness of breath).
5. CRITICAL AGE LIMIT INSTRUCTION: Do NOT assume or default to saying that a medicine is restricted to "15+" or "adults only" unless it is explicitly specified in the database details provided in your prompt. Analyze the specific medicine details in the prompt context to find the actual age limits (some are safe for children 5+, 6+, 8+, 12+, while others are indeed restricted to 15+). State the exact allowed age ranges or warnings from the product's actual database details. If the product's details are not available in your prompt context, state clearly that you do not have its age guidelines in your offline database and advise checking the official packaging.
"""

DEV_SYSTEM_PROMPT = """
You are the Lead Developer and Architect of the PharmaGlobe Mobile application.
Your goal is to explain the native cross-platform mobile frontend and backend architecture of the app to the user, help them understand the codebase, and guide them in writing Python code to extend the Kivy/KivyMD mobile app.

Technical Details of PharmaGlobe Mobile:
- Frontend: Kivy & KivyMD (Python Material Design framework). It uses native screens (`Screen`), a manager (`ScreenManager`), a navigation layout, and KivyMD elements like `MDCard`, `MDLabel`, `MDTextField`, `MDRaisedButton`, and native camera inputs.
- Local Database (med_database.py): Curated SQLite/dictionary data of regional OTC medicines for offline browsing.
- OpenFDA (openfda_helper.py): Pulls live US drug labels (brand, generic, warnings, uses, dosage) via HTTP requests when online.
- Barcode Decoder (barcode_helper.py): Uses OpenCV's BarcodeDetector to decode captured camera photo frames offline, and maps them to product titles via UPCitemdb.
- Packaging Config (buildozer.spec): The configuration file for compiling the Python project into an Android APK, defining packages, names, and permissions (`CAMERA`, `INTERNET`).
- Validation Suite (validate_mobile_app.py): Performs automated logic assertions.

Always be technical, clear, and provide KivyMD code snippets when helping the user write or refactor mobile layouts or logic.
"""

# ==================== LOCAL FALLBACK RESPONDER ====================

def get_local_fallback_response(persona, message, preferred_language=None, current_country=None, api_key=None):
    """Provides a smart keyword-based local response if no Gemini API Key is configured."""
    msg = message.lower()
    
    disclaimer = (
        "\n\n*⚠️ Disclaimer: I am an AI Assistant operating in offline fallback mode. "
        "This advice is for informational purposes only. Please consult a qualified doctor before taking any medicine.*"
    )
    
    if persona == "🩺 AI Health Consultant":
        # Check symptoms & locations
        symptom = None
        matched_meds = []
        
        # Determine symptom category
        if any(w in msg for w in ["pain", "headache", "toothache", "muscle", "fever", "cramp"]):
            symptom = "Pain & Fever"
            category = "Pain Reliever"
        elif any(w in msg for w in ["cold", "flu", "cough", "sore throat", "runny nose", "phlegm"]):
            symptom = "Cold & Flu Symptoms"
            category = "Cold & Flu"
        elif any(w in msg for w in ["stomach", "acid", "heartburn", "bloating", "digestion", "nausea", "reflux"]):
            symptom = "Stomach & Acid Issues"
            category = "Digestive Health"
        elif any(w in msg for w in ["allergy", "allergic", "sneeze", "itch", "hay fever"]):
            symptom = "Allergies"
            category = "Allergy"
        else:
            category = None
            
        # Determine country
        country = None
        if "japan" in msg:
            country = "Japan"
        elif "usa" in msg or "america" in msg or "us" in msg:
            country = "USA"
        elif "india" in msg:
            country = "India"
        elif "uk" in msg or "britain" in msg or "england" in msg:
            country = "UK"
        elif "france" in msg:
            country = "France"
        elif "spain" in msg:
            country = "Spain"
        elif "germany" in msg:
            country = "Germany"
        elif "korea" in msg:
            country = "South Korea"
        else:
            # Fall back to user's pre-selected destination country
            if current_country and current_country != "Global (All)":
                country = current_country
            
        if category:
            # Import med_database to query
            import med_database
            matched_meds = med_database.get_medicines_by_filters(country=country, category=category)
            
        if matched_meds:
            med_list_str = "\n".join([f"- **{m['name']}** ({m['generic_name']}): {', '.join(m['uses'][:2])}. Typical Price: {m['price']}" for m in matched_meds])
            loc_str = f" in **{country}**" if country else ""
            res_val = (
                f"Hello! It sounds like you are asking about symptoms relating to **{symptom}**{loc_str}.\n\n"
                f"Here are some common over-the-counter (OTC) options from our regional database:\n{med_list_str}\n\n"
                f"**General Guidelines:**\n"
                f"- Read the dosing labels carefully.\n"
                f"- Avoid taking multiple medicines containing the same active ingredient (e.g. paracetamol/acetaminophen) to prevent overdose.\n"
                f"- Take pain relievers with food if you have a sensitive stomach."
                f"{disclaimer}"
            )
        else:
            loc_msg = f" for **{country}**" if country else ""
            res_val = (
                f"Hello! I am operating in local fallback mode. I can assist with queries about pain, fever, cold, stomach upset, or allergy symptoms{loc_msg}.\n\n"
                f"To get more detailed symptom discussions and personalized suggestions, **please configure your Gemini API Key in the app settings sidebar**!\n"
                f"In the meantime, you can browse all regional OTC listings directly in the **🗺️ Directory** screen."
                f"{disclaimer}"
            )
            
    else:  # Developer Assistant Persona
        if any(w in msg for w in ["frontend", "app", "ui", "kivy", "layout"]):
            res_val = (
                "### Mobile Frontend Architecture (Kivy & KivyMD)\n"
                "PharmaGlobe Mobile uses Kivy/KivyMD in `main.py`:\n"
                "1. **App Structure**: Inherits from `MDApp`. Sets up colors using `self.theme_cls.primary_palette = 'Teal'` and `theme_style = 'Dark'`.\n"
                "2. **ScreenManager**: Coordinates navigation between `DirectoryScreen`, `SearchScreen`, `ScannerScreen`, and `ChatScreen`.\n"
                "3. **Material Widgets**: Displays medicine listings using responsive `MDCard` elements with custom action buttons.\n"
                "4. **Layout Builder**: Uses standard layout containers (BoxLayout, AnchorLayout, ScrollView) to structure native screen widgets."
            )
        elif any(w in msg for w in ["backend", "db", "database", "med"]):
            res_val = (
                "### Mobile Backend & Local Database\n"
                "The mobile backend utilizes the same robust logic modules:\n"
                "1. `med_database.py`: Stores local OTC records, prices, and links for offline search.\n"
                "2. `openfda_helper.py`: Dynamically fetches official US label descriptions over HTTPS when online.\n"
                "3. `barcode_helper.py`: Decodes raw EAN/UPC barcodes using OpenCV and resolves product titles via UPCitemdb."
            )
        elif any(w in msg for w in ["barcode", "scan", "camera"]):
            res_val = (
                "### Mobile Barcode Scanner & Camera\n"
                "The scanner implementation works as follows:\n"
                "1. **Kivy Camera**: Renders a live view of the phone's native camera inside the `ScannerScreen` layout.\n"
                "2. **Capture Snap**: Emits a trigger to save the current frame as an image.\n"
                "3. **OpenCV Decryption**: Reads the image BGR array and runs `cv2.barcode.BarcodeDetector().detectAndDecode()`.\n"
                "4. **Online/Local Sync**: Searches for the decoded barcode in OpenFDA. If offline or not found, queries UPCitemdb and maps to matching local DB records."
            )
        elif any(w in msg for w in ["build", "buildozer", "apk", "package", "deploy"]):
            res_val = (
                "### Packaging for Android (`buildozer.spec`)\n"
                "To package this python code into an Android APK:\n"
                "1. We define all project specs in `buildozer.spec` (name, version, package, imports).\n"
                "2. The spec requests native device permissions:\n"
                "   `android.permissions = CAMERA, INTERNET, WRITE_EXTERNAL_STORAGE`\n"
                "3. Running `buildozer -v android debug` compiles the python interpreter, Kivy, OpenCV, and your codebase into a single deployable `.apk` file."
            )
        else:
            res_val = (
                "### PharmaGlobe Mobile Codebase Overview\n"
                "I am the Mobile Dev Assistant. Here are the core files in this mobile project:\n"
                "- `main.py`: Main KivyMD App layouts and navigation.\n"
                "- `med_database.py`: Local database OTC medicine maps.\n"
                "- `openfda_helper.py`: Live FDA drug label search API.\n"
                "- `barcode_helper.py`: OpenCV barcode reader & UPC catalog lookups.\n"
                "- `buildozer.spec`: Packaging configuration file for Buildozer.\n"
                "- `validate_mobile_app.py`: Logic verification script.\n\n"
                "Ask me about: **frontend**, **backend**, **barcode scanning**, or **buildozer packaging** for details!"
            )
            
    # Translate the offline fallback response to the user's preferred language if needed
    if preferred_language and preferred_language != "English":
        translated_res = translate_text(res_val, preferred_language, api_key)
        # Avoid prepending translation failure warnings to chat bubbles
        if not translated_res.startswith("[Translation Offline") and not translated_res.startswith("[Translation Error"):
            return translated_res
            
    return res_val

# ==================== MAIN CHAT GENERATION ====================

def generate_chat_response(persona, chat_history, user_message, api_key=None, preferred_language=None, current_country=None, home_country=None):
    """
    Generates a response from the AI assistant.
    If the API key is active, queries Gemini. Otherwise, runs local fallback logic.
    """
    model = get_gemini_client(api_key)
    
    if not model:
        # Fallback to offline local model
        return get_local_fallback_response(persona, user_message, preferred_language, current_country, api_key)
        
    system_instruction = HEALTH_SYSTEM_PROMPT if persona == "🩺 AI Health Consultant" else DEV_SYSTEM_PROMPT
    
    # Inject user settings/context into system prompt
    context_injection = ""
    if preferred_language or current_country or home_country:
        context_injection = "\n\nUser Context:\n"
        if home_country:
            context_injection += f"- User's Home/Origin Country: {home_country}\n"
        if current_country and current_country != "Global (All)":
            context_injection += f"- User's target/travel location destination: {current_country}\n"
            if home_country and home_country != current_country:
                context_injection += f"Please note: User is traveling in {current_country} but is from {home_country}. When appropriate, explain how local OTC options compare to equivalents in {home_country}.\n"
        if preferred_language and preferred_language != "English":
            context_injection += f"- User's preferred language: {preferred_language}\n"
            if preferred_language in ["Korean", "Hindi", "Nepali"]:
                context_injection += (
                    f"IMPORTANT: Since the user's language is {preferred_language}, please write your response "
                    f"in a Romanized phonetic transliteration (using the standard English/Latin alphabet) so it can "
                    f"be read without native fonts. Do NOT output native characters for {preferred_language}."
                )
            else:
                context_injection += f"Please respond in the {preferred_language} language."
                
    system_instruction += context_injection

    # Scan for medicine details to inject as verified context
    if persona == "🩺 AI Health Consultant":
        matched_meds_context = []
        text_to_scan = (user_message + " " + " ".join([m["content"] for m in chat_history[-2:]])).lower()
        for med in med_database.MEDICINE_DATABASE:
            base_name = med["name"].split("(")[0].strip().lower()
            if base_name in text_to_scan or med["name"].lower() in text_to_scan:
                med_details = (
                    f"Product: {med['name']}\n"
                    f"- Generic Name: {med.get('generic_name', 'Not Specified')}\n"
                    f"- Category: {med.get('category', 'General')}\n"
                    f"- Country: {med.get('country', 'Unknown')}\n"
                    f"- Dosage & Directions: {med.get('dosage', 'Not Specified')}\n"
                    f"- Warnings & Contraindications: {', '.join(med.get('warnings', ['Not Specified']))}\n"
                    f"- Primary Uses: {', '.join(med.get('uses', ['Not Specified']))}\n"
                )
                matched_meds_context.append(med_details)
        if matched_meds_context:
            system_instruction += "\n\nRelevant Local Product Database Details for your analysis:\n" + "\n".join(matched_meds_context)
            system_instruction += "\nCRITICAL: You MUST analyze the specific age limits, dosing, and contraindications in the product details above and only report safety guidelines/age limits that align with them. Do NOT guess or default to saying it is restricted to 15+ unless specified above."
    
    formatted_chat = []
    formatted_chat.append(f"System Instructions: {system_instruction}")
    
    for msg in chat_history[-6:]:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        formatted_chat.append(f"{role_label}: {msg['content']}")
        
    formatted_chat.append(f"User: {user_message}\nAssistant:")
    
    full_prompt = "\n\n".join(formatted_chat)
    
    try:
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        print(f"Gemini generation error: {e}")
        fallback_res = get_local_fallback_response(persona, user_message, preferred_language, current_country, api_key)
        return f"Error communicating with Gemini API: {e}. Falling back to offline engine:\n\n" + fallback_res


# ==================== TRANSLATION HELPER ====================

def translate_text(text, target_language, api_key=None):
    """
    Translates the given text into the target_language using Gemini if online/key available,
    otherwise uses the free keyless Google Translate API.
    """
    # Map target language name to Google Translate language code
    lang_map = {
        "English": "en",
        "Japanese": "ja",
        "Spanish": "es",
        "French": "fr",
        "German": "de",
        "Korean": "ko",
        "Hindi": "hi",
        "Nepali": "ne",
        "Chinese": "zh-CN"
    }
    
    target_code = lang_map.get(target_language, "en")
    
    # Try Gemini first if API key is provided
    model = get_gemini_client(api_key)
    if model:
        if target_language in ["Korean", "Hindi", "Nepali"]:
            prompt = (
                f"Translate the following medical description into {target_language}. "
                f"IMPORTANT: Write the translation ONLY in a Romanized phonetic transliteration (using the standard English/Latin alphabet). "
                f"Do NOT output any native script characters (no Hangul, no Devanagari) as they will render as empty blocks. "
                f"For example, output 'Namaste' instead of 'Namaste (नमस्ते)'. Output ONLY Latin/English characters. "
                f"Keep the markdown formatting, bullet points, warning sections, and critical warning highlights intact. "
                f"Keep all medical/dosage values accurate. Translate only the text contents.\n\n"
                f"Text to translate:\n{text}"
            )
        else:
            prompt = (
                f"Translate the following medical description into {target_language}. "
                f"Keep the markdown formatting, bullet points, warning sections, and critical warning highlights intact. "
                f"Keep all medical/dosage values accurate. Translate only the text contents.\n\n"
                f"Text to translate:\n{text}"
            )
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Gemini translation error: {e}. Falling back to free translation API.")

    # Free Google Translate API Fallback
    try:
        import requests
        import urllib.parse
        import unicodedata
        
        encoded_text = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_code}&dt=t&dt=rm&q={encoded_text}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data and data[0]:
                sentences = data[0]
                
                # Check for transliteration element at the end
                transliteration = None
                if len(sentences) > 0 and isinstance(sentences[-1], list) and len(sentences[-1]) >= 3:
                    if sentences[-1][0] is None and sentences[-1][1] is None and isinstance(sentences[-1][2], str):
                        transliteration = sentences[-1][2]
                        sentences = sentences[:-1]
                
                # Reconstruct native translation
                native_translated_parts = []
                for s in sentences:
                    if isinstance(s, list) and len(s) > 0 and isinstance(s[0], str):
                        native_translated_parts.append(s[0])
                native_translation = "".join(native_translated_parts)
                
                # If target is Korean, Hindi, or Nepali, we want ONLY the Romanized transliteration to avoid empty boxes.
                if target_language in ["Korean", "Hindi", "Nepali"] and transliteration:
                    # Clean up transliteration to avoid any non-Latin characters (like devanagari full stop)
                    trans_clean = transliteration.replace('।', '.')
                    nfkd_form = unicodedata.normalize('NFKD', trans_clean)
                    ascii_clean = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
                    return ascii_clean
                else:
                    return native_translation
    except Exception as e:
        print(f"Free translation API error: {e}")
        
    return f"[Translation Offline (Failed to connect to translation server)]\n\n{text}"
