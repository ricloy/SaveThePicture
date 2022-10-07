#!/usr/bin/env python3

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError
from requests.exceptions import ReadTimeout
import socket

from lxml import etree
from time import sleep
import sys
import re
from os.path import exists
from pathlib import Path
import logging

API_URL = "https://www.openstreetmap.org/api/0.6/notes"
WEBARCHIVE_URL = "https://web.archive.org/save/"
LOGFILE = "./log/savethepicture.log"

# Italy bbox
MIN_LAT = 35.2889616
MAX_LAT = 47.0921462
MIN_LON = 6.6272658
MAX_LON = 18.7844746

# Connection Timeout (both for API OSM server and web.archive.org)
TIMEOUT = 60

# max retries for API queries connections and HTTPS connections to web.archive.org
MAX_RETRIES = 5

# manual wait time in seconds between each retry
WAIT_TIME = 10

# minumum wait time between each saving on web.archive.org
WAYBACK_WAIT_TIME = 60

# BBOX is divided in a STEPS x STEPS grid
STEPS = 4

# total counters for showing stats
total_notes = 0
total_closed_notes = 0
total_westnordost_links = 0
total_saved_westnordost_links = 0

session = requests.Session()
adapter = HTTPAdapter(max_retries=MAX_RETRIES)
session.mount("HTTPS://", adapter)

Path("./log").mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=LOGFILE, level=logging.INFO, format='%(asctime)s:%(levelname)s: %(message)s')


# this function saves, if it hasn't already been done, a photo identified by link
# on the Wayback Machine and writes some data in local CSV formatted file ./data/{directory}/{photo_name}.idx

def save_photo_link(link, directory, photo_name):

    # have we already saved this photo link in a previous run? If not…
    if not exists("./data/{}/{}.idx".format(directory, photo_name)):
        # if directory './data' doesn't exist create it
        Path("./data/").mkdir(parents=True, exist_ok=True)

        logging.info("Saving {} to {}".format(directory + photo_name, (WEBARCHIVE_URL + link)))

        try:
            r = session.head(WEBARCHIVE_URL + link, timeout=TIMEOUT)
        except socket.timeout as e:
            logging.critical("Error: something went wrong while connecting to web.archive.org server: {}; exiting…".format(e))
            sys.exit(-4)
        except ReadTimeout as e:
            logging.critical("Error: read timeout while connecting to web.archive.org: {}; exiting…".format(e))
            sys.exit(-5)
        except ConnectionError as e:
            logging.critical("Error: connection error while connecting to web.archive.org: {}; exiting…".format(e))
            sys.exit(-6)
        # we expect https://web.archive.org to return 302 when a link is saved with the HTTP location header pointing to the new link on https://web.archive.org
        if r.status_code != 302:
            logging.warning("Error: web.archive.org returned HTTP_CODE {} (expected 302); sleeping for {} seconds (saving current photo is skipped)…".format(r.status_code, WAIT_TIME))
            sleep(WAYBACK_WAIT_TIME)
            return False
        # saving the web.archive.org link to a local file which will be used in the successive runs of this script
        with open("./data/{}/{}.idx".format(directory, photo_name), 'w') as f:
            # write CSV header
            f.write("Latitude,Longitude,OSM Note link,Wayback Machine saved link")
            # write CSV data
            f.write(",".join([note.get('lat'), note.get('lon'), "https://www.openstreetmap.org/note/" + note.xpath('./id/text()[1]')[0], r.headers['location']]) + "\n")

        sleep(WAYBACK_WAIT_TIME)
        return True

for x in range(0, STEPS):
    for y in range(0, STEPS):
        logging.info("Analysing bbox {}/{}…".format(x*STEPS + y + 1, STEPS * STEPS))

        # bbox is one of the STEPS X STEPS rectangles inside the area identified by MIN_LAT, MAX_LAT, MIN_LON, MAX_LON
        bbox = (MIN_LON + x*(MAX_LON - MIN_LON)/STEPS, MIN_LAT + y*(MAX_LAT - MIN_LAT)/STEPS, MIN_LON + (x+1)*(MAX_LON - MIN_LON)/STEPS, MIN_LAT + (y+1)*(MAX_LAT - MIN_LAT)/STEPS)

        try:
            # query the OSM API for a maximum of 10000 notes (either open or closed) inside the current rectangle
            r = session.get(API_URL + "?bbox=" + ",".join([str(x) for x in bbox]) + "&limit=10000", timeout=TIMEOUT)
        except socket.timeout as e:
            logging.critical("Error: something went wrong while connecting to the API server: {}; exiting…".format(e))
            sys.exit(-1)
        except ReadTimeout as e:
            logging.critical("Error: read timeout while connecting to the API server: {}; exiting…".format(e))
            sys.exit(-2)
        except ConnectionError as e:
            logging.critical("Error: connection error while connecting to the API server: {}; exiting…".format(e))
            sys.exit(-3)
        # we expect the OSM API to return 200 or else we sleep for a while then we pass to the next rectangle
        if r.status_code != 200:
            logging.warning("Error: OSM API returned HTTP_CODE {}; sleeping for {} seconds (current step is skipped)…".format(r.status_code, WAIT_TIME))
            sleep(WAIT_TIME)
            continue

        notes = etree.fromstring(r.content)

        # partial counters for showing stats
        part_notes = len(notes.getchildren())
        part_closed_notes = 0
        part_westnordost_links = 0
        part_saved_westnordost_links = 0

        for note in notes.getchildren():
            # is it closed?
            if note.xpath('./status/text()')[0] == "closed":
                part_closed_notes = part_closed_notes + 1
                logging.info("Inspecting closed note {}…".format(note.xpath("./id/text()")[0]))

                comments = note.xpath('./comments/comment/text/text()')
                # for every comment in the note
                for comment in comments:

                    # search for every link to a photo hosted on https://westnordost.de present in comment
                    for westnordost_link in re.finditer(r'https://westnordost\.de/([a-z])/([0-9]+\.jpg)', comment):
                        part_westnordost_links = part_westnordost_links + 1
                        if save_photo_link(westnordost_link.group(0), westnordost_link.group(1), westnordost_link.group(2)):
                            part_saved_westnordost_links = part_saved_westnordost_links + 1

        logging.info("[Partial stats for this sub-area] notes: {}, closed notes: {}, westnordost links: {}, saved westnordost links: {}".format(part_notes, part_closed_notes, part_westnordost_links, part_saved_westnordost_links))
        total_notes = total_notes + part_notes
        total_closed_notes = total_closed_notes + part_closed_notes
        total_westnordost_links = total_westnordost_links + part_westnordost_links
        total_saved_westnordost_links = total_saved_westnordost_links + part_saved_westnordost_links

logging.info("[Final stats for this run] notes: {} closed notes: {}, total westnordost links: {}, total saved westnordost links: {}".format(total_notes, total_closed_notes, total_westnordost_links, total_saved_westnordost_links))
