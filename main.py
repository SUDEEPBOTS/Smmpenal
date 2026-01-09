import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, ForceReply
from pyrogram.enums import ChatAction
from motor.motor_asyncio import AsyncIOMotorClient
from api import smm
from support import ai_agent
import config

# ─────────────────────────────
# 🛠️ HARDCODED CONFIG
# ─────────────────────────────

# Tera User ID (Owner)
MY_OWNER_ID = 6356015122 

# Tera Log Group ID (Make sure Bot is Admin here)
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
# 🏠 START & MENUS (ADMIN VS USER)
# ─────────────────────────────

@app.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    
    # DB Entry
    user = await users_col.find_one({"_id": user_id})
    if not user:
        await users_col.insert_one({"_id": user_id, "name": name, "balance": 0.0, "total_spent": 0.0})

    # 👉 IF OWNER -> SHOW ADMIN PANEL
    if user_id == MY_OWNER_ID:
        stats_users = await users_col.count_documents({})
        stats_orders = await orders_col.count_documents({})
        
        admin_text = (
            f"👑 **{txt('admin panel')}**\n\n"
            f"👋 Welcome Boss!\n"
            f"👥 Users: `{stats_users}`\n"
            f"📦 Orders: `{stats_orders}`\n\n"
            f"👇 Control Panel:"
        )
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
             InlineKeyboardButton("🎁 Create Code", callback_data="admin_create_code")],
            [InlineKeyboardButton("📊 Full Stats", callback_data="admin_stats"),
             InlineKeyboardButton("🔙 User Mode", callback_data="home")]
        ])
        return await message.reply(admin_text, reply_markup=btns)

    # 👉 IF NORMAL USER -> SHOW USER MENU
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
    
    # 👑 ADMIN ACTIONS
    if data.startswith("admin_"):
        if user_id != MY_OWNER_ID: return await callback.answer("❌ Owner Only!", show_alert=True)
        
        if data == "admin_stats":
            u = await users_col.count_documents({})
            o = await orders_col.count_documents({})
            spent = 0
            async for x in users_col.find({}): spent += x.get("total_spent", 0)
            await callback.answer(f"👥 Users: {u}\n📦 Orders: {o}\n💰 Total Revenue: ₹{spent:.2f}", show_alert=True)
            
        elif data == "admin_broadcast":
            ADMIN_STATES[user_id] = {"step": "wait_broadcast"}
            await callback.message.reply("📢 **Send Message to Broadcast:**")
            
        elif data == "admin_create_code":
            ADMIN_STATES[user_id] = {"step": "wait_code_input"}
            await callback.message.reply("🎁 **Send Code Details:**\nFormat: `CODE Amount`\nEx: `DIWALI 100`")
        return

    # 🏠 USER MENU
    if data == "home":
        if user_id in USER_STATES: del USER_STATES[user_id]
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton(txt("🚀 new order"), callback_data="menu_categories")],
            [InlineKeyboardButton(txt("💳 add funds"), callback_data="menu_deposit"),
             InlineKeyboardButton(txt("🎁 redeem code"), callback_data="menu_redeem")],
            [InlineKeyboardButton(txt("👤 profile"), callback_data="menu_profile"),
             InlineKeyboardButton(txt("📞 support / help"), callback_data="ai_help")]
        ])
        # Agar Admin "User Mode" dabaye toh Text edit hoga, agar User dabaye toh Photo caption
        try: await callback.message.edit(txt("main menu"), reply_markup=btns)
        except: await callback.message.reply(txt("main menu"), reply_markup=btns)

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
# ✍️ INPUT HANDLER (User & Admin)
# ─────────────────────────────

