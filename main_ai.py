from transformers import pipeline
import re
import requests
from datetime import datetime

# Load a Pretrained Zero-Shot Classification Model
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
# qa_pipeline = pipeline("question-answering", model="deepset/roberta-base-squad2")  # QA Model for Date Extraction


# Define Expense Categories
labels = ["Entertainment", "Work", "Daily Expenses", "Family", "Shopping", "Health & Fitness", 
          "Food", "Education", "Hobbies", "Gifts & Social", "Tech", "Sports", "Transport", "Bills", "Other"]

def parse_duckling_time(duckling_response):
    """
    Extracts a single valid time from the Duckling response.
    If it's an interval, returns the midpoint (mean time).
    """
    if "value" in duckling_response and duckling_response["type"] == "value":
        extracted_time = duckling_response["value"]  # Return exact time

    elif "from" in duckling_response and "to" in duckling_response:
        from_time = duckling_response["from"]["value"]
        to_time = duckling_response["to"]["value"]

        # Convert to datetime objects
        from_dt = datetime.fromisoformat(from_time[:-6])  # Remove timezone offset
        to_dt = datetime.fromisoformat(to_time[:-6])

        # Calculate midpoint
        mean_dt = from_dt + (to_dt - from_dt) / 2
        extracted_time = mean_dt.isoformat()  # Return as ISO format

    else: return None  # If no valid date found
    extracted_dt = datetime.fromisoformat(extracted_time[:-6])  # Remove timezone offset
    now = datetime.now()

    # If Duckling returned a future date, shift it to last year
    while extracted_dt > now:
        extracted_dt = extracted_dt.replace(year=extracted_dt.year - 1)

    return extracted_dt.strftime('%d.%m.%Y %H:%M')


def duckling_response(text):
    url = "http://localhost:8081/parse"
    payload = {
        "text": text,  
        "dims": ["time"],  
        "locale": "en_US",
        "grain":"day",
        "tz": "CET",
    }

    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        data = response.json()
        return data
    return None 

def extract_date(text):
    data = duckling_response(text)
    if data:
        for item in data:
            if item["dim"] == "time" and not item["latent"]:
                return parse_duckling_time(item["value"])  # Process the time result

    return datetime.now().strftime('%d.%m.%Y %H:%M')   

def extract_amount(text, default_unit='EUR'):
    income_or_expense = classifier(text, ['income', 'expense'])
    income_or_expense_scores = list(zip(income_or_expense['labels'], income_or_expense['scores']))
    
    # Check Confidence income or expense
    top_res, top_score = income_or_expense_scores[0]
    sec_res, sec_score = income_or_expense_scores[1]

    if top_res == 'income':
        sign_of_number = 1
    elif top_res == 'expense':
        sign_of_number = -1
    
    data = duckling_response(text)
    if data:
        for item in data:
            if item["dim"] == "amount-of-money" and not item["latent"]:
                return item["value"]['value']*sign_of_number, item['value']['unit']  # Process the time result
        for item in data:
            if item["dim"] == "number" and not item["latent"]:
                return item["value"]['value']*sign_of_number, default_unit  # Process the time result
    return [None, default_unit]

def extract_categories(text):
    # AI Classifies the Category
    result = classifier(text, labels)
    category_scores = list(zip(result["labels"], result["scores"]))  # [(category, score), ...]
    
    # Check Confidence
    top_category, top_score = category_scores[0]
    second_category, second_score = category_scores[1]
    third_category, third_score = category_scores[2]

    # If AI is uncertain, ask the user to choose
    if (top_score - second_score) < 0.05 and (second_score - third_score) < 0.05:  
        return [top_category, second_category, third_category]
    elif (top_score - second_score) < 0.05:  
        return [top_category, second_category]
    return [top_category]


def analyze_expense(text):
    expense_date = extract_date(text)
    expense_amount = extract_amount(text)
    expense_categories = extract_categories(text)
    
    return {"expense_categories": expense_categories, "expense_amount": expense_amount, "expense_unit":expense_amount[1], "expense_date": expense_date}
