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

# Set up logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

def scrape_trustpilot():
    logging.info("Scraper started running")
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
        to_page = 10

        def extract_text(element, class_name=None):
            if element:
                return element.get_text(strip=True)
            return ""  # Silently return empty string if element is not found

        def extract_rating(element, class_name=None):
            if element:
                rating_child = element.findChild()
                return int(rating_child["alt"].split()[1]) if rating_child else 0
            return 0  # Silently return 0 if element is not found

        def extract_elements(soup, class_name):
            elements = soup.find_all(class_=class_name)
            return elements  # Silently return empty list if elements are not found

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
                total_reviews_elem = soup.find(class_="typography_body-l__v5JLj typography_appearance-default__t8iAq styles_reviewsAndRating__OIRXy")
                total_reviews_text = extract_text(total_reviews_elem)
                total_reviews = re.search(r'\d+', total_reviews_text).group() if total_reviews_text else ""

            if overall_rating is None:
                overall_rating_elem = soup.find(class_="typography_body-l__v5JLj typography_appearance-subtle__PYOVM")
                overall_rating = extract_text(overall_rating_elem)

            reviews = extract_elements(soup, "paper_paper__EGeEb paper_square__owXbO card_card__yyGgu card_noPadding__OOiac card_square___AZeg styles_reviewCard__Qwhpy")

            for review in reviews:
                rating_elem = review.find(class_="star-rating_starRating__sdbkn star-rating_medium__Oj7C9")
                rating_value = extract_rating(rating_elem)
                
                if rating_value >= 4:
                    # Title: Use <h2> tag with the class
                    title_elem = review.find("h2", class_="typography_heading-xs__osRhC typography_appearance-default__t8iAq")
                    review_titles.append(extract_text(title_elem))
                    
                    # Customer: Use <span> tag with the class
                    customer_elem = review.find("span", class_="typography_heading-xs__osRhC typography_appearance-default__t8iAq")
                    review_customers.append(extract_text(customer_elem))
                    
                    time_elem = review.select_one("time")
                    date_text = extract_text(time_elem)
                    review_dates.append(str(parse_review_date(date_text)) if date_text else "")
                    
                    review_ratings.append(f"Rated {rating_value} out of 5 stars")
                    
                    text_elem = review.find(class_="typography_body-l__v5JLj typography_appearance-default__t8iAq")
                    review_texts.append(extract_text(text_elem))
                    
                    review_link_elem = review.find("a", href=True, class_="link_link__jBdLV")
                    review_link = f"https://www.trustpilot.com{review_link_elem['href']}" if review_link_elem and "/reviews/" in review_link_elem["href"] else ""
                    if not review_link:
                        logging.error("Can't find review link class 'link_link__jBdLV' or valid href, please fix")
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
        
        output_dir = os.path.join(os.getcwd(), "data")
        output_path = os.path.join(output_dir, "trustpilot_reviews_4star_up.json")
        logging.info(f"Attempting to write JSON to {output_path}")
        
        os.makedirs(output_dir, exist_ok=True)
        logging.info(f"Directory {output_dir} exists or was created")
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=4)
        logging.info(f"Successfully wrote JSON to {output_path}")
        logging.info(f"File size: {os.path.getsize(output_path)} bytes")

        logging.info(f"Scraper ran successfully and pulled data: {len(df_reviews)} reviews collected")
    except Exception as e:
        logging.error(f"Error during scrape: {str(e)}")
        raise

@app.route('/trustpilot_reviews_4star_up.json')
def serve_json():
    file_path = os.path.join(os.getcwd(), "data", "trustpilot_reviews_4star_up.json")
    if os.path.exists(file_path):
        return send_from_directory(os.path.join(os.getcwd(), "data"), "trustpilot_reviews_4star_up.json")
    return {"message": "File not yet generated, please wait for the initial scrape"}, 503

def run_scheduler():
    scrape_trustpilot()  # Initial scrape
    schedule.every(6).hours.do(scrape_trustpilot)
    while True:
        schedule.run_pending()
        time.sleep(60)

# Start scheduler in a separate thread
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5050, debug=False)