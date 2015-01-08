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

import argparse
import io
import os
import re
import shutil
import sys

def main(l10n_src, l10n_dst, index_file_name):
    print "deleting existing l10n content tree:", l10n_dst
    shutil.rmtree(l10n_dst, ignore_errors=True)

    print "updating l10n tree from", l10n_src

    def create_locale(src_dir):
        dst_dir = src_dir.replace('_', '-')
        shutil.copytree(os.path.join(l10n_src, src_dir), os.path.join(l10n_dst, dst_dir))
        return dst_dir
    
    locale_dirs = os.listdir(l10n_src)
    locale_list = [create_locale(x) for x in locale_dirs if x[0] != "." and x != "templates"]

    print "updating locales list in", index_file_name
    with io.open(index_file_name, "r+") as index_file:
        index_html = index_file.read()

        new_content = re.sub(
            '<meta name=(["|\'])locales\\1.*? content=(["|\']).*?\\2.*? />',
            '<meta name="locales" content="' + ", ".join(locale_list) + '" />',
            index_html, 1, re.M | re.S)
        
        index_file.seek(0)
        index_file.truncate(0)
        index_file.write(new_content)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Loop Stand-alone Client localization update script")
    parser.add_argument('--src',
                        default=os.path.join(os.pardir, "loop-client-l10n", "l10n"),
                        metavar="path",
                        help="source path for l10n resources")
    parser.add_argument('--dst',
                        default=os.path.join("content", "l10n"),
                        metavar="path",
                        help="destination path for l10n resources")
    parser.add_argument('--index-file',
                        default=os.path.join("content", os.extsep.join(["index", "html"])),
                        metavar="name",
                        help="html file to be updated with the locales list")
    args = parser.parse_args()
    main(args.src, args.dst, args.index_file)

