import os
import requests
import re
import asyncio
import telegram
from urllib.parse import urlparse, parse_qs, urlunparse
import random

tele_token = os.environ['telegram_token']


def get_random_headers(site=None):
  user_agent_list = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:77.0) Gecko/20100101 Firefox/77.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:108.0) Gecko/20100101 Firefox/108.0'
  ]

  headers = {
    'User-Agent': random.choice(user_agent_list),
    'Accept-Language': 'en-US',
    'pin': '400020',
    'X-Requested-With': 'XMLHttpRequest',
    'X-KL-kfa-Ajax-Request': 'Ajax_Request',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'TE': 'trailers'
  }

  # ua = UserAgent()
  # headers = {'User-Agent': ua.random}
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
        return None

  try:
    response = requests.get(url,
                            headers=get_random_headers(),
                            allow_redirects=True)

    if response.history:
      # Use the final URL after following redirects
      final_url = response.url
    else:
      final_url = url

    parsed_url = urlparse(final_url)
    cleaned_url = urlunparse(
      (parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))

    if 'amazon' in cleaned_url:
      cleaned_url = re.sub(r'/ref=.*', '', cleaned_url)
    elif 'flipkart' in cleaned_url:
      query_params = parse_qs(parsed_url.query)
      pid_param = query_params.get('pid')
      if pid_param:
        pid_string = f'?pid={pid_param[0]}'
        cleaned_url += pid_string

    return cleaned_url

  except requests.RequestException:
    return None


# import this list whenever neccessary for convieniect ex.telegram.py> 455
supported_sites = [
  'Amazon', 'Flipkart', 'Snapdeal', 'Ajio', 'Nykaa', '1mg', 'Bewakoof',
  'Netmeds', 'MD-Computers', 'EZPZSolutions', 'TPStech', 'PC-Studio',
  'Primeabgb', 'Vedant-computers'
]


def getSite(url):
  site_regex = r'(amazon|flipkart|snapdeal|ajio|nykaa|1mg|bewakoof|netmeds|mdcomputers|ezpzsolutions|tpstech|pcstudio|primeabgb|vedantcomputers|elitehubs)'
  tld_regex = r'\.(com|co\.uk|in)'

  site_match = re.search(site_regex, url)
  tld_match = re.search(tld_regex, url)

  if site_match and tld_match:
    site = site_match.group(0)
    tld = tld_match.group(0)[1:]  # Remove the leading dot

    return [site, tld]

  return None  # Site not found


# Function to handle message in other files
async def send_message(chat_id, text):
  bot = telegram.Bot(token=tele_token)
  await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")


def sendTele(chat_id, msg):
  asyncio.run(send_message(chat_id, msg))
