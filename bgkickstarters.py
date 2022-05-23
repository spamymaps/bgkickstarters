import xml.etree.ElementTree as ET
import time
import requests
import os
from requests.exceptions import HTTPError
import re
import json
import sys
from datetime import datetime, timezone, timedelta, date
import pyairtable
import dictdiffer
from urllib.parse import urlencode, quote
from bs4 import BeautifulSoup

test_mode = False

config_path = os.path.join(sys.path[0])
config_file_path = ''
if os.path.isfile(os.path.join(config_path, "localconfig.json")):
    config_file_path = os.path.join(config_path, "localconfig.json")
    config = json.loads(open(os.path.join(config_path, "localconfig.json"), 'r').read())
else:
    config = json.loads(open(os.path.join(config_path, "config.json"), 'r').read())
    config_file_path = os.path.join(config_path, "config.json")

outputFile = 'out.txt'
print(config)
merge_fields = ['Min Pledge (USD)', 'Metadata', 'Players', 'BGG Link',
                'ExcludeFromRollup']  # ,'Days To Go','Funding Chance','Last Modified','Funding Percent','Campaign Length']
currency_lookup = {"USD": "${:,d}",
                   "MXN": "MX${:,d}",
                   "EUR": "\u20AC{:,d}",
                   "GBP": "\u00A3{:,d}",
                   "CAD": "C${:,d}",
                   "SEK": "kr{:,d} SEK",
                   "PLN": "{:,d} zl",
                   "CHF": "CHF{:,d}",
                   "SGD": "S${:,d}",
                   "JPY": "\u00A5{:,d}",
                   "NZD": "NZ${:,d}",
                   "HKD": "HK${:,d}",
                   "AUD": "A${:,d}",
                   "DKK": "kr{:,d} DKK",
                   "INR": "\u20B9{:,d}",
                   "NOK": "kr{:,d} NOK",
                   }


# unused now
# tags = ["Expansion",
#         "New Edition",
#         "Reprint",
#         "Take 2",
#         "Take 3",
#         "Take 4",
#         "Take 5",
#         "Take 6",
#         "Take 7",
#         "app",
#         "hmm",
#         "lolwut",
#         "nsfw",
#         "rpg",
#         "bling",
#         "minis"]


def get_yes_no_answer(prompt):
    while True:
        try:
            value = input(prompt + 'enter y or n')
        except ValueError:
            print("Sorry, I didn't understand that.")
            continue
        if value.lower() == 'y' or value.lower() == 'n':
            break
        else:
            print("Sorry, your response must be y or n.")
            continue
    return value


def get_min_pledge_amount(prompt):
    waiting_for_entry = True
    while waiting_for_entry:
        try:
            value = int(input(prompt + ' enter amount in $ or NA '))
            waiting_for_entry = False
        except ValueError:
            print("Sorry, I didn't understand that.")
    return value


def price_string(currency, amount):
    try:
        return currency_lookup[currency].format(amount)
    except KeyError:
        return f"Currency {currency} Not Recognized"


