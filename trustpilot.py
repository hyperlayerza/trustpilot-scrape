from bs4 import BeautifulSoup
import requests
import pandas as pd
import datetime as dt

# Initialize lists
review_titles = []
review_dates_original = []
review_dates = []
review_ratings = []
review_texts = []
page_number = []

# Set Trustpilot page numbers to scrape here
from_page = 1
to_page = 50

for i in range(from_page, to_page + 1):
    response = requests.get(f"https://www.trustpilot.com/review/hyperlayer.net")
    web_page = response.text
    soup = BeautifulSoup(web_page, "html.parser")

    for review in soup.find_all(class_ = "paper_paper__1PY90 paper_outline__lwsUX card_card__lQWDv card_noPadding__D8PcU styles_reviewCard__hcAvl"):
        # Review ratings
        review_rating = review.find(class_ = "star-rating_starRating__4rrcf star-rating_medium__iN6Ty").findChild()
        rating_value = int(review_rating["alt"].split()[1])
        
        # Only proceed if the rating is 4 stars or higher
        if rating_value >= 4:
            # Review titles
            review_title = review.find(class_ = "typography_heading-xxs__QKBS8 typography_appearance-default__AAY17")
            review_titles.append(review_title.getText())

            # Review dates
            review_date_original = review.select_one(selector="time")
            review_dates_original.append(review_date_original.getText())

            # Convert review date texts into Python datetime objects
            review_date = review.select_one(selector="time").getText().replace("Updated ", "")
            if "hours ago" in review_date.lower() or "hour ago" in review_date.lower():
                review_date = dt.datetime.now().date()
            elif "a day ago" in review_date.lower():
                review_date = dt.datetime.now().date() - dt.timedelta(days=1)
            elif "days ago" in review_date.lower():
                review_date = dt.datetime.now().date() - dt.timedelta(days=int(review_date[0]))
            else:
                review_date = dt.datetime.strptime(review_date, "%b %d, %Y").date()
            review_dates.append(review_date)

            # Append review rating
            review_ratings.append(f"Rated {rating_value} out of 5 stars")
            
            # When there is no review text, append "" instead of skipping so that data remains in sequence with other review data e.g. review_title
            review_text = review.find(class_ = "typography_body-l__KUYFJ typography_appearance-default__AAY17 typography_color-black__5LYEn")
            if review_text == None:
                review_texts.append("")
            else:
                review_texts.append(review_text.getText())
            
            # Trustpilot page number
            page_number.append(i)

# Create final dataframe from lists
df_reviews = pd.DataFrame(list(zip(review_titles, review_dates_original, review_dates, review_ratings, review_texts, page_number)),
                columns =['review_title', 'review_date_original', 'review_date', 'review_rating', 'review_text', 'page_number'])

# Save DataFrame to JSON file
df_reviews.to_json('trustpilot_reviews_4star_up.json', orient='records', indent=4)
