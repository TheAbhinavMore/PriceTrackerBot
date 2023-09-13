'''
Note : Improve duplicate product handling line 360
'''
import traceback  # for debugging remoce in prod
import os
from time import time
import asyncio
from utilities import cleanLink, getSite, supported_sites
from DB import (create_connection_pool, open_pool, readQuery, addUserDB,
                addLogDB, setTrackingDB, getProductsDB, writeQuery,
                addProductDB, untrackProductDB, showLogsDB,
                refresh_connection_pool)
from scrapping import master_scrapper
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, ReplyKeyboardMarkup
from telegram.ext import (filters, MessageHandler, ApplicationBuilder,
                          CommandHandler, ContextTypes, CallbackQueryHandler,
                          CallbackContext)

# asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

tele_token = os.environ['telegram_token']
webhook_url = 'https://price-tracker-bot-t1yv.onrender.com'

# Create and nitialize the connection pool
conn = create_connection_pool()

# log = logging.getLogger('werkzeug')
# log.setLevel(logging.ERROR)

start_time = time()
'''
Telegram Handles
'''
# to check keep track of open commands and products.
userData = dict()


# global function to refresh connection pool periodically
async def pool_checker():
  global conn
  while True:
    try:
      response = await readQuery(conn, 'SELECT 1;')
      # old pool is responsive
      if response:
        await asyncio.sleep(20 * 60)  # Sleep 20 Min
        continue
    except:
      conn = create_connection_pool()
    await open_pool(conn)
    await asyncio.sleep(1200)


#open pool
asyncio.get_event_loop().run_until_complete(open_pool(conn))
# Create an event loop and run the pool_checker in it
loop = asyncio.get_event_loop()
loop.create_task(pool_checker())


# global func to send msg
async def sendMessage(msg,
                      update,
                      context,
                      reply=False,
                      delete=False,
                      parse_mode="Markdown",
                      reply_markup=None,
                      web_preview=True):
  chat_id = update.effective_chat.id if update else None
  message_id = update.message.message_id if update and update.message else None
  reply_id = None

  if delete and chat_id and message_id:
    return await context.bot.delete_message(chat_id=chat_id,
                                            message_id=message_id)

  if reply and not delete and message_id:
    reply_id = message_id

  if chat_id:
    return await context.bot.send_message(
      chat_id=chat_id,
      text=msg,
      parse_mode=parse_mode,
      reply_to_message_id=reply_id,
      reply_markup=reply_markup,
      disable_web_page_preview=not web_preview)


# function to format product retrieved
async def productFetchSuccess(update, context, title, price, url):
  msg = '<b>Product Details:</b>\n---------------\n'
  if price == 999999:
    msg += f"Looks like {title.strip()} is <b>OUT OF STOCK!</b> 🚫\n\nBut no worries, I got your back and can still track the product for you! 🕵️‍♀️\n\nJust set the target price around actual MRP, okay? 💰"
  else:
    msg += f'☛ <a href="{url}"><b>{title.strip()}</b></a>\n\n❖Current Price - <b>{price}</b> ₹\n'
  await sendMessage(msg, update, context, parse_mode='HTML')
  await trackProducts(update, context, {
    "name": title,
    'price': price,
    'url': url
  }, 'add_product')


# function to get reply keybaord menu


