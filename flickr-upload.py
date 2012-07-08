#!/usr/bin/env python2.5

# Copyright 2009 Mark Longair

#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

# This depends on a couple of packages:
#   apt-get install python-pysqlite2 python-flickrapi

import os
import sys
import time
import re
import xml
import tempfile
from subprocess import call, Popen, PIPE
import flickrapi
from optparse import OptionParser
from common import *
import shutil
import sqlite3 as sqlite

parser = OptionParser(usage="Usage: %prog [OPTIONS] [FILENAME]")
parser.add_option('--public', dest='public', default=False, action='store_true',
                  help='make the image viewable by anyone')
parser.add_option('--family', dest='family', default=False, action='store_true',
                  help='make the image viewable by contacts marked as family')
parser.add_option('--friends', dest='friends', default=False, action='store_true',
                  help='make the image viewable by contacts marked as friends')
parser.add_option('-v', '--verbose', dest='verbose', default=False, action='store_true',
                  help='verbose output')
parser.add_option('-t', '--title', dest='title',
                  metavar='TITLE',
                  help='set the title of the photo')
parser.add_option('--date-uploaded', dest='date_uploaded',
                  metavar='DATE',
                  help='set the date and time when the photo was uploaded')
parser.add_option('--date-taken', dest='date_taken',
                  metavar='DATE',
                  help='set the date and time when the photo was taken')
parser.add_option('--batch', dest='batch',
				  metavar='BATCH',
				  help='set the max number of files to upload')
parser.add_option('--test', dest='test', default=False, action='store_true',
				  help='test script; don\t actually do anything')

options,args = parser.parse_args()

date_pattern = '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'
date_error_message = 'must be of the form "YYYY-MM-DD HH:MM:SS'

if options.date_uploaded and not re.search(date_pattern,options.date_uploaded):
    print "The --date-uploaded argument must be "+date_error_message

if options.date_taken and not re.search(date_pattern,options.date_taken):
    print "The --date-taken argument must be "+date_error_message

if not 1 == len(args):
    print "No filename to upload supplied:"
    parser.print_help()
    sys.exit(1)

flickr = flickrapi.FlickrAPI(configuration['api_key'],configuration['api_secret'])

(token, frob) = flickr.get_token_part_one(perms='write')
if not token:
    raw_input("Press 'Enter' after you have authorized this program")
flickr.get_token_part_two((token, frob))

db_filename = os.path.join(os.environ['HOME'],'.flickr-photos-checksummed.db')
connection = sqlite.connect(db_filename)
cursor = connection.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS done ( photo_id text unique )")

def carriage_return():
	sys.stdout.write('\r')
	sys.stdout.flush()

def add_to_done(photo_id):
	cursor.execute("INSERT INTO done ( photo_id ) VALUES ( ? )", (photo_id,))
	connection.commit()
	if options.verbose:
		print 'Add photo id to db, done.'

def progress(percent,done):
    if done and options.verbose:
        print "Finished."
    elif options.verbose:
		print '{0}{1}'.format(str(int(round(percent))), '%'),
		carriage_return()
		time.sleep(1)
        #print ""+str(int(round(percent)))+"%"

def upload_photo(file):
	real_sha1 = sha1sum(file)
	real_md5 = md5sum(file)

	tags = sha1_machine_tag_prefix + real_sha1 + " " + md5_machine_tag_prefix + real_md5

	result = flickr.upload(filename=file,
						   callback=progress,
						   title=(options.title or os.path.basename(file)),
						   tags=tags,
						   is_public=int(options.public),
						   is_family=int(options.family),
						   is_friend=int(options.friends))

	photo_id = result.getchildren()[0].text
	if options.verbose:
		print "photo_id of uploaded photo: "+str(photo_id)
		print "Uploaded to: "+short_url(photo_id)

	if options.date_uploaded or options.date_taken:
		if options.verbose:
			print "Setting dates:"
			if options.date_uploaded:
				print "  Date uploaded: "+options.date_uploaded
			if options.date_taken:
				print "  Date taken: "+options.date_taken
		result = flickr.photos_setDates(photo_id=photo_id,
										date_posted=options.date_uploaded,
										date_taken=options.date_taken,
										date_taken_granularity=0)

	# move and rename file using photo_id
	new_filename = photo_id + '.jpg'
	dest_path = os.path.join('/media/nas/Pictures/originals/', new_filename)
	shutil.move(file, dest_path)
	if options.verbose:
		print 'Moved {0} to {1}'.format(file, dest_path)
	
	# and add photo id to uploaded db
	add_to_done(photo_id)

if os.path.isfile(args[0]):
	if options.verbose:
		print 'isfile = true'
	upload_photo(args[0])
	sys.exit(0)

elif os.path.isdir(args[0]):
	if options.verbose:
		print 'isdir = true'
	queued_files = []
	walk_result = os.walk( args[0] )
	for data in walk_result:
		(dirpath, dirnames, filenames) = data
		for f in filenames:
			queued_files.append(os.path.join(dirpath, f))

	for f in queued_files:
		upload_photo(f)
	
	sys.exit(0)

else:
	print "Failed file/directory check."
	sys.exit(1)
