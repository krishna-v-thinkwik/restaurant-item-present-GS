from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import difflib
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Setup Google Sheets access
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
google_creds = os.getenv("GOOGLE_CREDS_JSON")

if not google_creds:
    raise Exception("Missing GOOGLE_CREDS_JSON environment variable")

service_account_info = json.loads(google_creds)
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(creds)
sheet = client.open("menu").worksheet("menu")

# Fetch data
data = sheet.get_all_records()

def get_menu_items():
    items = [row['Name'].strip().lower() for row in data if row['Name']]
    categories = list(set(row['Category'].strip().lower() for row in data if row['Category']))
    return items, categories

category_keywords = {
    "desserts": "desserts",
    "ice cream": "desserts",
    "sweets": "desserts",
    "drinks": "drinks",
    "buttermilk": "drinks",
    "milk": "drinks",
    "cold drink": "drinks",
    "soda": "drinks",
    "juice": "drinks",
}

def check_and_suggest(item_name, menu_items, categories):
    item_name = item_name.lower().strip()

    if item_name in menu_items:
        return {"status": "available", "message": f"✅ '{item_name}' is available on the menu."}

    for keyword, category in category_keywords.items():
        if keyword in item_name:
            suggestions = [row['Name'] for row in data if row['Category'].strip().lower() == category]
            return {
                "status": "category_suggested",
                "message": f"❌ '{item_name}' not found, but here are items from '{category.title()}':",
                "suggestions": suggestions
            }

    category_match = difflib.get_close_matches(item_name, categories, n=1, cutoff=0.6)
    if category_match:
        matched_category = category_match[0]
        suggestions = [row['Name'] for row in data if row['Category'].strip().lower() == matched_category]
        return {
            "status": "category_suggested",
            "message": f"❌ '{item_name}' not found, but here are items from '{matched_category.title()}':",
            "suggestions": suggestions
        }

    item_suggestions = difflib.get_close_matches(item_name, menu_items, n=3, cutoff=0.5)
    return {
        "status": "not_found",
        "message": f"❌ '{item_name}' not found.",
        "suggestions": item_suggestions
    }

@app.route('/')
def home():
    return "✅ Pizza order API is live."

@app.route('/check_order', methods=['POST'])
def check_order():
    request_data = request.get_json()
    user_order = request_data.get('order')

    if not user_order:
        return jsonify("❌ Missing 'order' in request body"), 400

    menu_items, categories = get_menu_items()
    result = check_and_suggest(user_order, menu_items, categories)

    # Build string response
    if result['status'] == 'available':
        response = result['message']

    elif result['status'] == 'category_suggested':
        suggestion_list = result['suggestions'][:3]
        suggestions_str = ', '.join(suggestion_list)
        response = f"{user_order} is not available, but here are some {result['message'].split('from ')[-1]} like {suggestions_str}. Would you like to order one of these?"

    elif result['status'] == 'not_found':
        suggestion_list = result['suggestions'][:3]
        if suggestion_list:
            suggestions_str = ', '.join(suggestion_list)
            response = f"{user_order} is not available, but did you mean {suggestions_str}? Would you like to order that instead?"
        else:
            response = f"Sorry, we couldn't find anything similar to '{user_order}' in the menu."

    else:
        response = "An unexpected error occurred."

    return response


if __name__ == '__main__':
    app.run(debug=True)