def process_kicktraq_data(this_api_key, this_kicktraq_url):
    global config
    this_new_project_data = []
    # get kicktraq data from custom endpoint
    kickstarter_types = []
    if test_mode:
        mydata = json.loads(open(os.path.join(config_path, config['currentKSjson']), 'r').read())
    else:
        req_response = ''
        query = {'key': this_api_key}
        try:
            req_response = requests.get(this_kicktraq_url, params=query)
            # If the response was successful, no Exception will be raised
            req_response.raise_for_status()
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')  # Python 3.6
        except Exception as err:
            print(f'Other error occurred: {err}')  # Python 3.6
        else:
            print('Success!')
        mydata = req_response.json()
        t = time.strftime('%y%m%d%H%M%S')
        json.dump(req_response.json(), open(os.path.join(config_path, 'ksdata_%s.json' % (t)), 'w'), indent=4)

        config['currentKSjson'] = 'ksdata_%s.json' % (t)

        json.dump(config, open(config_file_path, 'w'), indent=4)
    # only want tabletop games now - other types were too messy
    # if 'Games' in mydata['data']:
    #    kstypes.append('Games')
    if 'Tabletop Games' in mydata['data']:
        kickstarter_types.append('Tabletop Games')
    # if 'Playing Cards' in mydata['data']:
    #    kstypes.append('Playing Cards')
    print(len(kickstarter_types))
    for kickstarter_type in kickstarter_types:
        projects = mydata['data'][kickstarter_type]
        for kicktraq_id, p in projects.items():
            name = p['name']
            raised = int(p['raised'])
            goal = int(p['goal'])
            canceled = False
            if re.search('\(canceled\)', name, flags=re.IGNORECASE):
                canceled = True
                name = re.sub('\(canceled\)', '', name, flags=re.IGNORECASE).strip()
            name = name.replace('|', '-')
            project_start_time = datetime.strptime(p['start'], '%a, %d %b %Y %H:%M:%S %z')
            project_end_time = datetime.strptime(p['end'], '%a, %d %b %Y %H:%M:%S %z')
            project_days_to_go = max(0, (project_end_time - datetime.utcnow().replace(
                tzinfo=timezone.utc)).total_seconds() / 60 / 60 / 24)
            exclude_from_rollup = False
            if project_days_to_go == 0 or canceled:
                exclude_from_rollup = True
            funded = False
            if raised > goal:
                funded = True
            this_project_data = {'Name': name,
                                 'KTID': kicktraq_id,
                                 'Description': p['description'].replace('\r\n', ' ').replace('|', '-').replace('\n',
                                                                                                                ' '),
                                 'Campaign Link': p['url']['kickstarter'],
                                 'Kicktraq Link': p['url']['kicktraq'],
                                 'Launch Date': project_start_time.strftime('%Y-%m-%dT%H:%M:00.000Z'),
                                 'End Date': project_end_time.strftime('%Y-%m-%dT%H:%M:00.000Z'),
                                 'Avg Pledge': price_string(p['currency'], p['avg_pledge']),
                                 'Backers': int(p['backers']),
                                 'Currency': p['currency'],
                                 'Goal': goal,
                                 'Raised': raised,
                                 'KSType': kickstarter_type,
                                 }
            if exclude_from_rollup:
                this_project_data['ExcludeFromRollup'] = exclude_from_rollup
            if funded:
                this_project_data['Funded'] = funded
            if canceled:
                this_project_data['Canceled'] = canceled
            this_new_project_data.append(this_project_data)
    print(len(this_new_project_data))
    return this_new_project_data


def process_gamefound_data(gamefound_url):
    global config
    this_new_project_data = []

    if test_mode:
        mydata = json.loads(open(os.path.join(config_path, 'gfdata_220209154850.json'), 'r').read())
    else:
        req_response = ''
        try:
            req_response = requests.get(gamefound_url)
            # If the response was successful, no Exception will be raised
            req_response.raise_for_status()
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')  # Python 3.6
        except Exception as err:
            print(f'Other error occurred: {err}')  # Python 3.6
        else:
            print('Success!')
        mydata = req_response.json()
        t = time.strftime('%y%m%d%H%M%S')
        json.dump(req_response.json(), open(os.path.join(config_path, 'gfdata_%s.json' % (t)), 'w'), indent=4)
        global config
        config['currentGFjson'] = 'gfdata_%s.json' % (t)
        json.dump(config, open(config_file_path, 'w'), indent=4)

    print(len(mydata))
    projects = mydata
    for this_project in projects:
        name = this_project['projectName']
        raised = int(this_project['fundsGathered'])
        goal = int(this_project['campaignGoal'])
        canceled = False
        if re.search('\(canceled\)', name, flags=re.IGNORECASE):
            canceled = True
            name = re.sub('\(canceled\)', '', name, flags=re.IGNORECASE).strip()
        name = name.replace('|', '-')
        project_start_time = datetime.strptime(this_project['campaignStartDate'], '%Y-%m-%dT%H:%M:%SZ')
        project_end_time = datetime.strptime(this_project['campaignEndDate'], '%Y-%m-%dT%H:%M:%SZ')
        project_days_to_go = max(0, (
                project_end_time - datetime.utcnow().replace(tzinfo=None)).total_seconds() / 60 / 60 / 24)
        exclude_from_rollup = False
        if project_days_to_go == 0 or canceled:
            exclude_from_rollup = True
        funded = False
        if raised > goal:
            funded = True
        b = BeautifulSoup(requests.get(this_project['projectHomeUrl']).text, features='html.parser')
        description = b.find('meta', attrs={'property': 'og:description'}).attrs['content']
        avg_pledge = 0
        if int(this_project['backerCount']) > 0:
            avg_pledge = int(raised / int(this_project['backerCount']))
        this_project_data = {'Name': name,
                             'KTID': str(this_project['projectID']),
                             'Description': description.replace('\r\n', ' ').replace('|', '-').replace('\n', ' '),
                             'Campaign Link': this_project['projectHomeUrl'],
                             # 'Kicktraq Link': p['url']['kicktraq'],
                             'Launch Date': project_start_time.strftime('%Y-%m-%dT%H:%M:00.000Z'),
                             'End Date': project_end_time.strftime('%Y-%m-%dT%H:%M:00.000Z'),
                             'Avg Pledge': price_string(this_project['currencyShortName'], avg_pledge),
                             'Backers': int(this_project['backerCount']),
                             'Currency': this_project['currencyShortName'],
                             'Goal': goal,
                             'Raised': raised,
                             'KSType': 'GameFound',
                             }
        if exclude_from_rollup:
            this_project_data['ExcludeFromRollup'] = exclude_from_rollup
        if funded:
            this_project_data['Funded'] = funded
        if canceled:
            this_project_data['Canceled'] = canceled
        this_new_project_data.append(this_project_data)
    print(len(this_new_project_data))
    return this_new_project_data


