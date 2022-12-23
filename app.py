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
guidelines_url = os.environ.get("DD_GUIDELINES_URL")
storage_url = "/rest/api/content/2540733781?expand=body.storage,version"
post_url = "rest/api/content/2540733781"
non_conformant_titles = []
page_assignment_dict = {}

test_dict= {'cahillsf9@gmail.com': [['Premier SLAs in Zendesk', 'https://datadoghq.atlassian.net/wiki/spaces/PS/pages/2434698478/Premier+SLAs+in+Zendesk'], ['Slack Outage Procedure', 'https://datadoghq.atlassian.net/wiki/spaces/PS/pages/2397831426/Slack+Outage+Procedure'], ['Mgmt Resources', 'https://datadoghq.atlassian.net/wiki/spaces/PS/pages/2340421946/Mgmt+Resources'], ['Customer Relations', 'https://datadoghq.atlassian.net/wiki/spaces/PS/pages/2339637159/Customer+Relations'], ['Internal Procedures', 'https://datadoghq.atlassian.net/wiki/spaces/PS/pages/2339571631/Internal+Procedures']]}


def get_acceptable_quarters(date):
  ret_arr = []
  cur_q = (date.month-1)//3
  cur_yr = date.year % 2000
  for i in range (1,6):
    q = (cur_q + i) % 4
    yr_offset = (cur_q + i - 1) // 4
    if q == 0:
      q = 4
    ret_arr.append(str(cur_yr+yr_offset) + "q" + str(q))
  return ret_arr

def parse_owner_from_labels(labels):
  owner_re = re.compile('owner-[a-zA-Z]*-')
  for label in labels:
    if owner_re.match(label['label']):
      owner = label['label']
      owner = owner.replace("owner-", "")
      if owner in slack_funcs.handle_overrides:
        return slack_funcs.handle_overrides_test[owner]
      owner =  owner.replace("-", ".")
      owner += "@gmail.com"
      return owner
  return ""



def add_to_dict(page):
  url = BASE_URL[:-1] + page['_links']['webui']
  title = page['title']
  owner = parse_owner_from_labels(page['metadata']['labels']['results'])
  if owner == "":
    owner = page['history']['createdBy']['email']
  if owner in page_assignment_dict:
    page_assignment_dict[owner].append([title, url])
    return
  page_assignment_dict[owner] = [[title, url]]

def build_search_url_path(acceptable_quarters):
  tag_filter = "%22review-exempt%22,"
  for q in acceptable_quarters:
    tag_filter += "%22review-" + q + "%22,"
  
  search_url= "/rest/api/content/search?cql=label?NOT?IN(" + tag_filter[:-1] + ")?AND?type=%22page%22?AND?space=PS&expand=history,metadata.labels"
  return search_url

def get_nonconformant_pages(arr, url):
  pages = requests.get(BASE_URL + url, auth=(DD_EMAIL, API_KEY))
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
  return

def build_list(soup, titles_arr, ul):
  ul.clear()
  for title in titles_arr:
    # print("adding " + title)
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

def update_macros(soup, acceptable_qs):
  curq_target = "Here are the articles that are due for review in the current quarter.*"
  nextq_target = "Here are the articles that are due for review in the next quarter.*"
  curq_dict = {"target": curq_target, "quarter": acceptable_qs[1]}
  nextq_dict = {"target": nextq_target, "quarter": acceptable_qs[2]}
  updates_list = [curq_dict, nextq_dict]
  for update in updates_list:
    update_element(update["target"], update["quarter"], soup)

def update_element(target_str, quarter, soup):
  target = re.compile(target_str)
  p = soup.find(string=target).parent
  cur_q_list = p.next_sibling.find("ac:parameter")
  updated_filter = 'label = "review-' + quarter + '" and space = "PS"'
  cur_q_list.string.replace_with(updated_filter)
  code = p.find("code")
  code.string.replace_with(quarter)

def build_page_payload(titles_arr, acceptable_qs):
  soup = get_page(BASE_URL + storage_url)
  target = "Pages that are past due for review or don’t adhere to the tagging guidelines:"
  p = soup.find(string=target).parent
  ul = p.next_sibling
  build_list(soup, titles_arr, ul)
  update_macros(soup, acceptable_qs)
  target = "Table pages that are past due for review or don’t adhere to the tagging guidelines:"
  t = soup.find(string=target).parent
  table = t.next_sibling
  clear_rows(table)
  update_rows(soup, table, page_assignment_dict)
  return str(soup)

def clear_rows(table):
  trs = table.find_all('tr')
  for row in trs[1:]:
    row.decompose()

def update_rows(soup, table, pg_assign_dict):
  for k, v in pg_assign_dict.items():
    row = new_row(soup, k, v)
    table.append(row)

def new_row(soup, assignee, pages):
  row = soup.new_tag("tr")
  assignee_td = soup.new_tag("td")
  assignee_p = soup.new_tag("p")
  assignee_p.string = assignee
  assignee_td.append(assignee_p)
  row.append(assignee_td)
  pages_td = soup.new_tag("td")
  pages_ul = soup.new_tag("ul")
  for page in pages:
    page_li = soup.new_tag("li")
    page_p = soup.new_tag("p")
    ac_link = soup.new_tag("ac:link")
    ac_link['ac:card-appearance']="inline"
    page_p.append(ac_link)
    ri_page = soup.new_tag("ri:page")
    ri_page['ri:content-title'] = page[0]
    ac_link.append(ri_page)
    ac_link_tag = soup.new_tag("ac:link-body")
    ac_link_tag.string = page[0]
    ac_link.append(ac_link_tag)
    page_li.append(page_p)
    pages_ul.append(page_li)
  pages_td.append(pages_ul)
  row.append(pages_td)
  return row
  

def get_page(url):
  pg_content = requests.get(url, auth=(DD_EMAIL, API_KEY))
  html = pg_content.json()['body']['storage']['value']
  soup = BeautifulSoup(html, 'html.parser')
  return soup

def update_page_obj(page, payload):
  page['body']['storage']['value']=payload
  update_version(page)
  return page

def update_version(page):
  new_version = page['version']['number'] + 1
  page['version']['number'] = new_version
  return page

def put_conf_page(page, url):
  headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
  }
  payload = json.dumps(page)
  response = requests.request(
    "PUT",
    url,
    data=payload.encode(encoding = 'UTF-8', errors = 'strict'),
    auth=(DD_EMAIL, API_KEY),
    headers=headers
  )
  if response.status_code != 200:
    print("unexpected response code when posting updated page to confluence API.  response code: %d, reason: %s" % (response.status_code, response.reason))

acceptable_quarters = get_acceptable_quarters(datetime.datetime.now())
print("acceptable quarters here:" + str (acceptable_quarters))
search_url = build_search_url_path(acceptable_quarters)
get_nonconformant_pages(non_conformant_titles, search_url)

payload = build_page_payload(non_conformant_titles, acceptable_quarters)
page = requests.get(BASE_URL + storage_url, auth=(DD_EMAIL, API_KEY)).json()
new_page = update_page_obj(page, payload)
put_conf_page(new_page, BASE_URL + post_url)
# slack_funcs.process_notifications(test_dict)

