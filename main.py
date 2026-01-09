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
                            msg = f"{txt('order update')} ✅\n{txt('id')}: {order_id}\n{txt('status')}: {txt('completed')}"
                            try: await app.send_message(user_id, msg)
                            except: pass
                            
                        elif new_status == "canceled":
                            refund_amount = order["cost"]
                            await users_col.update_one({"_id": user_id}, {"$inc": {"balance": refund_amount}})
                            msg = f"{txt('order update')} ❌\n{txt('id')}: {order_id}\n{txt('status')}: {txt('canceled')}\n{txt('refunded')}: ₹{refund_amount:.2f}"
                            try: await app.send_message(user_id, msg)
                            except: pass

            await asyncio.sleep(300) 
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
    
    # 🖼️ START IMAGE
    start_img = "https://i.ibb.co/VcHB3c6q/247e441f5ad09d2e61ee25d64785c602.jpg" 
    
    welcome_text = (
        f"👋 **{txt('welcome to the premium smm bot')}**\n\n"
        f"👑 **{txt('user')}:** {txt(name)}\n"
        f"🆔 **{txt('id')}:** `{user_id}`\n\n"
        f"🚀 **{txt('boost your social media presence')}**\n"
        f"ᴡᴇ ᴘʀᴏᴠɪᴅᴇ ᴛʜᴇ ᴄʜᴇᴀᴘᴇsᴛ ᴀɴᴅ ғᴀsᴛᴇsᴛ sᴇʀᴠɪᴄᴇs ғᴏʀ ᴛᴇʟᴇɢʀᴀᴍ.\n"
        f"ᴀᴜᴛᴏᴍᴀᴛɪᴄ ᴏʀᴅᴇʀs, ɪɴsᴛᴀɴᴛ sᴛᴀʀᴛ, ᴀɴᴅ 24/7 sᴜᴘᴘᴏʀᴛ.\n\n"
        f"👇 **{txt('select an action below')}:**"
    )

    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton(txt("🚀 new order"), callback_data="menu_categories")],
        [InlineKeyboardButton(txt("💳 add funds"), callback_data="menu_deposit"),
         InlineKeyboardButton(txt("🎁 redeem code"), callback_data="menu_redeem")],
        [InlineKeyboardButton(txt("👤 profile"), callback_data="menu_profile"),
         InlineKeyboardButton(txt("📞 support"), url="https://t.me/Sudeep_Support")]
    ])
    
    await message.reply_photo(photo=start_img, caption=welcome_text, has_spoiler=True, reply_markup=btns)

# ─────────────────────────────
# 🖱️ CALLBACK HANDLER
# ─────────────────────────────

