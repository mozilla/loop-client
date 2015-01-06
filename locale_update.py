#!/usr/bin/python

##
# This script is designed to update the l10n files and locale registration
# for the standalone loop client. The source of the localization files
# is https://github.com/mozilla/loop-client-l10n repository.
# The loop client repo is assumed to be https://github.com/mozilla/loop-client.
#
# Run this script from the local version of loop-client. It assumes that a local
# version of loop-client-l10n is in a parallel directory: ../loop-client-l10n.
# Changes are then pushed back to loop-client.
##

import sys
import os
import shutil
import io
import re

l10n_src = "../loop-client-l10n/l10n/"
content_dir = "content/"
index_file_name = "index.html"

def createLocale(dst_name_list, src_dir):
    if len(src_dir) < 1 or src_dir[0] == "." or src_dir == 'templates':
        return dst_name_list
    
    dst_dir = src_dir.replace('_', '-')
    shutil.copytree(l10n_src + src_dir, content_dir + "l10n/" + dst_dir)
    dst_name_list.append(dst_dir)
    return dst_name_list

def main():
    print "deleting existing l10n content tree"
    shutil.rmtree(content_dir + "l10n", True)
    locale_dirs = os.listdir(l10n_src)

    print "updating l10n tree"
    locale_list = reduce(createLocale, locale_dirs, [])

    print "updating index.html locales list"
    index_file = io.open(content_dir + index_file_name, "r+")
    index_html = index_file.read()

    new_content = re.sub('<meta name=(["|\'])locales\\1.*? content=(["|\']).*?\\2.*? />',
                         '<meta name="locales" content="' + " ".join(locale_list) + '" />',
                         index_html, 1, re.M | re.S)

    index_file.seek(0)
    index_file.truncate(0)
    index_file.write(new_content)
    index_file.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        l10n_src = sys.argv[1]
        if l10n_src[-1] != "/":
            l10n_src = l10n_src + "/"
    if len(sys.argv) > 2:
        content_dir = sys.argv[2]
        if content_dir[-1] != "/":
            content_dir = content_dir + "/"
    main()

