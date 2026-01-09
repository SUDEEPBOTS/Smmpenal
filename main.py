import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, ForceReply
from pyrogram.enums import ChatAction
from motor.motor_asyncio import AsyncIOMotorClient
from api import smm
from support import ai_agent
import config

# ─────────────────────────────
# 🛠️ HARDCODED CONFIG (Fix for Heroku)
# ─────────────────────────────

# Tera User ID (Ab yahi owner hai)
MY_OWNER_ID = 6356015122 

# Tera Log Channel ID (Bot yahan Admin hona chahiye)
MY_LOG_CHANNEL = -1003639584506

app = Client(
    "SMM_Bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

mongo = AsyncIOMotorClient(config.MONGO_URL)
db = mongo["SMM_Panel_DB"]
users_col = db["users"]
orders_col = db["orders"]     
codes_col = db["redeem_codes"]

# MEMORY STATES
USER_STATES = {} 
ADMIN_STATES = {}

# ✨ SMALL CAPS CONVERTER
def txt(text):
    mapping = str.maketrans("abcdefghijklmnopqrstuvwxyz", "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ")
    return text.lower().translate(mapping)

# ─────────────────────────────
# 🔄 BACKGROUND TASK
# ─────────────────────────────
async def check_orders_loop():
    while True:
        try:
            async for order in orders_col.find({"status": {"$in": ["pending", "in progress", "processing"]}}):
                order_id = order["order_id"]
                user_id = order["user_id"]
                api_resp = await smm.get_status(order_id)
                
                if "status" in api_resp:
                    new_status = api_resp["status"].lower()
                    old_status = order["status"]
                    if new_status != old_status:
                        await orders_col.update_one({"order_id": order_id}, {"$set": {"status": new_status}})
                        if new_status == "completed":
                            try: await app.send_message(user_id, f"{txt('order update')} ✅\nID: {order_id}\nStatus: {txt('completed')}")
                            except: pass
                        elif new_status == "canceled":
                            refund = order["cost"]
                            await users_col.update_one({"_id": user_id}, {"$inc": {"balance": refund}})
                            try: await app.send_message(user_id, f"{txt('refunded')} ❌\nID: {order_id}\nRefund: ₹{refund}")
                            except: pass
            await asyncio.sleep(300) 
        except: await asyncio.sleep(60)

# ─────────────────────────────
# 🏠 MAIN MENU
# ─────────────────────────────

@app.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    
    user = await users_col.find_one({"_id": user_id})
    if not user:
        await users_col.insert_one({"_id": user_id, "name": name, "balance": 0.0, "total_spent": 0.0})
    
    start_img = "https://i.ibb.co/VcHB3c6q/247e441f5ad09d2e61ee25d64785c602.jpg" 
    
    welcome_text = (
        f"👋 **{txt('welcome to the premium smm bot')}**\n\n"
        f"👑 **{txt('user')}:** {txt(name)}\n"
        f"🆔 **{txt('id')}:** `{user_id}`\n\n"
        f"🤖 **{txt('ai support active')}**\n"
        f"You can ask me anything directly in chat!\n\n"
        f"👇 **{txt('select an action below')}:**"
    )

    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton(txt("🚀 new order"), callback_data="menu_categories")],
        [InlineKeyboardButton(txt("💳 add funds"), callback_data="menu_deposit"),
         InlineKeyboardButton(txt("🎁 redeem code"), callback_data="menu_redeem")],
        [InlineKeyboardButton(txt("👤 profile"), callback_data="menu_profile"),
         InlineKeyboardButton(txt("📞 support / help"), callback_data="ai_help")]
    ])
    
    await message.reply_photo(photo=start_img, caption=welcome_text, has_spoiler=True, reply_markup=btns)

# ─────────────────────────────
# 🖱️ CALLBACK HANDLER
# ─────────────────────────────

