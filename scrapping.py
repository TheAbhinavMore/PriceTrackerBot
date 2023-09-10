import aiohttp
from parsel import Selector
from utilities import getSite, get_random_headers
import requests


async def async_amazon_scrapper(url, response_text):
  selector = Selector(response_text)

  title = selector.css("span#productTitle::text").get()
  price = selector.css("span.a-price-whole::text").get()
  e = selector.css("span.a-size-medium.a-color-price::text").get()

  # handle out of stock
  if price is None or (e and e.strip() == 'Currently unavailable.'):
    price = '999999'  # giving str value for further int conversion

  if title and price:
    title = title.strip()
    price = float(price.strip().replace("₹", "").replace(",", ""))

  # small check for top-level-domain chech
  tld = getSite(url)[1]
  product = {
      'title': title,
      'price': price,
      'currency': 'INR' if tld == 'in' else 'USD',
      'site': 'amazon',
      'url': url
  }

  return product


async def async_flipkart_scrapper(url, response_text):
  selector = Selector(response_text)

  title = selector.css("span.B_NuCI::text").get()
  price = selector.css("div._25b18c > div:first-child::text").get()
  off_price = selector.css("div._2Tpdn3._1vevjr::text").get()

  # out of stock message
  if off_price:
    price = off_price
  else:
    msg = selector.css("div._16FRp0::text").get()
    if (price is None) or msg:
      price = '999999'  # indicated prod is out of stock

  if title and price:
    title = title.strip()
    price = float(price.strip().replace("₹", "").replace(",", ""))

  product = {
      'title': title,
      'price': price,
      'currency': 'INR',
      'site': 'flipkart',
      'url': url
  }

  return product


async def async_snapdeal_scrapper(url, response_text):
  selector = Selector(response_text)

  title = selector.css("h1.pdp-e-i-head::text").get()
  price = selector.css("span.payBlkBig::text").get()
  out_of_stock = selector.css('div.sold-out-err::text').get()

  if title:
    title = title.strip()
    if (not out_of_stock) and price:
      price = 999999.0
    else:
      price = float(price.strip().replace("₹", "").replace(",", ""))

  product = {
      'title': title,
      'price': price,
      'currency': 'INR',
      'site': 'snapdeal',
      'url': url
  }

  return product


async def async_netmeds_scrapper(url, response_text):
  selector = Selector(response_text)

  title = selector.css("h1.black-txt::text").get()
  price = selector.css("span.final-price::text").get()

  if title and price:
    title = title.strip()
    price = float(price.strip().replace("₹", "").replace(",", ""))

  product = {
      'title': title,
      'price': price,
      'currency': 'INR',
      'site': 'netmeds',
      'url': url
  }

  return product


async def async_nykaa_scrapper(url, response_text):
  selector = Selector(response_text)

  title = selector.css('h1[class="css-1gc4x7i"]::text').get()
  price = selector.css('span[class="css-1jczs19"]::text').get()

  if title and price:
    title = title.strip()
    price = float(price.strip().replace("₹", "").replace(",", ""))

  product = {
      'title': title,
      'price': price,
      'currency': 'INR',
      'site': 'nykaa',
      'url': url
  }

  return product


async def async_bewakoof_scrapper(url, response_text):
  selector = Selector(response_text)

  title = selector.css('h1[id="testProName"]::text').get()
  price = selector.css('span[class="sellingPrice mr-1"]::text').get()

  if title and price:
    title = title.strip()
    price = float(price.strip().replace("₹", "").replace(",", ""))

  product = {
      'title': title,
      'price': price,
      'currency': 'INR',
      'site': 'bewakoof',
      'url': url
  }

  return product


