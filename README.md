# bgkickstarters

## Initial setup:

- install requirements from requirements.txt
- copy the config.json to localconfig.json which you will not commit back to github
- Setup airtable account and setup new table.  Table should mimic this table:
  - https://airtable.com/shr78fiZCbWTh25nB
- copy the airtable baseid / key / table name to the appropriate places in the localconfig.json
- work with u/kicktraq on reddit to get an API key to access the kictraq kickstarter project data API
  - put this api in the appropriate field in the localconfig.json

## Execution:

The script has multiple parts that it walks through to generate the reddit post for the week.  These are described below:

- connect to gamefound and kicktraq to download current active projects json files
- auto-remove projects that have ended from the airtable to ensure you stay below your free 1k row limit
- parse gamefound and kicktraq data to find new projects
  - projects that match specified filtered terms will be asked to be ignored - you can override this by selecting items from the list which will move them to the include list
- for each project to include, the script will do the following:
  - attempt to look the game up on boardgamegeek by searching based on the title of the project
    - items found with a simple search will be printed out with the year published, min player, max player, game title, and link to item in bgg
  - print the link to the rewards page on kickstarter
    - user needs to open this page to then figure out the min pledge amount to get the physical item
  - ask the user to enter the min pledge amount (just USD here)
  - ask the user for a link to the game on bgg - you can copy/paste from the search results
  - ask the user for the player count
    - if it was found on bgg, this is easy as those are printed, otherwise you might need to do some searching on the kickstarter page to find this
    - format is generally min-max (i.e. 2-4).  though sometimes I will use a ? or just leave it blank if I can't figure it out
  - ask the user if this game should be included or excluded from the roll up
- After all new projects are completed, the rest of the existing data in the airtable will be updated for new data.  Most of this is automated, but if the title, description, or newly calculated exclude flag are different, it will prompt the user to agree to these changes
- Lastly it will print out the text for the reddit post as well as a title

## Tips:

In general, I like to use pycharm to run this as links are clickable to launch in a browser.  You can also right click on a link (without highlighting first) and select copy.  This is very useful for the bgg lookup



