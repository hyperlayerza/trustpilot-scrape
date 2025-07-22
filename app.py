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

# Set up logging with minimal output
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler()]
)

# Centralized selectors with comments for easy updates
SELECTORS = {
    # Review card container: Outer <div> or <article> for each review, used to find all reviews on a page
    "review_card": {"data-testid": "service-review-card-v2", "class": "styles_cardWrapper__.*"},
    
    # Rating: <div> with data-service-review-rating attribute or <img> with alt text, used for review_rating
    "rating": {
        "data_attr": "data-service-review-rating",
        "img_class": "CDS_StarRating_starRating__8ae3cf",
        "img_alt_pattern": r'Rated (\d+) out of 5 stars'
    },
    
    # Customer name: <span> containing the reviewer's name, used for review_customer
    "customer": {"class": "CDS_Typography_appearance-default__bedfe1 CDS_Typography_heading-xs__bedfe1 styles_consumerName__xKr9c"},
    
    # Title: <h2> containing the review title, used for review_title
    "title": {"tag": "h2", "class": "CDS_Typography_appearance-default__bedfe1 CDS_Typography_heading-xs__bedfe1"},
    
    # Review text: <p> containing the review description, used for review_text
    "text": {"tag": "p", "class": "CDS_Typography_appearance-default__bedfe1 CDS_Typography_body-l__bedfe1"},
    
    # Link: <a> with review URL, used for review_link
    "link": {"tag": "a", "data_attr": "data-review-title-typography", "value": "true"},
    
    # Date: <time> containing the review date, used for review_date
    "date": {"tag": "time"},
    
    # Total reviews: <div> with total review count, used for total_reviews
    "total_reviews": {"class": "styles_reviewsAndRating__.*"},
    
    # Overall rating: <div> with average rating, used for overall_rating
    "overall_rating": {"class": "CDS_Typography_appearance-default__.* CDS_Typography_display-m__.*"}
}

def test_selectors(url="https://www.trustpilot.com/review/hyperlayer.net"):
    """Helper function to test selectors and print matched elements."""
    logging.info("Testing selectors...")
    response = requests.get(url)
    if response.status_code != 200:
        logging.error(f"Failed to fetch page: Status code {response.status_code}")
        return
    soup = BeautifulSoup(response.text, "html.parser")
    
    for key, selector in SELECTORS.items():
        elements = []
        if "data-testid" in selector:
            elements = soup.find_all(attrs={"data-testid": selector["data-testid"]})
        elif "data_attr" in selector:
            elements = soup.find_all(attrs={selector["data_attr"]: True})
        elif "class" in selector:
            elements = soup.find_all(selector.get("tag", "div"), class_=re.compile(selector["class"]))
        elif "tag" in selector:
            elements = soup.find_all(selector["tag"])
        
        logging.info(f"Selector '{key}': Found {len(elements)} elements")
        for i, elem in enumerate(elements[:3], 1):  # Limit to first 3 for brevity
            logging.info(f"  Element {i}: {elem.get_text(strip=True)[:100]}...")