def get_master_menu():
  keyboard = [['Active Tracking 🛍', 'Bot Menu 📜'], ['Help ❓', 'Share Bot ❤️']]
  return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user = update.message.from_user
  name = user.full_name
  username = user.username
  if not username:
    username = user.link
  id = update.effective_chat.id

  await addUserDB(conn, id, name, username)
  msg = f"Hey {name.split()[0]},\n\nI'm Price Alert Bot and I'm here to help you get your desired product at the best price possible! 😎"
  # await show_menu(update, context, msg)
  await sendMessage(msg, update, context, reply_markup=get_master_menu())
  await addLogDB(conn, id, 'start_bot')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
  global conn  # global database connection
  chat_id = update.effective_chat.id

  message = update.message
  text = message.text
  caption = update.message.caption

  if not text:
    if caption:
      text = caption
    else:
      response = "*Text only please!*\n\n_Would you mind sharing the link to your product?_\nThanks! 😄"
      await sendMessage(response, update, context, True)
      return

  openCommands = context.user_data.get('command', None)

  # handle open commands (~line 450,490)
  if openCommands:
    # handle for feedback
    if openCommands == 'feedback':
      await feedback_message(update, context)

    elif openCommands == 'site_request':
      await site_request(update, context)

    # handle broadcast
    elif openCommands == 'broadcast':
      # here check commands after broad_,to pass action(~490)
      if text.startswith('/broad'):
        cmd = text[6:]
        if cmd == 'Confirm':
          await broadcast_message(update, context, 'broadcast_recheck')
        elif cmd == 'ConfirmF':
          # need to pass bot as well to send messages
          await broadcast_message(update, context, 'broadcast_confirm')
        else:
          await broadcast_message(update, context, 'broadcast_cancel')
      else:
        # log broadcast msg for later access in broadcast_message
        context.user_data['broadcast'] = text
        await broadcast_message(update, context, 'broadcast_preview')
    return

  # master keyboar menu handle
  if 'Active Tracking' in text:
    await showList(update, context, True)
    return

  if 'Help' in text:
    await help(update, context)
    return

  if 'Share Bot' in text:
    msg = "Sharing = Caring!\n\nThis bot is a solo effort, not affiliated with anyone else. Your shares go a long way in making this project meaningful.\n\nYour support is what makes it all worthwhile. 🌐💙"
    share_msg = "\n\nNever overpay again! Let this bot monitor product prices and notify you of drops.\n\nElevate your online shopping game today! 🛒\n\n https://telegram.me/PriceAlertAB9Bot"
    keyboard = [[
      InlineKeyboardButton("Share Bot", switch_inline_query=share_msg)
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await sendMessage(msg, update, context, reply_markup=reply_markup)
    return

  if 'Bot Menu' in text:
    await show_menu(update, context)
    return

  # check for pending target set
  openProduct = context.user_data.get('openProduct', None)

  if text.isdecimal():
    target = float(text)
    if openProduct:
      # pass message id of tracking message as context
      await trackProducts(update, context, target, 'set_price_target')
    else:
      response = '''🤔*Hmmm.... Strange...* \n\nDo you want to track product?🙃'''
      inline_button = InlineKeyboardButton(text="Track Product 🛒",
                                           callback_data='add_product')
      reply_markup = InlineKeyboardMarkup([[inline_button]])
      await sendMessage(response,
                        update,
                        context,
                        reply=True,
                        reply_markup=reply_markup)

    return

  else:
    # also check for open feedback (refer line 440)
    # add check to see if user is logged in db
    user_id = message.from_user.id
    user = message.from_user
    name = user.full_name
    username = user.username
    if not username:
      username = user.link

    if openProduct:
      # double check if any product requires price target
      msg = '*This product is missing the target price! *⚠️\n----------\n'
      msg += f'❖*{openProduct["name"][:70]}*...\n'
      msg += f'❖Price:*{openProduct["price"]}* ₹\n\n'
      msg += '_Tip: Enter the desired price as a number (e.g., 210 ) without any currency symbols or special characters:_\n\n'
      await sendMessage(msg, update, context)
      return

    # also check user has set reassigned tracking, REFER -> Alerts.sendAlert
    if text.startswith("/YES"):
      text = text.split('_')
      p_id = int(text[1])
      targ = int(text[2])
      # handle wrong input by user
      query = f"select check_retrack_db({chat_id},{p_id},{targ});"
      retrack_data = await readQuery(conn, query)
      retrack_id = retrack_data[0][0]
      if not retrack_id:
        await sendMessage("Hey that's invalid retracking request! 😳", update,
                          context, True)
      else:
        await sendMessage("Okay I'll keep tracking this product...🤗", update,
                          context, True)
        await setTrackingDB(conn, chat_id, p_id, targ)

      # log message
      await addLogDB(conn, chat_id, 'retrack')
      return

    # Check for commands without '/'
    if True in [text.lower() == i for i in ['start', 'hi', 'hello', 'hey']]:
      await start(update, context)
      return
    elif True in [text.lower() == i for i in ['list', 'track', 'untrack']]:
      await showList(update, context, True)
      return
    elif True in [text.lower() == i for i in ['alert', 'test', 'notify']]:
      await notifyMe(update, context)
      return
    elif True in [text.lower() == i for i in ['error', 'log', 'logs']]:
      await showLogs(update, context)
      return

  # handle links
  url = cleanLink(text)

  # if user sent link
  if url:
    sent_message = await sendMessage(
      "_Hold on, I'm trying to fetch the product..._🔍", update, context, True)
    await context.bot.send_chat_action(chat_id, 'typing')
    # log message
    await addLogDB(conn, chat_id, 'link')
    bot_msg_id = sent_message.message_id

    try:
      if getSite(url) is None:
        keyboard = [[
          InlineKeyboardButton("Supported Sites",
                               callback_data="supported_sites"),
          InlineKeyboardButton("Request Support",
                               callback_data="request_site"),
        ]]
        await sendMessage("*Sorry, but that's an unsupported site!* 😅",
                          update,
                          context,
                          reply_markup=InlineKeyboardMarkup(keyboard))
        return
      product_data = await master_scrapper(url)
      title, price = product_data['title'], product_data['price']

    except:
      await sendMessage("*Please try again with valid link! *😳", update,
                        context)
      return

    if title:
      await context.bot.delete_message(chat_id=chat_id,
                                       message_id=message.message_id)
      await context.bot.delete_message(chat_id=chat_id, message_id=bot_msg_id)
      await productFetchSuccess(update, context, title, price, url)

    else:
      msg = "*I'm sorry, but I wasn't able to retrieve any product.* 😳\n\nThink the product link was valid? I can try again!"

      # Store the URL and message ID in chat_data or user_data
      context.chat_data['url'] = url

      inline_button = InlineKeyboardButton('Try Harder',
                                           callback_data='try_harder')
      inline_markup = InlineKeyboardMarkup([[inline_button]])
      # Send the button to the user
      await sendMessage(msg, update, context, reply_markup=inline_markup)

    return

  if text.startswith('/'):
    await unknowncommand(update, context)
    return

  response = '''🤔*Hmmm... Strange...* \n\nI'm a bit confused by your message. Could you please recheck your message?🙃'''
  await sendMessage(response, update, context, reply=True)
  # log message
  await addLogDB(conn, chat_id, 'unknown_msg')


'''
Product Tracking
'''


# Define the callback function to handle the button click
async def try_harder_button_callback(update, context):
  chat_id = update.callback_query.message.chat_id
  query = update.callback_query

  url = context.chat_data.get('url', None)
  if url is None:
    return

  sent_msg = await query.edit_message_text(
    text=
    "_Okay, trying harder this time to fetch the product..._🔍\n\n*Wait for few seconds...*",
    parse_mode='Markdown')
  await context.bot.send_chat_action(chat_id, 'typing')
  await asyncio.sleep(5)
  await context.bot.send_chat_action(chat_id, 'typing')
  await asyncio.sleep(5)

  await context.bot.delete_message(chat_id=chat_id,
                                   message_id=sent_msg.message_id)

  product_data = await master_scrapper(url)
  title, price = product_data['title'], product_data['price']

  if title:
    await productFetchSuccess(update, context, title, price, url)
  else:
    # check site is amazon for extra fallback msg
    if getSite(url)[0] == 'amazon':
      msg = "Amazon products might sometimes be tricky to fetch. Give it a moment, then attempt once more.😔"
    else:
      msg = "*I'm sorry, but still I wasn't able to retrieve any product.* 😔\n\nCheck whether product URL is correct else try again in 15-20 seconds."

    inline_button = InlineKeyboardButton(text="Send Feedback",
                                         callback_data='feedback')
    reply_markup = InlineKeyboardMarkup([[inline_button]])
    await sendMessage(msg, update, context, reply_markup=reply_markup)

  # remove data from context
  context.chat_data.pop('url', None)


async def trackProducts(update, context, msg, act):

  if update.message is None:
    chat_id = update.callback_query.message.chat_id
  else:
    chat_id = update.message.chat_id

  # get user tracking list
  products = await getProductsDB(conn, chat_id)

  if act == 'add_product':
    if msg['url'] in list(products.keys()):
      p_id = products[msg['url']]['product_id']
      response = f"_Hey I'm already tracking this product!_🤔\n---------------\n❖Current Target - *{products[msg['url']]['target']}* ₹\n\n●*Steps to update target price:*\n   -Untrack Product\n   -Send link again.🤗"
      inline_button = InlineKeyboardButton(
        'Untrack Product ❎', callback_data=f'stop_tracking_{p_id}')
      inline_markup = InlineKeyboardMarkup([[inline_button]])
      await sendMessage(response, update, context, reply_markup=inline_markup)
      return

    # add product to database first in case the product is absent
    await addProductDB(conn, msg['name'], msg['url'], msg['price'])

    # intitiate tracking product
    title, price = msg['name'], msg['price']
    response = '*Great!*🤗\n\n*Now please set the target price: *'
    await sendMessage(response, update, context)
    # add the product to openProducts, as a flag
    context.user_data['openProduct'] = msg
    # log message
    await addLogDB(conn, chat_id, 'add_product')

  elif act == 'set_price_target':
    # only add if there is openProducts[refer line 134]
    prod = context.user_data['openProduct']
    price = prod['price']
    url = prod['url']

    min_target = 0.65 * price
    if chat_id == 677440016:
      min_target = 1

    if price != 999999 and (msg >= price or msg <= 0 or msg < min_target):
      error_msg = None
      if msg >= price:
        error_msg = f"Hey target must be *less* than *{price}* ₹ !"
      elif msg <= 0:
        error_msg = "Hey that's an invalid target price!"
      else:
        error_msg = f"Hey, that's too low of a target price!\n\nTarget price must be at least/more than *{int(min_target)+1}* ₹ ⚠️\n\nPlease note that setting a proper target price will ensure that you receive alerts at every price drop.📉"

      if error_msg:
        await sendMessage(error_msg, update, context, True)
      await sendMessage("Now please set a valid target price:", update,
                        context)
      return

    await setTrackingDB(conn, chat_id, url, msg)
    response = '*Great!* Product tracking is started.\n\nI will send you alert when the price of this product drop!😇'
    inline_button = InlineKeyboardButton('Updated Tracking List',
                                         callback_data='active_tracking')
    inline_markup = InlineKeyboardMarkup([[inline_button]])
    await sendMessage(response, update, context, reply_markup=inline_markup)

    # clear openProduct flag
    del context.user_data['openProduct']
    # log message
    await addLogDB(conn, chat_id, 'set_target')


async def send_product_details(update,
                               context,
                               chat_id,
                               url,
                               value,
                               bullet_point="●",
                               end=False):

  name = value["title"]
  price = value['price']
  target = value['target']
  change = ""

  if price == 999999:
    price_text = "Out of Stock"
  elif price == -1:
    price_text = "Site Error!"
  else:
    change = int((price - target) / target * 100)
    change = f"{change}% {'⬆️' if change > 0 else '🔻🔻🔻'}"
    price_text = f'₹<b>{price}.00</b> | {change}'

  details = (f'\n{bullet_point}. <a href="{url}"><b>{name}</b></a>\n\n'
             f'❖Target - ₹<b>{target}.00</b>\n'
             f'❖Price   - {price_text}\n\n'
             f'┉┉┉┉┉┉┉┉┉┉┉┉┉┉')

  keyboard = [[
    InlineKeyboardButton(f"Buy Now ✅", url=url),
    InlineKeyboardButton("Stop Tracking ⏹",
                         callback_data=f"stop_tracking_{value['product_id']}"),
  ]]
  if end:
    keyboard += [[
      InlineKeyboardButton(
        "Price History 📊",
        url=f"https://pricehistory.abhinav35.repl.co/price-history/{chat_id}")
    ], [InlineKeyboardButton("Hide List 🙈", callback_data='hide_messages')]]

  return await sendMessage(details,
                           update,
                           context,
                           parse_mode='HTML',
                           reply_markup=InlineKeyboardMarkup(keyboard))


async def showList(update, context, products):
  if update.message is None:
    chat_id = update.callback_query.message.chat_id
  else:
    chat_id = update.message.chat_id

  # to avoid spam
  last_use_time = context.chat_data.get("list_command_last_use", 0)
  time_since_last_use = time() - last_use_time

  if 0 < time_since_last_use < 30:
    remaining_time = 30 - time_since_last_use
    await context.bot.send_message(
      chat_id,
      f"Please wait {remaining_time:.0f} seconds before using that command again. ⏳"
    )
    return

  context.chat_data["list_command_last_use"] = time()
  await context.bot.send_chat_action(chat_id, 'typing')
  # Products == True means its difficult to pass product dict directly so request internally
  if products == True:
    products = await getProductsDB(conn, chat_id)

  if len(products) == 0:
    response = "_NO PRODUCT TRACKING ACTIVE_🤔\n\n*TO TRACK PRODUCT JUST SHARE ANY PRODUCT LINK*😃\n\n➖➖➖➖➖"
    inline_button = InlineKeyboardButton(text="Add Product 🛒",
                                         callback_data='feedback')
    reply_markup = InlineKeyboardMarkup([[inline_button]])
    await sendMessage(response, update, context, reply_markup=reply_markup)
    return

  message_ids_to_hide = []

  for i, (url, value) in enumerate(products.items(), start=1):
    if value['title'] == 'test':
      continue
    is_last_msg = i == len(products)
    sent_msg = await send_product_details(update, context, chat_id, url, value,
                                          i, is_last_msg)
    message_ids_to_hide.append(sent_msg.message_id)

  context.chat_data['message_ids_to_hide'] = message_ids_to_hide
  await addLogDB(conn, chat_id, "list")


async def untrackProduct(update, context, products, product_id):
  if update.message is None:
    chat_id = update.callback_query.message.chat_id
  else:
    chat_id = update.message.chat_id

  title, flag = '', False
  for prd_data in products.values():
    if product_id is None:
      break
    if prd_data['product_id'] == product_id:
      title = prd_data['title']
      flag = True
      break
  if flag:
    await untrackProductDB(conn, chat_id, product_id)
    response = f'Untrack: *{title}* Success!✔️\n➖➖➖➖➖'
  else:
    if product_id:
      response = '*I Could not find that product to untrack*❗'
    else:
      response = f"●*Steps to untrack a product:*\n   -Use /list command\n   -Use untrack option there.🤗"

  await sendMessage(response, update, context, True)
  # add command logging
  await addLogDB(conn, chat_id, "untrack")


async def showChart(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if update.message is None:
    chat_id = update.callback_query.message.chat_id
  else:
    chat_id = update.message.chat_id

  keyboard = [[
    InlineKeyboardButton(
      "Show Price History 📈",
      url=f"https://pricehistory.abhinav35.repl.co/price-history/{chat_id}")
  ]]

  chart_message = (
    '*Explore Your Price History!*\n ➖➖➖➖➖\n\n_Dive into the comprehensive price history for all your tracked products in one convenient location!_'
  )
  await sendMessage(chart_message,
                    update,
                    context,
                    reply_markup=InlineKeyboardMarkup(keyboard))


async def notifyMe(update: Update, context: ContextTypes.DEFAULT_TYPE):
  # only admin access command to avoid overload
  chat_id = update.effective_chat.id

  if chat_id != 677440016:
    await unknowncommand(update, context)
    return

  await sendMessage("*TELEGRAM BOT IS UP & ACTIVE*☑️\n➖➖➖➖", update, context)

  query = '''
    SELECT TO_CHAR(timestamp, 'DD Mon, HH24:MI') AS formatted_time
    FROM price_change_log
    WHERE product_id=99999
    LIMIT 1;
    '''
  last_price_update = await readQuery(conn, query)
  await sendMessage(f"*Last Price Log*: {last_price_update[0][0]}", update,
                    context)

  response = "_Hold on, you'll get test notification here soon..._😇"
  await sendMessage(response, update, context)
  # add test notification product
  await writeQuery(
    conn, 'update price_change_log set alerted=false where product_id=99999;')


async def showLogs(update: Update, context: ContextTypes.DEFAULT_TYPE):
  chat_id = update.effective_chat.id
  if chat_id != 677440016:
    await unknowncommand(update, context)
    return

  msg = '➽*Bot Summary*'
  await sendMessage(msg, update, context)
  await sendMessage(
    f"Price Bot Up since *{round((time() - start_time) / 3600, 1)}* Hours! 🕘",
    update, context)

  DBlogs = await showLogsDB(conn)
  if not DBlogs:
    return
  msg = '➽*User Summary*'
  await sendMessage(msg, update, context)
  msg = ''
  for u_type, num in DBlogs.items():
    msg += f'●*{u_type}*: {num}\n'
  await sendMessage(msg, update, context)

  msg = '➽*Site Summary*'
  await sendMessage(msg, update, context)
  q = 'SELECT name, round((requests - errors)::numeric / requests * 100, 2) AS success_rate FROM sites WHERE errors > 0;'
  msg = ''
  for n, sr in await readQuery(conn, q):
    msg += f"◷*{n.capitalize()}* : {sr:.2f}%\n"
  if msg:
    await sendMessage(msg, update, context)


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if update.message is None:
    chat_id = update.callback_query.message.chat_id
  else:
    chat_id = update.message.chat_id

  help_msg = '''Welcome to Price Alert Bot! 🤖

Here's a step-by-step guide on how to make the most of this bot:

1️⃣ *Send Product Link*: Start by sharing the link of the product from Amazon, Flipkart, or any other supported stores. If you're on a mobile device, you can directly share the product link from within the app. If you're using a PC or browser, you can share the page link.

2️⃣ *Set Target Price*: Set your target price. The bot will keep an eye on the price for you.

3️⃣ *Stay Relaxed*: Sit back and relax! 🏖️ The bot will monitor the price & send a notification on price drop.

Remember, the bot requires you to use  /start command at least once anywhere.

Happy shopping and saving money with Price Alert Bot! 🛍️
'''
  keyboard = [[
    InlineKeyboardButton("Supported Sites", callback_data="supported_sites")
  ], [
    InlineKeyboardButton("Show Bot Menu", callback_data="show_menu_help"),
  ]]
  await sendMessage(help_msg,
                    update,
                    context,
                    reply_markup=InlineKeyboardMarkup(keyboard))
  await addLogDB(conn, chat_id, 'help')


async def feedback_message(update, context):
  user = update.message.from_user
  name = user.first_name
  feedback_text = update.message.text

  # Send a message thanking the user for their feedback
  response = f"Awesome {name}, thanks for the heads up! 😎 I'll definitely take a look into this and see if I can find a solution that works for you. 🕵️‍♀️ If you have any other questions or concerns, don't hesitate to reach out. I'm here to help! 🤗\n\nIf you need to reach me directly, you can use my username @AbhinavMore."
  await update.message.reply_text(response)

  # Finally, reset the feedback flag
  del context.user_data['command']

  # Send the feedback message to you
  msg = f"👤 User: [{name}]({user.link})\n\nFeedback message:\n\n{feedback_text}"
  await context.bot.send_message(677440016, msg, 'Markdown')


async def site_request(update, context):
  user = update.message.from_user
  name = user.first_name
  site_name = update.message.text

  response = f"Thank you, {name}, for requesting the site *{site_name.capitalize()}*.\nI have noted your request and will consider adding it in the future updates. If you have any other feedback or questions, feel free to let me know. 😊"
  await update.message.reply_text(response, parse_mode='Markdown')

  # Finally, reset the feedback flag
  del context.user_data['command']
  # Send the feedback message to you
  msg = f"👤 User: [{name}]({user.link})\n\nSite Reqeust:\n\n{site_name}"
  await context.bot.send_message(677440016, msg, 'Markdown')


# broadcast handler
async def start_broadcast(update, context):
  chat_id = update.effective_chat.id
  if chat_id != 677440016:
    await unknowncommand(update, context)
    return

  await update.message.reply_text('Enter your message to broadcast:')
  # add flag
  context.user_data['command'] = 'broadcast'


async def broadcast_message(update, context, act):
  text, chat_id, flag = update.message.text, update.effective_chat.id, False
  broadcast_msg = context.user_data['broadcast']

  if act == 'broadcast_preview':
    msg = f'*Message Preview*:\n➖➖➖➖➖\n{broadcast_msg}\n➖➖➖➖\n/broadConfirm to send or /broadCancel to abort.'
  elif act == 'broadcast_recheck':
    msg = '*Are you sure???*\n\n/broadConfirmF to send or /broadCancel to abort.'
  elif act == 'broadcast_confirm':
    query = 'select tele_id from users where tele_id != 99999;'
    chat_ids = await readQuery(conn, query)

    s_count = 0
    for chat in chat_ids:
      try:
        await context.bot.send_message(chat_id=chat[0],
                                       text=broadcast_msg,
                                       parse_mode='Markdown')
      except Exception as e:
        s_count += 1
        print(e)

    msg = f'Brodacast Failed for {s_count}/{len(chat_ids)} users!\n\n'
    msg += "Broadcast Success!"
    flag = True
  else:
    msg = 'Broadcast cancelled!'
    flag = True

  await update.message.reply_text(msg, parse_mode='Markdown')

  # update flag (only if either cmd is cancel or final confirm)
  if flag:
    del context.user_data['command']


async def unknowncommand(update: Update, context: ContextTypes.DEFAULT_TYPE):
  response = "_Hmm...that's not a valid bot command!_😒\n\n"
  await sendMessage(response, update, context, True)
  msg = """*Here are the available commands:*

● /menu :
-Show the main menu.
● /list :
List your tracked products.
● /track :
Start tracking a new product.
● /add:
Add a new product to track.
● /untrack or /stop :
Stop tracking a product.
● /chart, /history, /graph :
Show price history chart.
● /tutorial, /help:
Get help and information.

Use these commands to interact with the bot and manage your tracked products. Enjoy! 😊
    """
  await sendMessage(msg, update, context)


async def error_handler(update, context):
  global conn
  """Log the error and send a telegram message to notify the developer."""
  error_message = f"An error occurred:\n{context.error}\n\nTraceback:\n{traceback.format_exc()}"

  # Print the error message
  print(error_message)
  conn = await refresh_connection_pool(conn)
  await open_pool(conn)
  # send user message
  inline_button = InlineKeyboardButton('Having Troubles?',
                                       callback_data='alert_admin')
  inline_markup = InlineKeyboardMarkup([[inline_button]])
  response = "🤖 Sorry, Something went wrong. Could you please try that again in a few seconds? Thank you for your patience! 🕒"
  await sendMessage(response, update, context, reply_markup=inline_markup)


def get_menu_keyboard(show_more=True):
  if show_more:
    keyboard = [[
      InlineKeyboardButton("Add a Product 🛒", callback_data="add_product"),
      InlineKeyboardButton("Active Tracking 🛍",
                           callback_data="active_tracking"),
    ],
                [
                  InlineKeyboardButton("Price History 📈",
                                       callback_data="price_history"),
                  InlineKeyboardButton("Hide Menu 🙈",
                                       callback_data="hide_menu")
                ],
                [
                  InlineKeyboardButton("Show More ➡️",
                                       callback_data="show_more")
                ]]
  else:
    keyboard = [[
      InlineKeyboardButton("Stop Tracking 🚫", callback_data="stop_tracking"),
      InlineKeyboardButton("Request Site 📝", callback_data="request_site"),
    ],
                [
                  InlineKeyboardButton("Send Feedback 🙌",
                                       callback_data="feedback"),
                  InlineKeyboardButton("Hide Menu 🙈",
                                       callback_data="hide_menu")
                ],
                [
                  InlineKeyboardButton("Main Menu 🔙",
                                       callback_data="main_menu")
                ]]

  return InlineKeyboardMarkup(keyboard)


async def show_master_menu(update: Update,
                           context: CallbackContext,
                           text=None):
  if text is None:
    text = "Hey, How can i help? 🧡"
  await sendMessage(text, update, context, reply_markup=get_master_menu())


async def show_menu(update: Update, context: CallbackContext, text=None):
  reply_markup = get_menu_keyboard()
  # add extra hadnler when coming from help menu
  if text is None:
    text = "Hey, How can i help? 🧡"
  if update.message:
    message = update.message
  else:
    message = update.callback_query.message
  await message.reply_text(text,
                           reply_markup=reply_markup,
                           parse_mode='Markdown')


async def show_more_options(query: CallbackQuery):
  await query.message.edit_reply_markup(get_menu_keyboard(show_more=False))


async def hide_menu(query: CallbackQuery):
  await query.message.edit_reply_markup(None)


async def button_click(update: Update, context: CallbackContext):
  query = update.callback_query
  chat_id = query.message.chat_id
  await query.answer()

  option = query.data
  timeout = 10

  async def handle_query():
    nonlocal timeout
    if option == "show_more":
      await show_more_options(query)

    elif option == "hide_menu":
      await hide_menu(query)

    elif option == "active_tracking":
      products = await getProductsDB(conn, chat_id)
      timeout = int(1.5 * len(products))
      await showList(update, context, products)

    elif option == "add_product":
      inline_button = InlineKeyboardButton('Supported Stores 📜',
                                           callback_data='supported_sites')
      inline_markup = InlineKeyboardMarkup([[inline_button]])

      response = "*Want to track products?*\n\nEasy! Just share a product link from our supported stores to get started 🤑"
      await query.message.reply_text(text=response,
                                     parse_mode='Markdown',
                                     reply_markup=inline_markup)

    elif option.startswith("stop_tracking"):
      l = option.split('_')
      if len(l) > 2:
        products = await getProductsDB(conn, chat_id)
        p_id = int(l[-1])
        await untrackProduct(update, context, products, p_id)
      else:
        # to send error message
        await untrackProduct(update, context, {}, None)

    elif option == "price_history":
      await showChart(update, context)

    elif option == "help":
      try:
        await context.bot.delete_message(chat_id=chat_id,
                                         message_id=query.message.message_id)
      except:
        pass
      await help(update, context)

    elif option == "show_menu_help":
      response = "Hey, How can i help? 🧡"
      await query.edit_message_text(text=response,
                                    reply_markup=get_menu_keyboard(),
                                    parse_mode='Markdown')

    elif option == "main_menu":
      await query.message.edit_reply_markup(get_menu_keyboard())

    elif option == 'supported_sites':
      site_msg = "🛍️ Available sites supported 🛍️"
      keyboard = InlineKeyboardMarkup(
        [[
          InlineKeyboardButton("General 🌐", callback_data="general_sites"),
          InlineKeyboardButton("Fashion 👗", callback_data="fashion_sites"),
        ],
         [
           InlineKeyboardButton("Pharmacy 💊", callback_data="pharmacy_sites"),
           InlineKeyboardButton("Electronics 🖥",
                                callback_data="electronics_sites"),
         ]])
      await query.message.reply_text(site_msg, reply_markup=keyboard)

    elif option == 'general_sites':
      general_sites = ['• Amazon', '• Flipkart', '• Snapdeal']
      msg = '𝗦𝘂𝗽𝗽𝗼𝗿𝘁𝗲𝗱 𝗦𝘁𝗼𝗿𝗲𝘀 🌐\n\n'
      msg += '\n'.join(general_sites)
      await query.message.reply_text(msg)

    elif option == 'fashion_sites':
      general_sites = ['• Ajio', '• Nykaa', '• Bewakoof']
      msg = '𝗦𝘂𝗽𝗽𝗼𝗿𝘁𝗲𝗱 𝗦𝘁𝗼𝗿𝗲𝘀 👗\n\n'
      msg += '\n'.join(general_sites)
      await query.message.reply_text(msg)

    elif option == 'pharmacy_sites':
      general_sites = ['• 1mg', '• Netmeds']
      msg = '𝗦𝘂𝗽𝗽𝗼𝗿𝘁𝗲𝗱 𝗦𝘁𝗼𝗿𝗲𝘀 💊\n\n'
      msg += '\n'.join(general_sites)
      await query.message.reply_text(msg)

    elif option == 'electronics_sites':
      general_sites = [
        '• MD-Computers', '• EZPZSolutions', '• TPStech', '• PC-Studio',
        '• Primeabgb', '• Vedant-computers'
      ]
      msg = '𝗦𝘂𝗽𝗽𝗼𝗿𝘁𝗲𝗱 𝗦𝘁𝗼𝗿𝗲𝘀 🖥\n\n'
      msg += '\n'.join(general_sites)
      await query.message.reply_text(msg)

    elif option == "feedback":
      response = "Hey there! 👋\nGot something on your mind? We'd love to hear it!\n\nGo ahead, share your thoughts!"
      await query.message.reply_text(response)
      # Listen for the user's response
      context.user_data['command'] = 'feedback'

    elif option == "request_site":
      msg = "Got a site in mind that you'd love to see supported?\n\nType the site's name, Ex. Myntra."
      await query.message.reply_text(msg)
      context.user_data['command'] = 'site_request'

    elif option == "alert_admin":
      msg = "🚨 Admin has been notified. Thanks for your patience!"
      await query.message.reply_text(msg)
      await context.bot.send_message(chat_id=chat_id, text='Bot Down 🚨')

    elif option == 'hide_messages':
      stored_list = context.chat_data.get('message_ids_to_hide', [])
      # corner case when bot restart and hide button wont work
      if len(stored_list) == 0:
        response = 'Sorry, The button has expired.⌛'
        await show_menu(update, context, response)
        return

      timeout = int(2 * len(stored_list))
      await context.bot.send_chat_action(chat_id, 'typing')
      for msg_id in stored_list:
        try:
          await context.bot.delete_message(chat_id, msg_id)
        except Exception as e:
          print(f"Failed to delete message {msg_id}: {e}")
      stored_list.clear()

    else:
      response = "Oops, I did not catch that. How can i help! 😁"
      await show_menu(update, context, response)

    return True  # success flag

  try:
    await asyncio.wait_for(handle_query(), timeout=timeout)
  except asyncio.TimeoutError:
    response = "Sorry, there seems to be a delay in processing. Please try again.⏳"
    await show_menu(update, context, response)


def start_bot():
  application = ApplicationBuilder().token(tele_token).build()
  #asyncio.get_event_loop().run_until_complete(application.bot.setWebhook(url=webhook_url))

  # start command handler
  start_handler = CommandHandler(['start', 'hello', 'hi'], start)
  application.add_handler(start_handler)

  # menu command handler
  menu_handler = CommandHandler(['menu'], show_master_menu)
  application.add_handler(menu_handler)

  # list command handler
  list_commands = ['list', 'track', 'add']
  list_handler = CommandHandler(
    list_commands, lambda update, context: showList(update, context, True))
  application.add_handler(list_handler)

  # untrack command handler
  untrack_commands = ['untrack', 'stop']
  untrack_handler = CommandHandler(
    untrack_commands,
    lambda update, context: untrackProduct(update, context, {}, None))
  application.add_handler(untrack_handler)

  # price history command handler
  chart_commands = ['chart', 'history', 'graph']
  chart_handler = CommandHandler(chart_commands, showChart)
  application.add_handler(chart_handler)

  # notification handler
  notification_handler = CommandHandler(['alert', 'test', 'notify'], notifyMe)
  application.add_handler(notification_handler)

  # help command handler
  help_handler = CommandHandler(['tutorial', 'help'], help)
  application.add_handler(help_handler)

  # broadcast command handler
  broadcast_handler = CommandHandler('broadcast', start_broadcast)
  application.add_handler(broadcast_handler)

  # master handler
  message_handler = MessageHandler(filters.ALL, handle_message)
  application.add_handler(message_handler)

  # try harder button handler
  application.add_handler(
    CallbackQueryHandler(try_harder_button_callback, pattern='try_harder'))

  application.add_handler(CallbackQueryHandler(button_click))

  # handle remaining commands
  unknown_handler = MessageHandler(filters.COMMAND, unknowncommand)
  application.add_handler(unknown_handler)

  # error handler
  application.add_error_handler(error_handler)

  application.run_polling()