def find_new_projects(table, this_kicktraq_ids):
    to_exclude = []
    to_include = []
    for this_project in kicktraq_data:
        if not this_project['KTID'] in this_kicktraq_ids:
            ignore_terms = ['zine', 'ttrpg', 'stl', 'trpg', '5e', 'bork', 'borg', '28mm', 'zimo', 'roleplaying',
                            'tarot',
                            'rpg', 'uspc', '3dprint', '3d print', '3d-print', 'dnd', 'd&d']
            if any(ignore_term in ' '.join([this_project['Name'].lower(), this_project['Description'].lower()]) for
                   ignore_term in ignore_terms):
                # print('i think this is a campaign to ignore')
                to_exclude.append(this_project)
            elif ((datetime.strptime(this_project['End Date'], '%Y-%m-%dT%H:%M:00.000Z') - datetime.utcnow().replace(
                    tzinfo=None)).total_seconds() / 60 / 60 / 24 < 0):
                to_exclude.append(this_project)
            else:
                to_include.append(this_project)

    while len(to_exclude):
        try:
            print(len(to_exclude), len(to_include))
            for count, this_project in enumerate(to_exclude):
                print(count, this_project['Name'], this_project['Description'], this_project['Campaign Link'])
            swap_item = input('Please enter the number of the item to include, or n to exlclude all ')
            if swap_item.lower() == 'n':
                print('found n')
                break
            if not (int(swap_item) in range(len(to_exclude))):
                print('sorry, you need to enter a number from the list')
            else:
                to_include.append(to_exclude[int(swap_item)])
                to_exclude.pop(int(swap_item))
        except ValueError:
            print('sorry, you need to enter a number from the list')

    while len(to_include):
        try:
            print(len(to_exclude), len(to_include))
            for count, this_project in enumerate(to_include):
                print(count, this_project['Name'], this_project['Description'], this_project['Campaign Link'])
            swap_item = input('Please enter the number of the item to exclude, or n to inlclude all ')
            if swap_item.lower() == 'n':
                print('found n')
                break
            if not (int(swap_item) in range(len(to_include))):
                print('sorry, you need to enter a number from the list')
            else:
                to_exclude.append(to_include[int(swap_item)])
                to_include.pop(int(swap_item))
        except ValueError:
            print('sorry, you need to enter a number from the list')
    this_added_entries = {}
    this_added_ids = {}
    for this_project in to_exclude:
        this_project['ExcludeFromRollup'] = True
        new_table_item = table.create(this_project)
        this_added_entries[new_table_item['id']] = new_table_item['fields']
        this_added_ids[new_table_item['fields']['KTID']] = new_table_item['id']
    return this_added_entries, this_added_ids


