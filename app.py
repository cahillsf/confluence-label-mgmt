import random
import time
import datetime
import os
import urllib
import re
import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from urllib.parse import parse_qs
import slack_funcs

API_KEY = os.environ.get("ATLASSIAN_API_KEY")
DD_EMAIL = os.environ.get("DD_EMAIL")
BASE_URL = os.environ.get("DD_BASE_URL")
acceptable_quarters = ["22q4","23q1", "23q2", "23q3", "23q4"]
guidelines_url = os.environ.get("DD_GUIDELINES_URL")
storage_url = "/rest/api/content/2540733781?expand=body.storage,version"
post_url = "rest/api/content/2540733781"
non_conformant_titles = []
page_assignment_dict = {}

test_dict= {'cahillsf9@gmail.com': [['Premier SLAs in Zendesk', 'https://datadoghq.atlassian.net/wiki/spaces/PS/pages/2434698478/Premier+SLAs+in+Zendesk'], ['Slack Outage Procedure', 'https://datadoghq.atlassian.net/wiki/spaces/PS/pages/2397831426/Slack+Outage+Procedure'], ['Mgmt Resources', 'https://datadoghq.atlassian.net/wiki/spaces/PS/pages/2340421946/Mgmt+Resources'], ['Customer Relations', 'https://datadoghq.atlassian.net/wiki/spaces/PS/pages/2339637159/Customer+Relations'], ['Internal Procedures', 'https://datadoghq.atlassian.net/wiki/spaces/PS/pages/2339571631/Internal+Procedures']]}

def parse_owner_from_labels(labels):
  owner_re = re.compile('owner-[a-zA-Z]*-')
  for label in labels:
    if owner_re.match(label['label']):
      # print("owner label here: " + label['label'])
      owner = label['label']
      owner = owner.replace("owner-", "")
      if owner in slack_funcs.handle_overrides:
        # print("overriding")
        return slack_funcs.handle_overrides_test[owner]
      owner =  owner.replace("-", ".")
      owner += "@gmail.com"
      return owner
  return ""



def add_to_dict(page):
  # print("page here: " + str(json.dumps(page)))
  url = BASE_URL[:-1] + page['_links']['webui']
  title = page['title']
  owner = parse_owner_from_labels(page['metadata']['labels']['results'])
  if owner == "":
    owner = page['history']['createdBy']['email']
  print("final owner is " + owner)
  if owner in page_assignment_dict:
    page_assignment_dict[owner].append([title, url])
    return
  page_assignment_dict[owner] = [[title, url]]

def build_search_url_path(acceptable_quarters):
  tag_filter = "%22review-exempt%22,"
  # tag_filter = ""
  for q in acceptable_quarters:
    tag_filter += "%22review-" + q + "%22,"
  
  search_url= "/rest/api/content/search?cql=label?NOT?IN(" + tag_filter[:-1] + ")?AND?type=%22page%22?AND?space=PS&expand=history,metadata.labels"
  print("search url is " + search_url)
  return search_url

def get_nonconformant_pages(arr, url):
  pages = requests.get(BASE_URL + url, auth=(DD_EMAIL, API_KEY))
  # print("pages info here")
  # print(json.dumps(pages.json()))
  for page in pages.json()['results']:
    add_to_dict(page)
    arr.append(page['title'])

  try: 
    ret_url = BASE_URL + pages.json()['_links']['next']
    parsed_url = urlparse(ret_url)
    captured_value = parse_qs(parsed_url.query)['cursor'][0]
    start = pages.json()['start'] + pages.json()['size']
    new_url = url + "&cursor=" + captured_value + "&start=" + str(start)
    # result set is limit to 25 pages
    # recursively calls itself until there is no 'next' attribute in response
    # indicating we have collected all of the revelant page titles
    get_nonconformant_pages(arr, new_url)
  except:
    print("No more pages")
    # print("dict of owners")
    # print(page_assignment_dict)
  return

def build_list(soup, titles_arr, ul):
  ul.clear()
  for title in titles_arr:
    print("adding " + title)
    new_item = soup.new_tag("li")
    new_item.append(soup.new_tag("p"))
    p_tag = new_item.p
    ac_link = soup.new_tag("ac:link")
    ac_link['ac:card-appearance']="inline"
    p_tag.append(ac_link)
    ri_page = soup.new_tag("ri:page")
    ri_page['ri:content-title'] = title
    ac_tag = new_item.find_all('ac:link')[0]
    ac_tag.append(ri_page)
    ac_link_tag = soup.new_tag("ac:link-body")
    ac_link_tag.string = title
    ac_tag.append(ac_link_tag)
    ul.append(new_item)
  return ul

def build_page_payload(titles_arr):
  pg_content = requests.get(BASE_URL + storage_url, auth=(DD_EMAIL, API_KEY))
  html = pg_content.json()['body']['storage']['value']
  soup = BeautifulSoup(html, 'html.parser')
  p_soup = soup.find_all('p')
  target = "Pages that are past due for review or don’t adhere to the tagging guidelines:"
  for p in p_soup:
    if (p.string == target):
      ul = p.next_sibling
  build_list(soup, titles_arr, ul)
  return str(soup)

def update_page_obj(page, payload):
  page['body']['storage']['value']=payload
  update_version(page)
  return page

def update_version(page):
  new_version = page['version']['number'] + 1
  page['version']['number'] = new_version
  return page

def put_conf_page(page):
  headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
  }
  payload = json.dumps(new_page)
  # print("unencoded payload")
  # print(payload)
  # print("encoded payload")
  # print(payload.encode(encoding = 'UTF-8', errors = 'strict'))
  response = requests.request(
    "PUT",
    BASE_URL + post_url,
    data=payload.encode(encoding = 'UTF-8', errors = 'strict'),
    auth=(DD_EMAIL, API_KEY),
    headers=headers
  )
  # print(response.text)

search_url = build_search_url_path(acceptable_quarters)
get_nonconformant_pages(non_conformant_titles, search_url)

payload = build_page_payload(non_conformant_titles)
page = requests.get(BASE_URL + storage_url, auth=(DD_EMAIL, API_KEY)).json()
new_page = update_page_obj(page, payload)
# print("new page is ")
# print(new_page)
put_conf_page(new_page)
# slack_funcs.process_notifications(test_dict)
