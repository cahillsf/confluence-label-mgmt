* activate the virtual environment using command: `source .venv/bin/activate`
* install dependencies, run `pip install -r requirements.txt`
* run `python3 app.py` to start the script

### Next Steps
* retrieve the creator emails of all nonconformant pages
* build a dictionary that maps each creator email to all of their nonconformant pages (+ hyperlink and whatever else would be relevant to update them)
* use a slack bot to:
  * retrieve the user ID associated with each email - https://stackoverflow.com/questions/29392407/how-to-get-a-slack-user-by-email-using-users-info-api and https://api.slack.com/methods/users.lookupByEmail
  * send a message with the details of action that needs to be taken for their pages - https://datadoghq.atlassian.net/wiki/spaces/ITENG/pages/1601898868/Creating+a+Slack+App+Integration+into+DD+Slack