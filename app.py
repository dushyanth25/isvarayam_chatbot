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

# Enhanced product knowledge base with attributes
product_data = {
    "groundnut oil": {
        "description": "Cold-pressed groundnut oil rich in vitamin E and healthy fats",
        "benefits": ["Heart healthy", "Rich in Vitamin E", "Good for skin", "High smoke point"],
        "usage": ["Cooking", "Frying", "Salad dressing", "Skin moisturizer"],
        "best_for": ["frying", "high heat cooking", "heart health"],
        "attributes": {
            "smoke_point": "230°C",
            "rating": 4.7
        }
    },
    "coconut oil": {
        "description": "Pure cold-pressed coconut oil with natural aroma and nutrients",
        "benefits": ["Boosts immunity", "Good for hair", "Skin moisturizer", "Contains MCTs"],
        "usage": ["Cooking", "Hair care", "Skin care", "Oil pulling"],
        "best_for": ["hair care", "skin care", "immunity"],
        "attributes": {
            "rating": 4.9
        }
    },
    "sesame oil": {
        "description": "Traditional cold-pressed sesame oil with rich flavor",
        "benefits": ["Rich in antioxidants", "Good for heart", "Anti-inflammatory", "High in zinc"],
        "usage": ["Tadka", "Massage oil", "Skin care", "Ayurvedic preparations"],
        "best_for": ["massage", "ayurveda", "flavor"],
        "attributes": {
            "rating": 4.5
        }
    },
    "ghee": {
        "description": "Pure cow's ghee made using traditional bilona method",
        "benefits": ["Boosts digestion", "Good for brain", "High smoke point", "Rich in CLA"],
        "usage": ["Cooking", "Ayurvedic medicine", "Drizzling on food", "Deep frying"],
        "best_for": ["digestion", "brain health", "taste"],
        "attributes": {
            "rating": 4.8
        }
    },
    "jaggery powder": {
        "description": "Unrefined natural sweetener made from sugarcane juice",
        "benefits": ["Rich in iron", "Better than sugar", "Boosts immunity", "Good for digestion"],
        "usage": ["Sweetening drinks", "Desserts", "Traditional sweets", "Healthy alternative to sugar"],
        "best_for": ["iron deficiency", "natural sweetener"],
        "attributes": {
            "rating": 4.6
        }
    },
    "super pack": {
        "description": "Combo of our 3 premium oils (groundnut, coconut, sesame)",
        "benefits": ["Variety of oils", "Cost effective", "Complete cooking solution", "Healthy combination"],
        "usage": ["Daily cooking", "Different culinary uses", "Varied nutrition", "Gift option"],
        "best_for": ["gifting", "variety", "complete kitchen"],
        "attributes": {
            "rating": 4.9
        }
    }
}

# Updated alias map
alias_map = {
    "combo pack": "super pack", "oil combo": "super pack", "3 oil combo": "super pack",
    "combo": "super pack", "sugar": "jaggery powder", "oil pack": "super pack",
    "oil set": "super pack", "oil bundle": "super pack", "oil collection": "super pack",
    "oil trio": "super pack", "oil variety": "super pack", "oil combo pack": "super pack",
    "brown sugar": "jaggery powder", "natural sweetener": "jaggery powder",
    "natu sakarai": "jaggery powder", "sakarai": "jaggery powder",
    "chekku ennai": "groundnut oil", "kachi ghani": "groundnut oil",
    "marachekku": "groundnut oil", "cold pressed": "oil"
}

# Updated recommendations with ratings
recommendations = {
    "groundnut oil": ["coconut oil", "sesame oil", "super pack", "ghee"],
    "coconut oil": ["sesame oil", "groundnut oil", "super pack", "jaggery powder"],
    "sesame oil": ["groundnut oil", "coconut oil", "super pack", "ghee"],
    "ghee": ["jaggery powder", "super pack"],
    "jaggery powder": ["ghee", "coconut oil"],
    "super pack": ["groundnut oil", "coconut oil", "sesame oil", "jaggery powder"]
}

