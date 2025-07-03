from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from bson import ObjectId
import json
from datetime import datetime
from difflib import get_close_matches
import os
import random
import time
from collections import defaultdict
import logging
from nltk.stem import PorterStemmer
import spacy

# Initialize NLP components
ps = PorterStemmer()
nlp = spacy.load("en_core_web_sm")

app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')

# Configure logging
logging.basicConfig(filename='chatbot.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# MongoDB connection
mongo_uri = os.environ.get("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["isvaryam"]
products = db["products"]
reviews = db["reviews"]

# Conversation context tracking
conversation_context = defaultdict(dict)
user_preferences = defaultdict(dict)

# Load data files
with open("ingredients.json") as f:
    ingredients_data = json.load(f)
with open("contact.json") as f:
    contact_data = json.load(f)
with open("faqs.json") as f:
    faqs_data = json.load(f)

# Product knowledge base
product_data = {
    "groundnut oil": {
        "description": "Cold-pressed groundnut oil rich in vitamin E and healthy fats",
        "benefits": ["Heart healthy", "Rich in Vitamin E", "Good for skin", "High smoke point"],
        "usage": ["Cooking", "Frying", "Salad dressing", "Skin moisturizer"],
        "storage": "Store in cool, dry place away from sunlight"
    },
    # Similar structures for other products...
}

# Aliases and synonyms
alias_map = {
    "combo pack": "super pack", "oil combo": "super pack", "3 oil combo": "super pack",
    "combo": "super pack", "sugar": "jaggery powder", "oil pack": "super pack",
    "oil set": "super pack", "oil bundle": "super pack", "oil collection": "super pack",
    "oil trio": "super pack", "oil variety": "super pack", "oil combo pack": "super pack",
    "brown sugar": "jaggery powder", "natural sweetener": "jaggery powder"
}

# Recommendations
recommendations = {
    "groundnut oil": ["coconut oil", "sesame oil", "super pack", "ghee"],
    "coconut oil": ["sesame oil", "groundnut oil", "super pack", "jaggery powder"],
    "sesame oil": ["groundnut oil", "coconut oil", "super pack", "ghee"],
    "ghee": ["jaggery powder", "super pack"],
    "jaggery powder": ["ghee", "coconut oil"],
    "super pack": ["groundnut oil", "coconut oil", "sesame oil", "jaggery powder"]
}

# Intent keywords
greetings = ["hi", "hello", "good morning", "good evening", "good afternoon", 
            "hey", "yo", "hola", "what's up", "greetings", "hi there", 
            "hello there", "hey there", "hiya", "howdy"]

price_keywords = ["price", "cost", "how much", "rate", "pricing", "amount", "value"]

benefit_keywords = ["benefit", "advantage", "why use", "good for", "healthy", 
                   "nutritious", "wellness", "pros", "positive", "help"]

order_keywords = ["order", "buy", "purchase", "get", "want", "need", "acquire",
                 "shop", "checkout", "cart", "payment", "pay"]

delivery_keywords = ["delivery", "shipping", "dispatch", "arrive", "receive",
                    "when get", "time take", "courier", "ship", "transport"]

contact_keywords = ["contact", "call", "phone", "number", "email", "address",
                   "location", "where", "visit", "store", "shop"]

# Helper functions
def get_greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning ☀️"
    elif hour < 17:
        return "Good afternoon 🌤️"
    return "Good evening 🌙"

def get_random_response(responses):
    return random.choice(responses)

def log_unanswered(query):
    logging.info(f"Unanswered query: {query}")

def stem_text(text):
    return ' '.join([ps.stem(word) for word in text.split()])

def extract_entities(text):
    doc = nlp(text)
    entities = {
        "products": [],
        "attributes": [],
        "actions": []
    }
    for ent in doc.ents:
        if ent.label_ == "PRODUCT":
            entities["products"].append(ent.text)
        elif ent.label_ == "ATTRIBUTE":
            entities["attributes"].append(ent.text)
    return entities

def detect_intent(text):
    text = text.lower()
    stemmed = stem_text(text)
    
    intents = {
        'greeting': any(word in text for word in greetings),
        'price_query': any(word in stemmed for word in price_keywords),
        'benefit_query': any(word in stemmed for word in benefit_keywords),
        'order_query': any(word in stemmed for word in order_keywords),
        'delivery_query': any(word in stemmed for word in delivery_keywords),
        'contact_query': any(word in stemmed for word in contact_keywords),
        'product_query': any(p.lower() in text for p in product_name_to_id.keys())
    }
    return intents

def get_product_info(product_name, info_type):
    product_name = product_name.lower()
    db_name = alias_map.get(product_name, product_name)
    
    if db_name not in product_data:
        return None
        
    return product_data[db_name].get(info_type, [])

def get_all_prices():
    all_items = products.find()
    price_lines = []
    for item in all_items:
        name = item.get("name", "Product").title()
        prices = [f"{q['size']} - ₹{q['price']}" for q in item.get("quantities", [])]
        price_lines.append(f"💰 <b>{name}</b>: {', '.join(prices)}")
    return "<br><br>".join(price_lines)

def get_specific_price(product_name):
    product_name = product_name.lower()
    db_name = alias_map.get(product_name, product_name)
    item = products.find_one({"name": {"$regex": db_name, "$options": "i"}})
    
    if not item:
        return None
        
    prices = [f"{q['size']} - ₹{q['price']}" for q in item.get("quantities", [])]
    return f"💰 <b>{item['name'].title()}</b>: {', '.join(prices)}"

# Initialize product mappings
product_map = {str(p["_id"]): p["name"] for p in products.find()}
product_name_to_id = {p["name"].lower(): str(p["_id"]) for p in products.find()}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chatbot", methods=["POST"])
def chatbot():
    start_time = time.time()
    user_input = request.json.get("message", "").strip()
    user_id = request.json.get("user_id", "default")
    
    # Update context
    context = conversation_context[user_id]
    intents = detect_intent(user_input)
    entities = extract_entities(user_input)
    
    # Log the interaction
    logging.info(f"User {user_id}: {user_input}")
    
    # Handle greetings
    if intents['greeting']:
        greeting_responses = [
            f"{get_greeting()}! I'm Isvaryam's helpful assistant. How can I serve you today?",
            f"{get_greeting()}! Welcome to Isvaryam. What can I help you with?",
            f"{get_greeting()}! I'm here to assist with your Isvaryam product queries. How may I help?"
        ]
        context['last_intent'] = 'greeting'
        return jsonify(response=get_random_response(greeting_responses))

    # Handle price queries
    if intents['price_query']:
        if entities['products']:
            price_info = get_specific_price(entities['products'][0])
            if price_info:
                return jsonify(response=price_info)
        
        return jsonify(response=f"Here are all our product prices:<br><br>{get_all_prices()}")

    # Handle benefit queries
    if intents['benefit_query']:
        if entities['products']:
            benefits = get_product_info(entities['products'][0], "benefits")
            if benefits:
                return jsonify(response=f"🌟 Benefits of {entities['products'][0].title()}:<br>- " + "<br>- ".join(benefits))
        
        return jsonify(response=f"Here are health benefits of our products:<br><br>{get_all_benefits()}")

    # Handle product-specific queries
    if intents['product_query']:
        product = entities['products'][0] if entities['products'] else None
        
        if not product:
            # Try fuzzy matching
            all_product_names = list(product_name_to_id.keys()) + list(alias_map.keys())
            match = get_close_matches(user_input, all_product_names, n=1, cutoff=0.6)
            product = match[0] if match else None
            
        if product:
            # Get all available info about the product
            response_parts = []
            
            # Add description
            desc = get_product_info(product, "description")
            if desc:
                response_parts.append(f"📝 {product.title()}: {desc}")
            
            # Add prices if price intent exists
            if intents['price_query']:
                price_info = get_specific_price(product)
                if price_info:
                    response_parts.append(price_info)
            
            # Add benefits if benefit intent exists
            if intents['benefit_query']:
                benefits = get_product_info(product, "benefits")
                if benefits:
                    response_parts.append(f"🌟 Benefits:<br>- " + "<br>- ".join(benefits))
            
            # Add usage if mentioned
            if "use" in user_input or "usage" in user_input:
                usage = get_product_info(product, "usage")
                if usage:
                    response_parts.append(f"🔧 Usage:<br>- " + "<br>- ".join(usage))
            
            # Add recommendations
            if product.lower() in recommendations:
                response_parts.append(f"🤝 Customers also buy: {', '.join([r.title() for r in recommendations[product.lower()]])}")
            
            if response_parts:
                return jsonify(response="<br><br>".join(response_parts))

    # Handle order queries
    if intents['order_query']:
        order_responses = [
            f"🛒 To order, call us at {contact_data['phone']} or visit {contact_data['address']}",
            f"📲 Order via phone: {contact_data['phone']} or in-store at {contact_data['address']}",
            f"💳 For orders, contact {contact_data['phone']} or visit our store"
        ]
        return jsonify(response=get_random_response(order_responses))

    # Handle delivery queries
    if intents['delivery_query']:
        delivery_responses = [
            "🚚 Delivery takes 2 days in Coimbatore, 3-4 days elsewhere in India",
            "📦 Local delivery in 2 days, other locations in 3-4 working days",
            "⏱️ We dispatch within 24 hours, delivery time depends on location"
        ]
        return jsonify(response=get_random_response(delivery_responses))

    # Handle contact queries
    if intents['contact_query']:
        contact_responses = [
            f"📞 Call us at {contact_data['phone']}<br>"
            f"✉️ Email: {contact_data['email']}<br>"
            f"📍 Visit: {contact_data['address']}",
            
            f"Contact details:<br>Phone: {contact_data['phone']}<br>"
            f"Email: {contact_data['email']}<br>Address: {contact_data['address']}"
        ]
        return jsonify(response=get_random_response(contact_responses))

    # Handle FAQs
    for faq in faqs_data:
        if faq['question'].lower() in user_input.lower():
            return jsonify(response=faq['answer'])

    # Fallback response
    fallback_responses = [
        "🤖 I'm not sure I understand. Could you rephrase or ask about:<br>"
        "- Product prices<br>- Health benefits<br>- How to order<br>- Delivery info",
        
        "❓ I didn't catch that. Try asking about:<br>"
        "- Specific products (groundnut oil, ghee, etc.)<br>"
        "- Ordering process<br>- Store location<br>- Product benefits",
        
        "💡 Need help? You can ask:<br>"
        "- 'What are your products?'<br>- 'Price of coconut oil'<br>"
        "- 'How to order?'<br>- 'Contact information'"
    ]
    
    log_unanswered(user_input)
    return jsonify(response=get_random_response(fallback_responses))

@app.route("/feedback", methods=["POST"])
def feedback():
    feedback_data = request.json
    logging.info(f"Feedback received: {feedback_data}")
    return jsonify({"status": "success", "message": "Thank you for your feedback!"})

if __name__ == "__main__":
    app.run(debug=True)
