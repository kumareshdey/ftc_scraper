import requests
from setup import get_driver, log
from urllib.parse import quote
from selenium import webdriver
from bs4 import BeautifulSoup
from retry import retry


base_url = "https://search.ftc.gov/search?utf8=%E2%9C%93&affiliate=ftc_prod&query={query}&commit=Search&page={page}"

def download_pdf(log, url, save_path):
    if not url.endswith(".pdf"):
        return
    response = requests.get(url)
    path = "/".join([save_path, url.split("/")[-1]])
    if response.status_code == 200:
        with open(path, 'wb') as f:
            f.write(response.content)
        log.info(f"PDF downloaded successfully and saved as {path}")
    else:
        log.error(f"Failed to download PDF. Status code: {response.status_code}")


def final_page(log, url, save_path):
    includes  = [
    "Order",
    "Complaint",
    "Administrative Complaint",
    "Administrative Complaint [Redacted Public Version]",
    "Final Order",
    "Decision and Order",
    "Decision of Chief Administrative Law Judge",
    "Regarding Potential Criminal Violations of",
    "Provisionally Redacted Public Version",
    "Stipulated Order for Civil Penalty, Monetary Judgment and Injunctive Relief",
    "Stipulated Order for Permanent Injunction and Monetary Judgment",
    "Complaint for Civil Penalties, Injunction, and Other Relief",
    "Complaint for Permanent Injunction, Monetary Relief, Civil Penalties, and Other Relief",
    "Complaint for Permanent Injunction, Other Equitable Relief, and Civil Penalties",
    "Complaint for Permanent Injunction and Other Equitable Relief",
    "Complaint for Permanent Injunction and Other Equitable Relief [Seal Lifted]",
    "Complaint for Permanent Injunction and Civil Penalties",
    "[Redacted] Complaint for Permanent Injunction and Other Equitable Relief",
    "Order for Permanent Injunction and Civil Penalty Judgment [Entered by the Court]",
    "Commission Final Order",
    "Consent Decree",
    "Administrative Part 1 Complaint",
    "Administrative Part 2 Complaint",
    "Administrative Part 3 Complaint",
    "Administrative Part 4 Complaint"
]

    with get_driver() as driver:
        driver.get(url)
        urls = []
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for link in soup.find_all('a', string=lambda text: text and text in includes):
            download_pdf(log, "https://www.ftc.gov" + link['href'], save_path)
        log.info(f"Successfully downloaded all PDFs from {url}")


def per_page_operation(log, soup: BeautifulSoup, save_path):
    search_result_items: list[BeautifulSoup] = soup.find_all("div", {
        "data-testid": "gridContainer",
        "class": "grid-container result search-result-item"
    })
    try:
        for search_result_item in search_result_items:
            text = search_result_item.find('h2', class_='result-title-label')
            if ("|" or "In the Matter of") in text.text:
                url = text.find('a')['href']
                final_page(log, url, save_path)
    except:
        pass
    return


@retry(tries=2, delay=2, logger=log)
def first_page(log, query, save_path, driver: webdriver.Chrome) -> None:
    url = base_url.format(query=quote(query), page=1)
    log.info(f"Fetching URL: {url}")
    driver.get(url)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    # Find pagination items
    pagination_items = soup.find_all("li", class_="usa-pagination__item usa-pagination__page-no")
    log.debug(f"Pagination items found: {pagination_items}")
    
    # Extract numeric page numbers
    try:
        page_numbers = [int(item.text) for item in pagination_items if item.text.isdigit()]
        if not page_numbers:
            log.warning("No page numbers found. Defaulting to 1.")
            max_page = 0  # Default if no pagination is found
        else:
            max_page = max(page_numbers)
    except Exception as e:
        log.error(f"Error parsing page numbers: {e}")
        raise ValueError("Failed to extract page numbers.") from e

    log.info(f"Total pages found: {max_page}")
    
    # Perform per-page operation
    per_page_operation(log, soup, save_path)
    return max_page


