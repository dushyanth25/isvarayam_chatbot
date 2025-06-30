from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
import json
from datetime import datetime
from difflib import get_close_matches
import os  # <-- important for environment variable

app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')

# Secure MongoDB connection using environment variable
mongo_uri = os.environ.get("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["isvaryam"]
products = db["products"]


# Load local data
with open("ingredients.json") as f:
    ingredients_data = json.load(f)
with open("contact.json") as f:
    contact_data = json.load(f)

# Aliases and recommendations
alias_map = {
    "combo pack": "super pack",
    "oil combo": "super pack",
    "3 oil combo": "super pack"
}

recommendations = {
    "groundnut oil": ["coconut oil", "sesame oil", "super pack"],
    "coconut oil": ["sesame oil", "groundnut oil", "super pack"],
    "sesame oil": ["groundnut oil", "coconut oil", "super pack"],
    "ghee": ["jaggery powder"],
    "jaggery powder": ["ghee"],
    "super pack": ["groundnut oil", "coconut oil", "sesame oil"]
}

def get_greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning ☀️"
    elif hour < 17:
        return "Good afternoon 🌤️"
    else:
        return "Good evening 🌙"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chatbot", methods=["POST"])
def chatbot():
    user_input = request.json.get("message", "").lower()

    # 1. Greeting intent
    if any(greet in user_input for greet in ["hi", "hello", "good morning", "good afternoon", "good evening", "hey"]):
        return jsonify(response=f"{get_greeting()}! I'm here to help you explore Isvaryam’s natural products. What would you like to know?")

    # 2. Contact info
    if any(word in user_input for word in ["contact", "phone", "email", "address", "reach you"]):
        return jsonify(response=(
            f"You can reach us at:\n📞 {contact_data['phone']}\n"
            f"✉️ {contact_data['email']}\n📍 {contact_data['address']}"
        ))

    # 3. Delivery info
    if "delivery" in user_input or "shipping" in user_input:
        return jsonify(response="We deliver to Coimbatore in 2 days 🚚 and to other cities in 3–4 days.")

    # 4. Product listing
    if any(word in user_input for word in ["products", "what do you have", "show all", "available items", "list items"]):
        return jsonify(response="We currently offer: Groundnut Oil, Coconut Oil, Sesame Oil, Ghee, Jaggery Powder, and a Super Pack (1L each of 3 oils).")

    # 5. Normalize query and detect product
    all_product_names = list(ingredients_data.keys()) + list(alias_map.keys())
    words = user_input.split()
    matched = get_close_matches(" ".join(words), all_product_names, n=1, cutoff=0.6)
    pname = matched[0] if matched else None
    if not pname:
        for word in words:
            match = get_close_matches(word, all_product_names, n=1, cutoff=0.8)
            if match:
                pname = match[0]
                break

    if pname:
        db_name = alias_map.get(pname, pname)
        item = products.find_one({"name": {"$regex": db_name, "$options": "i"}})
        if not item:
            return jsonify(response=f"Sorry, I couldn't find any information for {db_name.title()}.")

        response_parts = []

        # 6. Price queries
        if any(word in user_input for word in ["price", "cost", "rate", "how much"]):
            prices = [f"{q['size']} - ₹{q['price']}" for q in item.get("quantities", [])]
            response_parts.append(f"🛒 Prices for {db_name.title()}: {', '.join(prices)}")

        # 7. Ingredient queries
        if any(word in user_input for word in ["ingredient", "what is in", "contains", "made of"]):
            if db_name in ingredients_data:
                ingredients = ", ".join(ingredients_data[db_name])
                response_parts.append(f"🧾 {db_name.title()} contains: {ingredients}")
            else:
                response_parts.append(f"ℹ️ {db_name.title()} includes a blend of our best oils.")

        # 8. Image queries
        if any(word in user_input for word in ["image", "photo", "pic", "picture", "show me"]):
            imgs = item.get("images", [])[:3]
            if imgs:
                img_html = " ".join([f"<img src='{img}' width='100' style='margin:5px;'/>" for img in imgs])
                response_parts.append(f"📸 Here are some images of {db_name.title()}:<br>{img_html}")

        # 9. Description if nothing matched
        if not response_parts:
            description = item.get("description", "This is a premium product made with care.")
            response_parts.append(f"📝 {db_name.title()}: {description}")

        # 10. Recommendations
        related = recommendations.get(db_name, [])
        if related:
            response_parts.append(f"🤝 Customers also buy: {', '.join([r.title() for r in related])}")

        return jsonify(response="<br><br>".join(response_parts))

    # Fallback
    return jsonify(response="I'm sorry, I couldn't understand that. You can ask about product prices, ingredients, images, delivery info, or our contact details.")

if __name__ == "__main__":
    app.run(debug=True)
