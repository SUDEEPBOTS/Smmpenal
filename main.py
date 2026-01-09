import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, ForceReply
from motor.motor_asyncio import AsyncIOMotorClient
from api import smm
import config

# ─────────────────────────────
# 🛠️ SETUP & UTILS
# ─────────────────────────────

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
# 🔄 BACKGROUND TASK (AUTO STATUS & REFUND)
# ─────────────────────────────
async def check_orders_loop():
    while True:
        try:
            # Sirf Pending orders check karo
            async for order in orders_col.find({"status": {"$in": ["pending", "in progress", "processing"]}}):
                order_id = order["order_id"]
                user_id = order["user_id"]
                
                api_resp = await smm.get_status(order_id)
                
                if "status" in api_resp:
                    new_status = api_resp["status"].lower()
                    old_status = order["status"]
                    
                    if new_status != old_status:
                        await orders_col.update_one({"order_id": order_id}, {"$set": {"status": new_status}})

                        # COMPLETE NOTIFICATION
                        if new_status == "completed":
                            msg = (
                                f"{txt('order update')} ✅\n\n"
                                f"{txt('id')}: {order_id}\n"
                                f"{txt('status')}: {txt('completed')}"
                            )
                            try: await app.send_message(user_id, msg)
                            except: pass
                            
                        # CANCELED -> AUTO REFUND
                        elif new_status == "canceled":
                            refund_amount = order["cost"]
                            await users_col.update_one({"_id": user_id}, {"$inc": {"balance": refund_amount}})
                            
                            msg = (
                                f"{txt('order update')} ❌\n\n"
                                f"{txt('id')}: {order_id}\n"
                                f"{txt('status')}: {txt('canceled')}\n"
                                f"{txt('refunded')}: ₹{refund_amount:.2f}"
                            )
                            try: await app.send_message(user_id, msg)
                            except: pass

            await asyncio.sleep(300) # 5 Min wait
        except Exception as e:
            print(f"Loop Error: {e}")
            await asyncio.sleep(60)

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
    
    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton(txt("🚀 new order"), callback_data="services_0")],
        [InlineKeyboardButton(txt("👤 profile"), callback_data="menu_profile"),
         InlineKeyboardButton(txt("💳 add funds"), callback_data="menu_deposit")],
        [InlineKeyboardButton(txt("📞 support"), url="https://t.me/Sudeep_Support")]
    ])
    
    await message.reply(
        f"{txt('welcome to panel')}\n\n"
        f"{txt('select an option below')}:",
        reply_markup=btns
    )

# ─────────────────────────────
# 🖱️ CALLBACK HANDLER (LOGIC CORE)
# ─────────────────────────────

