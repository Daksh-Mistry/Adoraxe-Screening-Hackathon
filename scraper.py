import os
import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from urllib.parse import urljoin

load_dotenv()

# read tokens from .env
cf_clearance = os.getenv("CF_CLEARANCE", "").strip()
asp_session = os.getenv("ASP_NET_SESSION_ID", "").strip()

# standard chrome user-agent
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"

# calculate dynamic dates (today and 80 days ago)
today = datetime.now()
from_date = (today - timedelta(days=80)).strftime("%m/%d/%Y")
to_date = today.strftime("%m/%d/%Y")
print(f"Searching dates from {from_date} to {to_date}")

# setup session
session = requests.Session()

# build cookie string
cookie_parts = []
if cf_clearance:
    cookie_parts.append(f"cf_clearance={cf_clearance}")
if asp_session:
    cookie_parts.append(f"ASP.NET_SessionId={asp_session}")

session.headers.update({
    "User-Agent": user_agent,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.searchiqs.com/CTASH/",
    "Cookie": "; ".join(cookie_parts)
})

# 1. open landing page
r = session.get("https://www.searchiqs.com/CTASH/", impersonate="chrome120")
if "Just a moment..." in r.text:
    print("Warning: Cloudflare challenged request. Please update CF_CLEARANCE in .env")

soup = BeautifulSoup(r.text, "html.parser")

# 2. click search records as guest
guest_data = {inp.get("name"): inp.get("value", "") for inp in soup.find_all("input") if inp.get("name")}
guest_data["__EVENTTARGET"] = "btnGuestLogin"
guest_data["__EVENTARGUMENT"] = ""

r = session.post("https://www.searchiqs.com/CTASH/", data=guest_data, impersonate="chrome120")
soup = BeautifulSoup(r.text, "html.parser")

# 3. select land records under document group
group_data = {inp.get("name"): inp.get("value", "") for inp in soup.find_all("input") if inp.get("name")}
group_data["__EVENTTARGET"] = "ctl00$ContentPlaceHolder1$cboDocGroup"
group_data["__EVENTARGUMENT"] = ""
group_data["ctl00$ContentPlaceHolder1$cboDocGroup"] = "LR"

form_elem = soup.find("form")
search_action = form_elem.get("action", "SearchAdvancedMP.aspx") if form_elem else "SearchAdvancedMP.aspx"
search_url = urljoin("https://www.searchiqs.com/CTASH/", search_action)

r = session.post(search_url, data=group_data, impersonate="chrome120")
soup = BeautifulSoup(r.text, "html.parser")

# 4. fill dates and submit search
search_data = {inp.get("name"): inp.get("value", "") for inp in soup.find_all("input") if inp.get("name")}
search_data["ctl00$ContentPlaceHolder1$cboDocGroup"] = "LR"
search_data["ctl00$ContentPlaceHolder1$cboDocType"] = "(ALL)"
search_data["ctl00$ContentPlaceHolder1$txtFromDate"] = from_date
search_data["ctl00$ContentPlaceHolder1$txtThruDate"] = to_date
search_data["ctl00$ContentPlaceHolder1$cmdSearch"] = "Search"
search_data["ctl00$ContentPlaceHolder1$cmdSearch.x"] = "30"
search_data["ctl00$ContentPlaceHolder1$cmdSearch.y"] = "15"

r = session.post(search_url, data=search_data, impersonate="chrome120")
results_url = "https://www.searchiqs.com/CTASH/SearchResultsMP.aspx"

# if redirected, load results page
if "SearchResultsMP.aspx" not in r.url:
    r = session.get(results_url, impersonate="chrome120")

soup = BeautifulSoup(r.text, "html.parser")

# 5. extract table rows
all_records = []
current_soup = soup

while True:
    table = current_soup.find("table", id=lambda x: x and "grdResults" in x)
    if not table:
        break

    rows = table.find_all("tr")
    headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
    try:
        p1 = headers.index("Party 1")
    except ValueError:
        p1 = 4

    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) < 8:
            continue
        all_records.append({
            "Party 1": cells[p1] if len(cells) > p1 else "",
            "Party 2": cells[p1 + 1] if len(cells) > p1 + 1 else "",
            "Type": cells[p1 + 2] if len(cells) > p1 + 2 else "",
            "Book-Page": cells[p1 + 3] if len(cells) > p1 + 3 else "",
            "Date": cells[p1 + 4] if len(cells) > p1 + 4 else "",
            "Description": cells[p1 + 5] if len(cells) > p1 + 5 else "",
            "Additional Description": cells[p1 + 6] if len(cells) > p1 + 6 else "",
            "Related": cells[p1 + 7] if len(cells) > p1 + 7 else ""
        })

    # check pagination dropdown
    page_sel = current_soup.find("select", id=lambda x: x and "ddlGoToPage1" in x)
    if not page_sel:
        break

    selected_page = page_sel.find("option", selected=True)
    current_page = int(selected_page.get("value", 1)) if selected_page else 1
    total_pages = len(page_sel.find_all("option"))

    if current_page >= total_pages:
        break

    next_page = str(current_page + 1)
    print(f"Loading page {next_page}...")

    page_data = {inp.get("name"): inp.get("value", "") for inp in current_soup.find_all("input") if inp.get("name")}
    page_data["__EVENTTARGET"] = "ctl00$ContentPlaceHolder1$ddlGoToPage1"
    page_data["__EVENTARGUMENT"] = ""
    page_data["ctl00$ContentPlaceHolder1$ddlGoToPage1"] = next_page
    page_data["ctl00$ContentPlaceHolder1$ddlGoToPage2"] = next_page

    r = session.post(results_url, data=page_data, impersonate="chrome120")
    current_soup = BeautifulSoup(r.text, "html.parser")

# 6. save to csv
df = pd.DataFrame(all_records)
df.to_csv("sample_sheet_output.csv", index=False)
print(f"Saved {len(df)} records to sample_sheet_output.csv")