def clean_up_bgg(table):
    this_formula = 'AND({ExcludeFromRollup}=0,{Canceled}=0,{BGG Link}="")'
    intable = table.all(formula=this_formula, sort=['End Date'])
    for table_row in intable:
        boardgamegeek_search(table_row['fields']['Name'])
        print(table_row)
        print(table_row['fields']['Campaign Link'])
        this_bgg_link = input('Enter the bgg link: ')

        if this_bgg_link:
            table_row['fields']['BGG Link'] = this_bgg_link

            table.update(table_row['id'], {'BGG Link': table_row['fields']['BGG Link']})
        # print(i)


def add_to_airtable(table, this_airtable_data, kicktraq_ids):
    this_added_entries = {}
    this_added_ids = {}
    for this_project in kicktraq_data:
        if this_project['KTID'] in kicktraq_ids:
            print('already in the database', this_project)
            for this_item in merge_fields:
                if this_item in this_airtable_data[kicktraq_ids[this_project['KTID']]]:
                    this_project[this_item] = this_airtable_data[kicktraq_ids[this_project['KTID']]][this_item]

        else:
            print('need to add to database', this_project)
            ignore_terms = ['zine', 'ttrpg', 'stl', 'trpg', '5e', 'bork', 'borg', '28mm', 'zimo', 'roleplaying',
                            'tarot', 'rpg', 'uspc']
            ignore_item = False
            if any(ignore_term in ' '.join([this_project['Name'].lower(), this_project['Description'].lower()]) for
                   ignore_term in ignore_terms):
                print('i think this is a campaign to ignore')
                response = get_yes_no_answer('Do you agree this should be excluded?')
                if response == 'y':
                    ignore_item = True
            days_to_go = max(0, (datetime.strptime(this_project['End Date'],
                                                   '%Y-%m-%dT%H:%M:00.000Z') - datetime.utcnow().replace(
                tzinfo=None)).total_seconds() / 60 / 60 / 24)
            if days_to_go > 0 and not ignore_item:
                this_project['Min Pledge (USD)'] = 0
                boardgamegeek_search(this_project['Name'])
                min_amount = check_kickstarter_pledges(this_project)
                # if minamount > 0:
                this_project['Min Pledge (USD)'] = min_amount
            else:
                print('skipping checking pledge levels due to old campaign or ignored', this_project)
                this_project['ExcludeFromRollup'] = True
                new_table_item = table.create(this_project)
                this_added_entries[new_table_item['id']] = new_table_item['fields']
                this_added_ids[new_table_item['fields']['KTID']] = new_table_item['id']
                continue
            this_bgg_link = input('Enter the bgg link: ')
            if this_bgg_link:
                this_project['BGG Link'] = this_bgg_link

            # thistemptags = [item for item in input("Enter the tag items : ").split(',')]
            # thistags = []
            # for t in thistemptags:
            #    if t.strip() in tags:
            #        thistags.append(t.strip())
            # i['Metadata'] = thistags
            players = input('Enter number of players ')
            if players:
                this_project['Players'] = players

            response = get_yes_no_answer('Would you like to update the database or exclude ')
            if response == 'y':
                new_table_item = table.create(this_project)
                this_added_entries[new_table_item['id']] = new_table_item['fields']
                this_added_ids[new_table_item['fields']['KTID']] = new_table_item['id']
            elif response == 'n':
                this_project['ExcludeFromRollup'] = True
                new_table_item = table.create(this_project)
                this_added_entries[new_table_item['id']] = new_table_item['fields']
                this_added_ids[new_table_item['fields']['KTID']] = new_table_item['id']
    return this_added_entries, this_added_ids


