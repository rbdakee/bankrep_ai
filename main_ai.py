from transformers import pipeline
import re
import dateparser
from datetime import datetime

# Load a Pretrained Zero-Shot Classification Model
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
qa_pipeline = pipeline("question-answering", model="deepset/roberta-base-squad2")  # QA Model for Date Extraction


# Define Expense Categories
labels = ["Entertainment", "Work", "Daily Expenses", "Family", "Shopping", "Health & Fitness", 
          "Food", "Education", "Other", "Hobbies", "Gifts & Social", "Tech", "Sports", "Transport", "Bills"]

def extract_date(text):
    """Extracts a date using regex first, then falls back to QA model if necessary."""

    # Use QA model
    question = f"When did this expense happen if today is {datetime.now().strftime('%d.%m.%Y')}?"
    result = qa_pipeline(question=question, context=text)
    extracted_date = result["answer"]
    parsed_date = dateparser.parse(extracted_date, settings={'PREFER_DATES_FROM': 'past'})

    if parsed_date and 1900 <= parsed_date.year <= 2100:  # Ensure valid year
        return parsed_date.strftime('%d.%m.%Y')

    return datetime.now().strftime('%d.%m.%Y')  # Fallback to today’s date

def extract_amount(text):
    amount_match = re.search(r"\d+", text)  # Find numbers in the text
    amount = amount_match.group() if amount_match else None
    return amount

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
    
    return {"expense_categories": expense_categories, "expense_amount": expense_amount, "expense_date": expense_date}
