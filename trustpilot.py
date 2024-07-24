from bs4 import BeautifulSoup
import requests
import pandas as pd
import datetime as dt
import json
import re

# Initialize lists
review_titles = []
review_customers = []
review_dates = []
review_ratings = []
review_texts = []
review_links = []
page_number = []

# Initialize overall_rating and total_reviews variables
overall_rating = None
total_reviews = None

# Set Trustpilot page numbers to scrape here
from_page = 1
to_page = 7

# Function to extract and clean text
def extract_text(element, default="N/A"):
    return element.get_text(strip=True) if element else default

# Function to extract review date
def parse_review_date(date_text):
    date_text = date_text.replace("Updated ", "")
    if "hours ago" in date_text.lower() or "hour ago" in date_text.lower():
        return dt.datetime.now().date()
    elif "a day ago" in date_text.lower():
        return dt.datetime.now().date() - dt.timedelta(days=1)
    elif "days ago" in date_text.lower():
        return dt.datetime.now().date() - dt.timedelta(days=int(date_text[0]))
    else:
        return dt.datetime.strptime(date_text, "%b %d, %Y").date()

# Loop through the pages
for i in range(from_page, to_page + 1):
    response = requests.get(f"https://www.trustpilot.com/review/hyperlayer.net?page={i}")
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract total reviews number (only once)
    if total_reviews is None:
        total_reviews_elem = soup.find(class_="typography_body-l__KUYFJ typography_appearance-subtle__8_H2l styles_text__W4hWi")
        total_reviews_text = extract_text(total_reviews_elem, "")
        total_reviews = re.search(r'\d+', total_reviews_text).group() if total_reviews_text else ""

    # Extract overall rating (only once)
    if overall_rating is None:
        overall_rating_elem = soup.find(class_="typography_heading-m__T_L_X typography_appearance-default__AAY17")
        overall_rating = extract_text(overall_rating_elem, "")

    # Loop through each review card
    for review in soup.find_all(class_="paper_paper__1PY90 paper_outline__lwsUX card_card__lQWDv card_noPadding__D8PcU styles_reviewCard__hcAvl"):
        review_rating_elem = review.find(class_="star-rating_starRating__4rrcf star-rating_medium__iN6Ty").findChild()
        rating_value = int(review_rating_elem["alt"].split()[1]) if review_rating_elem else 0
        
        # Only proceed if the rating is 4 stars or higher
        if rating_value >= 4:
            review_titles.append(extract_text(review.find(class_="typography_heading-s__f7029 typography_appearance-default__AAY17")))
            review_customers.append(extract_text(review.find(class_="typography_heading-xxs__QKBS8 typography_appearance-default__AAY17")))
            review_dates.append(str(parse_review_date(extract_text(review.select_one(selector="time")))))
            review_ratings.append(f"Rated {rating_value} out of 5 stars")
            review_texts.append(extract_text(review.find(class_="typography_body-l__KUYFJ typography_appearance-default__AAY17 typography_color-black__5LYEn"), ""))
            
            review_link_elem = review.find("a", href=True, class_="link_link__IZzHN")
            if review_link_elem and "/reviews/" in review_link_elem["href"]:
                review_link = f"https://www.trustpilot.com{review_link_elem['href']}"
            else:
                review_link = "N/A"
            review_links.append(review_link)
            
            page_number.append(i)

# Create final dataframe from lists
df_reviews = pd.DataFrame({
    'review_title': review_titles,
    'review_customer': review_customers,
    'review_date': review_dates,
    'review_rating': review_ratings,
    'review_text': review_texts,
    'review_link': review_links,
    'page_number': page_number
})

# Save DataFrame to JSON file with total_reviews and overall_rating at the top
output_data = {
    "total_reviews": total_reviews,
    "overall_rating": overall_rating,
    "reviews": df_reviews.to_dict(orient='records')
}

with open('trustpilot_reviews_4star_up.json', 'w') as f:
    json.dump(output_data, f, indent=4)