@app.on_callback_query()
async def callback_handler(client, callback: CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id
    
    if data == "home":
        if user_id in USER_STATES: del USER_STATES[user_id]
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton(txt("🚀 new order"), callback_data="menu_categories")],
            [InlineKeyboardButton(txt("💳 add funds"), callback_data="menu_deposit"),
             InlineKeyboardButton(txt("🎁 redeem code"), callback_data="menu_redeem")],
            [InlineKeyboardButton(txt("👤 profile"), callback_data="menu_profile"),
             InlineKeyboardButton(txt("📞 support / help"), callback_data="ai_help")]
        ])
        await callback.message.edit(txt("main menu"), reply_markup=btns)

    elif data == "ai_help":
        msg = f"🤖 **{txt('ai support system')}**\n\nConnected to **Groq AI**.\n👉 **Type your query directly.**"
        await callback.message.edit(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(txt("🔙 back"), callback_data="home")]]))

    elif data == "menu_categories":
        text = f"📂 **{txt('select category')}**\n{txt('choose what you want to buy')}:"
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton(txt("👁️ views"), callback_data="cat_view"),
             InlineKeyboardButton(txt("👤 members"), callback_data="cat_member")],
            [InlineKeyboardButton(txt("👍 reactions"), callback_data="cat_reaction"),
             InlineKeyboardButton(txt("⚡ others"), callback_data="cat_other")],
            [InlineKeyboardButton(txt("🔙 back"), callback_data="home")]
        ])
        await callback.message.edit(text, reply_markup=btns)

    elif data == "menu_profile":
        user = await users_col.find_one({"_id": user_id})
        msg = f"{txt('👤 user profile')}\n\nID: `{user_id}`\nWallet: ₹{user.get('balance', 0.0):.2f}"
        await callback.message.edit(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(txt("🔙 back"), callback_data="home")]]))

    elif data == "menu_redeem":
        USER_STATES[user_id] = {"step": "waiting_code"}
        await callback.message.edit(f"{txt('🎁 redeem code')}\nSend code now:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(txt("🔙 back"), callback_data="home")]]))

    elif data == "menu_deposit":
        qr_url = "https://i.ibb.co/HTdfpLgv/Screenshot-20260109-103131-Phone-Pe.png"
        caption = f"{txt('💳 add funds')}\n\nUPI: `sudeepkumar8202@ybl`\nSend Screenshot after payment."
        await callback.message.delete()
        await client.send_photo(user_id, qr_url, caption=caption, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(txt("🔙 back"), callback_data="home")]]))

    elif data.startswith("cat_"):
        new_data = f"services_{data.split('_')[1]}_0"
        callback.data = new_data 
        await callback_handler(client, callback)

    elif data.startswith("services_"):
        parts = data.split("_")
        cat_filter, offset = parts[1], int(parts[2])
        limit = 10 
        await callback.answer(txt("loading..."))
        services = await smm.get_services()
        if "error" in services: return await callback.message.edit("API Error")

        tg_services = [s for s in services if "telegram" in s.get("name", "").lower()]
        final_list = []
        for s in tg_services:
            comb = (s.get("name", "") + " " + s.get("category", "")).lower()
            if cat_filter == "view" and "view" in comb: final_list.append(s)
            elif cat_filter == "member" and ("member" in comb or "sub" in comb): final_list.append(s)
            elif cat_filter == "reaction" and ("reaction" in comb or "like" in comb): final_list.append(s)
            elif cat_filter == "other" and not any(x in comb for x in ["view", "member", "sub", "reaction", "like"]): final_list.append(s)

        if not final_list: return await callback.message.edit("No services found.")
        current_batch = final_list[offset : offset + limit]
        
        btns_list = []
        for s in current_batch:
            btns_list.append([InlineKeyboardButton(f"₹{float(s['rate'])*1.5:.1f} | {s['name'][:25]}..", callback_data=f"sel_srv_{s['service']}")])

        nav_btns = []
        if offset >= limit: nav_btns.append(InlineKeyboardButton("⬅️", callback_data=f"services_{cat_filter}_{offset - limit}"))
        nav_btns.append(InlineKeyboardButton(f"Page {(offset//limit)+1}", callback_data="ignore"))
        if offset + limit < len(final_list): nav_btns.append(InlineKeyboardButton("➡️", callback_data=f"services_{cat_filter}_{offset + limit}"))

        btns_list.append(nav_btns)
        btns_list.append([InlineKeyboardButton(txt("🔙 back"), callback_data="menu_categories")])
        await callback.message.edit(f"{txt(f'select {cat_filter}')}:", reply_markup=InlineKeyboardMarkup(btns_list))

    elif data.startswith("sel_srv_"):
        s_id = int(data.split("_")[2])
        all_services = await smm.get_services()
        service = next((s for s in all_services if str(s["service"]) == str(s_id)), None)
        if not service: return await callback.answer("Error")
        USER_STATES[user_id] = {"step": "waiting_link", "service": service}
        desc = service.get("description", "No info").replace("<br>", "\n").replace("<b>", "")
        text = f"💠 **{service['name']}**\n\n📄 {desc[:200]}...\n💵 Rate: ₹{float(service['rate'])*1.5:.2f}\n👇 **Send Link:**"
        await callback.message.edit(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="home")]]))

# ─────────────────────────────
# ✍️ INPUT HANDLER
# ─────────────────────────────