# Updated intent keywords
best_keywords = ["best", "top", "recommend", "healthiest", "popular", "favorite", "suggest"]
greetings = ["hi", "hello", "good morning", "good evening", "good afternoon", "hey", "yo", "hola", "what's up", "greetings", "hi there", "hello there", "hey there", "hiya", "howdy", "hey!", "good day!", "hello, assistant"]
price_keywords = ["price", "cost", "how much", "rate", "pricing", "amount", "value", "tell me the cost", "what's the rate", "product pricing", "list all prices", "give me product cost", "cost details", "item rates", "prices please"]
image_keywords = ["images", "show image", "product image", "picture", "photos", "pics", "can i see images", "show me product pictures", "send me photos", "display images", "i want pictures", "visuals of items", "product visuals", "give me pics"]
oil_keywords = ["oil", "oils", "ennai", "checku ennai", "oil types", "types of oil", "do you sell oils", "show your oils", "list oils", "oil categories", "ennai types", "cold pressed oils", "oil products", "all oil names"]
benefit_keywords = ["benefit", "advantage", "why use", "good for", "healthy", "nutritious", "wellness", "pros", "positive", "help", "why is it good", "tell me health benefits", "product advantages", "is it nutritious", "healthy effects", "good for body", "any advantages"]
usage_keywords = ["how to use", "usage", "application", "recipe", "cook", "use this for", "usage examples", "what can i do with this", "can i cook with it", "how to use this", "where can i use this", "what's this for", "any recipes", "application of this", "in what way do i use this", "cooking use"]
order_keywords = ["order", "buy", "purchase", "get", "want", "need", "acquire", "shop", "checkout", "cart", "payment", "pay", "i'd like to place an order", "how to purchase", "add this to cart", "order now", "i want to shop", "book this product", "place this order"]
delivery_keywords = ["delivery", "shipping", "dispatch", "arrive", "receive", "when get", "time take", "courier", "ship", "transport", "delivery charges", "is delivery free", "shipping days", "courier time", "how fast is delivery", "any delivery fee", "expected delivery"]
contact_keywords = ["contact", "call", "phone", "number", "email", "address", "location", "where", "visit", "store", "shop", "give me contact info", "need your number", "i want your address", "what's your phone", "email id", "where to call", "contact number"]
faq_keywords = ["cold-pressed", "organic", "preservatives", "how is oil made", "why choose", "pure jaggery", "store ghee", "shelf life", "return policy", "ship outside india"]

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
        'price_query': any(word in text for word in price_keywords),
        'image_query': any(word in text for word in image_keywords),
        'oil_query': any(word in text for word in oil_keywords),
        'benefit_query': any(word in text for word in benefit_keywords),
        'usage_query': any(word in text for word in usage_keywords),
        'order_query': any(word in text for word in order_keywords),
        'delivery_query': any(word in text for word in delivery_keywords),
        'contact_query': any(word in text for word in contact_keywords),
        'faq_query': any(word in text for word in faq_keywords),
        'product_query': any(p.lower() in text for p in product_name_to_id.keys()),
        'best_query': any(word in text for word in best_keywords)
    }
    return intents

def get_product_images(product_name=None):
    if product_name:
        product_name = product_name.lower()
        db_name = alias_map.get(product_name, product_name)

        if db_name in ["oil", "oils", "ennai", "checku ennai"]:
            all_images = []
            for oil_name in ["groundnut oil", "coconut oil", "sesame oil"]:
                item = products.find_one({"name": {"$regex": oil_name, "$options": "i"}})
                if item and "images" in item:
                    all_images.extend(item["images"])
            return all_images

        if db_name in ["sugar", "sakarai", "natu sakarai", "jaggery", "jaggery powder"]:
            item = products.find_one({"name": {"$regex": "jaggery powder", "$options": "i"}})
            if item and "images" in item:
                return [img for img in item["images"]]

        item = products.find_one({"name": {"$regex": db_name, "$options": "i"}})
        if item and "images" in item:
            return [img for img in item["images"]]
    else:
        all_images = []
        for item in products.find():
            if "images" in item:
                all_images.extend(item["images"])
        return all_images
    return []

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

def get_all_benefits():
    benefit_lines = []
    for product, data in product_data.items():
        if "benefits" in data:
            benefit_lines.append(f"🌟 <b>{product.title()}</b>:<br>- " + "<br>- ".join(data["benefits"]))
    return "<br><br>".join(benefit_lines)

def get_top_rated_products(limit=3):
    """Returns top rated products based on reviews"""
    top_products = list(reviews.aggregate([
        {"$group": {"_id": "$product_id", "avg_rating": {"$avg": "$rating"}}},
        {"$sort": {"avg_rating": -1}},
        {"$limit": limit}
    ]))
    
    result = []
    for product in top_products:
        product_name = product_map.get(product["_id"], "Product")
        result.append(f"{product_name} (⭐ {product['avg_rating']:.1f}/5)")
    return result

def get_best_for_use_case(use_case):
    """Returns best product for specific use case"""
    matched_products = []
    for product, data in product_data.items():
        if "best_for" in data and use_case in data["best_for"]:
            rating = data["attributes"].get("rating", 0)
            matched_products.append((product, rating))
    
    if not matched_products:
        return None
    
    # Sort by rating
    matched_products.sort(key=lambda x: x[1], reverse=True)
    return matched_products[0][0]

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

    # Handle best/top/recommendation queries
    if intents['best_query']:
        # Check for specific use cases
        doc = nlp(user_input.lower())
        use_cases = [token.text for token in doc if token.pos_ == "NOUN" and token.text not in best_keywords]
        
        if use_cases:
            # Handle "best for X" queries
            best_product = get_best_for_use_case(use_cases[0])
            if best_product:
                benefits = get_product_info(best_product, "benefits")
                response = (f"✨ For {use_cases[0]}, our <b>{best_product.title()}</b> is recommended "
                           f"(⭐ {product_data[best_product]['attributes'].get('rating', 4.5)}/5):<br>"
                           f"- " + "<br>- ".join(benefits[:3]))
                return jsonify(response=response)
        
        # Handle general "best" queries
        top_products = get_top_rated_products(3)
        if top_products:
            return jsonify(response="🏆 Our top-rated products:<br>- " + "<br>- ".join(top_products))
        else:
            popular_products = ["Super Pack", "Coconut Oil", "Ghee"]  # Fallback
            return jsonify(response="🌟 Customer favorites:<br>- " + "<br>- ".join(popular_products))

    # [Rest of your existing intent handlers...]
    # (Price queries, image queries, etc. remain the same as in your original code)

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