def update_airtable(table, this_airtable_data, kicktraq_ids):
    # for j in atData:
    for this_project in kicktraq_data:
        # if i['KTID'] == atData[j]['KTID']:
        if this_project['KTID'] in kicktraq_ids:
            # if
            temp_airtable_data_item = this_airtable_data[kicktraq_ids[this_project['KTID']]]
            compare_keys = ['Backers', 'Currency', 'Goal', 'Raised', 'Avg Pledge', 'Funded', 'Name', 'KTID', 'KSType',
                            'Campaign Link', 'Kicktraq Link', 'Players', 'Canceled', 'ExcludeFromRollup',
                            'Min Pledge (USD)', 'BGG Link', 'Description', 'Launch Date', 'End Date']
            same = True
            for key in compare_keys:
                if key in this_project:
                    if key in temp_airtable_data_item:
                        if not this_project[key] == temp_airtable_data_item[key]:
                            same = False
                    else:
                        same = False
            if same:
                print('data in the database is up to date', this_project)
            else:
                print('need to update the database', this_project)
                ignored_keys = {'Avg Pledge', 'Backers', 'Funded', 'Metadata', 'Currency', 'Goal', 'Raised',
                                'Funding Percent', 'Days To Go', 'Funding Chance', 'Last Modified', 'Campaign Length',
                                'IncludeNew'}

                # 'ExcludeFromRollup'])
                auto_update_excluded = False
                if 'ExcludeFromRollup' in this_airtable_data[kicktraq_ids[this_project['KTID']]]:
                    if this_airtable_data[kicktraq_ids[this_project['KTID']]]['ExcludeFromRollup'] == 1:
                        auto_update_excluded = True
                if len(list(dictdiffer.diff(this_airtable_data[kicktraq_ids[this_project['KTID']]], this_project,
                                            ignore=ignored_keys))) and not auto_update_excluded:
                    for diff in list(
                            dictdiffer.diff(this_airtable_data[kicktraq_ids[this_project['KTID']]], this_project,
                                            ignore=ignored_keys)):
                        print(diff)
                    response = get_yes_no_answer('Would you like to update the database? ')
                    if response == 'y':
                        table.update(kicktraq_ids[this_project['KTID']], this_project)
                else:
                    print('updating kicktraq based data automatically')
                    table.update(kicktraq_ids[this_project['KTID']], this_project)


def write_project_table_row(this_project_data):
    # posts a formatted version of the passed in data to the output file
    funding_bold = ''
    checkmark = ''
    end_date = ''
    if 'End Date' in this_project_data:
        this_end_date = datetime.strptime(this_project_data['End Date'], '%Y-%m-%dT%H:%M:00.000Z')
        end_date = this_end_date.strftime('%b %d')
    if 'Funded' in this_project_data:
        if this_project_data['Funded']:
            funding_bold = '*'
            checkmark = " \u2611"
    players = ''
    backers = ''
    min_pledge = ''
    avg_pledge = ''
    if 'Players' in this_project_data:
        players = str(this_project_data['Players'])
    if 'Backers' in this_project_data:
        backers = str(this_project_data['Backers'])
    if 'Min Pledge (USD)' in this_project_data:
        min_pledge = this_project_data['Min Pledge (USD)']
    if 'Avg Pledge' in this_project_data:
        avg_pledge = this_project_data['Avg Pledge']
    min_avg = '%s / %s' % (min_pledge, avg_pledge)
    current_funding = '%s of %s' % (price_string(this_project_data['Currency'], this_project_data['Raised']),
                                    price_string(this_project_data['Currency'], this_project_data['Goal']))
    project_info = '**[%s](%s)** %s // *%sHas raised %s so far. (~%.0f%%)%s%s*' % (
        this_project_data['Name'], this_project_data['Campaign Link'], this_project_data['Description'], funding_bold,
        current_funding, 100 * this_project_data['Funding Percent'], checkmark, funding_bold)
    bgg = ''
    # tags = ''
    if 'Kicktraq Link' in this_project_data:
        kicktraq = ' [kicktraq](%s)' % (this_project_data['Kicktraq Link'])
    elif 'gamefound' in this_project_data['Campaign Link'].lower():
        kicktraq = ' [gamefound](%s)' % (this_project_data['Campaign Link'])
    else:
        kicktraq = ' [kicktraq](%s)' % (this_project_data['Campaign Link'].replace('kickstarter', 'kicktraq'))
    if 'BGG Link' in this_project_data:
        bgg = ' [bgg](%s)' % (this_project_data['BGG Link'])
    # if 'Metadata' in thisdata:
    #    for meta in thisdata['Metadata']:
    #        tags += ' #`%s`' %("".join(meta.lower().split()))
    # comments = ''.join([kicktraq,bgg,tags])
    comments = ''.join([kicktraq, bgg])
    table_row = '|'.join([project_info, players, backers, min_avg, end_date, comments])
    return table_row


