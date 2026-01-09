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

MY_OWNER_ID = 6356015122  # Tera ID

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
                            try: await app.send_message(user_id, f"✅ **{txt('order completed')}**\n🆔 `{order_id}`")
                            except: pass
                        elif new_status == "canceled":
                            refund = order["cost"]
                            await users_col.update_one({"_id": user_id}, {"$inc": {"balance": refund}})
                            try: await app.send_message(user_id, f"❌ **{txt('order canceled')}**\n💸 Refunded: ₹{refund}")
                            except: pass
            await asyncio.sleep(300) 
        except: await asyncio.sleep(60)

# ─────────────────────────────
# 🏠 START MENU
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
        f"👋 **{txt('welcome to the #1 premium smm bot')}** 🚀\n\n"
        f"👑 **{txt('user')}:** {txt(name)}\n"
        f"🆔 **{txt('id')}:** `{user_id}`\n\n"
        f"✨ **{txt('boost your social media presence')}**\n"
        f"▫️ {txt('cheapest & fastest services')}\n"
        f"▫️ {txt('instant delivery & 24/7 support')}\n"
        f"▫️ {txt('advanced ai assistant integrated')}\n\n"
        f"🤖 **{txt('need help?')}**\n"
        f"{txt('you can chat with our ai support directly here!')}\n\n"
        f"👇 **{txt('select an action below')}:**"
    )

    # Standard Buttons
    btn_list = [
        [InlineKeyboardButton(txt("🚀 new order"), callback_data="menu_categories")],
        [InlineKeyboardButton(txt("📦 my orders"), callback_data="my_orders_list")], 
        [InlineKeyboardButton(txt("💳 add funds"), callback_data="menu_deposit"),
         InlineKeyboardButton(txt("🎁 redeem code"), callback_data="menu_redeem")],
        [InlineKeyboardButton(txt("👤 profile"), callback_data="menu_profile"),
         InlineKeyboardButton(txt("📞 support"), callback_data="ai_help")]
    ]

    # Add Owner Button if Admin
    if user_id == MY_OWNER_ID:
        btn_list.insert(0, [InlineKeyboardButton("👑 OWNER PANEL", callback_data="admin_home")])

    await message.reply_photo(photo=start_img, caption=welcome_text, has_spoiler=True, reply_markup=InlineKeyboardMarkup(btn_list))

# ─────────────────────────────
# 👮 ADMIN DIRECT COMMANDS
# ─────────────────────────────

@app.on_message(filters.command("addmoney") & filters.user(MY_OWNER_ID))
async def add_money_cmd(client, message):
    try:
        _, target, amt = message.text.split(" ")
        target_id = int(target)
        amount = float(amt)
        
        await users_col.update_one({"_id": target_id}, {"$inc": {"balance": amount}})
        await message.reply(f"✅ **Added** ₹{amount} to `{target_id}`")
        try: await client.send_message(target_id, f"🥳 **Funds Added:** ₹{amount}")
        except: pass
    except:
        await message.reply("❌ **Usage:** `/addmoney 123456 100`")

@app.on_message(filters.command("removemoney") & filters.user(MY_OWNER_ID))
async def remove_money_cmd(client, message):
    try:
        _, target, amt = message.text.split(" ")
        target_id = int(target)
        amount = float(amt)
        
        await users_col.update_one({"_id": target_id}, {"$inc": {"balance": -amount}})
        await message.reply(f"🗑️ **Removed** ₹{amount} from `{target_id}`")
    except:
        await message.reply("❌ **Usage:** `/removemoney 123456 100`")

# ─────────────────────────────
# 🖱️ MASTER CALLBACK HANDLER (ALL BUTTONS HERE)
# ─────────────────────────────

