from groq import Groq
import config

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
            return "⚠️ AI Support Disabled. Contact Admin."

        # User Info Format
        user_info = (
            f"User: {user_data.get('name', 'User')}\n"
            f"Balance: ₹{user_data.get('balance', 0)}\n"
        )

        # Orders Format
        orders_text = "No recent orders."
        if recent_orders:
            orders_list = []
            for o in recent_orders:
                orders_list.append(f"ID: {o.get('order_id')} | Status: {o.get('status')} | Cost: {o.get('cost')}")
            orders_text = "\n".join(orders_list)

        # AI Prompt
        system_prompt = f"""
        You are 'Sudeep SMM AI', a helpful support assistant.
        
        USER DATA:
        {user_info}
        
        RECENT ORDERS:
        {orders_text}
        
        RULES:
        1. Answer in Hinglish (Hindi + English mix) like a friendly bro.
        2. Keep answers SHORT.
        3. If user asks about 'pending' order, tell them to wait.
        4. If user asks for funds, tell them to use 'Add Funds' button.
        5. Do not hallucinate order IDs. Use only the list above.
        
        User Query: {query}
        """

        try:
            chat = self.client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
                model="llama3-8b-8192",
            )
            return chat.choices[0].message.content
        except Exception as e:
            return f"Error: {e}"

ai_agent = AISupport()