def check_kickstarter_pledges(thisdata):
    kickstarter_rewards_page = thisdata['Campaign Link'].replace('?ref=kicktraq', '/rewards')
    print(kickstarter_rewards_page)
    # this works only a few times, lost my work around getting around their rate limits
    # headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36'}
    # b = BeautifulSoup(requests.get(ksrewardspage, headers=headers).text, features='html.parser')
    # pledge = 0
    # pledgestring = ''
    # for p in b.find_all('div', attrs={'class': 'pledge__info'}):
    #     title = ''
    #     if p.find('h3', attrs={'class': 'pledge__title'}):
    #         title = p.find('h3', attrs={'class': 'pledge__title'}).text.strip()
    #     else:
    #         continue
    #     desc = p.find('div',
    #                   attrs={'class': 'pledge__reward-description pledge__reward-description--expanded'}).p.text.strip()
    #     price = ''
    #     convprice = ''
    #     for i in p.find('h2', attrs={'class': 'pledge__amount'}).find_all('span'):
    #         if 'class' in i.attrs:
    #             if 'money' in i.attrs['class']:
    #                 price = i.text
    #         elif i.attrs == {}:
    #             convprice = i.text
    #     thispledgestring = ' '.join([convprice + price + title, desc]).strip()
    #     print(thispledgestring)
    #     if thispledgestring:
    #         pledgestring += thispledgestring + '\n'
    # if pledgestring:
    pledge = get_min_pledge_amount('')
    # else:
    #    print(b)
    if pledge:
        return pledge
    else:
        return 0


def boardgamegeek_search(name):
    found_item = False
    ids = []
    for j in range(len(re.split('\W', name))):
        if found_item:
            break
        print(' '.join(re.split('\W', name)[:len(re.split('\W', name)) - j]))
        bgg = 'https://boardgamegeek.com/xmlapi2/'
        call_type = 'search'
        call_dict = {'query': ' '.join(re.split('\W', name)[:len(re.split('\W', name)) - j]),
                     'type': ','.join(['boardgame']),
                     'exact': 0}

        url = '{}/{}?{}'.format(bgg,
                                quote(call_type),
                                urlencode(call_dict),
                                )
        print(url)
        valid_request = False
        a = ''
        while not valid_request:
            a = requests.get(url)
            if a.status_code == 200:
                valid_request = True
            else:
                time.sleep(2)

        root = ET.fromstring(a.text)

        idstring = ''
        ids = []
        if len(list(root)) > 300:
            continue
        for child in list(root):
            call_type = 'thing'
            type = child.attrib['type']
            id = child.attrib['id']
            ids.append(id)
            if len(ids) > 100:
                call_dict = {'id': ','.join(ids)}
                url = '{}/{}?{}'.format(bgg,
                                        quote(call_type),
                                        urlencode(call_dict),
                                        )
                print(url)
                valid_request = False
                r = ''
                while not valid_request:
                    r = requests.get(url)
                    if r.status_code == 200:
                        valid_request = True
                    else:
                        time.sleep(2)

                this_games = ET.fromstring(r.text)
                # print(r.text)
                for this_child in list(this_games):
                    this_id = this_child.attrib['id']
                    name = this_child.find('name').attrib['value']
                    min_players = this_child.find('minplayers').attrib['value']
                    max_players = this_child.find('maxplayers').attrib['value']
                    year_published = this_child.find('yearpublished').attrib['value']
                    print(year_published, name, min_players, max_players,
                          'https://boardgamegeek.com/%s/%s' % (type, this_id))
                ids = []
            found_item = True
        if len(ids) > 0:
            call_dict = {'id': ','.join(ids)}
            url = '{}/{}?{}'.format(bgg,
                                    quote(call_type),
                                    urlencode(call_dict),
                                    )
            print(url)
            valid_request = False
            r = ''
            while not valid_request:
                r = requests.get(url)
                if r.status_code == 200:
                    valid_request = True
                else:
                    time.sleep(2)
            this_games = ET.fromstring(r.text)

            # print(r.text)
            for this_child in list(this_games):
                this_id = this_child.attrib['id']
                name = this_child.find('name').attrib['value']
                min_players = this_child.find('minplayers').attrib['value']
                max_players = this_child.find('maxplayers').attrib['value']
                year_published = this_child.find('yearpublished').attrib['value']
                print(year_published, name, min_players, max_players,
                      'https://boardgamegeek.com/%s/%s' % (type, this_id))


