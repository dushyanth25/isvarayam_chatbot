from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from bson import ObjectId
import json
from datetime import datetime
from difflib import get_close_matches
import os
import random

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

# Aliases
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

# Benefits information
product_benefits = {
    "groundnut oil": ["Heart healthy", "Rich in Vitamin E", "Good for skin", "High smoke point"],
    "coconut oil": ["Boosts immunity", "Great for hair care", "Natural moisturizer", "Antimicrobial properties"],
    "sesame oil": ["Rich in antioxidants", "Good for bone health", "Anti-inflammatory", "Helps reduce stress"],
    "ghee": ["Improves digestion", "Boosts immunity", "Good for brain function", "Rich in fat-soluble vitamins"],
    "jaggery powder": ["Natural detoxifier", "Rich in iron", "Good for digestion", "Better than refined sugar"],
    "super pack": ["Variety of oils", "Cost effective", "Try different options", "Complete cooking solution"]
}

# Review helpers
product_map = {str(p["_id"]): p["name"] for p in products.find()}
product_name_to_id = {p["name"].lower(): str(p["_id"]) for p in products.find()}

def get_greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning ☀️"
    elif hour < 17:
        return "Good afternoon 🌤️"
    return "Good evening 🌙"

def get_random_response(responses):
    return random.choice(responses)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chatbot", methods=["POST"])
