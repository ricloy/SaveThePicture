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

api_url = "https://www.openstreetmap.org/api/0.6/notes"
webarchive_url = "https://web.archive.org/save/"
logfile = "./log/savethepicture.log"

# Italy bbox
min_lat = 35.2889616
max_lat = 47.0921462
min_lon = 6.6272658
max_lon = 18.7844746

# Connection Timeout (both for API OSM server and web.archive.org)
TIMEOUT = 60

# max retries for API queries connections and HTTPS connections to web.archive.org
MAX_RETRIES = 5

# manual wait time in seconds between each retry
WAIT_TIME = 10

# BBOX is divided in a steps x steps grid
steps = 4

# total counters
total_notes = 0
total_closed_notes = 0
total_westnordost_links = 0
total_saved_westnordost_links = 0

session = requests.Session()
adapter = HTTPAdapter(max_retries=MAX_RETRIES)
session.mount("HTTPS://", adapter)

Path("./log").mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=logfile, level=logging.INFO, format='%(asctime)s:%(levelname)s: %(message)s')

for x in range(0, steps):
    for y in range(0, steps):
        logging.info("Analysing bbox {}/{}…".format(x*steps + y + 1, steps * steps))

        # bbox is one of the steps X steps rectangles inside the area identified by min_lat, max_lat, min_lon, max_lon
        bbox = (min_lon + x*(max_lon - min_lon)/steps, min_lat + y*(max_lat - min_lat)/steps, min_lon + (x+1)*(max_lon - min_lon)/steps, min_lat + (y+1)*(max_lat - min_lat)/steps)

        try:
            # query the OSM API for a maximum of 10000 notes (either open or closed) inside the current rectangle
            r = session.get(api_url + "?bbox=" + ",".join([str(x) for x in bbox]) + "&limit=10000", timeout=TIMEOUT)
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

        # partial counters
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
                    # search for a link to a photo hosted on https://westnordost.de
                    westnordost_link = re.search(r'https://westnordost\.de/([a-z])/([0-9]+\.jpg)', comment)
                    if westnordost_link:
                        part_westnordost_links = part_westnordost_links + 1
                        # have we already saved this photo link in a previous run? If not…
                        if not exists("./data/{}/{}.idx".format(westnordost_link.group(1), westnordost_link.group(2))):
                            # if directory './data' doesn't exist create it
                            Path("./data/").mkdir(parents=True, exist_ok=True)

                            logging.info("Saving {} to {}".format(westnordost_link.group(1) + westnordost_link.group(2), (webarchive_url + westnordost_link.group(0))))

                            try:
                                r = session.head(webarchive_url + westnordost_link.group(0), timeout=TIMEOUT)
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
                                sleep(WAIT_TIME)
                                continue
                            # saving the web.archive.org link to a local file which will be used in the successive runs of this script
                            with open("./data/{}/{}.idx".format(westnordost_link.group(1), westnordost_link.group(2)), 'w') as f:
                                f.write(",".join([note.get('lat'), note.get('lon'), "https://www.openstreetmap.org/note/" + note.xpath('./id/text()[1]')[0], r.headers['location']]) + "\n")
                                part_saved_westnordost_links = part_saved_westnordost_links + 1
        logging.info("[Partial stats for this sub-area] notes: {}, closed notes: {}, westnordost links: {}, saved westnordost links: {}".format(part_notes, part_closed_notes, part_westnordost_links, part_saved_westnordost_links))
        total_notes = total_notes + part_notes
        total_closed_notes = total_closed_notes + part_closed_notes
        total_westnordost_links = total_westnordost_links + part_westnordost_links
        total_saved_westnordost_links = total_saved_westnordost_links + part_saved_westnordost_links

logging.info("[Final stats for this run] notes: {} closed notes: {}, total westnordost links: {}, total saved westnordost links: {}".format(total_notes, total_closed_notes, total_westnordost_links, total_saved_westnordost_links))