def create_kickstarter_post(table, interval_start=datetime.today().date()):
    this_formula = 'AND({ExcludeFromRollup}=0,{Canceled}=0,{Funding Chance}=1)'
    intable = table.all(formula=this_formula, sort=['End Date'])
    end_interval_begin = interval_start + timedelta(days=1)
    end_interval_end = end_interval_begin + timedelta(weeks=1)
    this_ending_soon_count = 0
    this_top_backers = (0, '')
    this_post_text = ''
    this_post_text += "## What this is:\n\n"
    this_post_text += "This is a weekly, curated listing of Kickstarter board game projects that are either:\n\n"
    this_post_text += "- **ending in the next 7 days (starting %s)**" % (end_interval_begin.strftime('%b %d'))
    this_post_text += " that have at least 100 backers and have at least a fighting chance of being funded.\n"
    this_post_text += "- **newly posted in the past 7 days and have averaged at least 10 backers per day**\n\n"
    this_post_text += "All board game projects meeting those criteria will automatically be included, **no need to ask.** (The occasional non-board game project may also sneak in!)\n\n"
    this_post_text += "Expect new lists each Sunday sometime between midnight and noon PST.\n*****\n"
    this_post_text += "## Ending Soon\n"
    this_post_text += "Project Info|Players|Backers|Min / Avg Pledge|Ends|Comments\n:--|:--|:--|:--|:--|:--\n"
    for this_project in intable:
        include = True
        # thisproject = intable[project]
        if 'Backers' in this_project['fields']:
            if this_project['fields']['Backers'] < 100:
                include = False
        if 'ExcludeFromRollup' in this_project['fields']:
            if this_project['fields']['ExcludeFromRollup'] == True:
                include = False
        if include:
            this_end_date = datetime.strptime(this_project['fields']['End Date'], '%Y-%m-%dT%H:%M:00.000Z')
            if this_end_date.date() > end_interval_begin and this_end_date.date() <= end_interval_end:
                # if (atdata[project]['Funding Percent'] >= (70 -(atdata[project]['Days To Go'] * 3.58))):
                this_post_text += write_project_table_row(this_project['fields'])
                this_post_text += '\n'
                if this_project['fields']['Backers'] > this_top_backers[0]:
                    this_top_backers = (this_project['fields']['Backers'], this_project['fields']['Name'])
                this_ending_soon_count += 1
    return this_post_text, this_ending_soon_count, this_top_backers


def create_kickstarter_post_2(table, interval_start=datetime.today().date()):
    this_formula = 'AND({ExcludeFromRollup}=0,{Canceled}=0)'
    in_table = table.all(formula=this_formula, sort=['Name'])
    this_new_count = 0
    post_text = ''
    new_interval_begin = interval_start - timedelta(weeks=1)
    new_interval_end = interval_start
    this_top_backers = (0, '')
    post_text += '## New This Week\n'
    post_text += "Project Info|Players|Backers|Min / Avg Pledge|Ends|Comments\n:--|:--|:--|:--|:--|:--\n"
    for this_project in in_table:
        include = True
        if 'ExcludeFromRollup' in this_project['fields']:
            if this_project['fields']['ExcludeFromRollup']:
                include = False
        if include:
            begin_date = datetime.strptime(this_project['fields']['Launch Date'], '%Y-%m-%dT%H:%M:00.000Z')
            if begin_date.date() >= new_interval_begin and begin_date.date() < new_interval_end and (
                    (((datetime.utcnow().date() - begin_date.date()).days) * 10) < this_project['fields']['Backers']):
                post_text += write_project_table_row(this_project['fields'])
                post_text += '\n'
                if this_project['fields']['Backers'] > this_top_backers[0]:
                    this_top_backers = (this_project['fields']['Backers'], this_project['fields']['Name'])
                this_new_count += 1

    # old stuff about tags - don't use this any more

    #    posttext += '''## Need moar Kickstarter goodness?
    # Check out...
    #
    # - BoardGameGeek's variety of [Kickstarter-oriented Geeklists](https://boardgamegeek.com/geeklist/166152/kickstarter-project-metalist)
    # - [Kicktraq's data-driven views](https://www.kicktraq.com/categories/games/tabletop%20games/)
    #
    ### Footnotes
    # - `#hmm` means that something about the project seems a little off. Buyer beware kinda thing.
    # - `#lolwut` is reserved for projects that seem like copycat games or campaigns put together with little thought. Check 'em out for amusement.
    # - `#take` tags are for projects that have been restarted for some reason, with the number indicating what iteration we're currently on.
    # - `#reprint` when used along with `#expansion` indicates this campaign allows you to pledge for the base game by itself.
    # - `#bling` tags are for accessories, upgrades, sleeves, toys, tables, etc.
    # - `#dtpick` tags identify the games the various Dice Tower folks identified as their pick of the week
    # - Did I miss something? Particularly something **new in the last 7 days** or **ending in the next 7 days**? Let me know in the comments and I'll add it in.

    ### Tip Jar
    # If you enjoy these lists, give me an upvote. [Signing up for a free AirTable account](https://airtable.com/invite/r/yWYZuT6G) via my referral link can help, too. Plus, it's swell!'''

    post_text += '''## Need moar Kickstarter goodness?
Check out... 

- BoardGameGeek's variety of [Kickstarter-oriented Geeklists](https://boardgamegeek.com/geeklist/166152/kickstarter-project-metalist)
- [Kicktraq's data-driven views](https://www.kicktraq.com/categories/games/tabletop%20games/)

## Footnotes
- Did I miss something? Particularly something **new in the last 7 days** or **ending in the next 7 days**? Let me know in the comments and I'll add it in.

## Tip Jar
If you enjoy these lists, give me an upvote. [Signing up for a free AirTable account](https://airtable.com/invite/r/yWYZuT6G) via my referral link can help, too. Plus, it's swell!'''
    return (post_text, this_new_count, this_top_backers)