def chatbot():
    user_input = request.json.get("message", "").lower().strip()

    # Expanded greeting responses
    greetings = ["hi", "hello", "good morning", "good evening", "good afternoon", 
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

    # Expanded location/contact responses
    location_keywords = ["location", "where is isvaryam", "where is your store", "store address", 
                        "address", "location of company", "physical store", "visit us", 
                        "come to shop", "outlet", "shop location"]
    
    contact_keywords = ["contact", "phone", "email", "reach you", "call", "number", 
                       "contact info", "customer care", "support", "helpline", "contact number"]

    # Expanded delivery responses
    delivery_keywords = ["delivery", "shipping", "how many days", "when will it reach", 
                        "delivery time", "how fast", "dispatch", "courier", "shipment", 
                        "arrival time", "when delivered", "reach my home", "reach my place",
                        "shipping policy", "delivery options", "shipping cost", "delivery charges"]

    # Expanded image responses
    image_keywords = ["all images", "show all images", "product images", "pictures of products", 
                     "show products visually", "display items", "product photos", "see products",
                     "product gallery", "visual catalog", "show me pictures", "can i see"]

    # Expanded product type responses
    type_keywords = ["types of oil", "oil types", "types of products", "products offered", 
                    "what do you sell", "offered by isvaryam", "range of oils", "product range",
                    "product categories", "what products", "what items", "product list",
                    "inventory", "catalog", "offerings"]

    # Expanded order responses
    order_keywords = ["how to order", "place an order", "order now", "buy", "want to buy", 
                     "book", "purchase", "make a purchase", "get product", "acquire", 
                     "procure", "checkout", "add to cart", "shopping", "ordering process",
                     "payment", "online order", "website order", "where to buy"]

    # Expanded tracking responses
    track_keywords = ["track", "tracking", "track my order", "where is my order", 
                     "order status", "check order", "tracking details", "how do i track",
                     "order location", "shipment status", "delivery status", "where is package",
                     "order update", "status update", "parcel tracking"]

    # Expanded product list responses
    product_list_keywords = ["products", "what do you have", "show all", "available items", 
                            "list items", "what can i buy", "items available", "product catalog",
                            "all offerings", "complete list", "full range", "entire collection"]

    # Expanded price responses
    all_price_keywords = ["product price", "all prices", "prices of products", "cost of all", 
                         "price list", "how much", "pricing", "rate list", "cost", "rates",
                         "price range", "amount", "product cost", "what's the price"]

    # Expanded benefit/feature responses
    benefit_keywords = ["benefits", "advantages", "features", "why choose", "good for", 
                       "health benefits", "nutritional value", "why use", "pros", "uses",
                       "how helps", "what's good", "positive effects", "nutrition", "healthy",
                       "wellness", "advantages of"]

    # Expanded payment responses
    payment_keywords = ["payment methods", "how to pay", "payment options", "accepted payments",
                       "credit card", "debit card", "upi", "paytm", "phonepe", "net banking",
                       "cash on delivery", "cod", "online payment", "payment gateway"]

    # Expanded return/refund responses
    return_keywords = ["return policy", "refund", "exchange", "return product", "not satisfied",
                      "wrong item", "damaged product", "return process", "how to return",
                      "refund policy", "money back", "replace", "replacement"]

    # Expanded quality responses
    quality_keywords = ["quality", "how pure", "authentic", "original", "genuine", "certified",
                       "organic", "natural", "purity", "quality check", "standards", "testing",
                       "lab tested", "quality assurance", "how good"]

    # Expanded discount responses
    discount_keywords = ["discount", "offer", "coupon", "promo", "promotion", "deal", "special",
                        "sale", "festival offer", "seasonal offer", "price off", "reduced price",
                        "bargain", "savings", "cheaper", "lower price"]

    # Expanded usage responses
    usage_keywords = ["how to use", "usage", "how consume", "how apply", "application", "recipe",
                     "cooking", "how cook", "how eat", "how take", "diet", "consumption",
                     "dosage", "quantity", "amount to use"]

    # Handle greetings
    if any(greet in user_input for greet in greetings):
        return jsonify(response=get_random_response(greeting_responses))

    # Handle silly queries
    if any(word in user_input for word in silly_queries):
        return jsonify(response=get_random_response(silly_responses))

    # Handle location/contact queries
    if any(word in user_input for word in location_keywords + contact_keywords):
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
    if any(word in user_input for word in delivery_keywords):
        delivery_response = [
            "🚚 We deliver to Coimbatore in 2 days and to other cities in 3–4 days.",
            "📦 Delivery takes 2 days in Coimbatore and 3-4 days to other locations.",
            "⏱️ Local Coimbatore orders arrive in 2 days, other cities in 3-4 days."
        ]
        return jsonify(response=get_random_response(delivery_response))

    # Handle product list queries
    if any(word in user_input for word in product_list_keywords):
        product_list_response = [
            "📦 We offer: Groundnut Oil, Coconut Oil, Sesame Oil, Ghee, Jaggery Powder, and a Super Pack (1L each of 3 oils).",
            "🛍️ Our products include: Groundnut Oil, Coconut Oil, Sesame Oil, Ghee, Jaggery Powder, and a Super Pack combo.",
            "🛒 Available products: Groundnut Oil, Coconut Oil, Sesame Oil, Ghee, Jaggery Powder, and our popular Super Pack."
        ]
        return jsonify(response=get_random_response(product_list_response))

    # Handle image requests
    if any(word in user_input for word in image_keywords):
        all_items = products.find()
        img_block = ""
        for item in all_items:
            name = item.get("name", "Product")
            images = item.get("images", [])[:1]
            for img in images:
                img_block += f"<b>{name.title()}</b><br><img src='{img}' width='100' style='margin:5px;'><br><br>"
        return jsonify(response=f"🖼️ Our product gallery:<br><br>{img_block}")

    # Handle product type queries
    if any(word in user_input for word in type_keywords):
        oils = [name.title() for name in ingredients_data.keys()]
        type_response = [
            f"🛍️ We offer the following: {', '.join(oils)}",
            f"🌿 Our natural products include: {', '.join(oils)}",
            f"✨ Available items: {', '.join(oils)}"
        ]
        return jsonify(response=get_random_response(type_response))

    # Specific oil type queries
    if user_input.strip() in ["oil", "oils", "types of oil", "oil types"]:
        oil_names = [name.title() for name in product_name_to_id.keys() if "oil" in name]
        oil_response = [
            f"🛢️ We offer these oils: {', '.join(oil_names)}",
            f"🌱 Our premium oils: {', '.join(oil_names)}",
            f"💧 Available oils: {', '.join(oil_names)}"
        ]
        return jsonify(response=get_random_response(oil_response))

    # Handle order queries
    if any(word in user_input for word in order_keywords):
        order_response = [
            f"🛒 To place an order, call us at 📞 {contact_data['phone']} or visit our store at {contact_data['address']}",
            f"📲 You can order by calling {contact_data['phone']} or visiting our location at {contact_data['address']}",
            f"💳 For orders, please contact us at {contact_data['phone']} or come to {contact_data['address']}"
        ]
        return jsonify(response=get_random_response(order_response))

    # Handle tracking queries
    if any(word in user_input for word in track_keywords):
        track_response = [
            f"📦 For tracking, please call 📞 {contact_data['phone']} with your order number",
            f"🚚 To check your order status, contact us at {contact_data['phone']}",
            f"🔍 Please call {contact_data['phone']} for tracking information with your order details"
        ]
        return jsonify(response=get_random_response(track_response))

    # Handle price list queries
    if any(word in user_input for word in all_price_keywords):
        all_items = products.find()
        price_lines = []
        for item in all_items:
            name = item.get("name", "Product").title()
            prices = [f"{q['size']} - ₹{q['price']}" for q in item.get("quantities", [])]
            price_lines.append(f"💰 <b>{name}</b>: {', '.join(prices)}")
        return jsonify(response="<br><br>".join(price_lines))

    # Handle payment method queries
    if any(word in user_input for word in payment_keywords):
        payment_response = [
            "💳 We accept: Cash on Delivery (COD), UPI, Credit/Debit Cards, and Net Banking",
            "💰 Payment options: COD, UPI (PhonePe, Google Pay, Paytm), Cards, and Net Banking",
            "🪙 You can pay via: Cash on Delivery, all major UPI apps, Credit/Debit Cards"
        ]
        return jsonify(response=get_random_response(payment_response))

    # Handle return/refund queries
    if any(word in user_input for word in return_keywords):
        return_response = [
            "🔄 Return Policy: You can return products within 7 days if unopened and in original condition",
            "♻️ We accept returns within 7 days for unopened products in original packaging",
            "🛍️ Returns allowed within 1 week for unused products with original packaging and receipt"
        ]
        return jsonify(response=get_random_response(return_response))

    # Handle quality queries
    if any(word in user_input for word in quality_keywords):
        quality_response = [
            "🌿 All our products are 100% natural, organic, and lab-tested for purity",
            "✨ We guarantee authentic, high-quality products with strict quality checks",
            "🏆 Isvaryam products are certified organic and tested for highest quality standards"
        ]
        return jsonify(response=get_random_response(quality_response))

    # Handle discount queries
    if any(word in user_input for word in discount_keywords):
        discount_response = [
            "🎁 Special offers available during festivals - call us to check current deals!",
            "💸 We occasionally run promotions - contact us at {contact_data['phone']} for current discounts",
            "🛍️ Check with our team at {contact_data['phone']} for any ongoing offers or combo deals"
        ]
        return jsonify(response=get_random_response(discount_response))

    # Handle usage queries
    if any(word in user_input for word in usage_keywords):
        usage_response = [
            "🍳 Our oils are perfect for cooking, while ghee and jaggery can be used in food preparation",
            "🧑‍🍳 Usage varies by product - oils for cooking, ghee for flavor, jaggery as sweetener",
            "🥘 Each product has different uses - contact us for specific usage recommendations"
        ]
        return jsonify(response=get_random_response(usage_response))

    # Handle benefit queries
    if "benefit" in user_input or "advantage" in user_input or any(word in user_input for word in ["good for", "why use"]):
        found_product = None
        for pname in product_name_to_id.keys():
            if pname in user_input:
                found_product = pname
                break
        if not found_product and "sugar" in user_input:
            found_product = "jaggery powder"

        if found_product:
            benefits = product_benefits.get(found_product, [])
            if benefits:
                return jsonify(response=f"🌟 Benefits of {found_product.title()}:<br>- " + "<br>- ".join(benefits))
            else:
                return jsonify(response=f"ℹ️ {found_product.title()} is a natural product with many health benefits.")

    # Reviews intent
    if any(word in user_input for word in ["reviews", "product reviews", "show reviews", "customer feedback", "testimonials"]):
        review_list = reviews.find()
        product_reviews = {}
        for rev in review_list:
            prod_id = str(rev.get("productId"))
            prod_name = product_map.get(prod_id, "Unknown Product")
            text = rev.get("review", "No text")
            product_reviews.setdefault(prod_name, []).append(f"🗣️ {text} ({rev.get('rating', 0)}/5)")
        response = ""
        for pname, revs in product_reviews.items():
            response += f"<b>{pname.title()}</b>:<br>" + "<br>".join(revs) + "<br><br>"
        return jsonify(response=response.strip() if response else "No reviews available yet.")

    if "review" in user_input:
        found_product = None
        for pname in product_name_to_id.keys():
            if pname in user_input:
                found_product = pname
                break
        if not found_product and "sugar" in user_input:
            found_product = "jaggery powder"

        if found_product:
            prod_id = ObjectId(product_name_to_id[found_product])
            revs = list(reviews.find({"productId": prod_id}))
            if not revs:
                return jsonify(response=f"No reviews yet for {found_product.title()}.")
            response_lines = [f"🗣️ {r['review']} ({r.get('rating', 0)}/5)" for r in revs]
            return jsonify(response=f"<b>Reviews for {found_product.title()}:</b><br>" + "<br>".join(response_lines))

    if any(word in user_input for word in ["ratings", "rate all", "average rating", "all ratings"]):
        response_lines = []
        for pid, pname in product_map.items():
            product_reviews = list(reviews.find({"productId": ObjectId(pid)}))
            if product_reviews:
                avg = sum([r.get("rating", 0) for r in product_reviews]) / len(product_reviews)
                response_lines.append(f"⭐ {pname.title()}: {round(avg, 1)}/5 ({len(product_reviews)} reviews)")
            else:
                response_lines.append(f"⭐ {pname.title()}: No reviews yet")
        return jsonify(response="<br><br>".join(response_lines))

    if "rating" in user_input:
        found_product = None
        for pname in product_name_to_id.keys():
            if pname in user_input:
                found_product = pname
                break
        if not found_product and "sugar" in user_input:
            found_product = "jaggery powder"

        if found_product:
            prod_id = ObjectId(product_name_to_id[found_product])
            product_reviews = list(reviews.find({"productId": prod_id}))
            if product_reviews:
                avg = sum([r.get("rating", 0) for r in product_reviews]) / len(product_reviews)
                return jsonify(response=f"⭐ Average rating for {found_product.title()}: {round(avg,1)}/5 based on {len(product_reviews)} reviews.")
            else:
                return jsonify(response=f"⚠️ No ratings available for {found_product.title()}.")

    # Fuzzy match product info
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

        if any(word in user_input for word in benefit_keywords):
            benefits = product_benefits.get(db_name, [])
            if benefits:
                response_parts.append(f"🌟 Benefits: {', '.join(benefits)}")

        if not response_parts:
            desc = item.get("description", "This is a premium product made with care.")
            response_parts.append(f"📝 {db_name.title()}: {desc}")

        related = recommendations.get(db_name, [])
        if related:
            response_parts.append(f"🤝 Customers also buy: {', '.join([r.title() for r in related])}")

        return jsonify(response="<br><br>".join(response_parts))

    # Default response with more suggestions
    default_responses = [
        "🤖 I didn't catch that. Try asking about:<br>- Product prices<br>- Oil types<br>- How to order<br>- Delivery info<br>- Product benefits",
        "❓ Not sure I understand. You can ask about:<br>- Specific products<br>- Ordering process<br>- Store location<br>- Product reviews<br>- Payment options",
        "💡 Need help? Try asking about:<br>- Our product range<br>- Pricing details<br>- Health benefits<br>- How to contact us<br>- Current offers"
    ]
    return jsonify(response=get_random_response(default_responses))

if __name__ == "__main__":
    app.run(debug=True)