@app.on_callback_query()
async def callback_handler(client, callback: CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id
    
    # 🏠 HOME
    if data == "home":
        if user_id in USER_STATES: del USER_STATES[user_id]
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton(txt("🚀 new order"), callback_data="services_0")],
            [InlineKeyboardButton(txt("👤 profile"), callback_data="menu_profile"),
             InlineKeyboardButton(txt("💳 add funds"), callback_data="menu_deposit")]
        ])
        await callback.message.edit(txt("main menu"), reply_markup=btns)

    # 👤 PROFILE
    elif data == "menu_profile":
        user = await users_col.find_one({"_id": user_id})
        msg = (
            f"{txt('👤 user profile')}\n\n"
            f"{txt('id')}: `{user_id}`\n"
            f"{txt('wallet')}: ₹{user.get('balance', 0.0):.2f}\n"
            f"{txt('spent')}: ₹{user.get('total_spent', 0.0):.2f}"
        )
        await callback.message.edit(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(txt("🔙 back"), callback_data="home")]]))

    # 💳 DEPOSIT
    elif data == "menu_deposit":
        msg = (
            f"{txt('💳 add funds')}\n\n"
            f"UPI: `yourupi@paytm`\n"
            f"{txt('send screenshot after payment')}"
        )
        await callback.message.edit(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(txt("🔙 back"), callback_data="home")]]))

    # 🚀 SERVICES (PAGINATION SYSTEM)
    elif data.startswith("services_"):
        offset = int(data.split("_")[1])
        limit = 10 

        await callback.answer(txt("loading..."))
        services = await smm.get_services()
        if "error" in services: return await callback.message.edit(txt("api error"))

        # FILTER: Only Telegram
        tg_services = [s for s in services if "telegram" in s.get("name", "").lower() or "telegram" in s.get("category", "").lower()]
        
        if not tg_services: return await callback.message.edit(txt("no telegram services found"))

        # SLICING
        current_batch = tg_services[offset : offset + limit]
        total_services = len(tg_services)

        btns_list = []
        for s in current_batch:
            rate = float(s['rate']) * 1.5 # 50% Profit
            btn_text = f"₹{rate:.1f} | {s['name'][:25]}.."
            btns_list.append([InlineKeyboardButton(btn_text, callback_data=f"sel_srv_{s['service']}")])

        # Nav Buttons
        nav_btns = []
        if offset >= limit:
            nav_btns.append(InlineKeyboardButton("⬅️", callback_data=f"services_{offset - limit}"))
        
        current_page = (offset // limit) + 1
        total_pages = (total_services // limit) + 1 if total_services % limit != 0 else total_services // limit
        nav_btns.append(InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="ignore"))

        if offset + limit < total_services:
            nav_btns.append(InlineKeyboardButton("➡️", callback_data=f"services_{offset + limit}"))

        btns_list.append(nav_btns)
        btns_list.append([InlineKeyboardButton(txt("🔙 back to home"), callback_data="home")])
        
        await callback.message.edit(f"{txt('select service')}:", reply_markup=InlineKeyboardMarkup(btns_list))

    elif data == "ignore":
        await callback.answer(txt("page info"), show_alert=False)

    # 📝 SERVICE SELECTION
    elif data.startswith("sel_srv_"):
        s_id = int(data.split("_")[2])
        all_services = await smm.get_services()
        service = next((s for s in all_services if str(s["service"]) == str(s_id)), None)
        
        if not service: return await callback.answer("Error")
        
        USER_STATES[user_id] = {"step": "waiting_link", "service": service}
        
        rate = float(service['rate']) * 1.5
        desc = service.get("description", "No info").replace("<br>", "\n").replace("<b>", "").replace("</b>", "")

        text = (
            f"💠 **{service['name']}**\n\n"
            f"📄 {txt('desc')}:\n{desc[:300]}...\n\n"
            f"💵 {txt('rate')}: ₹{rate:.2f} / 1000\n"
            f"📉 {txt('min')}: {service['min']} | {txt('max')}: {service['max']}\n\n"
            f"👇 **{txt('send your link below')}**:"
        )
        
        btn = InlineKeyboardMarkup([[InlineKeyboardButton(txt("❌ cancel"), callback_data="home")])])
        await callback.message.edit(text, reply_markup=btn, disable_web_page_preview=True)

# ─────────────────────────────
# ✍️ INPUT HANDLER (LINK -> QUANTITY)
# ─────────────────────────────

@app.on_message(filters.text & filters.private)
async def input_handler(client, message: Message):
    user_id = message.from_user.id
    if user_id not in USER_STATES: return
    
    state = USER_STATES[user_id]
    step = state["step"]
    
    # STEP 1: LINK
    if step == "waiting_link":
        link = message.text.strip()
        if "t.me" not in link and "telegram" not in link:
            return await message.reply(txt("invalid link. send telegram link."))
            
        USER_STATES[user_id]["link"] = link
        USER_STATES[user_id]["step"] = "waiting_qty"
        
        s = state["service"]
        await message.reply(f"🔗 {txt('link saved')}\n\n🔢 {txt('enter quantity')}\n({s['min']} - {s['max']}):")

    # STEP 2: QUANTITY & ORDER
    elif step == "waiting_qty":
        try: qty = int(message.text)
        except: return await message.reply(txt("number only"))
            
        s = state["service"]
        min_q, max_q = int(s["min"]), int(s["max"])
        
        if qty < min_q or qty > max_q:
            return await message.reply(f"❌ {txt('range')}: {min_q} - {max_q}")
            
        rate = float(s['rate']) * 1.5
        cost = (rate * qty) / 1000
        
        user = await users_col.find_one({"_id": user_id})
        if user["balance"] < cost:
            del USER_STATES[user_id]
            return await message.reply(f"❌ {txt('low balance')}\n{txt('needed')}: ₹{cost:.2f}\n{txt('have')}: ₹{user['balance']:.2f}")
            
        status_msg = await message.reply(txt("processing..."))
        
        link = state["link"]
        resp = await smm.add_order(s['service'], link, qty)
        
        if "order" in resp:
            oid = resp["order"]
            await users_col.update_one({"_id": user_id}, {"$inc": {"balance": -cost, "total_spent": cost}})
            await orders_col.insert_one({"order_id": oid, "user_id": user_id, "status": "pending", "cost": cost})
            
            final_msg = (
                f"✅ **{txt('order successful')}**\n\n"
                f"🆔 {txt('id')}: `{oid}`\n"
                f"🔗 {txt('link')}: {link}\n"
                f"🔢 {txt('qty')}: {qty}\n"
                f"💰 {txt('cost')}: ₹{cost:.2f}\n\n"
                f"⚠️ **{txt('alerts')}**\n"
                f"⚠️ Do not submit multiple orders for same link until fully delivered\n"
                f"⚠️ If link is changed/private, order marked complete without refund"
            )
            await status_msg.edit(final_msg)
        else:
            await status_msg.edit(f"❌ {txt('error')}: {resp}")
            
        del USER_STATES[user_id]