kicktraq_data = process_gamefound_data(config['gamefoundurl'])
kicktraq_data += process_kicktraq_data(config['ktkey'], config['kturl'])
thisktids = set()
for i in kicktraq_data:
    thisktids.add(i['KTID'])

airtable_handle = pyairtable.Table(config['at_key'], config['at_baseid'], config['at_table_name'])

# never fully implemented this
# #cleanupbgg(table)
# exit()

full_table = airtable_handle.all()
uploaded_kicktraq_ids = {}
airtable_data = {}
for i in full_table:
    airtable_data[i['id']] = i['fields']
    uploaded_kicktraq_ids[i['fields']['KTID']] = i['id']
print(len(airtable_data), len(uploaded_kicktraq_ids))
print(len(set(uploaded_kicktraq_ids.keys()) - thisktids))
for removedid in set(uploaded_kicktraq_ids.keys()) - thisktids:
    print(removedid)
    print(uploaded_kicktraq_ids[removedid])
    print(airtable_data[uploaded_kicktraq_ids[removedid]])
    airtable_handle.delete(uploaded_kicktraq_ids[removedid])

# exit()
added_entries, added_ids = find_new_projects(airtable_handle, uploaded_kicktraq_ids)
airtable_data = airtable_data | added_entries
uploaded_kicktraq_ids = uploaded_kicktraq_ids | added_ids

# createKsPost(config['at_key'],atdata)
added_entries, added_ids = add_to_airtable(airtable_handle, airtable_data, uploaded_kicktraq_ids)
airtable_data = airtable_data | added_entries
uploaded_kicktraq_ids = uploaded_kicktraq_ids | added_ids

print(len(airtable_data), len(uploaded_kicktraq_ids))
update_airtable(airtable_handle, airtable_data, uploaded_kicktraq_ids)
c = 0

text, ending_soon_count, top_backers = create_kickstarter_post(airtable_handle)

formula = 'AND({ExcludeFromRollup}=0,{Canceled}=0)'
full_table = airtable_handle.all(formula=formula, sort=['Name'])
text2, new_count, top_new_backers = create_kickstarter_post_2(airtable_handle)
text += text2

print(text)
print(ending_soon_count, new_count)
print(top_backers)
# datetime.date.today().strftime('%b %d, %Y')
print('Crowdfunding Roundup: %s | %d+ Ending Soon (including: %s) & %d+ New This Past Week (including: %s)' % (
    date.today().strftime('%b %d, %Y'), ending_soon_count, top_backers[1], new_count, top_new_backers[1]))