@app.on_message(filters.text & (filters.private | filters.group))
async def input_handler(client, message: Message):
    user_id = message.from_user.id
    
    # 👑 ADMIN LOGIC (Broadcast, Code, Funds)
    if user_id == MY_OWNER_ID:
        if user_id in ADMIN_STATES:
            st = ADMIN_STATES[user_id]
            
            # 📢 Broadcast
            if st["step"] == "wait_broadcast":
                msg = await message.reply("🚀 **Broadcasting...**")
                done, fail = 0, 0
                async for u in users_col.find({}):
                    try: 
                        await message.copy(u["_id"])
                        done += 1
                        await asyncio.sleep(0.5)
                    except: fail += 1
                await msg.edit(f"✅ Broadcast Done!\nSuccess: {done}\nFailed: {fail}")
                del ADMIN_STATES[user_id]
                return

            # 🎁 Create Code
            elif st["step"] == "wait_code_input":
                try: 
                    code, val = message.text.split(" ")
                    await codes_col.insert_one({"code": code.upper(), "val": float(val), "used_by": []})
                    await message.reply(f"✅ Code `{code.upper()}` Created for ₹{val}")
                except: await message.reply("❌ Format: `CODE Amount`")
                del ADMIN_STATES[user_id]
                return
            
            # 💰 Add Funds (From Approval)
            elif st["step"] == "wait_fund_amount":
                target = st["target"]
                try: amt = float(message.text)
                except: return await message.reply("❌ Numbers only!")
                await users_col.update_one({"_id": target}, {"$inc": {"balance": amt}})
                await client.send_message(target, f"✅ Funds Added: ₹{amt}")
                await message.reply(f"✅ Added ₹{amt} to User `{target}`")
                del ADMIN_STATES[user_id]
                return

    # 👤 USER LOGIC
    if user_id in USER_STATES:
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
        return

    # 🤖 AI LOGIC (Only in Private Chat & if not command)
    if message.chat.type == pyrogram.enums.ChatType.PRIVATE and not message.text.startswith("/"):
        user_data = await users_col.find_one({"_id": user_id})
        recent_orders = []
        async for o in orders_col.find({"user_id": user_id}).sort("_id", -1).limit(5): recent_orders.append(o)
        await client.send_chat_action(user_id, ChatAction.TYPING)
        response = ai_agent.get_response(user_data, recent_orders, message.text)
        await message.reply(response)

# ─────────────────────────────
# 📸 PAYMENT (FIXED)
# ─────────────────────────────

@app.on_message(filters.photo & filters.private)
async def handle_ss(client, message):
    if message.from_user.id in USER_STATES: return
    uid, name = message.from_user.id, message.from_user.first_name
    btns = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"pay_app_{uid}"), InlineKeyboardButton("❌ Reject", callback_data=f"pay_rej_{uid}")]])
    try:
        await client.send_photo(MY_LOG_CHANNEL, message.photo.file_id, caption=f"📩 Pay: {name} (`{uid}`)", has_spoiler=True, reply_markup=btns)
        await message.reply(txt("screenshot submitted. wait for approval."))
    except Exception as e:
        await message.reply(f"❌ Error sending to admin: {e}")

@app.on_callback_query()
async def pay_cb(client, cb):
    if cb.data.startswith("pay_rej_"):
        if cb.from_user.id != MY_OWNER_ID: return await cb.answer("Admin Only!", show_alert=True)
        uid = int(cb.data.split("_")[2])
        await cb.message.delete()
        await client.send_message(uid, txt("payment rejected ❌"))
    
    elif cb.data.startswith("pay_app_"):
        if cb.from_user.id != MY_OWNER_ID: return await cb.answer("Admin Only!", show_alert=True)
        uid = int(cb.data.split("_")[2])
        
        # State Set karo ki Admin ab Amount dalega
        ADMIN_STATES[cb.from_user.id] = {"step": "wait_fund_amount", "target": uid}
        
        # Group/Private jahan button click hua wahan reply mango
        await cb.message.reply(
            f"💰 **Approve Payment for User** `{uid}`\n👇 **Enter Amount below:**",
            reply_markup=ForceReply(selective=True)
        )

if __name__ == "__main__":
    try: import uvloop; uvloop.install()
    except: pass
    import pyrogram # Import for enum check above
    try: asyncio.get_event_loop()
    except RuntimeError: asyncio.set_event_loop(asyncio.new_event_loop())
    print("🤖 SMM Bot Live...")
    loop = asyncio.get_event_loop()
    loop.create_task(check_orders_loop())
    app.run()
