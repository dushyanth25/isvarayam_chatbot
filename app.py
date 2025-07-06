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
    "coconut oil": {
        "description": "Pure cold-pressed coconut oil with natural aroma and nutrients",
        "benefits": ["Boosts immunity", "Good for hair", "Skin moisturizer", "Contains MCTs"],
        "usage": ["Cooking", "Hair care", "Skin care", "Oil pulling"],
        "storage": "Store below 30°C, may solidify in cold temperatures"
    },
    "sesame oil": {
        "description": "Traditional cold-pressed sesame oil with rich flavor",
        "benefits": ["Rich in antioxidants", "Good for heart", "Anti-inflammatory", "High in zinc"],
        "usage": ["Tadka", "Massage oil", "Skin care", "Ayurvedic preparations"],
        "storage": "Store in airtight container away from light"
    },
    "ghee": {
        "description": "Pure cow's ghee made using traditional bilona method",
        "benefits": ["Boosts digestion", "Good for brain", "High smoke point", "Rich in CLA"],
        "usage": ["Cooking", "Ayurvedic medicine", "Drizzling on food", "Deep frying"],
        "storage": "Store in airtight container at room temperature"
    },
    "jaggery powder": {
        "description": "Unrefined natural sweetener made from sugarcane juice",
        "benefits": ["Rich in iron", "Better than sugar", "Boosts immunity", "Good for digestion"],
        "usage": ["Sweetening drinks", "Desserts", "Traditional sweets", "Healthy alternative to sugar"],
        "storage": "Store in airtight container in cool dry place"
    },
    "super pack": {
        "description": "Combo of our 3 premium oils (groundnut, coconut, sesame)",
        "benefits": ["Variety of oils", "Cost effective", "Complete cooking solution", "Healthy combination"],
        "usage": ["Daily cooking", "Different culinary uses", "Varied nutrition", "Gift option"],
        "storage": "Store each oil as per individual requirements"
    }
}

# Aliases and synonyms
alias_map = {
    "combo pack": "super pack", "oil combo": "super pack", "3 oil combo": "super pack",
    "combo": "super pack", "sugar": "jaggery powder", "oil pack": "super pack",
    "oil set": "super pack", "oil bundle": "super pack", "oil collection": "super pack",
    "oil trio": "super pack", "oil variety": "super pack", "oil combo pack": "super pack",
    "brown sugar": "jaggery powder", "natural sweetener": "jaggery powder",
    "natu sakarai": "jaggery powder", "sakarai": "jaggery powder"
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

# Keywords per intent
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
    return {
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
        'product_query': any(p.lower() in text for p in product_name_to_id.keys())
    }

# Helper to get product images
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

    # Handle image queries
    if intents['image_query']:
        if entities['products']:
            images = get_product_images(entities['products'][0])
            if images:
                return jsonify(response=f"Here are images of {entities['products'][0].title()}:", images=images)
        
        all_images = get_product_images()
        if all_images:
            return jsonify(response="Here are some of our product images:", images=random.sample(all_images, min(5, len(all_images))))
        return jsonify(response="I couldn't find images for that product.")

    # Handle oil queries
    if intents['oil_query']:
        oil_responses = [
            "We offer these premium cold-pressed oils:<br>- Groundnut oil<br>- Coconut oil<br>- Sesame oil",
            "Our oil collection includes:<br>- Traditional groundnut oil<br>- Pure coconut oil<br>- Nutritious sesame oil",
            "You can choose from:<br>- Groundnut oil for cooking<br>- Coconut oil for hair/skin<br>- Sesame oil for its rich flavor"
        ]
        return jsonify(response=get_random_response(oil_responses))

    # Handle benefit queries
    if intents['benefit_query']:
        if entities['products']:
            benefits = get_product_info(entities['products'][0], "benefits")
            if benefits:
                return jsonify(response=f"🌟 Benefits of {entities['products'][0].title()}:<br>- " + "<br>- ".join(benefits))
        
        return jsonify(response=f"Here are health benefits of our products:<br><br>{get_all_benefits()}")

    # Handle usage queries
    if intents['usage_query']:
        if entities['products']:
            usage = get_product_info(entities['products'][0], "usage")
            if usage:
                return jsonify(response=f"🔧 How to use {entities['products'][0].title()}:<br>- " + "<br>- ".join(usage))
        
        return jsonify(response="Please specify which product you'd like usage information for.")

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
            if intents['usage_query']:
                usage = get_product_info(product, "usage")
                if usage:
                    response_parts.append(f"🔧 Usage:<br>- " + "<br>- ".join(usage))
            
            # Add images if image intent exists
            if intents['image_query']:
                images = get_product_images(product)
                if images:
                    response_parts.append(f"Here are images of {product.title()}:")
                    return jsonify(response="<br><br>".join(response_parts), images=images)
            
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
