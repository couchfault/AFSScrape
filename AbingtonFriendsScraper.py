#!/usr/bin/env python
# Enumerate information about Abington Friends faculty/staff
# I already tried sql wildcard queries, but to no avail :(
# Looks like we're gonna do this mark zuckerberg style :)

from HTMLParser import HTMLParser
from threading import Thread
from urllib2 import urlopen
from urllib import urlencode, quote
from os import chdir, mkdir
from os.path import isdir
import argparse
import string
import re


# After about 5 minutes of reading their ugly source code I gots this :P
FACULTY_DETAIL_PAGE = 'Modals/Directories/ViewFacultyBio.aspx'
FACULTY_IDENTIFIER = 'fid'
FACULTY_ID_MIN = 1 # ID 1 is actually Tamera, she isn't the oldest teacher here I wonder why she's first
FACULTY_ID_MAX = 400
# I spent 20 minutes creating all these regexes. I stink @ regexes. This was probably the hardest part for me
PHONE_REGEX = '([0-9](|\-)[0-9]|[0-9])[0-9][0-9](|\-)[0-9][0-9][0-9](|\-)[0-9][0-9][0-9][0-9]'
NAME_FIELD_REGEX = '(?<=popupName...)([A-z\' ]{6,25})'
PROFILE_PICTURE_REGEX = '\/Media_Library\/[0-9 A-z\']{1,20}\.jpg'
WORK_EMAIL_REGEX = '(?<=mailto.)[0-9 A-z ]{6,35}@abingtonfriends.net' # ** NOTE- email is given in every faculty detail age, can be used to filter out null results
# COLLEGE_EDUCATION_REGEX = '(?<=Education\:\<\/strong\>)([A-z 0-9 \. , \- \: \; \< \> \/]{5,25})(?=.br...)'
COLLEGE_EDUCATION_REGEX = '((?<=Education \:\<\/strong\>)|(?<=Education\:\<\/strong\>))[A-z 0-9 \: \. \,]{10,200}'
BIO_REGEX = '((?<=\<br \/\>\n)|(?<=because\:\<\/strong\>) )[A-z   0-9 \. , \- \: \; \< \> \/]{100,750}' # SEQUENTIAL_FALCULTY_IDENTIFIER = 0

def fix_fancy_quotes(s):
  for p in s:
    if p not in string.printable or p=='\r':
      s.replace(p, '')
  return s

class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

class FacultyProfile:
  def __init__(self):
    self.full_name = ''
    self.phone_number = ''
    self.picture_url = ''
    self.email_address = ''
    self.education = ''
    self.selfwritten_bio = ''
    self.faculty_id = 0
    self.bio_url = 'about:blank'
  def __str__(self):
    data = "Details for %s (Faculty ID %d):\n\tBio URL:\t%s\n\tPhone number: %s\n\tPicture URL: %s\n\tEmail Address: %s\n\tHigher Education: %s\n\tBio:\n\t\t%s" % (self.full_name, self.faculty_id, self.bio_url, self.phone_number, self.picture_url, self.email_address, self.education, self.selfwritten_bio)
    return data

class FacultyIDIterator:
  def __init__(self, skip, start, end):
    self.skip = skip
    self.start = start
    self.end = end
  def __iter__(self):
    self.a = self.start
    return self
  def next(self):
    self.a = self.a+self.skip
    if self.a>self.end:
      raise StopIteration
    return self.a
  def __str__(self):
    return "Skip: %d\tStart: %s\tEnd: %s\n" % (self.skip, self.start, self.end)

class IterativeWebCrawlerThread(Thread):
  def __init__(self, host, page_location, match_seq_regexp, vary_param, id):
    Thread.__init__(self)
    self.id = id
    self.matching_URIs = []
    self.done_crawling = False
    self.host = host
    self.page_location = page_location
    self.match_seq_regexp = match_seq_regexp
    self.vary_param = vary_param
  def request(self, page_uri):
    req = urlopen(page_uri)
    resp = req.read()
    return resp
  def iterate_through_pages(self):
    print self.vary_param['iterator']
    for param in self.vary_param['iterator']:
      params = urlencode(
        {
          self.vary_param['val'] : str(param)
        }
      )
      url = 'http://' + self.host + self.page_location + '?' + params
      print "\n[* Thread %s] Requesting %s. . .\n" % (self.id, url)
      html = self.request(url)
      try:
        re.search(self.match_seq_regexp, html).group()
        self.matching_URIs.append(url)
      except Exception:
        pass
  def run(self):
    self.iterate_through_pages()
    self.done_crawling = True