@app.on_callback_query()
async def callback_handler(client, callback: CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id
    
    # 🏠 HOME
    if data == "home":
        if user_id in USER_STATES: del USER_STATES[user_id]
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton(txt("🚀 new order"), callback_data="menu_categories")],
            [InlineKeyboardButton(txt("💳 add funds"), callback_data="menu_deposit"),
             InlineKeyboardButton(txt("🎁 redeem code"), callback_data="menu_redeem")],
            [InlineKeyboardButton(txt("👤 profile"), callback_data="menu_profile"),
             InlineKeyboardButton(txt("📞 support"), url="https://t.me/Sudeep_Support")]
        ])
        await callback.message.edit(txt("main menu"), reply_markup=btns)

    # 📂 CATEGORIES
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

    # 🎁 REDEEM
    elif data == "menu_redeem":
        USER_STATES[user_id] = {"step": "waiting_code"}
        text = f"{txt('🎁 redeem promo code')}\n\n{txt('send your promo code below')}:"
        await callback.message.edit(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(txt("🔙 back"), callback_data="home")]]))

    # 💳 DEPOSIT
    elif data == "menu_deposit":
        qr_url = "https://i.ibb.co/HTdfpLgv/Screenshot-20260109-103131-Phone-Pe.png"
        caption = (
            f"{txt('💳 add funds')}\n\n"
            f"UPI: `sudeepkumar8202@ybl`\n"
            f"**{txt('how to pay')}:**\n1. Scan QR or use UPI.\n2. Pay amount.\n3. Send **Screenshot** here."
        )
        await callback.message.delete()
        await client.send_photo(user_id, qr_url, caption=caption, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(txt("🔙 back"), callback_data="home")]]))

    # 🔍 PREPARE CATEGORY
    elif data.startswith("cat_"):
        new_data = f"services_{data.split('_')[1]}_0"
        callback.data = new_data 
        await callback_handler(client, callback)

    # 🚀 SERVICES LIST
    elif data.startswith("services_"):
        parts = data.split("_")
        cat_filter, offset = parts[1], int(parts[2])
        limit = 10 

        await callback.answer(txt("loading..."))
        services = await smm.get_services()
        if "error" in services: return await callback.message.edit(txt("api error"))

        tg_services = [s for s in services if "telegram" in s.get("name", "").lower() or "telegram" in s.get("category", "").lower()]
        
        final_list = []
        for s in tg_services:
            comb = (s.get("name", "") + " " + s.get("category", "")).lower()
            if cat_filter == "view" and "view" in comb: final_list.append(s)
            elif cat_filter == "member" and ("member" in comb or "subscriber" in comb): final_list.append(s)
            elif cat_filter == "reaction" and ("reaction" in comb or "like" in comb): final_list.append(s)
            elif cat_filter == "other" and not any(x in comb for x in ["view", "member", "subscriber", "reaction", "like"]): final_list.append(s)

        if not final_list: return await callback.message.edit(txt("no services found in this category"))

        current_batch = final_list[offset : offset + limit]
        btns_list = []
        for s in current_batch:
            rate = float(s['rate']) * 1.5 
            btns_list.append([InlineKeyboardButton(f"₹{rate:.1f} | {s['name'][:25]}..", callback_data=f"sel_srv_{s['service']}")])

        nav_btns = []
        if offset >= limit: nav_btns.append(InlineKeyboardButton("⬅️", callback_data=f"services_{cat_filter}_{offset - limit}"))
        current_page = (offset // limit) + 1
        total_pages = (len(final_list) // limit) + 1 if len(final_list) % limit != 0 else len(final_list) // limit
        nav_btns.append(InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="ignore"))
        if offset + limit < len(final_list): nav_btns.append(InlineKeyboardButton("➡️", callback_data=f"services_{cat_filter}_{offset + limit}"))

        btns_list.append(nav_btns)
        btns_list.append([InlineKeyboardButton(txt("🔙 back to categories"), callback_data="menu_categories")])
        await callback.message.edit(f"{txt(f'select {cat_filter} service')}:", reply_markup=InlineKeyboardMarkup(btns_list))

    elif data == "ignore": await callback.answer(txt("page info"), show_alert=False)

    # 📝 SERVICE DETAILS
    elif data.startswith("sel_srv_"):
        s_id = int(data.split("_")[2])
        all_services = await smm.get_services()
        service = next((s for s in all_services if str(s["service"]) == str(s_id)), None)
        if not service: return await callback.answer("Error")
        
        USER_STATES[user_id] = {"step": "waiting_link", "service": service}
        rate = float(service['rate']) * 1.5
        desc = service.get("description", "No info").replace("<br>", "\n").replace("<b>", "").replace("</b>", "")

        text = (
            f"💠 **{service['name']}**\n\n📄 {txt('desc')}:\n{desc[:300]}...\n\n"
            f"💵 {txt('rate')}: ₹{rate:.2f} / 1000\n📉 {txt('min')}: {service['min']} | {txt('max')}: {service['max']}\n\n"
            f"👇 **{txt('send your link below')}**:"
        )
        await callback.message.edit(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(txt("❌ cancel"), callback_data="home")]]), disable_web_page_preview=True)

# ─────────────────────────────
# ✍️ INPUT HANDLER
# ─────────────────────────────

@app.on_message(filters.text & filters.private)
async def input_handler(client, message: Message):
    user_id = message.from_user.id
    if user_id not in USER_STATES: return
    
    state = USER_STATES[user_id]
    step = state["step"]
    
    # REDEEM
    if step == "waiting_code":
        code = message.text.strip().upper()
        data = await codes_col.find_one({"code": code})
        if not data: return await message.reply(txt("❌ invalid code"))
        if user_id in data["used_by"]: return await message.reply(txt("⚠️ code already used"))
        await users_col.update_one({"_id": user_id}, {"$inc": {"balance": data["val"]}})
        await codes_col.update_one({"code": code}, {"$push": {"used_by": user_id}})
        await message.reply(f"🥳 {txt('redeem successful')}!\n₹{data['val']} {txt('added to wallet')}")
        del USER_STATES[user_id]

    # LINK
    elif step == "waiting_link":
        link = message.text.strip()
        if "t.me" not in link and "telegram" not in link: return await message.reply(txt("invalid link. send telegram link."))
        USER_STATES[user_id]["link"] = link
        USER_STATES[user_id]["step"] = "waiting_qty"
        s = state["service"]
        await message.reply(f"🔗 {txt('link saved')}\n\n🔢 {txt('enter quantity')}\n({s['min']} - {s['max']}):")

    # QUANTITY
    elif step == "waiting_qty":
        try: qty = int(message.text)
        except: return await message.reply(txt("number only"))
        s = state["service"]
        if qty < int(s["min"]) or qty > int(s["max"]): return await message.reply(f"❌ {txt('range')}: {s['min']} - {s['max']}")
            
        rate = float(s['rate']) * 1.5
        cost = (rate * qty) / 1000
        
        user = await users_col.find_one({"_id": user_id})
        if user["balance"] < cost:
            del USER_STATES[user_id]
            return await message.reply(f"❌ {txt('low balance')}\n{txt('needed')}: ₹{cost:.2f}")
            
        status_msg = await message.reply(txt("processing..."))
        resp = await smm.add_order(s['service'], state["link"], qty)
        
        if "order" in resp:
            oid = resp["order"]
            await users_col.update_one({"_id": user_id}, {"$inc": {"balance": -cost, "total_spent": cost}})
            await orders_col.insert_one({"order_id": oid, "user_id": user_id, "status": "pending", "cost": cost})
            await status_msg.edit(f"✅ **{txt('order successful')}**\n🆔 {txt('id')}: `{oid}`\n💰 {txt('cost')}: ₹{cost:.2f}\n⚠️ **{txt('alerts')}**\nDon't submit multiple orders for same link.")
        else: await status_msg.edit(f"❌ {txt('error')}: {resp}")
        del USER_STATES[user_id]

