#!/usr/bin/env python
# aka carmendiff. cc dolapo.

import json
import urllib
import urllib2
import re
import sys
import math
import os
import datetime
import Queue
import threading
import traceback
from collections import defaultdict
from optparse import OptionParser

# TODO: move this to thrift

parser = OptionParser(usage="%prog [input_file]")
parser.add_option("-o", "--old", dest="serverOld")
parser.add_option("-n", "--new", dest="serverNew")
parser.add_option("-c", "--countMode", action="store_true", default=False, dest="inCountMode")
(options, args) = parser.parse_args()

if not options.serverOld:
  print 'missing old server'
  parser.print_usage()
  sys.exit(1)

if not options.serverNew:
  print 'missing new server'
  parser.print_usage()
  sys.exit(1)

if len(args) == 0:
  print 'weird number of remaining args'
  parser.print_usage()
  sys.exit(1)

inputFile = args[0]

outputFilename = ('dist/twofishes/eval/eval-%s.html' % datetime.datetime.now()).replace(' ', '_')

if not os.path.exists('dist/twofishes/eval'):
  os.makedirs('dist/twofishes/eval')
if os.path.exists("dist/twofishes/eval/eval-latest.html"):
  os.unlink("dist/twofishes/eval/eval-latest.html")
os.symlink(os.path.abspath(outputFilename), "dist/twofishes/eval/eval-latest.html")

outputFile = open(outputFilename, 'w')
outputFile.write('<meta charset="utf-8">')

def getUrl(server, param):
  if not server.startswith('http'):
    server = 'http://%s' % server
  return server.rstrip('/') + '/' + param.lstrip('/')

def getResponse(server, param):
  try:
    response = urllib2.urlopen(getUrl(server, param))
    json_response = json.loads(response.read())
    return json_response
  except Exception as e:
    print e
    print getUrl(server, param)
    return None

# Haversine formula, see http://www.movable-type.co.uk/scripts/gis-faq-5.1.html
def earthDistance(lat_1, long_1, lat_2, long_2):
  # Convert from decimal degrees to radians.
  lat_1 = lat_1 * math.pi / 180
  lat_2 = lat_2 * math.pi / 180
  long_1 = long_1 * math.pi / 180
  long_2 = long_2 * math.pi / 180

  dlong = long_2 - long_1
  dlat = lat_2 - lat_1
  a = (math.sin(dlat / 2))**2 + math.cos(lat_1) * math.cos(lat_2) * (math.sin(dlong / 2))**2
  c = 2 * math.asin(min(1, math.sqrt(a)))
  dist = 3956 * c
  return dist

evalLogDict = defaultdict(lambda : defaultdict(list))
queue = Queue.Queue()

count = 0

