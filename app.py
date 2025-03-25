from flask import Flask, send_from_directory
import schedule
import threading
import time
from bs4 import BeautifulSoup
import requests
import pandas as pd
import datetime as dt
import json
import re
import logging
import os

app = Flask(__name__)

domain = "hyperlayer.net"

# Ensure the data directory exists and set up logging
os.makedirs('/app/data', exist_ok=True)
logging.basicConfig(filename='/app/data/scraper.log', level=logging.INFO)

def scrape_trustpilot():
    try:
        review_titles = []
        review_customers = []
        review_dates = []
        review_ratings = []
        review_texts = []
        review_links = []
        page_number = []

        overall_rating = None
        total_reviews = None
        from_page = 1
        to_page = 7

        def extract_text(element, default="N/A"):
            return element.get_text(strip=True) if element else default

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

        for i in range(from_page, to_page + 1):
            response = requests.get(f"https://www.trustpilot.com/review/{domain}?page={i}")
            soup = BeautifulSoup(response.text, "html.parser")
            if total_reviews is None:
                total_reviews_elem = soup.find(class_="typography_body-l__v5JLj typography_appearance-default__t8iAq styles_reviewsAndRating__Syz6V")
                total_reviews_text = extract_text(total_reviews_elem, "")
                total_reviews = re.search(r'\d+', total_reviews_text).group() if total_reviews_text else ""

            if overall_rating is None:
                overall_rating_elem = soup.find(class_="typography_body-l__v5JLj typography_appearance-subtle__PYOVM")
                overall_rating = extract_text(overall_rating_elem, "")

            for review in soup.find_all(class_="paper_paper__EGeEb paper_square__owXbO card_card__yyGgu card_noPadding__OOiac card_square___AZeg styles_reviewCard__rvE5E"):
                review_rating_elem = review.find(class_="star-rating_starRating__sdbkn star-rating_medium__Oj7C9").findChild()
                rating_value = int(review_rating_elem["alt"].split()[1]) if review_rating_elem else 0
                
                if rating_value >= 4:
                    review_titles.append(extract_text(review.find(class_="typography_heading-xs__osRhC typography_appearance-default__t8iAq")))
                    review_customers.append(extract_text(review.find(class_="typography_heading-xs__osRhC typography_appearance-default__t8iAq")))
                    review_dates.append(str(parse_review_date(extract_text(review.select_one(selector="time")))))
                    review_ratings.append(f"Rated {rating_value} out of 5 stars")
                    review_texts.append(extract_text(review.find(class_="typography_body-l__v5JLj typography_appearance-default__t8iAq"), ""))
                    
                    review_link_elem = review.find("a", href=True, class_="link_link__jBdLV")
                    review_link = f"https://www.trustpilot.com{review_link_elem['href']}" if review_link_elem and "/reviews/" in review_link_elem["href"] else "N/A"
                    review_links.append(review_link)
                    
                    page_number.append(i)

        df_reviews = pd.DataFrame({
            'review_title': review_titles,
            'review_customer': review_customers,
            'review_date': review_dates,
            'review_rating': review_ratings,
            'review_text': review_texts,
            'review_link': review_links,
            'page_number': page_number
        })

        output_data = {
            "total_reviews": total_reviews,
            "overall_rating": overall_rating,
            "reviews": df_reviews.to_dict(orient='records')
        }
        
        os.makedirs('/app/data', exist_ok=True)
        output_path = '/app/data/trustpilot_reviews_4star_up.json'
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=4)
        
        logging.info(f"Successfully ran scrape at {dt.datetime.now()}")
    except Exception as e:
        logging.error(f"Error during scrape: {str(e)}")

@app.route('/trustpilot_reviews_4star_up.json')
def serve_json():
    file_path = '/app/data/trustpilot_reviews_4star_up.json'
    if os.path.exists(file_path):
        return send_from_directory('/app/data', 'trustpilot_reviews_4star_up.json')
    return {"message": "File not yet generated, please wait for the initial scrape"}, 503

def run_scheduler():
    # Initial scrape on startup
    scrape_trustpilot()
    # Schedule subsequent scrapes every 6 hours
    schedule.every(6).hours.do(scrape_trustpilot)
    while True:
        schedule.run_pending()
        time.sleep(60)

# Start the scheduler thread immediately when the module is imported
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

if __name__ == "__main__":
    # For local testing only; Gunicorn overrides this in Docker
    app.run(host='0.0.0.0', port=5050)