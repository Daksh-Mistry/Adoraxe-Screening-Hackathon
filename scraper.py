import os
import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from urllib.parse import urljoin

load_dotenv()

cf_clearance = os.getenv("CF_CLEARANCE", "").strip()
asp_session = os.getenv("ASP_NET_SESSION_ID", "").strip()
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"

today = datetime.now()
from_date = (today - timedelta(days=80)).strftime("%m/%d/%Y")
to_date = today.strftime("%m/%d/%Y")
print(f"Date range: {from_date} to {to_date}")

session = requests.Session()
if cf_clearance:
    session.cookies.set("cf_clearance", cf_clearance, domain=".searchiqs.com")
if asp_session:
    session.cookies.set("ASP.NET_SessionId", asp_session, domain="www.searchiqs.com")

session.headers.update({
    "User-Agent": user_agent,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.searchiqs.com",
    "Referer": "https://www.searchiqs.com/CTASH/SearchResultsMP.aspx",
})

results_url = "https://www.searchiqs.com/CTASH/SearchResultsMP.aspx"

def parse_results(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id=lambda x: x and "grdResults" in x)
    if not table:
        return [], soup

    records = []
    rows = table.find_all("tr")
    headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
    try:
        p1 = headers.index("Party 1")
    except ValueError:
        p1 = 4

    for r in rows[1:]:
        cells = [td.get_text(strip=True) for td in r.find_all("td")]
        if len(cells) < 8:
            continue
        records.append({
            "Party 1": cells[p1] if len(cells) > p1 else "",
            "Party 2": cells[p1 + 1] if len(cells) > p1 + 1 else "",
            "Type": cells[p1 + 2] if len(cells) > p1 + 2 else "",
            "Book-Page": cells[p1 + 3] if len(cells) > p1 + 3 else "",
            "Date": cells[p1 + 4] if len(cells) > p1 + 4 else "",
            "Description": cells[p1 + 5] if len(cells) > p1 + 5 else "",
            "Additional Description": cells[p1 + 6] if len(cells) > p1 + 6 else "",
            "Related": cells[p1 + 7] if len(cells) > p1 + 7 else ""
        })
    return records, soup

# 1. Fetch Page 1
print("Fetching Search Results Page 1...")
r1 = session.get(results_url, impersonate="chrome120")
all_records, current_soup = parse_results(r1.text)
print(f"Scraped Page 1: {len(all_records)} records")

# 2. Check and scrape remaining pages
page_sel = current_soup.find("select", id=lambda x: x and "ddlGoToPage" in x)
if page_sel:
    pages = [opt.get("value") for opt in page_sel.find_all("option")]
    for p in pages:
        if p == "1":
            continue
        print(f"Scraping Page {p}...")
        page_data = {inp.get("name"): inp.get("value", "") for inp in current_soup.find_all("input") if inp.get("name")}
        page_data["__EVENTTARGET"] = "ctl00$ContentPlaceHolder1$ddlGoToPage1"
        page_data["__EVENTARGUMENT"] = ""
        page_data["ctl00$ContentPlaceHolder1$ddlGoToPage1"] = p
        page_data["ctl00$ContentPlaceHolder1$ddlGoToPage2"] = p

        r_page = session.post(results_url, data=page_data, impersonate="chrome120")
        page_records, _ = parse_results(r_page.text)
        print(f"Scraped Page {p}: {len(page_records)} records")
        all_records.extend(page_records)

# 3. Export to CSV
df = pd.DataFrame(all_records)
df.to_csv("sample_sheet_output.csv", index=False)
print(f"SUCCESS! Total records scraped: {len(df)}")
print("Saved to: sample_sheet_output.csv")