async def async_onemg_scrapper(url, response_text):
  # Parse the title
  title_start = response_text.find('"entity_name":') + 15
  title_end = response_text.find(',', title_start) - 1
  title = response_text[title_start:title_end]

  # Parse the price
  price_start = response_text.find('"price"') + 8
  price_end = response_text.find(',', price_start)
  price = response_text[price_start:price_end]

  if title and price:
    title = title.strip()
    price = float(price.strip().replace("₹", "").replace(",", ""))

  product = {
      'title': title,
      'price': price,
      'currency': 'INR',
      'site': '1mg',
      'url': url
  }

  return product


async def async_ajio_scrapper(url, response_text):

  # Parse the title
  title_start = response_text.find('"name":  ') + 10
  title_end = response_text.find(',', title_start) - 1
  title = response_text[title_start:title_end]

  # Parse the price
  price_start = response_text.find('"price": ') + 10
  price_end = response_text.find(',', price_start) - 1
  price = response_text[price_start + 1:price_end]

  if title and price:
    title = title.strip()
    price = float(price.strip().replace("₹", "").replace(",", ""))

  product = {
      'title': title,
      'price': price,
      'currency': 'INR',
      'site': 'ajio',
      'url': url
  }

  return product


async def async_mdcomputers_scrapper(url, response_text):
  selector = Selector(response_text)

  title = selector.css('span[class="product_name"]::text').get()
  off_price = selector.css('span[id="price-special"]::text').get()
  price = selector.css('#price-old::text').get()
  if title:
    title = title.strip()
    if off_price:
      price = float(off_price.strip().replace("₹", "").replace(",", ""))
    elif price:
      price = float(price.strip().replace("₹", "").replace(",", ""))
    else:
      price = 999999.0

  product = {
      'title': title,
      'price': price,
      'currency': 'INR',
      'site': 'mdcomputers',
      'url': url
  }

  return product


async def async_ezpzsolutions_scrapper(url, response_text):
  selector = Selector(response_text)

  title = selector.css('h1.product_title.entry-title::text').get().strip()
  price = selector.css(
      'p.price > span:nth-child(1) > bdi:nth-child(1)::text').get()
  off_price = selector.css(
      'p.price > ins:nth-child(2) > span:nth-child(1) > bdi:nth-child(1)::text'
  ).get()
  out_of_stock = selector.css('p.stock.out-of-stock::text').get()

  if off_price:
    price = float(off_price.strip().replace("₹", "").replace(",", ""))
  elif out_of_stock is None and price:
    price = float(price.strip().replace("₹", "").replace(",", ""))
  else:
    price = 999999.0

  product = {
      'title': title,
      'price': price,
      'currency': 'INR',
      'site': 'ezpzsolutions',
      'url': url
  }

  return product


async def async_tpstech_scrapper(url, response_text):
  selector = Selector(requests.get(url).text)

  title = selector.css(
      'h1[class="product-meta__title heading h1"]::text').get()
  price = selector.css('span#product-price-e::text').get()

  if title and price:
    title = title.strip()
    price = float(price[4:].strip().replace("₹", "").replace(",", ""))

  product = {
      'title': title,
      'price': price,
      'currency': 'INR',
      'site': 'tpstech',
      'url': url
  }

  return product


async def async_pcstudio_scrapper(url, response_text):
  selector = Selector(response_text)

  title = selector.css('h1.product_title.entry-title::text').get()
  price = selector.css(
      'p.price > span:nth-child(1) > bdi:nth-child(1)::text').get()
  off_price = selector.css(
      'p.price > ins:nth-child(2) > span:nth-child(1) > bdi:nth-child(1)::text'
  ).get()
  out_of_stock = selector.css(
      'div.stock-availability.out-of-stock::text').get()

  if title:
    title = title.strip()
    if off_price:
      price = float(off_price.strip().replace("₹", "").replace(",", ""))
    elif price and not out_of_stock:
      price = float(price.strip().replace("₹", "").replace(",", ""))
    else:
      price = 999999.0

  product = {
      'title': title,
      'price': price,
      'currency': 'INR',
      'site': 'pcstudio',
      'url': url
  }

  return product


