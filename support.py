from groq import Groq
import config

# ✨ Helper: Small Caps Converter
def txt(text):
    mapping = str.maketrans("abcdefghijklmnopqrstuvwxyz", "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ")
    return text.lower().translate(mapping)

class AISupport:
    def __init__(self):
        self.client = None
        if config.GROQ_API_KEY:
            try:
                self.client = Groq(api_key=config.GROQ_API_KEY)
            except:
                print("❌ Groq API Key Missing")

    def get_response(self, user_data, recent_orders, query):
        if not self.client:
            return txt("ai support disabled. contact admin.")

        # User Name nikal rahe hain taaki AI gender guess kar sake
        user_name = user_data.get('name', 'User')
        
        # Context Data
        user_info = (
            f"Customer Name: {user_name}\n"
            f"Wallet Balance: ₹{user_data.get('balance', 0)}\n"
        )

        orders_text = "No recent orders."
        if recent_orders:
            orders_list = []
            for o in recent_orders:
                orders_list.append(f"Order ID: {o.get('order_id')} | Status: {o.get('status')}")
            orders_text = "\n".join(orders_list)

        # 🧠 SIYA KA DIMAAG (SYSTEM PROMPT)
        system_prompt = f"""
        You are 'Siya', a female customer support executive for a Premium SMM Panel.
        
        USER DETAILS:
        {user_info}
        
        RECENT ORDERS:
        {orders_text}
        
        INSTRUCTIONS FOR SIYA:
        1. GENDER DETECTION: Look at the customer's name '{user_name}'. 
           - If it sounds Male, address as 'Sir'. 
           - If it sounds Female, address as 'Ma'am'.
           - If unsure, use 'Sir'.
        
        2. GREETING: If the user says "Hi", "Hello" or starts a conversation, say: 
           "Hello [Sir/Ma'am], I am Siya. How can I help you today?"
        
        3. TONE: Professional, Polite, and Helpful (Like a real corporate assistant).
        
        4. KNOWLEDGE:
           - Pending Orders: "Please wait, server load is high."
           - Add Funds: "Use the 'Add Funds' button in the main menu."
           - Order Issues: Check the order list above. If ID not found, say "Invalid Order ID".
           
        5. FORMAT: Keep it short (Max 20 words). Speak in Hinglish (Hindi + English).
        
        User Query: {query}
        """

        try:
            chat = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.6,
                max_tokens=150,
            )
            
            response = chat.choices[0].message.content
            
            # ✨ Jadoo: Text ko Small Caps mein convert karke bhejo
            return txt(response)

        except Exception as e:
            return txt(f"siya is sleeping (error): {e}")

ai_agent = AISupport()