@app.on_callback_query()
async def master_callback(client, callback: CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id
    
    # 💰 PAYMENT APPROVAL/REJECT (PRIORITY)
    if data.startswith("pay_"):
        if user_id != MY_OWNER_ID: 
            return await callback.answer("⚠️ Admin Only!", show_alert=True)
        
        uid = int(data.split("_")[2])
        
        if "pay_rej_" in data:
            await callback.message.delete()
            await client.send_message(uid, txt("payment rejected ❌"))
            await callback.answer("Rejected!", show_alert=True)
            
        elif "pay_app_" in data:
            ADMIN_STATES[user_id] = {"step": "wait_fund_amount", "target": uid}
            await callback.message.reply(f"💰 **Enter Amount for User** `{uid}`:")
            await callback.answer()
        return

    # 👑 ADMIN PANEL
    if data == "admin_home":
        if user_id != MY_OWNER_ID: return
        stats_u = await users_col.count_documents({})
        stats_o = await orders_col.count_documents({})
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
             InlineKeyboardButton("🎁 Create Code", callback_data="admin_create_code")],
            [InlineKeyboardButton("🔙 Back to User Mode", callback_data="home")]
        ])
        await callback.message.edit(f"👑 **Admin Panel**\nUsers: `{stats_u}` | Orders: `{stats_o}`", reply_markup=btns)
    
    elif data == "admin_broadcast":
        ADMIN_STATES[user_id] = {"step": "wait_broadcast"}
        await callback.message.reply("📢 Send Message to Broadcast")
    
    elif data == "admin_create_code":
        ADMIN_STATES[user_id] = {"step": "wait_code_input"}
        await callback.message.reply("🎁 Send: `CODE Amount`")

    # 📦 USER MENUS
    elif data == "home":
        if user_id in USER_STATES: del USER_STATES[user_id]
        btn_list = [
            [InlineKeyboardButton(txt("🚀 new order"), callback_data="menu_categories")],
            [InlineKeyboardButton(txt("📦 my orders"), callback_data="my_orders_list")], 
            [InlineKeyboardButton(txt("💳 add funds"), callback_data="menu_deposit"),
             InlineKeyboardButton(txt("🎁 redeem code"), callback_data="menu_redeem")],
            [InlineKeyboardButton(txt("👤 profile"), callback_data="menu_profile"),
             InlineKeyboardButton(txt("📞 support"), callback_data="ai_help")]
        ]
        if user_id == MY_OWNER_ID: btn_list.insert(0, [InlineKeyboardButton("👑 OWNER PANEL", callback_data="admin_home")])
        try: await callback.message.edit(txt("main menu"), reply_markup=InlineKeyboardMarkup(btn_list))
        except: await callback.message.reply(txt("main menu"), reply_markup=InlineKeyboardMarkup(btn_list))

    elif data == "my_orders_list":
        orders = []
        async for o in orders_col.find({"user_id": user_id}).sort("_id", -1).limit(5):
            icon = "✅" if o['status'] == 'completed' else "⏳"
            orders.append(f"🆔 `{o['order_id']}` | {icon} {txt(o['status'])}")
        text = f"📦 **{txt('recent orders')}**\n\n" + ("\n".join(orders) if orders else txt("no orders found"))
        await callback.message.edit(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(txt("🔙 back"), callback_data="home")]]))

    elif data == "ai_help":
        msg = f"🤖 **{txt('ai support system')}**\n\nConnected to **Groq AI**.\n👉 **Type your query directly.**"
        await callback.message.edit(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(txt("🔙 back"), callback_data="home")]]))

    elif data == "menu_categories":
        text = f"📂 **{txt('select category')}**:"
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
        caption = f"{txt('💳 add funds')}\n\nUPI: `ᴀɴʏ ᴘʀᴏʙʟᴇᴍ ᴘʟᴇᴀsᴇ ᴅᴍ ᴍᴇ @Kaito_3_2 `\nSend Screenshot after payment."
        await callback.message.delete()
        await client.send_photo(user_id, qr_url, caption=caption, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(txt("🔙 back"), callback_data="home")]]))

    elif data.startswith("cat_"):
        callback.data = f"services_{data.split('_')[1]}_0"
        await master_callback(client, callback)

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

@app.on_message(filters.text & (filters.private | filters.group))
async def input_handler(client, message: Message):
    user_id = message.from_user.id
    
    # 👑 ADMIN INPUTS
    if user_id == MY_OWNER_ID and user_id in ADMIN_STATES:
        st = ADMIN_STATES[user_id]
        if st["step"] == "wait_fund_amount":
            t = st["target"]
            try: 
                a = float(message.text)
                await users_col.update_one({"_id": t}, {"$inc": {"balance": a}})
                await client.send_message(t, f"✅ **Funds Added:** ₹{a}")
                await message.reply(f"✅ Added ₹{a} to `{t}`")
            except: await message.reply("Numbers Only")
            del ADMIN_STATES[user_id]
        
        elif st["step"] == "wait_broadcast":
            async for u in users_col.find({}):
                try: await message.copy(u["_id"]); await asyncio.sleep(0.5)
                except: pass
            await message.reply("✅ Broadcast Done!")
            del ADMIN_STATES[user_id]
            
        elif st["step"] == "wait_code_input":
            try: c, v = message.text.split(" "); await codes_col.insert_one({"code": c.upper(), "val": float(v), "used_by": []}); await message.reply("Created")
            except: pass
            del ADMIN_STATES[user_id]
        return

    # 👤 USER INPUTS
    if user_id in USER_STATES:
        state = USER_STATES[user_id]
        step = state["step"]
        if step == "waiting_code":
            code = message.text.strip().upper()
            data = await codes_col.find_one({"code": code})
            if not data or user_id in data["used_by"]: return await message.reply("Invalid/Used")
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

    # 🤖 AI
    if message.chat.type == pyrogram.enums.ChatType.PRIVATE and not message.text.startswith("/"):
        user_data = await users_col.find_one({"_id": user_id})
        recent_orders = []
        async for o in orders_col.find({"user_id": user_id}).sort("_id", -1).limit(5): recent_orders.append(o)
        await client.send_chat_action(user_id, ChatAction.TYPING)
        response = ai_agent.get_response(user_data, recent_orders, message.text)
        await message.reply(response)

# ─────────────────────────────
# 📸 PAYMENT SCREENSHOT
# ─────────────────────────────

@app.on_message(filters.photo & filters.private)
async def handle_ss(client, message):
    if message.from_user.id in USER_STATES: return
    uid, name = message.from_user.id, message.from_user.first_name
    
    # ⚠️ UNIQUE CALLBACK DATA: "pay_app_UID"
    btns = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"pay_app_{uid}"), 
        InlineKeyboardButton("❌ Reject", callback_data=f"pay_rej_{uid}")
    ]])
    
    await client.send_photo(MY_OWNER_ID, message.photo.file_id, caption=f"📩 Pay: {name} (`{uid}`)", reply_markup=btns)
    await message.reply(txt("screenshot sent to admin. please wait."))

if __name__ == "__main__":
    try: import uvloop; uvloop.install()
    except: pass
    import pyrogram 
    try: asyncio.get_event_loop()
    except RuntimeError: asyncio.set_event_loop(asyncio.new_event_loop())
    print("🤖 SMM Bot Live...")
    loop = asyncio.get_event_loop()
    loop.create_task(check_orders_loop())
    app.run()
