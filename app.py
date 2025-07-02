from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
import json
from datetime import datetime
from difflib import get_close_matches
import os

app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')

# MongoDB connection
mongo_uri = os.environ.get("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["isvaryam"]
products = db["products"]

# Local data
with open("ingredients.json") as f:
    ingredients_data = json.load(f)
with open("contact.json") as f:
    contact_data = json.load(f)

# Aliases
alias_map = {
    "combo pack": "super pack", "oil combo": "super pack", "3 oil combo": "super pack",
    "combo": "super pack", "sugar": "jaggery powder"
}

# Product recommendations
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
    return "Good evening 🌙"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chatbot", methods=["POST"])
def chatbot():
    user_input = request.json.get("message", "").lower()

    greetings = ["hi", "hello", "good morning", "good evening", "good afternoon", "hey", "yo", "hola", "what's up"]
    silly_queries = [
        "are you real", "can i marry you", "what's your name", "do you love me", "you single", "can you cook",
        "sing a song", "tell a joke", "you look nice", "you cute", "what is 0/0", "do you sleep", "are you ai",
        "how are you", "how do you know this", "what are you"
    ]
    location_keywords = [
        "location", "where is isvaryam", "where is your store", "store address", "address", "location of company"
    ]
    delivery_keywords = [
        "delivery", "shipping", "how many days", "when will it reach", "delivery time", "how fast"
    ]
    image_keywords = [
        "all images", "show all images", "product images", "pictures of products", "show products visually", "display items"
    ]
    type_keywords = [
        "types of oil", "oil types", "types of products", "products offered", "what do you sell", "offered by isvaryam", "range of oils"
    ]
    order_keywords = [
        "how to order", "place an order", "order now", "buy", "want to buy", "book", "purchase", "make a purchase"
    ]
    track_keywords = [
        "track", "tracking", "track my order", "where is my order", "order status", "check order", "tracking details", "how do i track"
    ]
    product_list_keywords = [
        "products", "what do you have", "show all", "available items", "list items", "what can i buy", "items available"
    ]
    all_price_keywords = [
        "product price", "all prices", "prices of products", "cost of all", "price list"
    ]

    if any(greet in user_input for greet in greetings):
        return jsonify(response=f"{get_greeting()}! I'm Isvaryam’s assistant. How can I help you today?")

    if any(word in user_input for word in silly_queries):
        return jsonify(response="😄 I'm just a helpful chatbot. Let's talk about oils and orders!")

    if any(word in user_input for word in location_keywords + ["contact", "phone", "email", "reach you"]):
        return jsonify(response=(
            f"📞 Phone: {contact_data['phone']}<br>"
            f"✉️ Email: {contact_data['email']}<br>"
            f"📍 Address: {contact_data['address']}"
        ))

    if any(word in user_input for word in delivery_keywords):
        return jsonify(response="🚚 We deliver to Coimbatore in 2 days and to other cities in 3–4 days.")

    if any(word in user_input for word in product_list_keywords):
        return jsonify(response="📦 We offer: Groundnut Oil, Coconut Oil, Sesame Oil, Ghee, Jaggery Powder, and a Super Pack (1L each of 3 oils).")

    if any(word in user_input for word in image_keywords):
        all_items = products.find()
        img_block = ""
        for item in all_items:
            name = item.get("name", "Product")
            images = item.get("images", [])[:1]
            for img in images:
                img_block += f"<b>{name.title()}</b><br><img src='{img}' width='100' style='margin:5px;'><br><br>"
        return jsonify(response=f"🖼️ Our product gallery:<br><br>{img_block}")

    if any(word in user_input for word in type_keywords):
        oils = [name.title() for name in ingredients_data.keys()]
        return jsonify(response=f"🛍️ We offer the following: {', '.join(oils)}")

    if any(word in user_input for word in order_keywords):
        return jsonify(response=f"🛒 To place an order, call us at 📞 {contact_data['phone']}")

    if any(word in user_input for word in track_keywords):
        return jsonify(response=f"📦 For tracking, please call 📞 {contact_data['phone']}")

    if any(word in user_input for word in all_price_keywords):
        all_items = products.find()
        price_lines = []
        for item in all_items:
            name = item.get("name", "Product").title()
            prices = [f"{q['size']} - ₹{q['price']}" for q in item.get("quantities", [])]
            price_lines.append(f"💰 <b>{name}</b>: {', '.join(prices)}")
        return jsonify(response="<br><br>".join(price_lines))

    # Specific product fuzzy match
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
            return jsonify(response=f"Sorry, I couldn't find information for {db_name.title()}.")

        response_parts = []

        if any(word in user_input for word in ["price", "cost", "rate", "how much"]):
            prices = [f"{q['size']} - ₹{q['price']}" for q in item.get("quantities", [])]
            response_parts.append(f"🛒 {db_name.title()} Prices: {', '.join(prices)}")

        if any(word in user_input for word in ["ingredient", "contains", "what is in", "made of"]):
            if db_name in ingredients_data:
                ingredients = ", ".join(ingredients_data[db_name])
                response_parts.append(f"🧾 Ingredients of {db_name.title()}: {ingredients}")
            else:
                response_parts.append(f"ℹ️ {db_name.title()} is a natural product.")

        if any(word in user_input for word in ["image", "photo", "pic", "picture", "show me"]):
            imgs = item.get("images", [])[:3]
            if imgs:
                img_html = " ".join([f"<img src='{img}' width='100' style='margin:5px;'/>" for img in imgs])
                response_parts.append(f"📸 Images of {db_name.title()}:<br>{img_html}")

        if not response_parts:
            desc = item.get("description", "This is a premium product made with care.")
            response_parts.append(f"📝 {db_name.title()}: {desc}")

        related = recommendations.get(db_name, [])
        if related:
            response_parts.append(f"🤝 Customers also buy: {', '.join([r.title() for r in related])}")

        return jsonify(response="<br><br>".join(response_parts))

    return jsonify(response="🤖 I didn’t get that. Try asking about products, prices, oils, ordering, or delivery info.")

if __name__ == "__main__":
    app.run(debug=True)