@app.on_message(filters.text & filters.private)
async def input_handler(client, message: Message):
    user_id = message.from_user.id
    if user_id not in USER_STATES: 
        # AI SUPPORT
        if not message.text.startswith("/"):
            user_data = await users_col.find_one({"_id": user_id})
            recent_orders = []
            async for o in orders_col.find({"user_id": user_id}).sort("_id", -1).limit(5): recent_orders.append(o)
            await client.send_chat_action(user_id, ChatAction.TYPING)
            response = ai_agent.get_response(user_data, recent_orders, message.text)
            await message.reply(response)
        return

    state = USER_STATES[user_id]
    step = state["step"]
    
    if step == "waiting_code":
        code = message.text.strip().upper()
        data = await codes_col.find_one({"code": code})
        if not data: return await message.reply("Invalid Code")
        if user_id in data["used_by"]: return await message.reply("Already Used")
        await users_col.update_one({"_id": user_id}, {"$inc": {"balance": data["val"]}})
        await codes_col.update_one({"code": code}, {"$push": {"used_by": user_id}})
        await message.reply(f"Redeemed ₹{data['val']}")
        del USER_STATES[user_id]

    elif step == "waiting_link":
        if "t.me" not in message.text: return await message.reply("Invalid Link")
        USER_STATES[user_id]["link"] = message.text
        USER_STATES[user_id]["step"] = "waiting_qty"
        s = state["service"]
        await message.reply(f"Enter Quantity ({s['min']}-{s['max']}):")

    elif step == "waiting_qty":
        try: qty = int(message.text)
        except: return await message.reply("Number only")
        s = state["service"]
        if qty < int(s["min"]) or qty > int(s["max"]): return await message.reply("Invalid Quantity")
        cost = (float(s['rate']) * 1.5 * qty) / 1000
        user = await users_col.find_one({"_id": user_id})
        if user["balance"] < cost: 
            del USER_STATES[user_id]
            return await message.reply(f"Low Balance. Need ₹{cost:.2f}")
        
        resp = await smm.add_order(s['service'], state["link"], qty)
        if "order" in resp:
            await users_col.update_one({"_id": user_id}, {"$inc": {"balance": -cost, "total_spent": cost}})
            await orders_col.insert_one({"order_id": resp["order"], "user_id": user_id, "status": "pending", "cost": cost})
            await message.reply(f"Order Placed! ID: {resp['order']}")
        else: await message.reply(f"Error: {resp}")
        del USER_STATES[user_id]

# ─────────────────────────────
# 📸 PAYMENT & ADMIN (FIXED OWNER & CHANNEL)
# ─────────────────────────────

@app.on_message(filters.photo & filters.private)
async def handle_ss(client, message):
    if message.from_user.id in USER_STATES: return
    uid, name = message.from_user.id, message.from_user.first_name
    btns = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"pay_app_{uid}"), InlineKeyboardButton("❌ Reject", callback_data=f"pay_rej_{uid}")]])
    
    try:
        # LOG CHANNEL MEIN BHEJ RAHE HAIN
        await client.send_photo(MY_LOG_CHANNEL, message.photo.file_id, caption=f"📩 Pay: {name} (`{uid}`)", has_spoiler=True, reply_markup=btns)
        await message.reply(txt("screenshot submitted. wait for approval."))
    except Exception as e:
        await message.reply(f"❌ Error sending to Admin: {e}")
        print(f"ERROR Sending Photo: {e}")

@app.on_callback_query()
async def pay_cb(client, cb):
    # 👇 OWNER CHECK (Hardcoded)
    if cb.from_user.id != MY_OWNER_ID: 
        return await cb.answer(f"⚠️ You are not Admin! (ID: {cb.from_user.id})", show_alert=True)

    if cb.data.startswith("pay_rej_"):
        uid = int(cb.data.split("_")[2])
        await cb.message.delete()
        await client.send_message(uid, txt("payment rejected ❌"))
    
    elif cb.data.startswith("pay_app_"):
        uid = int(cb.data.split("_")[2])
        ADMIN_STATES[cb.from_user.id] = {"act": "fund", "target": uid}
        
        # Log Channel mein hi reply mangenge
        await cb.message.reply_text(
            f"💰 {txt('enter amount for user')} `{uid}`:",
            reply_markup=ForceReply(selective=True)
        )

# ✅ ADMIN REPLY HANDLER
@app.on_message(filters.reply & filters.user(MY_OWNER_ID))
async def admin_pay_reply(client, message):
    aid = message.from_user.id
    if aid in ADMIN_STATES and ADMIN_STATES[aid]["act"] == "fund":
        uid = ADMIN_STATES[aid]["target"]
        try: amt = float(message.text)
        except: return await message.reply("Numbers Only!")
        
        await users_col.update_one({"_id": uid}, {"$inc": {"balance": amt}})
        await client.send_message(uid, f"✅ Funds Added: ₹{amt}")
        await message.reply(f"Done. Added ₹{amt}")
        del ADMIN_STATES[aid]

# ─────────────────────────────
# 🛠️ ADMIN COMMANDS
# ─────────────────────────────

@app.on_message(filters.command("createcode") & filters.user(MY_OWNER_ID))
async def cc(c, m):
    try: _, n, v = m.text.split(" "); await codes_col.insert_one({"code": n.upper(), "val": float(v), "used_by": []}); await m.reply("Created.")
    except: pass

@app.on_message(filters.command("broadcast") & filters.user(MY_OWNER_ID))
async def bc(c, m):
    if not m.reply_to_message: return
    async for u in users_col.find({}):
        try: await m.reply_to_message.copy(u["_id"]); await asyncio.sleep(0.5)
        except: pass
    await m.reply("Done.")

if __name__ == "__main__":
    try: import uvloop; uvloop.install()
    except: pass
    try: asyncio.get_event_loop()
    except RuntimeError: asyncio.set_event_loop(asyncio.new_event_loop())
    print("🤖 SMM Bot Live...")
    loop = asyncio.get_event_loop()
    loop.create_task(check_orders_loop())
    app.run()
    