def scrape_trustpilot():
    logging.info("Scanning for reviews...")
    try:
        reviews_data = []
        total_reviews = None
        overall_rating = None
        from_page = 1
        to_page = 10

        def extract_text(element):
            return element.get_text(strip=True) if element else ""

        def extract_rating(review):
            # Try data attribute
            rating_div = review.find("div", attrs={SELECTORS["rating"]["data_attr"]: True})
            if rating_div and rating_div.get(SELECTORS["rating"]["data_attr"]):
                return int(rating_div[SELECTORS["rating"]["data_attr"]])
            
            # Fallback to img alt text
            rating_img = review.find("img", class_=re.compile(SELECTORS["rating"]["img_class"]))
            if rating_img and rating_img.get("alt"):
                match = re.search(SELECTORS["rating"]["img_alt_pattern"], rating_img["alt"])
                if match:
                    return int(match.group(1))
            return 0

        def parse_review_date(date_text):
            date_text = date_text.replace("Updated ", "")
            if "hours ago" in date_text.lower() or "hour ago" in date_text.lower():
                return dt.datetime.now().date()
            elif "a day ago" in date_text.lower():
                return dt.datetime.now().date() - dt.timedelta(days=1)
            elif "days ago" in date_text.lower():
                return dt.datetime.now().date() - dt.timedelta(days=int(date_text.split()[0]))
            try:
                return dt.datetime.strptime(date_text, "%b %d, %Y").date()
            except ValueError:
                return dt.datetime.now().date()

        # Get total reviews and calculate pages
        response = requests.get(f"https://www.trustpilot.com/review/{domain}", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/127.0.0.0"})
        if response.status_code != 200:
            logging.error(f"Failed to fetch initial page: Status code {response.status_code}")
            return
        soup = BeautifulSoup(response.text, "html.parser")
        
        total_reviews_elem = soup.find(class_=re.compile(SELECTORS["total_reviews"]["class"]))
        total_reviews_text = extract_text(total_reviews_elem)
        total_reviews = int(re.search(r'\d+', total_reviews_text).group()) if total_reviews_text else 0
        
        overall_rating_elem = soup.find(class_=re.compile(SELECTORS["overall_rating"]["class"]))
        overall_rating = extract_text(overall_rating_elem) or "N/A"
        
        to_page = min(to_page, (total_reviews // 20) + 1)

        # Scrape reviews from each page
        for page in range(from_page, to_page + 1):
            url = f"https://www.trustpilot.com/review/{domain}?page={page}"
            time.sleep(1)  # Avoid rate limiting
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/127.0.0.0"})
            if response.status_code != 200:
                logging.error(f"Failed to fetch page {page}: Status code {response.status_code}")
                break
            soup = BeautifulSoup(response.text, "html.parser")
            
            reviews = soup.find_all(attrs={"data-testid": SELECTORS["review_card"]["data-testid"]})
            logging.info(f"{len(reviews)} reviews found on page {page}")

            for review in reviews:
                rating = extract_rating(review)
                if rating >= 4:
                    review_data = {
                        "review_customer": extract_text(review.find("span", class_=SELECTORS["customer"]["class"])),
                        "review_title": extract_text(review.find(SELECTORS["title"]["tag"], class_=SELECTORS["title"]["class"])),
                        "review_text": extract_text(review.find(SELECTORS["text"]["tag"], class_=SELECTORS["text"]["class"])),
                        "review_link": f"https://www.trustpilot.com{review_link_elem['href']}" if (review_link_elem := review.find(SELECTORS["link"]["tag"], attrs={SELECTORS["link"]["data_attr"]: SELECTORS["link"]["value"]})) and review_link_elem.get("href") else "",
                        "review_date": str(parse_review_date(extract_text(review.find(SELECTORS["date"]["tag"])))),
                        "review_rating": f"Rated {rating} out of 5 stars",
                        "page_number": page
                    }
                    if not review_data["review_link"]:
                        logging.warning("No valid review link found for a review")
                    reviews_data.append(review_data)

        # Save to JSON
        output_dir = os.path.join(os.path.dirname(__file__), "data")
        output_path = os.path.join(output_dir, "trustpilot_reviews_4star_up.json")
        os.makedirs(output_dir, exist_ok=True)
        logging.info(f"Adding {len(reviews_data)} reviews to JSON at {os.path.abspath(output_path)}")
        
        with open(output_path, 'w') as f:
            json.dump({"total_reviews": total_reviews, "overall_rating": overall_rating, "reviews": reviews_data}, f, indent=4)
        
        logging.info(f"Successfully added {len(reviews_data)} reviews to JSON")

    except Exception as e:
        logging.error(f"Error during scrape: {str(e)}")
        raise

@app.route('/trustpilot_reviews_4star_up.json')
def serve_json():
    output_dir = os.path.join(os.path.dirname(__file__), "data")
    file_path = os.path.join(output_dir, "trustpilot_reviews_4star_up.json")
    logging.info(f"Serving JSON from {os.path.abspath(file_path)}")
    if os.path.exists(file_path):
        return send_from_directory(output_dir, "trustpilot_reviews_4star_up.json")
    return {"message": "File not yet generated, please wait for the initial scrape"}, 503

def run_scheduler():
    time.sleep(5)  # Wait for container startup
    scrape_trustpilot()
    schedule.every(6).hours.do(scrape_trustpilot)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_selectors()
    else:
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        app.run(host='0.0.0.0', port=5050, debug=False)