from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from bson import ObjectId
import json
from datetime import datetime
from difflib import get_close_matches
import os
import random
import re

app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')

# MongoDB connection
mongo_uri = os.environ.get("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["isvaryam"]
products = db["products"]
reviews = db["reviews"]

# Local data
with open("ingredients.json") as f:
    ingredients_data = json.load(f)
with open("contact.json") as f:
    contact_data = json.load(f)

# Product mappings and configurations
tanglish_map = {
    "chekku ennai": "sesame oil", "chekku oil": "sesame oil", "chekku": "sesame oil",
    "naalennai": "sesame oil", "gingelly oil": "sesame oil", "nellennai": "sesame oil",
    "kadalai ennai": "groundnut oil", "groundnut ennai": "groundnut oil", 
    "kadalai oil": "groundnut oil", "verkadalai ennai": "groundnut oil",
    "coconut ennai": "coconut oil", "thengai ennai": "coconut oil", 
    "ennai": "oil", "thengai ennai": "coconut oil", 
    "thengai oil": "coconut oil", "vennai": "coconut oil",
    "sakkarai": "jaggery powder", "vellam": "jaggery powder", 
    "karupatti": "jaggery powder", "panai vellam": "jaggery powder",
    "nei": "ghee", "vennai": "ghee", "thuppa": "ghee",
    "combo pack": "super pack", "oil combo": "super pack", 
    "3 oil combo": "super pack", "combo": "super pack",
    "oil pack": "super pack", "oil set": "super pack", 
    "oil bundle": "super pack", "oil collection": "super pack",
    "oil trio": "super pack", "oil variety": "super pack", 
    "oil combo pack": "super pack",
    "sugar": "jaggery powder", "brown sugar": "jaggery powder", 
    "natural sweetener": "jaggery powder"
}

alias_map = {
    "combo pack": "super pack", "oil combo": "super pack", "3 oil combo": "super pack",
    "combo": "super pack", "sugar": "jaggery powder", "oil pack": "super pack",
    "oil set": "super pack", "oil bundle": "super pack", "oil collection": "super pack",
    "oil trio": "super pack", "oil variety": "super pack", "oil combo pack": "super pack",
    "brown sugar": "jaggery powder", "natural sweetener": "jaggery powder",
    "gingelly oil": "sesame oil", "peanut oil": "groundnut oil"
}

combined_map = {**tanglish_map, **alias_map}

# Product links
product_links = {
    "coconut oil": "https://isvaryam.com/products/cold-pressed-coconut-oil?sku_id=24459981",
    "groundnut oil": "https://isvaryam.com/products/cold-pressed-groundnut-oil?sku_id=26795436",
    "sesame oil": "https://isvaryam.com/products/cold-pressed-sesame-oil?sku_id=26795647",
    "jaggery powder": "https://isvaryam.com/products/organic-jaggery-powder?sku_id=24463067",
    "super pack": "https://isvaryam.com/products/super-pack-1-lt-coconut-oil-1-lt-sesame-oil-1-lt-groundnut-oil?sku_id=24633382",
    "ghee": "https://isvaryam.com"  # Add actual ghee link when available
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

# Benefits information
product_benefits = {
    "groundnut oil": ["Heart healthy", "Rich in Vitamin E", "Good for skin", "High smoke point"],
    "coconut oil": ["Boosts immunity", "Great for hair care", "Natural moisturizer", "Antimicrobial properties"],
    "sesame oil": ["Rich in antioxidants", "Good for bone health", "Anti-inflammatory", "Helps reduce stress"],
    "ghee": ["Improves digestion", "Boosts immunity", "Good for brain function", "Rich in fat-soluble vitamins"],
    "jaggery powder": ["Natural detoxifier", "Rich in iron", "Good for digestion", "Better than refined sugar"],
    "super pack": ["Variety of oils", "Cost effective", "Try different options", "Complete cooking solution"]
}

# Security and content filtering
OFFENSIVE_KEYWORDS = {
    "sex", "rape", "porn", "fuck", "shit", "ass", "dick", "rat", "cock", "pussy", "gommapunda", "goma", "kenathayoli", 
    "cunt", "bitch", "slut", "whore", "penis", "vagina", "boobs", "nude", "punda", "gotha", "thailii", "thayoli", "thayolli", "oombu", "ombu", "gomma", "kenap", "kenappunda", "gothapunda",
    "naked", "xxx", "adult", "nsfw", "hentai", "incest", "molest", "pedo"
}

UNRELATED_KEYWORDS = {
    "movie", "sports", "music", "politics", "religion", "football", "cricket","lusu","mairu"
    "weather", "news", "bitcoin", "crypto", "stock", "elon", "musk", "ai", "gugan", "sannathayoli", "sannanai",
    "chatgpt", "google", "facebook", "tiktok", "instagram", "whatsapp","pranaesh","sannam","deepak"
}

PRODUCT_GUIDANCE_RESPONSES = [
    "🌿 I specialize in Isvaryam products. Ask about: <b>sesame oil</b>, <b>coconut oil</b>, or <b>ghee</b>!",
    "🛢️ Need help with oils? Try: <b>'price of groundnut oil'</b> or <b>'benefits of coconut oil'</b>",
    "💡 Example queries: <br>- <b>'Show sesame oil prices'</b><br>- <b>'What's in your super pack?'</b>"
]

# Initialize product mappings
product_map = {str(p["_id"]): p["name"] for p in products.find()}
product_name_to_id = {p["name"].lower(): str(p["_id"]) for p in products.find()}

# Helper functions
def is_invalid_query(user_input):
    """Check if query contains offensive/unrelated terms"""
    words = set(re.findall(r'\w+', user_input.lower()))
    return bool(words & OFFENSIVE_KEYWORDS or words & UNRELATED_KEYWORDS)

def get_greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Good Day"
    elif hour < 17:
        return "Good Day"
    return "Good Day"

def get_random_response(responses):
    return random.choice(responses)

def get_all_prices():
    all_items = products.find()
    price_lines = []
    for item in all_items:
        name = item.get("name", "Product").title()
        prices = [f"{q['size']} - ₹{q['price']}" for q in item.get("quantities", [])]
        product_link = product_links.get(name.lower(), "https://isvaryam.com")
        price_lines.append(f"💰 <b>{name}</b>: {', '.join(prices)} <a href='{product_link}' target='_blank'>[Buy Now]</a>")
    return "<br><br>".join(price_lines)

def get_all_benefits():
    all_items = products.find()
    benefit_lines = []
    for item in all_items:
        name = item.get("name", "Product").lower()
        benefits = product_benefits.get(name, [
            "100% natural and chemical-free",
            "Made with traditional methods",
            "Rich in nutrients and health benefits",
            "Premium quality product"
        ])
        product_link = product_links.get(name, "https://isvaryam.com")
        benefit_lines.append(f"🌟 <b>{name.title()}</b>:<br>- " + "<br>- ".join(benefits) + f"<br><a href='{product_link}' target='_blank'>[View Product]</a>")
    return "<br><br>".join(benefit_lines)

def translate_tanglish_to_english(user_input):
    """Convert Tanglish terms to standard product names"""
    user_input = user_input.lower()
    
    # First check for exact matches
    for tanglish, english in combined_map.items():
        if tanglish in user_input:
            return english
    
    # Then check for partial matches with word boundaries
    words = re.findall(r'\b\w+\b', user_input)
    for word in words:
        if word in combined_map:
            return combined_map[word]
    
    # Check for common oil terms
    oil_terms = ["oil", "ennai", "taila", "thailam"]
    if any(term in user_input for term in oil_terms):
        if "kadalai" in user_input or "peanut" in user_input or "groundnut" in user_input:
            return "groundnut oil"
        elif "thengai" in user_input or "coconut" in user_input:
            return "coconut oil"
        elif "chekku" in user_input or "gingelly" in user_input or "nalla" in user_input or "gingerly" in user_input:
            return "sesame oil"
        elif "isvaryam" in user_input:
            return None  # Let the main logic handle brand-specific queries
    
    # Check for other product terms
    if "sakkarai" in user_input or "vellam" in user_input or "karupatti" in user_input:
        return "jaggery powder"
    elif "nei" in user_input or "ghee" in user_input or "thuppa" in user_input:
        return "ghee"
    
    return None

def extract_product_name(user_input):
    """Extract product name from user input with Tanglish support and security checks"""
    if is_invalid_query(user_input):
        return None
        
    # First try Tanglish translation
    translated = translate_tanglish_to_english(user_input)
    if translated:
        return translated
    
    # Then check for exact product names
    user_input = user_input.lower()
    for pname in product_name_to_id.keys():
        if pname in user_input:
            return pname
    
    # Check for partial matches with word boundaries
    words = re.findall(r'\b\w+\b', user_input)
    for word in words:
        if word in combined_map:
            return combined_map[word]
    
    # Check for generic oil queries only if brand is mentioned
    if "oil" in user_input and ("isvaryam" in user_input or "your" in user_input or "product" in user_input):
        if "groundnut" in user_input or "peanut" in user_input:
            return "groundnut oil"
        elif "coconut" in user_input:
            return "coconut oil"
        elif "sesame" in user_input or "gingelly" in user_input:
            return "sesame oil"
        elif "ghee" in user_input:
            return "ghee"
        elif "jaggery" in user_input or "sugar" in user_input:
            return "jaggery powder"
        elif "combo" in user_input or "pack" in user_input:
            return "super pack"
    
    # Fuzzy match product info
    all_product_names = list(ingredients_data.keys()) + list(combined_map.keys())
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
        return combined_map.get(pname, pname)
    
    return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chatbot", methods=["POST"])
def chatbot():
    try:
        user_input = request.json.get("message", "").lower().strip()

        # Block invalid queries immediately
        if is_invalid_query(user_input):
            return jsonify(
                response=get_random_response(PRODUCT_GUIDANCE_RESPONSES),
                status=200
            )

        # Handle "isvaryam" or "about isvaryam" queries
        if "isvaryam" in user_input and ("about" in user_input or "what" in user_input or "who" in user_input or "tell me" in user_input):
            about_responses = [
                "We are Isvaryam, offering premium natural products including: Groundnut Oil, Coconut Oil, Sesame Oil, Ghee, Jaggery Powder, and our Super Pack (1L each of 3 oils).",
                "Isvaryam specializes in high-quality natural products. Our range includes: Groundnut Oil, Coconut Oil, Sesame Oil, Ghee, Jaggery Powder, and a Super Pack combo.",
                "At Isvaryam, we sell these authentic products: Groundnut Oil, Coconut Oil, Sesame Oil, Ghee, Jaggery Powder, and our popular Super Pack."
            ]
            return jsonify(response=get_random_response(about_responses))

        # Handle simple price query
        if user_input in ["price", "prices", "price details", "cost", "rate"]:
            return jsonify(response=f"Here are all our product prices:<br><br>{get_all_prices()}")

        # Handle simple benefits query
        if user_input in ["benefits", "benefit", "product benefits", "health benefits", "advantages"]:
            return jsonify(response=f"Here are the benefits of all our products:<br><br>{get_all_benefits()}")

        # Expanded greeting responses
        greetings = ["hi", "hello", 
                    "hey", "yo", "hola", "what's up", "greetings", "hi there", 
                    "hello there", "hey there", "hiya", "howdy"]
        
        greeting_responses = [
            f"{get_greeting()}! I'm Isvaryam's helpful assistant. How can I serve you today?",
            f"{get_greeting()}! Welcome to Isvaryam. What can I help you with?",
            f"{get_greeting()}! I'm here to assist with your Isvaryam product queries. How may I help?",
            f"{get_greeting()}! Ready to explore Isvaryam's natural products? What would you like to know?"
        ]

        # Expanded silly/fun responses
        silly_queries = ["are you real", "can i marry you", "what's your name", "do you love me", 
                        "you single", "can you cook", "sing a song", "tell a joke", "you look nice", 
                        "you cute", "what is 0/0", "do you sleep", "are you ai", "how are you", 
                        "how do you know this", "what are you", "who made you", "are you human",
                        "do you dream", "what do you eat", "your age", "how old are you"]
        
        silly_responses = [
            "😄 I'm just a virtual assistant here to talk about Isvaryam's wonderful products!",
            "🤖 I'm a chatbot focused on oils and natural products - let's keep it professional!",
            "😊 While I appreciate the chat, I'm here to help with product queries. What would you like to know?",
            "💡 I exist to share information about Isvaryam's natural products. How can I assist you?"
        ]

        # Handle greetings
        if any(greet in user_input for greet in greetings):
            return jsonify(response=get_random_response(greeting_responses))

        # Handle silly queries
        if any(word in user_input for word in silly_queries):
            return jsonify(response=get_random_response(silly_responses))

        # Handle location/contact queries
        if any(word in user_input for word in ["location","contact","contact isvaryam","isvaryam contact","isvaryam location","location of isvaryam", "where is isvaryam", "where is your store", "store address", 
                                            "address", "location of company", "physical store", "visit us", 
                                            "come to shop", "outlet", "shop location"]):
            contact_response = [
                f"📞 Phone: {contact_data['phone']}<br>"
                f"✉️ Email: {contact_data['email']}<br>"
                f"📍 Address: {contact_data['address']}",
                
                f"Here's how to reach us:<br>"
                f"Call: {contact_data['phone']}<br>"
                f"Email: {contact_data['email']}<br>"
                f"Visit: {contact_data['address']}",
                
                f"Our contact details:<br>"
                f"Phone: {contact_data['phone']}<br>"
                f"Email: {contact_data['email']}<br>"
                f"Store: {contact_data['address']}"
            ]
            return jsonify(response=get_random_response(contact_response))

        # Handle delivery queries
        if any(word in user_input for word in ["delivery","deliver", "shipping", "how many days", "when will it reach", 
                                            "delivery time", "how fast", "dispatch", "courier", "shipment", 
                                            "arrival time", "when delivered", "reach my home", "reach my place",
                                            "shipping policy", "delivery options", "shipping cost", "delivery charges"]):
            delivery_response = [
                "🚚 We deliver to Coimbatore in 2 days and to other cities in 3–4 days.",
                "📦 Delivery takes 2 days in Coimbatore and 3-4 days to other locations.",
                "⏱️ Local Coimbatore orders arrive in 2 days, other cities in 3-4 days."
            ]
            return jsonify(response=get_random_response(delivery_response))

        # Handle product list queries
        if any(word in user_input for word in ["products","isvaryam", "what do you have", "show all", "available items", 
                                            "list items", "what can i buy", "items available", "product catalog",
                                            "all offerings", "complete list", "full range", "entire collection"]):
            product_list_response = [
                "📦 We offer: <a href='https://isvaryam.com/products/cold-pressed-groundnut-oil?sku_id=26795436' target='_blank'>Groundnut Oil</a>, <a href='https://isvaryam.com/products/cold-pressed-coconut-oil?sku_id=24459981' target='_blank'>Coconut Oil</a>, <a href='https://isvaryam.com/products/cold-pressed-sesame-oil?sku_id=26795647' target='_blank'>Sesame Oil</a>, Ghee, <a href='https://isvaryam.com/products/organic-jaggery-powder?sku_id=24463067' target='_blank'>Jaggery Powder</a>, and our <a href='https://isvaryam.com/products/super-pack-1-lt-coconut-oil-1-lt-sesame-oil-1-lt-groundnut-oil?sku_id=24633382' target='_blank'>Super Pack</a> (1L each of 3 oils).",
                "🛍️ Our products include: <a href='https://isvaryam.com/products/cold-pressed-groundnut-oil?sku_id=26795436' target='_blank'>Groundnut Oil</a>, <a href='https://isvaryam.com/products/cold-pressed-coconut-oil?sku_id=24459981' target='_blank'>Coconut Oil</a>, <a href='https://isvaryam.com/products/cold-pressed-sesame-oil?sku_id=26795647' target='_blank'>Sesame Oil</a>, Ghee, <a href='https://isvaryam.com/products/organic-jaggery-powder?sku_id=24463067' target='_blank'>Jaggery Powder</a>, and a <a href='https://isvaryam.com/products/super-pack-1-lt-coconut-oil-1-lt-sesame-oil-1-lt-groundnut-oil?sku_id=24633382' target='_blank'>Super Pack</a> combo.",
                "🛒 Available products: <a href='https://isvaryam.com/products/cold-pressed-groundnut-oil?sku_id=26795436' target='_blank'>Groundnut Oil</a>, <a href='https://isvaryam.com/products/cold-pressed-coconut-oil?sku_id=24459981' target='_blank'>Coconut Oil</a>, <a href='https://isvaryam.com/products/cold-pressed-sesame-oil?sku_id=26795647' target='_blank'>Sesame Oil</a>, Ghee, <a href='https://isvaryam.com/products/organic-jaggery-powder?sku_id=24463067' target='_blank'>Jaggery Powder</a>, and our popular <a href='https://isvaryam.com/products/super-pack-1-lt-coconut-oil-1-lt-sesame-oil-1-lt-groundnut-oil?sku_id=24633382' target='_blank'>Super Pack</a>."
            ]
            return jsonify(response=get_random_response(product_list_response))

        # Extract product name with Tanglish support
        pname = extract_product_name(user_input)
        if pname:
            # Handle benefit queries
            if "benefit" in user_input or "advantage" in user_input or any(word in user_input for word in ["good for", "why use"]):
                benefits = product_benefits.get(pname, [
                    "100% natural and chemical-free",
                    "Made with traditional methods",
                    "Rich in nutrients and health benefits",
                    "Premium quality product"
                ])
                product_link = product_links.get(pname, "https://isvaryam.com")
                return jsonify(
                    response=f"🌟 Benefits of {pname.title()}:<br>- " + 
                    "<br>- ".join(benefits) + 
                    f"<br><br><a href='{product_link}' target='_blank'>[View Product Details]</a>"
                )

            # Reviews intent
            if any(word in user_input for word in ["reviews", "product reviews", "show reviews", "customer feedback", "testimonials"]):
                prod_id = ObjectId(product_name_to_id.get(pname, ""))
                if prod_id:
                    revs = list(reviews.find({"productId": prod_id}))
                    if not revs:
                        product_link = product_links.get(pname, "https://isvaryam.com")
                        return jsonify(response=f"No reviews yet for {pname.title()}. <a href='{product_link}' target='_blank'>Be the first to review!</a>")
                    response_lines = [f"🗣️ {r['review']} ({r.get('rating', 0)}/5)" for r in revs]
                    product_link = product_links.get(pname, "https://isvaryam.com")
                    return jsonify(
                        response=f"<b>Reviews for {pname.title()}:</b><br>" + 
                        "<br>".join(response_lines) + 
                        f"<br><br><a href='{product_link}' target='_blank'>[Purchase Now]</a>"
                    )

            # Rating intent
            if "rating" in user_input:
                prod_id = ObjectId(product_name_to_id.get(pname, ""))
                if prod_id:
                    product_reviews = list(reviews.find({"productId": prod_id}))
                    if product_reviews:
                        avg = sum([r.get("rating", 0) for r in product_reviews]) / len(product_reviews)
                        product_link = product_links.get(pname, "https://isvaryam.com")
                        return jsonify(
                            response=f"⭐ Average rating for {pname.title()}: {round(avg,1)}/5 based on {len(product_reviews)} reviews.<br>" +
                            f"<a href='{product_link}' target='_blank'>[View Product]</a>"
                        )
                    else:
                        product_link = product_links.get(pname, "https://isvaryam.com")
                        return jsonify(
                            response=f"⚠️ No ratings available for {pname.title()}. " +
                            f"<a href='{product_link}' target='_blank'>[Be the first to review]</a>"
                        )

            # Get product info from database
            db_name = combined_map.get(pname, pname)
            item = products.find_one({"name": {"$regex": db_name, "$options": "i"}})
            if not item:
                return jsonify(response=f"Sorry, I couldn't find information for {db_name.title()}.")

            response_parts = []
            product_link = product_links.get(db_name, "https://isvaryam.com")

            if any(word in user_input for word in ["price", "cost", "rate", "how much"]):
                prices = [f"{q['size']} - ₹{q['price']}" for q in item.get("quantities", [])]
                response_parts.append(f"🛒 {db_name.title()} Prices: {', '.join(prices)} <a href='{product_link}' target='_blank'>[Buy Now]</a>")

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

            if any(word in user_input for word in ["benefit", "advantages", "features", "why choose", "good for", 
                                                "health benefits", "nutritional value", "why use", "pros", "uses",
                                                "how helps", "what's good", "positive effects", "nutrition", "healthy",
                                                "wellness", "advantages of"]):
                benefits = product_benefits.get(db_name, [
                    "100% natural and chemical-free",
                    "Made with traditional methods",
                    "Rich in nutrients and health benefits",
                    "Premium quality product"
                ])
                response_parts.append(f"🌟 Benefits of {db_name.title()}:<br>- " + "<br>- ".join(benefits))

            if not response_parts:
                desc = item.get("description", "This is a premium product made with care.")
                response_parts.append(f"📝 {db_name.title()}: {desc}")

            # Always include product link at the end
            response_parts.append(f"<a href='{product_link}' target='_blank'>[View Product Details]</a>")

            related = recommendations.get(db_name, [])
            if related:
                related_links = []
                for r in related:
                    r_link = product_links.get(r, "https://isvaryam.com")
                    related_links.append(f"<a href='{r_link}' target='_blank'>{r.title()}</a>")
                response_parts.append(f"🤝 Customers also buy: {', '.join(related_links)}")

            return jsonify(response="<br><br>".join(response_parts))

        # Handle all reviews request
        if any(word in user_input for word in ["reviews", "review", "product reviews", "show reviews", "customer feedback", "testimonials"]):
            review_list = reviews.find()
            product_reviews = {}
            for rev in review_list:
                prod_id = str(rev.get("productId"))
                prod_name = product_map.get(prod_id, "Unknown Product")
                text = rev.get("review", "No text")
                product_link = product_links.get(prod_name.lower(), "https://isvaryam.com")
                product_reviews.setdefault(prod_name, []).append(
                    f"🗣️ {text} ({rev.get('rating', 0)}/5) <a href='{product_link}' target='_blank'>[View Product]</a>"
                )
            response = ""
            for pname, revs in product_reviews.items():
                response += f"<b>{pname.title()}</b>:<br>" + "<br>".join(revs) + "<br><br>"
            return jsonify(response=response.strip() if response else "No reviews available yet.")

        # Handle all ratings request
        if any(word in user_input for word in ["ratings", "rate all", "average rating", "all ratings"]):
            response_lines = []
            for pid, pname in product_map.items():
                product_reviews = list(reviews.find({"productId": ObjectId(pid)}))
                product_link = product_links.get(pname.lower(), "https://isvaryam.com")
                if product_reviews:
                    avg = sum([r.get("rating", 0) for r in product_reviews]) / len(product_reviews)
                    response_lines.append(
                        f"⭐ {pname.title()}: {round(avg, 1)}/5 ({len(product_reviews)} reviews) " +
                        f"<a href='{product_link}' target='_blank'>[View Product]</a>"
                    )
                else:
                    response_lines.append(
                        f"⭐ {pname.title()}: No reviews yet " +
                        f"<a href='{product_link}' target='_blank'>[Be the first to review]</a>"
                    )
            return jsonify(response="<br><br>".join(response_lines))

        # Default response with more suggestions
        default_responses = [
            "🤖 I didn't catch that. Try asking about:<br>- Product prices<br>- Oil types<br>- How to order<br>- Delivery info<br>- Product benefits",
            "❓ Not sure I understand. You can ask about:<br>- Specific products<br>- Ordering process<br>- Store location<br>- Product reviews<br>- Payment options",
            "💡 Need help? Try asking about:<br>- Our product range<br>- Pricing details<br>- Health benefits<br>- How to contact us<br>- Current offers"
        ]
        return jsonify(response=get_random_response(default_responses))

    except Exception as e:
        app.logger.error(f"Error in chatbot: {str(e)}")
        return jsonify(response="⚠️ Sorry, something went wrong. Please try again."), 500

if __name__ == "__main__":
    app.run(debug=True)
