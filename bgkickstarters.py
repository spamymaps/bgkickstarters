import requests
import os
from requests.exceptions import HTTPError
import re
import json


confPath = os.path.join(sys.path[0])
if os.path.isfile(os.path.join(confPath, "localconfig.json")):
    config = json.loads(open(os.path.join(confPath, "localconfig.json"), 'r').read())
else:
    config = json.loads(open(os.path.join(confPath, "config.json"), 'r').read())
outputFile = 'out.txt'

currencylookup = {"USD": "${:,d}",
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


def priceString(currency, amount):
    try:
        return currencylookup[currency].format(amount)
    except:
        return "Currency %s Not Recognized" % (currency)


def processKicktraq(apiKey):
    # ktData <- tibble("Name"=character(),
    #               "KTID"=character(),
    #               "Description"=character(),
    #               "Campaign Link"=character(),
    #               "Launch Date"=Date(),
    #               "End Date"=Date(),
    #               "Funded"=logical(),
    #               "Backers"=numeric(),
    #               "Current Funding"=character(),
    #               "Funding Percent"=numeric(),
    #               "Avg Pledge"=character(),
    #               "Cancelled"=logical())

    ktData = []

    # get kicktraq data from custom endpoint
    ktResp = ''
    query = {'key': apiKey}
    try:
        ktResp = requests.get('http://api.kicktraq.com/zelbinian/raw/0.1', params=query)
        # If the response was successful, no Exception will be raised
        ktResp.raise_for_status()
    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')  # Python 3.6
    except Exception as err:
        print(f'Other error occurred: {err}')  # Python 3.6
    else:
        print('Success!')

    # ktJSON <- content(ktResp, "text") %>% fromJSON()

    # focus only on the nodes with game info

    # projects <- c(ktJSON$data$Games, ktJSON$data$`Tabletop Games`, ktJSON$data$`Playing Cards`)

    projects = ktResp.json()['data']['Games'] | ktResp.json()['data']['Tabletop Games'] | ktResp.json()['data'][
        'Playing Cards']

    # for(p in projects) {
    for ktid, p in projects.items():
        # name <- p$name
        name = p['name']
        # raised <- as.integer(p$raised)
        raised = int(p['raised'])
        # goal <- as.integer(p$goal)
        goal = int(p['goal'])
        # if (str_detect(name, "(Cancelled)")) {
        #      cancelled = TRUE
        #      p$name %<>% str_remove(fixed(" (Cancelled)"))
        #      p$end <- now()
        #    } else {
        #      cancelled = FALSE
        #    }
        canceled = False
        if re.search('\(canceled\)', name, flags=re.IGNORECASE):
            canceled = True
            name = re.sub('\(canceled\)', '', name, flags=re.IGNORECASE).strip()

        # name %<>% str_replace_all(fixed("|"), "-")
        name = name.replace('|', '-')

        funded = False
        if raised > goal:
            funded = True
        # ktData %<>% add_row("Name" = name,
        #                "KTID" = p$uuid,
        #                "Description" = p$description %>% str_replace_all("[\r\n]", "") %>% str_replace_all("\\|", "-"),
        #                "Campaign Link" = p$url$kickstarter,
        #                "Launch Date" = dmy_hms(p$start) %>% floor_date("minute"),
        #                "End Date" = dmy_hms(p$end) %>% floor_date("minute"),
        #                "Funded" = ifelse(raised >= goal, TRUE, FALSE),
        #                "Avg Pledge" = priceString(p$currency, p$avg_pledge),
        #                "Backers" = as.integer(p$backers),
        #                "Current Funding" = paste(priceString(p$currency, raised),"of", priceString(p$currency, goal)),
        #                "Funding Percent" = round(raised/goal * 100),
        #                "Cancelled" = cancelled)
        thisktData = {'Name': name,
                      'KTID': ktid,
                      'Description': p['description'].replace('\r\n', '').replace('|', '-'),
                      'Campaign Link': p['url']['kickstarter'],
                      'Launch Date': datetime.strptime(p['start'], '%a, %d %b %Y %H:%M:%S %z').strftime(
                          '%Y-%m-%d %H:%M:00 %Z'),
                      'End Date': datetime.strptime(p['end'], '%a, %d %b %Y %H:%M:%S %z').strftime(
                          '%Y-%m-%d %H:%M:00 %Z'),
                      'Funded': funded,
                      'Avg Pledge': priceString(p['currency'], p['avg_pledge']),
                      'Backers': int(p['backers']),
                      'Current Funding': '%s of %s' % (
                      priceString(p['currency'], raised), priceString(p['currency'], goal)),
                      'Funding Percent': round(raised / goal * 100),
                      'Canceled': canceled
                      }

        ktData.append(thisktData)

    return (ktData)

}



