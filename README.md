# SearchIQS Ashford, CT - Scraper

Python scraper for extracting Land Records from SearchIQS Ashford, CT without browser automation (no Selenium, Playwright, or Puppeteer).

## Features
- Accesses website and selects "Search Records as Guest"
- Filters by Document Group: "Land Records"
- Dynamically sets date range from 80 days before current date to today
- Scrapes all available result pages
- Extracts: Party 1, Party 2, Type, Book-Page, Date, Description, Additional Description, Related
- Exports scraped records to CSV

## Requirements & Setup

1. Connect to a US-based VPN.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt