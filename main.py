import re
import requests
from urllib.parse import urlparse, urlunparse, parse_qs
from fake_useragent import UserAgent  # You'll need to install this package

def get_random_headers():
    # You can implement your logic to generate random headers here
    # For example, using the UserAgent library to get a random user-agent
    ua = UserAgent()
    headers = {'User-Agent': ua.random}
    return headers

def cleanLink(text):
    # Check for https:// link
    https_match = re.search(r'https?://[^\s]+', text)
    if https_match:
        url = https_match.group(0)
    else:
        # Check for http:// link
        http_match = re.search(r'http://[^\s]+', text)
        if http_match:
            url = http_match.group(0)
        else:
            # Check for www link
            www_match = re.search(r'www\.[^\s]+', text)
            if www_match:
                url = www_match.group(0)
                url = f'https://{url}'  # Add 'https://' if it starts with 'www'
            else:
                print("No valid URL found in the text.")
                return None

    print(f"Original URL: {url}")

    try:
        response = requests.get(url, headers=get_random_headers(), allow_redirects=True)

        print(f"Response Status Code: {response.status_code}")

        if response.history:
            # Use the final URL after following redirects
            final_url = response.url
        else:
            final_url = url

        print(f"Final URL: {final_url}")

        parsed_url = urlparse(final_url)
        cleaned_url = urlunparse(
            (parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))

        print(f"Cleaned URL: {cleaned_url}")

        if 'amazon' in cleaned_url:
            cleaned_url = re.sub(r'/ref=.*', '', cleaned_url)
        elif 'flipkart' in cleaned_url:
            query_params = parse_qs(parsed_url.query)
            pid_param = query_params.get('pid')
            if pid_param:
                pid_string = f'?pid={pid_param[0]}'
                cleaned_url += pid_string

        print(f"Processed URL: {cleaned_url}")

        return cleaned_url

    except requests.RequestException:
        print("RequestException occurred.")
        return None


text='''Plus Back Cover for Realme X2 Pro (TPU_Black) https://amzn.eu/d/dHa4YyF'''

url=cleanLink(text)
from asyncio import run 

from scrapping import master_scrapper
print(run(master_scrapper(url)))