# ─────────────────────────────
# 📸 PAYMENT SYSTEM
# ─────────────────────────────

@app.on_message(filters.photo & filters.private)
async def handle_ss(client, message):
    if message.from_user.id in USER_STATES: return
    
    uid = message.from_user.id
    name = message.from_user.first_name
    
    cap = f"📩 {txt('new payment')}\n👤: {name} (`{uid}`)"
    btns = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"pay_app_{uid}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"pay_rej_{uid}")
    ]])
    
    await client.send_photo(config.LOG_CHANNEL_ID, message.photo.file_id, caption=cap, has_spoiler=True, reply_markup=btns)
    await message.reply(txt("screenshot submitted. wait for approval."))

@app.on_callback_query()
async def pay_cb(client, cb):
    if cb.data.startswith("pay_rej_"):
        uid = int(cb.data.split("_")[2])
        await cb.message.delete()
        await client.send_message(uid, txt("payment rejected ❌"))
    
    elif cb.data.startswith("pay_app_"):
        uid = int(cb.data.split("_")[2])
        ADMIN_STATES[cb.from_user.id] = {"act": "fund", "target": uid}
        await cb.message.reply_text("Enter Amount:", reply_markup=ForceReply(selective=True))

@app.on_message(filters.reply & filters.user(config.OWNER_ID))
async def admin_pay_reply(client, message):
    aid = message.from_user.id
    if aid in ADMIN_STATES and ADMIN_STATES[aid]["act"] == "fund":
        uid = ADMIN_STATES[aid]["target"]
        try: amt = float(message.text)
        except: return
        
        await users_col.update_one({"_id": uid}, {"$inc": {"balance": amt}})
        await client.send_message(uid, f"✅ {txt('funds added')}: ₹{amt}")
        await message.reply("Done.")
        del ADMIN_STATES[aid]

# ─────────────────────────────
# 🎁 ADMIN TOOLS (Broadcast/Redeem)
# ─────────────────────────────

@app.on_message(filters.command("createcode") & filters.user(config.OWNER_ID))
async def cc(c, m):
    try: _, n, v = m.text.split(" "); await codes_col.insert_one({"code": n.upper(), "val": float(v), "used_by": []}); await m.reply("Created.")
    except: pass

@app.on_message(filters.command("redeem"))
async def rc(c, m):
    try: code = m.text.split(" ")[1].upper()
    except: return
    data = await codes_col.find_one({"code": code})
    uid = m.from_user.id
    if not data or uid in data["used_by"]: return await m.reply(txt("invalid/used"))
    await users_col.update_one({"_id": uid}, {"$inc": {"balance": data["val"]}})
    await codes_col.update_one({"code": code}, {"$push": {"used_by": uid}})
    await m.reply(f"{txt('redeemed')}: ₹{data['val']}")

@app.on_message(filters.command("broadcast") & filters.user(config.OWNER_ID))
async def bc(c, m):
    if not m.reply_to_message: return
    async for u in users_col.find({}):
        try: await m.reply_to_message.copy(u["_id"]); await asyncio.sleep(0.5)
        except: pass
    await m.reply("Done.")

# 🏁 START
if __name__ == "__main__":
    print("🤖 SMM Bot Live...")
    loop = asyncio.get_event_loop()
    loop.create_task(check_orders_loop())
    app.run()
      
