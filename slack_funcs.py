import os
import sys
# Enable debug logging
import logging
import urllib.parse
logging.basicConfig(level=logging.DEBUG)
from slack_sdk import WebClient


client = WebClient(token=os.environ['PERSONAL_SLACK_CHAT_TOKEN'])

def build_markdown(channel, pages):
  # blocks = '[{"type": "section", "text": {"type": "mrkdwn", "text": "%s"}}]' % (shepherd)
  full_links = ''
  intro = "Hi <@%s> :wave:, \n You are receiving this message because the confluence pages you've created in the Premier Support space do not conform to the <https://datadoghq.atlassian.net/wiki/spaces/PS/pages/2540733781/Confluence+Space+Guidelines|Confluence space labeling guidelines>.  Specifically, they do not contain <https://datadoghq.atlassian.net/wiki/spaces/PS/pages/2540733781/Confluence+Space+Guidelines#Required-Labels|required review cycle tags>.\n\n Please review the linked KBs and apply the required labels to the following pages:\n\n" % (channel)
  for page in pages:
    # link = '[' + str(page[0]) + '](' + str(page[1]) + ')'
    link = "<%s|%s>\n" % (str(page[1]), str(page[0]))
    full_links += link
  blocks = '[{"type": "section", "text": {"type": "mrkdwn", "text": "%s %s"}}]' % (intro, full_links)
  return blocks

def build_message(email, pages_list):
  message_dict = {}
  channel = get_id_from_email(email)
  message_dict['channel'] = channel
  message_dict['blocks'] = build_markdown(channel, pages_list)
  print("message dict is " + str(message_dict))
  return message_dict


def get_id_from_email(email):
  resp = client.users_lookupByEmail(email=email)
  print(resp)
  return resp['user']['id']

def post_message(channel, message):
  resp = client.chat_postMessage(channel=channel, text=message)
  print(resp)

def process_notifications(dict):
  for key in dict:
    msg = build_message(key, dict[key])
    resp = client.chat_postMessage(channel=msg['channel'], blocks=msg['blocks'])
    print(resp)