async def async_primeabgb_scrapper(url, response_text):
  selector = Selector(response_text)

  title = selector.css('h1.product_title.entry-title::text').get()
  off_price = selector.css(
      'p.price > ins:nth-child(2) > span:nth-child(1) > bdi:nth-child(1)::text'
  ).get()
  price = selector.css(
      'p.price > span:nth-child(1) > bdi:nth-child(1)::text').get()
  out_of_stock = selector.css(
      'div.stock-availability.out-of-stock::text').get()

  # bit diff specific syntax due to structure
  if title:
    title = title.strip()
    if out_of_stock:
      price = 999999.0
    elif off_price:
      price = float(off_price.strip().replace("₹", "").replace(",", ""))
    elif price:
      price = float(price.strip().replace("₹", "").replace(",", ""))
    else:
      price = 999999.0

  product = {
      'title': title,
      'price': price,
      'currency': 'INR',
      'site': 'primeabgb',
      'url': url
  }

  return product


async def async_vedantcomputers_scrapper(url, response_text):
  selector = Selector(response_text)

  title = selector.css('div.title.page-title::text').get()
  price = selector.css('div.product-price-new::text').get()
  out_of_stock = selector.css(
      'div.stock-availability.out-of-stock::text').get()

  if title:
    title = title.strip()
    if not out_of_stock and price:
      price = float(price.strip().replace("₹", "").replace(",", ""))
    else:
      price = 999999.0

  product = {
      'title': title,
      'price': price,
      'currency': 'INR',
      'site': 'vedantcomputers',
      'url': url
  }

  return product


async def async_elitehubs_scrapper(url, response_text):
  selector = Selector(response_text)

  title = selector.css('h1.productView-title span::text').get()
  price_container = selector.css('div.price.price--medium')
  price = price_container.css('span.price-item.price-item--sale::text').get()
  out_of_stock = selector.css(
      'div.stock-availability.out-of-stock::text').get()

  if title and price:
    title = title.strip()
    if out_of_stock:
      price = 999999.0
    else:
      price = float(price[4:].strip().replace("₹", "").replace(",", ""))

  product = {
      'title': title,
      'price': price,
      'currency': 'INR',
      'site': 'elitehubs',
      'url': url
  }

  return product


async def fetch_page(url):
  async with aiohttp.ClientSession() as session:
    async with session.get(url, headers=get_random_headers()) as response:
      return await response.text()


async def master_scrapper(clean_url):
  scraper_mapping = {
      'amazon': async_amazon_scrapper,
      'flipkart': async_flipkart_scrapper,
      'snapdeal': async_snapdeal_scrapper,
      'netmeds': async_netmeds_scrapper,
      'nykaa': async_nykaa_scrapper,
      'bewakoof': async_bewakoof_scrapper,
      '1mg': async_onemg_scrapper,
      'ajio': async_ajio_scrapper,
      'mdcomputers': async_mdcomputers_scrapper,
      'ezpzsolutions': async_ezpzsolutions_scrapper,
      'tpstech': async_tpstech_scrapper,
      'pcstudio': async_pcstudio_scrapper,
      'primeabgb': async_primeabgb_scrapper,
      'vedantcomputers': async_vedantcomputers_scrapper,
      'elitehubs': async_elitehubs_scrapper,
  }

  site = getSite(clean_url)
  if site is None:
    return
  site = getSite(clean_url)[0]

  try:
    scraper_function = scraper_mapping.get(site, None)
    if scraper_function == None:
      return
    # Send an asynchronous GET request to the URL with the headers
    try:
      # sites where aiohtml wont work properly
      # if site in ['tpstech','elitehubs']:
      #     html_content = "handle in respective scraper..."
      html_content = await fetch_page(clean_url)
    except:
      print('Connection error while fetching url.')
      return
    # Call the corresponding async scraper function with the Selector object
    product_data = await scraper_function(clean_url, html_content)

    return product_data

  except KeyError:
    print('No scraper is available for this site!')
    return
