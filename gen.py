import os
import traceback
import sys
import uuid
import time
import json
import pysftp
import logging
import datetime
import html
import subprocess
import ffmpeg
from typing import Dict, List, Text, Tuple, Union, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
import bowtiedb

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


load_dotenv()

downloads_path = os.environ["DOWNLOADS_PATH"]
web_path = os.environ["WEB_PATH"]
sftp_host = os.environ["SFTP_HOST"]
sftp_user = os.environ["SFTP_USER"]
sftp_pass = os.environ["SFTP_PASS"]
sftp_path = os.environ["SFTP_PATH"]
VARIANT_256 = "256x256jpg"
VARIANT_128 = "128x128jpg"
VARIANT_128GIF = "128x128gif"
PAGE_BUDGET = 120_000

TEMPLATE_BEGIN = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
<meta name="viewport" content="width=device-width">
<title>Cendyne Bowtie Blog</title>
</head>
<body bgcolor="#3F2E26">
"""
NAV_BEGIN = """
<table align="center" border="0" cellpadding="20" width="460">
<tr>
"""
NAV_END = """
</tr>
</table>
"""
ENTRIES_BEGIN = """
<table align="center" border="2" cellpadding="20" width="460" bordercolor="#deb836">
"""
ENTRIES_END = """
</table>
"""
TEMPLATE_END = """
</body>
</html>
"""

@dataclass
class State():
    lastEntry: Optional[bowtiedb.Entry] = None

def getLatestEntry() -> Optional[bowtiedb.Entry]:
    entries = bowtiedb.find_entries(limit=1)
    if len(entries) > 0:
        return entries[0]
    return None

def makeAsset(variant, source, destination):
    web_dest = web_path + "/" + destination
    download_source = downloads_path + "/" + source
    if not os.path.exists(web_dest):
        if variant == VARIANT_256:
            result = subprocess.Popen([
                "convert",
                download_source,
                "-background", "#3f2e26",
                "-flatten",
                "-resize", "256x256>",
                "-alpha", "off",
                web_dest
                ])
            text = result.communicate()[0]
            return_code = result.returncode
            logging.info("Converted %s to %s: %s", source, destination, text)
            if return_code != 0:
                logging.warn("convert exited with code %d", return_code)
            else:
                # Save successfully created assets
                bowtiedb.add_asset(bowtiedb.Asset(source, variant, destination))
        elif variant == VARIANT_128:
            result = subprocess.Popen([
                "convert",
                download_source,
                "-background", "#3f2e26",
                "-flatten",
                "-resize", "128x128>",
                "-alpha", "off",
                web_dest
                ])
            text = result.communicate()[0]
            return_code = result.returncode
            logging.info("Converted %s to %s: %s", source, destination, text)
            if return_code != 0:
                logging.warn("convert exited with code %d", return_code)
            else:
                # Save successfully created assets
                bowtiedb.add_asset(bowtiedb.Asset(source, variant, destination))
        elif variant == VARIANT_128GIF:
            result = ffmpeg.probe(download_source)
            stream = result["streams"][0]
            width = stream["width"]
            height = stream["height"]
            ratio = min(min(128, width) / width, min(128, height) / height)
            duration = float(stream["duration"])
            resized_height = int(ratio * height)
            resized_width = int(ratio * width)
            stream = ffmpeg.input(download_source)

            if duration > 10:
                stream = ffmpeg.trim(stream, duration=10)
            if duration > 2:
                rate = int(max(min(20 / duration, 10), 1))
            else:
                rate = 10
            if duration > 10:
                stream = ffmpeg.trim(stream, duration=10)
            stream = ffmpeg.filter(stream, 'scale', str(resized_width), str(resized_height))
            stream = ffmpeg.output(stream, web_dest, r=rate)
            try:
                stream = ffmpeg.run(stream, capture_stdout=True)
                bowtiedb.add_asset(bowtiedb.Asset(source, variant, destination))
            except:
                logging.info("Unable to work on file?")


# This is a highly inefficient algorithm
def makeHtml(content: Text, entities: List[bowtiedb.TelegramMessageEntity]) -> Text:
    output = ""
    position = 0
    active = set()
    for i in content:
        before = ""
        after = ""
        nl2br = True

        for entity in entities:
            if entity.offset == position:
                print("Entity: %s", entity)
                if entity.type == "bold":
                    before = "<b>"
                elif entity.type == "italic":
                    before = "<i>"
                elif entity.type == "underline":
                    before = "<u>"
                elif entity.type == "strikethrough":
                    before = "<strike>"
                elif entity.type == "code":
                    before = "<code>"
                elif entity.type == "pre":
                    before = "<pre>"
                elif entity.type == "url":
                    before = '<a href="' + content[position:(position+entity.length)] + '"><font color="#f7b2a9">'
                elif entity.type == "text_link":
                    before = '<a href="' + entity.url + '"><font color="#f7b2a9">'
                elif entity.type == "email":
                    before = '<a href="mailto:' + content[position:(position+entity.length)] + '"><font color="#f7b2a9">'
                elif entity.type == "mention":
                    before = '<a href="https://t.me/' + content[position + 1:(position+entity.length)] + '"><font color="#f7b2a9">'
                active.add(entity.type)
            
            if entity.offset + entity.length - 1 == position:
                if entity.type == "bold":
                    after = "</b>"
                elif entity.type == "italic":
                    after = "</i>"
                elif entity.type == "underline":
                    after = "</u>"
                elif entity.type == "strikethrough":
                    after = "</strike>"
                elif entity.type == "code":
                    after = "</code>"
                elif entity.type == "pre":
                    after = "</pre>"
                elif entity.type == "text_link":
                    after = '</font></a>'
                elif entity.type == "url":
                    after = '</font></a>'
                elif entity.type == "email":
                    after = '</font></a>'
                elif entity.type == "mention":
                    after = '</font></a>'
                active.remove(entity.type)
            if (entity.offset <= position 
                and entity.offset + entity.length <= position 
                and entity.type == "pre"):
                nl2br = False

        output += before
        if i == '\n' and nl2br:
            output += "<br>\n"
        else:
            output += html.escape(i)
        output += after
        position += 1

    return output

@bowtiedb.with_connection
def build(state:State) -> None:
    latest = getLatestEntry()
    if latest is None:
        return
    if state.lastEntry and state.lastEntry.identity == latest.identity:
        return
    # A change has occurred!
    state.lastEntry = latest
    logging.info("Rebuilding")
    entries = bowtiedb.find_entries(100)
    icons = {}
    files = []
    entry_htmls = []
    file_sizes = dict()

    for entry in entries:
        photo = entry.photo
        icon = entry.icon
        web_photo = None
        web_icon = None
        if photo:
            variant = None
            if photo.endswith(".webp"):
                # Convert to jpg with background
                variant=VARIANT_256
            elif photo.endswith(".jpg"):
                # Resized
                variant=VARIANT_256
            elif photo.endswith(".mp4") or photo.endswith(".gif"):
                # Resized and limited gif
                variant=VARIANT_128GIF
            asset = None
            if variant:
                asset = bowtiedb.find_asset(photo, variant)
            source = None
            destination = None
            if not asset and variant:
                if variant == VARIANT_256:
                    destination = str(uuid.uuid4())[24:] + ".jpg"
                    source = photo
                elif variant == VARIANT_128GIF:
                    destination = str(uuid.uuid4())[24:] + ".gif"
                    source = photo
            elif asset:
                destination = asset.destination
                source = asset.source
            if variant and destination and source:
                # Check and see if we need to create this
                makeAsset(variant, source, destination)
                web_photo = destination
        if icon and not (icon in icons):
            variant = VARIANT_128
            source = icon
            asset = bowtiedb.find_asset(source, variant)
            if not asset:
                destination = str(uuid.uuid4())[24:] + ".jpg"
            else:
                destination = asset.destination
            makeAsset(variant, source, destination)
            web_icon = destination
            icons[icon] = destination
        elif icon in icons:
            web_icon = icons[icon]
        display_name = entry.display_name or 'Null'
        entry_html = ""
        entry_html += '<tr><td><font color="#deb836"><b>' + html.escape(display_name) + '</b></font></td>'
        entry_html += '<td><font color="#f6f3ed"><i>' + str(datetime.datetime.fromtimestamp(entry.date)) + ' UTC</i></font></td></tr>\n'
        entry_html += '<tr><td>'
        if web_icon:
            entry_html += '<img src="' + web_icon + '" alt="">'
            files.append(web_icon)
            if not web_icon in file_sizes:
                file_sizes[web_icon] = os.stat(web_path + "/" + web_icon).st_size
        entry_html += '</td><td valign="top">'
        if web_photo:
            entry_html += '<center><img src="' + web_photo + '" alt=""><br></center>'
            files.append(web_photo)
            if not web_photo in file_sizes:
                file_sizes[web_photo] = os.stat(web_path + "/" + web_photo).st_size
        if entry.content:
            entry_html += '<font color="#f6f3ed">'
            entry_html += makeHtml(entry.content, entry.entities or [])
            entry_html += '</font>'
        entry_html += '</td></tr>\n'
        entry_htmls.append({
            "html": entry_html,
            "icon": web_icon,
            "photo": web_photo
        })
    budget = PAGE_BUDGET
    page_num = 0
    page_entries = dict()
    page_entries[0] = dict()
    page_entries[0]["entries"] = []
    page_entries[0]["files"] = set()
    for entry in entry_htmls:
        size = len(entry["html"])
        if entry["icon"] and not entry["icon"] in page_entries[page_num]["files"]:
            size += file_sizes[entry["icon"]]
        if entry["photo"] and not entry["photo"] in page_entries[page_num]["files"]:
            size += file_sizes[entry["photo"]]
        budget -= size
        if (budget < 0 and len(page_entries[page_num]["entries"]) > 0) or len(page_entries[page_num]["entries"]) > 9:
            budget = PAGE_BUDGET - len(entry["html"])
            page_num += 1
            page_entries[page_num] = dict()
            page_entries[page_num]["entries"] = [entry["html"]]
            page_entries[page_num]["files"] = set()
            files_set: set = page_entries[page_num]["files"]
            if entry["icon"]:
                files_set.add(entry["icon"])
                budget -= file_sizes[entry["icon"]]
            if entry["photo"]:
                files_set.add(entry["photo"])
                budget -= file_sizes[entry["photo"]]
        else:
            page_entries[page_num]["entries"].append(entry["html"])
            files_set: set = page_entries[page_num]["files"]
            if entry["icon"]:
                files_set.add(entry["icon"])
            if entry["photo"]:
                files_set.add(entry["photo"])

    for page in page_entries:
        filename = "page" + str(page) + ".html"
        if page == 0:
            filename = "index.html"
        page_html = TEMPLATE_BEGIN
        nav_html = NAV_BEGIN
        nav_html += '<td align="left">'
        if page == 1:
            nav_html += '<a href="index.html"><font color="#f7b2a9">First Page</font></a>'
        elif page > 1:
            nav_html += '<a href="page' + str(page - 1) + '.html"><font color="#f7b2a9">Previous Page</font></a>'
        nav_html += '</td><td align="right">'
        if len(page_entries) > page + 2:
            nav_html += '<a href="page' + str(page + 1) + '.html"><font color="#f7b2a9">Next Page</font></a>'
        elif len(page_entries) > page + 1:
            nav_html += '<a href="page' + str(page + 1) + '.html"><font color="#f7b2a9">Last Page</font></a>'
        nav_html += '</td>' + NAV_END
        page_html += nav_html + ENTRIES_BEGIN
        page_html += "".join(page_entries[page]["entries"]) + ENTRIES_END
        page_html += nav_html + TEMPLATE_END
        with open(web_path + "/" + filename, 'wb') as fh:
            fh.write(page_html.encode("iso-8859-1", 'ignore'))
            logging.info("Wrote %s", filename)
            files.append(filename)

    if sftp_host and len(sftp_host) > 0 and sftp_pass and sftp_user and sftp_path:
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None
        with pysftp.Connection(sftp_host, username=sftp_user, password=sftp_pass, cnopts=cnopts) as sftp:
            with sftp.cd(sftp_path):
                for f in files:
                    web_file = web_path + "/" + f
                    if not sftp.exists(f):
                        logging.info("Upload %s", f)
                        sftp.put(web_file, f)
                    else:
                        remote_stat = sftp.lstat(f)
                        local_stat = os.stat(web_file)
                        if local_stat.st_size != remote_stat.st_size:
                            # The files are different!
                            logging.info("Upload %s", f)
                            sftp.put(web_file, f)






def main() -> None:
    logging.info("Init")
    bowtiedb.init()

    state = State()
    while True:
        time.sleep(1)
        build(state)

if __name__ == '__main__':
    main()
