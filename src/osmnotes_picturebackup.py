#!/usr/bin/env python3

import requests
from lxml import etree
from time import sleep
import sys
import re
from os.path import exists
from pathlib import Path

api_url = "https://www.openstreetmap.org/api/0.6/notes"
webarchive_url = "https://web.archive.org/save/"

# Italy bbox
min_lat = 35.2889616
max_lat = 47.0921462
min_lon = 6.6272658
max_lon = 18.7844746

# max retries
MAX_RETRIES = 5

# wait time in seconds between each retry
WAIT_TIME = 10

# BBOX is divided in a steps x steps grid
steps = 4

# total counters
total_notes = 0
total_closed_notes = 0
total_westnordost_links = 0
total_saved_westnordost_links = 0

for x in range(0, steps):
    for y in range(0, steps):
        print("Analysing bbox {}/{}…".format(x*steps + y + 1, steps * steps))
        bbox = (min_lon + x*(max_lon - min_lon)/steps, min_lat + y*(max_lat - min_lat)/steps, min_lon + (x+1)*(max_lon - min_lon)/steps, min_lat + (y+1)*(max_lat - min_lat)/steps)
        r = requests.get(api_url + "?bbox=" + ",".join([str(x) for x in bbox]) + "&limit=10000")
        retry = 0
        while (r is None or r.status_code != 200) and retry < MAX_RETRIES:
            sleep(WAIT_TIME)
            retry = retry + 1
            r = requests.get(api_url + "?bbox=" + ",".join([str(x) for x in bbox]) + "&limit=10000")
        if retry >= MAX_RETRIES:
            print("Error: max number of retries ({}) reached; exiting…".format(MAX_RETRIES))
            sys.exit(-1)
        notes = etree.fromstring(r.content)

        # partial counters
        part_notes = len(notes.getchildren())
        part_closed_notes = 0
        part_westnordost_links = 0
        part_saved_westnordost_links = 0

        for note in notes.getchildren():
            if note.xpath('./status/text()')[0] == "closed":
                part_closed_notes = part_closed_notes + 1
                print("Inspecting closed note {}…".format(note.xpath("./id/text()")[0]))
                comments = note.xpath('./comments/comment/text/text()')
                for comment in comments:
                    westnordost_link = re.search(r'https://westnordost\.de/([a-z])/([0-9]+\.jpg)', comment)
                    if westnordost_link:
                        part_westnordost_links = part_westnordost_links + 1
                        if not exists("./data/{}/{}.idx".format(westnordost_link.group(1), westnordost_link.group(2))):
                            Path("./data/{}".format(westnordost_link.group(1))).mkdir(parents=True, exist_ok=True)

                            retry = 0
                            print("Saving {} to {}".format(westnordost_link.group(1) + westnordost_link.group(2), (webarchive_url + westnordost_link.group(0))))
                            r = requests.head(webarchive_url + westnordost_link.group(0))
                            while (r is None or r.status_code != 302) and retry < MAX_RETRIES:
                                sleep(WAIT_TIME)
                                retry = retry + 1
                                r = requests.head(webarchive_url + westnordost_link.group(0))
                            if retry >= MAX_RETRIES:
                                print("Error: max number of retries ({}) reached; exiting…".format(MAX_RETRIES))
                                sys.exit(-2)

                            with open("./data/{}/{}.idx".format(westnordost_link.group(1), westnordost_link.group(2)), 'w') as f:
                                f.write(r.headers['location'] + "\n")
                                part_saved_westnordost_links = part_saved_westnordost_links + 1
        print("[Partial stats for this sub-area] notes: {}, closed notes: {}, westnordost links: {}, saved westnordost links: {}".format(part_notes, part_closed_notes, part_westnordost_links, part_saved_westnordost_links))
        total_notes = total_notes + part_notes
        total_closed_notes = total_closed_notes + part_closed_notes
        total_westnordost_links = total_westnordost_links + part_westnordost_links
        total_saved_westnordost_links = total_saved_westnordost_links + part_saved_westnordost_links

print("[Final stats for this run] notes: {} closed notes: {}, total westnordost links: {}, total saved westnordost links: {}".format(total_notes, total_closed_notes, total_westnordost_links, total_saved_westnordost_links))