class GeocodeFetch(threading.Thread):
  def __init__(self, queue):
    threading.Thread.__init__(self)
    self.queue = queue

  def run(self):
    global count
    while True:
      line = self.queue.get()
      lineCount = 1

      if options.inCountMode:
        m = re.match(r' *(\d+) (.*)', line)
        if not m:
          print('line did not conform to count mode: %s' % line)
          self.queue.task_done()
          continue
        else:
          line = m.group(2)
          lineCount = int(m.group(1))

      if count % 100 == 0:
        print 'processed %d queries' % count
      #print 'processed %d queries' % count
      #print 'procesing: %s' % line
      count += 1

      param = line.strip()
      import urlparse

      if '?' not in param:
        param = '?' +  urllib.urlencode([('query', param)])
      param_str = param[param.find('?')+1:]
      params = urlparse.parse_qs(param_str)

      responseOld = getResponse(options.serverOld, param)
      responseNew = getResponse(options.serverNew, param)

      def getId(response):
        if (response and
            'interpretations' in response and
            len(response['interpretations']) and
            'feature' in response['interpretations'][0] and
            'ids' in response['interpretations'][0]['feature']):
          return response['interpretations'][0]['feature']['ids']
        else:
          return ''

      def mkString(o):
        if isinstance(o, basestring):
          return o
        # elif isinstance(o, list):
        #   return ', '.join(o)
        else:
          return str(o)

      def evallog(title, old = None, new = None):
        responseKey = '%s:%s' % (getId(responseOld), getId(responseNew))

        query = ''
        if 'query' in params:
          query = params['query'][0]
        elif 'll' in params:
          query = params['ll'][0]
        elif 'json' in params:
          query = params['json'][0]

        extraTitle = ''
        # if we only got one extra argument, assume it's more info for the title
        if old and not new:
          extraTitle = old
          old = ''

        oldMessage = ''
        newMessage = ''
        if old:
          oldMessage = ': '  + mkString(old).encode('utf-8')
        if new:
          newMessage = ': ' + mkString(new).encode('utf-8')

        if 'json' in params:
          message = ('%s: %s %s<ul>' % (query, title, extraTitle) +
                   '<li><a href="%s">OLD</a>%s ' % (options.serverOld + param, oldMessage) +
                   '<li><a href="%s">NEW</a>%s' % (options.serverNew + param, newMessage) +
                   '</ul>')
        else:
          message = ('%s: <b>%s</b><ul>' % (query, title) +
                   '<li><a href="%s">OLD</a>%s' % (options.serverOld + '/twofishes-static/geocoder.html#' + param_str, oldMessage) +
                   '<li><a href="%s">NEW</a>%s' % (options.serverNew + '/twofishes-static/geocoder.html#' + param_str, newMessage) +
                    '</ul>')

        for i in xrange(0, lineCount):
          evalLogDict[title][responseKey].append(message)

      if (responseOld == None and responseNew == None):
        pass
      elif (responseOld == None and responseNew != None):
        evallog('error from OLD, something from NEW')
      elif (responseNew == None and responseOld != None):
        evallog('error from NEW, something from OLD')
      elif (len(responseOld['interpretations']) == 0 and
          len(responseNew['interpretations']) > 0):
        evallog('geocoded NEW, not OLD')

      elif (len(responseOld['interpretations']) > 0 and
          len(responseNew['interpretations']) == 0):
        evallog('geocoded OLD, not NEW')

      elif (len(responseOld['interpretations']) and len(responseNew['interpretations'])):
        interpA = responseOld['interpretations'][0]
        interpB = responseNew['interpretations'][0]

        oldIds = [str(interp['feature']['ids'][0]) for interp in responseOld['interpretations']]
        newIds = [str(interp['feature']['ids'][0]) for interp in responseNew['interpretations']]


        if len(interpA['what']) < len(interpB['what']):
          evallog('geocoded LESS', interpA['where'], interpB['where'])
        elif len(interpA['what']) > len(interpB['what']):
          evallog('geocoded MORE', interpA['where'], interpB['where'])
        elif interpA['feature']['ids'] != interpB['feature']['ids'] and \
            interpA['feature']['woeType'] != 11 and \
            interpB['feature']['woeType'] != 11 and \
            interpA['feature']['ids'] != filter(lambda x: x['source'] != 'woeid', interpB['feature']['ids']):
          if set(oldIds) == set(newIds):
            evallog('interp order changed', ', '.join(oldIds), ', '.join(newIds))
          else:
            evallog('ids changed', interpA['feature']['ids'], interpB['feature']['ids'])
        else:
          scoresA = interpA.get('scores', {})
          scoresB = interpB.get('scores', {})
          geomA = interpA['feature']['geometry']
          geomB = interpB['feature']['geometry']
          centerA = geomA['center']
          centerB = geomB['center']
          distance = earthDistance(
            centerA['lat'],
            centerA['lng'],
            centerB['lat'],
            centerB['lng'])
          if distance > 0.1:
            evallog('center moved', '%s miles' % distance)
          if 'bounds' in geomA and 'bounds' not in geomB:
            evallog('bounds in OLD, but not NEW')
          elif 'bounds' not in geomA and 'bounds' in geomB:
            evallog('bounds in NEW, but not OLD')
          elif 'bounds' in geomA and 'bounds' in geomB and geomA['bounds'] != geomB['bounds']:
            evallog('bounds differ')
          elif (len(responseOld['interpretations']) != len(responseNew['interpretations'])):
            evallog('# of interpretations differ')
          elif interpA['feature']['displayName'] != interpB['feature']['displayName']:
            evallog('displayName changed', interpA['feature']['displayName'], interpB['feature']['displayName'])
          elif 'wktGeometry' in geomA and 'wktGeometry' in geomB and geomA['wktGeometry'] != geomB['wktGeometry']:
            evallog('polygon geometries differ')
          elif abs(scoresA.get('percentOfRequestCovered', 0.0) - scoresB.get('percentOfRequestCovered', 0.0)) > 0.000001:
            evallog('percentOfRequestCovered differ')
          elif abs(scoresA.get('percentOfFeatureCovered', 0.0) - scoresB.get('percentOfFeatureCovered', 0.0)) > 0.000001:
            evallog('percentOfFeatureCovered differ')

      self.queue.task_done()

if __name__ == '__main__':
  print "going"
  for i in range(50):
    t = GeocodeFetch(queue)
    t.setDaemon(True)
    t.start()

  for line in open(inputFile):
    queue.put(line.strip())

  queue.join()

  for (sectionName, sectionDict) in evalLogDict.iteritems():
    outputFile.write('<li><a href="#%s">%s</a>: %s changes' % (sectionName, sectionName, len(sectionDict)))

  for (sectionName, sectionDict) in evalLogDict.iteritems():
    outputFile.write('<a name="%s"><h2>%s</h2></a>' % (sectionName, sectionName))
    for k in sorted(sectionDict, key=lambda x: -1*len(sectionDict[x])):
      outputFile.write('%d changes\n<br/>' % len(sectionDict[k]))
      outputFile.write(sectionDict[k][0])

