#!/usr/bin/python

##
# This script is designed to import Loop standalone content from
# mozilla-central, to the git repo, with necessary translations of
# file locations, and some in-file corrections.
#
# It is typically expected to be run from a cron job.
#
# It expects to be run in the root directory of
# https://github.com/mozilla/loop-client
# and expects http://hg.mozilla.org/mozilla-central/ to be in
# "../mozilla-central"
#
# It also assumes the "origin" remote is correctly set on the repository
##

import argparse
import sys
import os
from datetime import datetime
import subprocess
import dateutil
import dateutil.tz
from mercurial import hg, ui, commands
# We use gitpython for the repository branch. I was hoping to use it for
# more, but unfortunately gitpython doesn't seem to want
# to set dates on commits, so we revert to calling git directly for that.
# Also push and pull just didn't seem to work - the documentation is really
# minimal, which doesn't help.
from git import Repo

LATEST_REV_FILE = "last_m_c_import_rev.txt"
M_C_SOURCE_URL = "http://hg.mozilla.org/mozilla-central/"
M_C_SOURCE_REPO = "../mozilla-central"


# Is this interesting to Loop?
def interestingFilename(filename):
    return (filename.startswith("browser/components/loop/standalone") or
            filename.startswith("browser/components/loop/content/shared") or
            filename.startswith("browser/components/loop/test/standalone") or
            filename.startswith("browser/components/loop/test/shared"))


# This is how we map files from mozilla-central to loop-client repo
def updatePathsFor(filename):
    filename = filename.replace("browser/components/loop/standalone/", "")
    filename = filename.replace("browser/components/loop/content/shared/",
                                "content/shared/")
    filename = filename.replace("browser/components/loop/test/standalone/",
                                "test/standalone/")
    filename = filename.replace("browser/components/loop/test/shared/",
                                "test/shared/")
    return filename


def testFileNeedsUpdatedPaths(filename):
    return (filename == "test/standalone/index.html" or
            filename == "test/shared/index.html")


def updatePathsInTestFile(filename, fileContext):
    print "Translating %s" % filename
    return fileContext.data().replace('src="../../standalone/', 'src="../../')


# Write a file out to disk, fileContext is the hg file context.
def writeFile(filename, fileContext):
    outFile = open(filename, "w")
    if testFileNeedsUpdatedPaths(filename):
        outFile.write(updatePathsInTestFile(filename, fileContext))
    else:
        outFile.write(fileContext.data())
    outFile.close()


def deleteFile(filename):
    os.remove(filename)


def runCommand(cmd):
    p = subprocess.Popen(cmd)
    result = p.wait()
    if result != 0:
        sys.exit(result)


def gitAdd(filename):
    runCommand(['git', 'add', filename])


def gitRemove(filename):
    runCommand(['git', 'rm', filename])


# Deals with writing all parts of a cset to disk, updating the git index
# as we go.
def writeCset(cset):
    print "%s %s" % (cset.hex(), cset.description())

    for filename in cset.files():
        # Write the files
        if interestingFilename(filename):
            newFilename = updatePathsFor(filename)
            try:
                fileData = cset[filename]
            except:
                # print "Deleting file %s" % (filename)
                deleteFile(newFilename)
                gitRemove(newFilename)
            else:
                # print "Writing %s to %s" % (filename, newFilename)
                writeFile(newFilename, fileData)
                gitAdd(newFilename)


# Actually commits the cset
def commitCset(cset):
    commitMsg = "%s\nmozilla-central hg revision: %s" % (cset.description(),
                                                         cset.hex())
    csetDate = datetime.fromtimestamp(cset.date()[0],
                                      dateutil.tz.tzoffset(None,
                                                           -cset.date()[1]))
    runCommand(['git', 'commit', '-m', commitMsg, '--author=' + cset.user(),
                '--date=' + str(csetDate)])


# Outputs to the lastest revision file
def writeLatestRev(cset):
    outFile = open(LATEST_REV_FILE, "w")
    outFile.write(cset.hex() + "\n")
    outFile.close()

    gitAdd(LATEST_REV_FILE)
    runCommand(['git', 'commit', '-m', 'update latest merged cset file'])


def pullHg(hgRepo, hgUI):
    # And update it
    if commands.incoming(hgUI, hgRepo, source=M_C_SOURCE_URL, bundle=None,
                         force=None) == 0:
        commands.pull(hgUI, hgRepo, source=M_C_SOURCE_URL)


def pullGit(branch):
    runCommand(['git', 'pull', '--ff-only', 'origin', branch])


def pushGit(branch):
    runCommand(['git', 'push', 'origin', branch])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--push-result', dest='push_result',
                        action='store_true', default=False,
                        help='Push the result of the extraction')

    args = parser.parse_args()

    # First of all, check we're up to date for the git repo.
    gitRepo = Repo(".")
    assert gitRepo.bare is False
    assert gitRepo.is_dirty() is False

    pullGit(gitRepo.active_branch.name)

    # Find out the last revision we checked against
    lastestRevFile = open(LATEST_REV_FILE, "r")
    firstRevText = lastestRevFile.read().strip()
    lastestRevFile.close()

    print "Starting at %s" % (firstRevText)

    # Last revision to check to.
    lastRevText = "default"

    # Open the Mercurial repo...
    hgUI = ui.ui()
    hgRepo = hg.repository(hgUI, M_C_SOURCE_REPO)

    pullHg(hgRepo, hgUI)

    committedFiles = False
    print firstRevText
    print lastRevText
    firstRev = hgRepo[firstRevText].rev()
    lastRev = hgRepo[lastRevText].rev()

    # Now work through any new changesets
    for i in xrange(firstRev, lastRev):
        cset = hgRepo[i]

        # Use the very last cset, not the one that affects loop,
        # to avoid attempting to port the same cset all the time
        lastCset = cset

        if len(cset.parents()) > 1:
            continue

        affectsLoop = False
        # If one of the files is interesting to loop, then we need to
        # do the whole changeset
        for filename in cset.files():
            if interestingFilename(filename):
                print filename
                affectsLoop = True
                break

        if affectsLoop:
            # Create a new index for the repo (indexes get translated
            # into commits)
            # Write the cset, then commit it.
            writeCset(cset)
            commitCset(cset)
            committedFiles = True

    # Only bother committing if we're updated the files.
    # In theory we shouldn't need to commit anyway, but it
    # may be a useful check
    if committedFiles:
        writeLatestRev(lastCset)

    if args.push_result:
        pushGit(gitRepo.active_branch.name)

if __name__ == "__main__":
    main()
