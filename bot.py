import main_ai as ai
import telebot, gspread, os
from telebot import types
from oauth2client.service_account import ServiceAccountCredentials


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)

# Google Sheets Authentication
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CREDS = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
client = gspread.authorize(CREDS)

# Open Google Sheet (Insert your spreadsheet name)
SHEET_ID = "1EKMTKNRQtnHQoSzmvC0-Ta-8JSCaaL7zyGfxSo7hP0c"
spreadsheet = client.open_by_key(SHEET_ID).sheet1

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "👋 **Welcome to Expense Tracker Bot!** 📊💰\n\n"
        "I can help you track your expenses, categorize them, and save them to Google Sheets automatically. 📝📈\n\n"
        "✨ **How to use me?**\n"
        "➡️ Just send a message like:\n"
        "  • *'I spent 500 on groceries yesterday.'*\n"
        "  • *'Paid 1200 for rent on 5th Jan.'*\n"
        "  • *'Bought a laptop for 250,000 KZT today.'*\n\n"
        "🔍 I will automatically extract:\n"
        "✔️ **Category**\n"
        "✔️ **Amount**\n"
        "✔️ **Date**\n\n"
        "🚀 **Commands you can use:**\n"
        "• `/report` - Get a summary of your expenses\n"
        "• `/help` - See how to use the bot\n"
        "• `/settings` - Configure the bot settings\n\n"
        "💡 *If the bot isn't sure about a category or amount, it will ask you to clarify!* 🛠️\n"
        "Let's start tracking your expenses! 🚀💰"
    )
    
    bot.reply_to(message, welcome_text, parse_mode="Markdown")


pending_categories = {}

@bot.message_handler(func=lambda message: True)
def add_expense(message):
    try:
        text = message.text.strip()
        result = ai.analyze_expense(text)

        categories = result['expense_categories']
        amount = result['expense_amount']
        date = result['expense_date']

        if amount[0] is None:
            msg = bot.reply_to(message, "❌ Could you enter the amount again?")
            bot.register_next_step_handler(msg, process_amount, message, categories, amount, date)
        elif len(categories) > 1:
            ask_category(message, categories, amount, date)
        else:
            finalize_expense(message, categories[0], amount, date)

    except Exception as e:
        bot.reply_to(message, f"❌ Could you try again, some error came out!\n{e}")

def process_amount(message, original_message, categories, amount, date):
    try:
        amount[0] = float(message.text.strip()) 
        if len(categories) > 1:
            ask_category(original_message, categories, amount, date)
        else:
            finalize_expense(original_message, categories[0], amount, date)
    except ValueError:
        msg = bot.reply_to(message, "❌ Please enter a valid number for the amount.")
        bot.register_next_step_handler(msg, process_amount, original_message, categories, date)

def ask_category(message, categories, amount, date):
    """ Ask the user to choose a category if multiple are suggested """
    markup = types.InlineKeyboardMarkup()
    for i, category in enumerate(categories):
        button = types.InlineKeyboardButton(category, callback_data=f"cat_{message.message_id}_{i}")
        markup.add(button)
    
    pending_categories[message.message_id] = {
        "categories": categories,
        "amount": amount,
        "date": date,
        "user_id": message.chat.id,
    }
    
    bot.reply_to(message, "🤔 I am not sure. Please choose the category of the expense:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def process_category_selection(call):
    """ Handle category selection from inline keyboard """
    try:
        _, message_id, index = call.data.split("_")
        message_id = int(message_id)
        index = int(index)

        if message_id in pending_categories:
            data = pending_categories[message_id]

            if call.message.chat.id == data["user_id"]:  # Ensure same user
                selected_category = data["categories"][index]
                amount = data["amount"]
                date = data["date"]
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"Clarification. Category chosen: {selected_category}"
                )
                # Remove from pending data
                del pending_categories[message_id]

                finalize_expense(call.message, selected_category, amount, date)
            else:
                bot.reply_to(call.message, "❌ You can't select this category.")
        else:
            bot.reply_to(call.message, "❌ This selection is no longer available.")

    except Exception as e:
        bot.reply_to(call.message, f"❌ An error occurred while processing your choice: {e}")


def finalize_expense(message, category, amount, date):
    """ Finalize the expense entry and save to Google Sheets """
    try:
        id = message.date+message.chat.id
        spreadsheet.append_row([id, category, amount[0], amount[1], date])
        bot.reply_to(message, f"✅ Noted: \n{category}: {amount[0]}{amount[1]}.\nDate: {date}")
    except Exception as e:
        bot.reply_to(message, f"❌ Error saving to Google Sheets!\n{e}")



if __name__ == "__main__":
    bot.polling(none_stop=True)
