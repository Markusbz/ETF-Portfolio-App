import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

class etf_list_getter:

    def __init__(self, browser_binary_path, chrome_driver_path):
        self.browser_binary_path = browser_binary_path
        self.chrome_driver_path = chrome_driver_path
        self.options = webdriver.ChromeOptions()
        self.options.binary_location = browser_binary_path
        self.options.add_argument("--headless=new")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--window-size=1920,1200")
        self.options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_driver_path = Service(chrome_driver_path)

    def get_etf_list(self):
        driver = webdriver.Chrome(options=self.options)
        #open general site to set cookie
        driver.get("https://www.ishares.com/uk/professional/en")
        wait = WebDriverWait(driver, 5)
        element = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler")))
        driver.find_element("id","onetrust-reject-all-handler").click()
        driver.get("https://www.ishares.com/uk/professional/en?switchLocale=y&siteEntryPassthrough=true")
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.get("https://www.ishares.com/uk/professional/en/products/etf-investments#/?productView=etf&pageNumber=1&sortColumn=totalFundSizeInMillions&sortDirection=desc&keyFacts=all&dataView=keyFacts&showAll=true")

        # Fluent wait for the rows to appear
        try:
            rows = WebDriverWait(driver, 30, poll_frequency=2).until(
                EC.presence_of_all_elements_located((By.XPATH, "//table/tbody/tr"))
            )

            # Initialize a list to store the fund data
            self.fund_data = []

            # Iterate through each row and extract the desired information
            for row in rows:
                try:
                    # Extract the ticker, name, and link
                    elements = row.text.splitlines()

                    name = elements[0]
                    ticker = elements[1].split("Factsheet")[0] if "Factsheet" in elements[1] else elements[1]
                    currency = elements[3]
                    hedging = "Unhedged" if elements[4] == "-" else elements[4]
                    distribution = elements[5]
                    link = row.find_element(By.TAG_NAME, "a").get_attribute("href")
                    
                    # Store the extracted data in a dictionary and add it to the list
                    fund_dict = {
                        'name': name,
                        'ticker': ticker,
                        'currency': currency,
                        'hedging': hedging,
                        'distribution': distribution,
                        'link': link
                    }
                    self.fund_data.append(fund_dict)

                except Exception as e:
                    print(f"Error occurred while processing a row: {e}")

            driver.quit()
            self.fund_data = pd.DataFrame(self.fund_data)

        except TimeoutException:
            print("Timeout occurred while waiting for the table rows to load.")
            driver.quit()