class ThreadedIterativeWebCrawler:
  def __init__(self, host, page_location, match_seq_regexp, vary_params, num_threads):
    self.result_URIs = []
    self.crawlers = []
    self.num_threads = num_threads
    self.num_crawling = 0
    self.finished = False
    for i in range(num_threads):
      self.crawlers.append(IterativeWebCrawlerThread(host, page_location, match_seq_regexp, vary_params[i], i))
  def all_child_crawlers_complete(self):
    finished = True;
    for crawler in self.crawlers:
      if crawler.done_crawling==False:
        finished = False
        self.num_crawling -= 1
    return finished
  def crawl(self):
    num = 1
    for crawler in self.crawlers:
      print("[*] Starting thread %d. . ." % (num))
      self.num_crawling += 1
      crawler.start()
      num += 1
  def get_all_result_URIs(self):
    print "\n[*] Waiting for %d children to finish crawling. . .\n" % (self.num_crawling)
    while self.all_child_crawlers_complete()==False:
      pass
    for crawler in self.crawlers:
      for uri in crawler.matching_URIs:
        self.result_URIs.append(uri)
    return self.result_URIs


class AbingtonFriendsCrawler:
  def __init__(self, num_threads, max_id):
    self.num_threads = num_threads
    vary_params = []
    for i in range(num_threads):
      vary_params.append({'val':'fid', 'iterator':FacultyIDIterator(self.num_threads, i, max_id)})
    self.tiwc = ThreadedIterativeWebCrawler("www.abingtonfriends.net", "/Modals/Directories/ViewFacultyBio.aspx", PHONE_REGEX, vary_params, self.num_threads)
  def run(self):
    self.tiwc.crawl()
  def get_results(self):
    return self.tiwc.get_all_result_URIs()

class AbingtonFriendsFacultyDataExtractor:
  def __init__(self, uri):
    self.html = urlopen(uri).read().replace('\xe2\x80\x9c', '"').replace('\xe2\x80\x9d', '"').replace('\xe2\x80\x98', "'").replace('\xe2\x80\x99', "'")
    self.fp = FacultyProfile()
    self.fp.bio_url = uri
    self.fp.faculty_id = int(uri.split('=')[1])
    self.init_faculty_attributes()
  def init_faculty_attributes(self):
    try:
      self.fp.selfwritten_bio = strip_tags(re.search(BIO_REGEX, self.html).group())
    except  Exception:
      self.fp.selfwritten_bio = 'Not Specified'
    try:
      self.fp.full_name = re.search(NAME_FIELD_REGEX, self.html).group().replace("\'88", '')
    except  Exception:
      self.fp.full_name = 'Not Specified'
    try:
      self.fp.phone_number = re.search(PHONE_REGEX, self.html).group()
    except  Exception:
      self.fp.phone_number = 'Not Specified'
    try:
      self.fp.picture_url = 'http://www.abingtonfriends.net' + re.search(PROFILE_PICTURE_REGEX, self.html).group()
    except  Exception:
      self.fp.picture_url = 'Not Specified'
    try:
      self.fp.email_address = re.search(WORK_EMAIL_REGEX, self.html).group()
    except  Exception:
      self.fp.email_address = 'Not Specified'
    try:
      self.fp.education = strip_tags(re.search(COLLEGE_EDUCATION_REGEX, self.html).group())
    except  Exception:
      self.fp.education = 'Not Specified'
  def get_faculty_member_profile(self):
    return self.fp

def init_args():
  parser = argparse.ArgumentParser(description='AFS Scraper\nThis script scrapes information abot different faculty and staff from www.abingtonfirends.net')
  parser.add_argument('-f', '--folder', help='Folder in which to store faculty data, will be created if it doesn\'t exist', required=True)
  parser.add_argument('-t', '--threads', help='Number of threads with which to crawl', type=int, required=True)
  parser.add_argument('-m', '--max', help='Maximum faculty id value to check (default is 400)', type=int, required=False)
  args = parser.parse_args()
  return args

if __name__=="__main__":
  args = init_args()
  max = 400
  if args.max:
    max = args.max
  afc = AbingtonFriendsCrawler(args.threads, max)
  afc.run()
  URIs = afc.get_results()
  profiles = []
  print "[*] Collecting data. . ."
  for URI in URIs:
    ex = AbingtonFriendsFacultyDataExtractor(URI)
    profiles.append(ex.get_faculty_member_profile())
  if not isdir(args.folder):
    mkdir(args.folder)
  chdir(args.folder)

  for profile in profiles:
    print "[*] Writing data for %s to %s.txt\n" % (profile.full_name, profile.full_name.replace(' ', '_'))
    f = open(profile.full_name.replace(' ', '_')+'.txt', 'w')
    f.write(str(profile))
    f.close()
    if not 'Not Specified' in profile.picture_url:
      print "[*] Downloading profile image from %s for %s to %s.jpg" % (profile.picture_url, profile.full_name, profile.full_name.replace(' ', '_'))
      f = open(profile.full_name.replace(' ', '_')+'.jpg', 'wb')
      f.write(urlopen('http://'+quote(profile.picture_url.replace('http://', ''))).read())
      f.close()
