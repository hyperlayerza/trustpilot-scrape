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

# Initialize overall_rating variable
overall_rating = None

# Initialize total_reviews variable
total_reviews = None

# Set Trustpilot page numbers to scrape here
from_page = 1
to_page = 7

for i in range(from_page, to_page + 1):
    response = requests.get(f"https://www.trustpilot.com/review/hyperlayer.net?page={i}")
    web_page = response.text
    soup = BeautifulSoup(web_page, "html.parser")

    # Extract total reviews number (only do this once)
    if total_reviews is None:
        total_reviews_elem = soup.find(class_="typography_body-l__KUYFJ typography_appearance-subtle__8_H2l styles_text__W4hWi")
        total_reviews_text = total_reviews_elem.text.strip() if total_reviews_elem else ""
        total_reviews = re.search(r'\d+', total_reviews_text).group() if total_reviews_text else ""

    # Extract overall rating (only do this once)
    if overall_rating is None:
        overall_rating_elem = soup.find(class_="typography_heading-m__T_L_X typography_appearance-default__AAY17")
        overall_rating = overall_rating_elem.text.strip() if overall_rating_elem else ""

    for review in soup.find_all(class_="paper_paper__1PY90 paper_outline__lwsUX card_card__lQWDv card_noPadding__D8PcU styles_reviewCard__hcAvl"):
        # Review ratings
        review_rating = review.find(class_="star-rating_starRating__4rrcf star-rating_medium__iN6Ty").findChild()
        rating_value = int(review_rating["alt"].split()[1])
        
        # Only proceed if the rating is 4 stars or higher
        if rating_value >= 4:
            # Review titles
            review_title = review.find(class_="typography_heading-s__f7029 typography_appearance-default__AAY17")
            if review_title:
                review_titles.append(review_title.getText())
            else:
                review_titles.append("N/A")

            # Review customers
            review_customer = review.find(class_="typography_heading-xxs__QKBS8 typography_appearance-default__AAY17")
            review_customers.append(review_customer.getText())

            # Review dates
            review_date_original = review.select_one(selector="time").getText().replace("Updated ", "")
            if "hours ago" in review_date_original.lower() or "hour ago" in review_date_original.lower():
                review_date = dt.datetime.now().date()
            elif "a day ago" in review_date_original.lower():
                review_date = dt.datetime.now().date() - dt.timedelta(days=1)
            elif "days ago" in review_date_original.lower():
                review_date = dt.datetime.now().date() - dt.timedelta(days=int(review_date_original[0]))
            else:
                review_date = dt.datetime.strptime(review_date_original, "%b %d, %Y").date()
            review_dates.append(str(review_date))

            # Append review rating
            review_ratings.append(f"Rated {rating_value} out of 5 stars")
            
            # When there is no review text, append "" instead of skipping so that data remains in sequence with other review data e.g. review_title
            review_text = review.find(class_="typography_body-l__KUYFJ typography_appearance-default__AAY17 typography_color-black__5LYEn")
            if review_text == None:
                review_texts.append("")
            else:
                review_texts.append(review_text.getText())
            
            # Extract review link
            review_link_elem = review.find("a", href=True, class_="link_link__IZzHN")
            if review_link_elem and "/reviews/" in review_link_elem["href"]:
                review_path = review_link_elem["href"]
                review_link = f"https://www.trustpilot.com{review_path}"
            else:
                review_link = "N/A"
            review_links.append(review_link)
            
            # Trustpilot page number
            page_number.append(i)

# Create final dataframe from lists
df_reviews = pd.DataFrame(list(zip(review_titles, review_customers, review_dates, review_ratings, review_texts, review_links, page_number)),
                columns =['review_title', 'review_customer', 'review_date', 'review_rating', 'review_text', 'review_link', 'page_number'])

# Save DataFrame to JSON file with total_reviews and overall_rating at the top
output_data = {
    "total_reviews": total_reviews,
    "overall_rating": overall_rating,
    "reviews": df_reviews.to_dict(orient='records')
}

with open('trustpilot_reviews_4star_up.json', 'w') as f:
    json.dump(output_data, f, indent=4)
