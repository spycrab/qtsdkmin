import argparse
import sys
import pathlib
import time
import re
import yaml

import requests
import defusedxml.ElementTree as ET
import libarchive.public

BASE_REPO_URL = "http://download.qt.io/online/qtsdkrepository"

CONFIG = {}

def get_xml(url):
    text = requests.get(url).text
    return ET.fromstring(text)

packages={}
urls={}

def add_package(package, url):
    global packages, urls
    
    name = package.find("Name").text
    
    packages[name] = package
    urls[name] = url
    
def install_package(package_name):
    global CONFIG, urls

    if package_name in CONFIG["ignore"]:
        return
        
    if package_name not in packages:
        print("Package '{}' not found".format(package_name))
        exit(1)

    package = packages[package_name]

    dependencies = package.find("Dependencies")
    
    if dependencies is not None:
        for requirement in dependencies.text.split(", "):
            install_package(requirement)

    archives = package.find("DownloadableArchives")

    if archives is not None:
        if archives.text is not None:
            for archive in archives.text.split(", "):

                if package_name in CONFIG["config"]:
                    if CONFIG["config"][package_name]["ignore_archives"]:
                        ignored = False
                        for regex in CONFIG["config"][package_name]["ignore_archives"]:
                            if re.match(regex, archive):
                                ignored = True
                                break

                        if ignored:
                            print("Ignoring {}...".format(archive))
                            continue
                
                url = urls[package_name]+"/"+package_name+"/"+package.find("Version").text+archive
                print("Downloading {}...".format(url))

                r = requests.get(url)

                print("Extracting...")

                for entry in libarchive.public.memory_pour(r.content):
                    pass
                                                

def add_repository(url):
    global args
    
    repo = get_xml(url+"/Updates.xml")

    # Add repositories
    for repo in repo.iter("Repository"):

        url = repo.attrib["url"]
        action = repo.attrib["action"]
        displayname = repo.attrib["displayname"]
        
        if action != "add":
            continue

        if args.verbose:
            print("Adding '{}'...".format(repo.attrib["displayname"]))

        add_repository(url)

    # Add packages
    for package in repo.iter("PackageUpdate"):
        add_package(package, url)


parser = argparse.ArgumentParser(description="Create a minimal Qt install")

parser.add_argument("manifest", type=str)
parser.add_argument("--verbose", action="store_true")

args = parser.parse_args()

stream = open(args.manifest, "r")
CONFIG = yaml.load(stream)

print("Parsing repositories (this may take a while)...")
for repo in CONFIG["repos"]:
    add_repository(BASE_REPO_URL + "/" + CONFIG["platform"] + "/" + repo)

print("Done. {} packages found.".format(len(packages)))

for package in CONFIG["packages"]:
    install_package(package)