# ─────────────────────────────
# 📸 PAYMENT & ADMIN (GROUP LOGIC)
# ─────────────────────────────

@app.on_message(filters.command("deposit"))
async def deposit_info(client, message):
    qr_url = "https://i.ibb.co/HTdfpLgv/Screenshot-20260109-103131-Phone-Pe.png"
    msg = f"{txt('add funds')}\n\nUPI: `sudeepkumar8202@ybl`\n{txt('note')}: {txt('send screenshot after payment')}"
    await message.reply_photo(photo=qr_url, caption=msg)

@app.on_message(filters.photo & filters.private)
async def handle_ss(client, message):
    if message.from_user.id in USER_STATES: return
    uid, name = message.from_user.id, message.from_user.first_name
    cap = f"📩 {txt('new payment')}\n👤: {name} (`{uid}`)"
    btns = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"pay_app_{uid}"), InlineKeyboardButton("❌ Reject", callback_data=f"pay_rej_{uid}")]])
    await client.send_photo(config.LOG_CHANNEL_ID, message.photo.file_id, caption=cap, has_spoiler=True, reply_markup=btns)
    await message.reply(txt("screenshot submitted. wait for approval."))

@app.on_callback_query()
async def pay_cb(client, cb):
    if cb.data.startswith("pay_rej_"):
        if cb.from_user.id != config.OWNER_ID: return await cb.answer("Admin only", show_alert=True)
        uid = int(cb.data.split("_")[2])
        await cb.message.delete()
        await client.send_message(uid, txt("payment rejected ❌"))
    
    # ✅ GROUP LOGIC: Reply in Group/Channel directly
    elif cb.data.startswith("pay_app_"):
        if cb.from_user.id != config.OWNER_ID: return await cb.answer("Admin only", show_alert=True)
        uid = int(cb.data.split("_")[2])
        ADMIN_STATES[cb.from_user.id] = {"act": "fund", "target": uid}
        
        # Log Group/Channel mein hi reply karo (ForceReply)
        await cb.message.reply_text(
            f"💰 {txt('enter amount for user')} `{uid}`:",
            reply_markup=ForceReply(selective=True)
        )

# ✅ ADMIN REPLY HANDLER (Work in Group/Channel)
@app.on_message(filters.reply & filters.user(config.OWNER_ID))
async def admin_pay_reply(client, message):
    aid = message.from_user.id
    if aid in ADMIN_STATES and ADMIN_STATES[aid]["act"] == "fund":
        uid = ADMIN_STATES[aid]["target"]
        try: amt = float(message.text)
        except: return await message.reply("Number Only!")
        
        await users_col.update_one({"_id": uid}, {"$inc": {"balance": amt}})
        await client.send_message(uid, f"✅ {txt('funds added')}: ₹{amt}")
        await message.reply(f"Done. Added ₹{amt} to `{uid}`")
        del ADMIN_STATES[aid]

@app.on_message(filters.command("createcode") & filters.user(config.OWNER_ID))
async def cc(c, m):
    try: _, n, v = m.text.split(" "); await codes_col.insert_one({"code": n.upper(), "val": float(v), "used_by": []}); await m.reply("Created.")
    except: pass

@app.on_message(filters.command("broadcast") & filters.user(config.OWNER_ID))
async def bc(c, m):
    if not m.reply_to_message: return
    async for u in users_col.find({}):
        try: await m.reply_to_message.copy(u["_id"]); await asyncio.sleep(0.5)
        except: pass
    await m.reply("Done.")

if __name__ == "__main__":
    try:
        import uvloop
        uvloop.install()
    except: pass
    try: asyncio.get_event_loop()
    except RuntimeError: asyncio.set_event_loop(asyncio.new_event_loop())
    print("🤖 SMM Bot Live...")
    loop = asyncio.get_event_loop()
    loop.create_task(check_orders_loop())
    app.run()
    
