#! /usr/bin/env python 

import sys
import flowtools
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch import helpers
#import GeoIP
import pygeoip
from pprint import pprint

flowFile = sys.argv[1]
flowData = []

geoCity = pygeoip.GeoIP("/usr/local/share/GeoIP/GeoLiteCity.dat")
geoIP   = pygeoip.GeoIP("/usr/local/share/GeoIP/GeoIP.dat")
geoIPAS = pygeoip.GeoIP("/usr/local/share/GeoIP/GeoIPASNum.dat")

esHost = "10.1.1.2"
esIndex = 'flowstash-%(date)s' % {"date": datetime.utcnow().strftime("%Y.%m.%d") }
esIndexSettings = {
                   "settings": {
                     "number_of_shards": 5,
                     "number_of_replicas": 0,
                    }
                  }

for flow in flowtools.FlowSet( flowFile ):

  if flow.first.is_integer():
    first_pkt = datetime.utcfromtimestamp(flow.first) + ".000000"
  else:
    first_pkt = datetime.utcfromtimestamp(flow.first)

  if flow.last.is_integer():
    last_pkt = datetime.utcfromtimestamp(flow.last) + ".000000"
  else:
    last_pkt = datetime.utcfromtimestamp(flow.last)

  currentFlow = {
                 '_index': esIndex,
                 '_type': 'netflow',
                 '_source': {
                   '@timestamp': last_pkt,
                   'dOctets':    flow.dOctets,
                   'dPackets':   flow.dPkts,
                   'dstaddr':    flow.dstaddr,
                   'dstport':    flow.dstport,
                   'rtr_addr':   flow.exaddr,
                   'first_pkt':  first_pkt,
                   'last_pkt':   last_pkt,
                   'protocol':   flow.prot,
                   'src_addr':   flow.srcaddr,
                   'src_port':   flow.srcport,
                   'rtr_uptime': flow.sysUpTime,
                   'tcp_flags':  flow.tcp_flags,
                   'unix_nsecs': flow.unix_nsecs,
                   'unix_secs':  flow.unix_secs, 
                  }
                }

  if geoIPAS.asn_by_addr(flow.dstaddr):
    splitResponse = geoIPAS.asn_by_addr(flow.dstaddr).split(' ',1)
    currentFlow['_source']['dst_asn'] = splitResponse[0].rsplit("AS")[1]
    if len(splitResponse) > 1:
      currentFlow['_source']['dst_asn_name'] = splitResponse[1]

  if geoIPAS.asn_by_addr(flow.srcaddr):
    splitResponse = geoIPAS.asn_by_addr(flow.srcaddr).split(' ',1)
    currentFlow['_source']['src_asn'] = splitResponse[0].rsplit("AS")[1]
    if len(splitResponse) > 1:
      currentFlow['_source']['src_asn_name'] = splitResponse[1]

  #check if source address is valid
  if geoIP.country_code_by_addr(flow.srcaddr):
    countryData = geoCity.record_by_addr(flow.srcaddr)

    currentFlow['_source']['src_geodata'] = []
    if countryData['longitude']:
      currentFlow['_source']['src_geodata'].append(countryData['longitude'])
    if countryData['latitude']:
      currentFlow['_source']['src_geodata'].append(countryData['latitude'])

    for key in countryData:
      if countryData[key]:
        keyName = "src_" + key
        currentFlow['_source'][keyName] = countryData[key]

  #check if destination address is valid
  if geoIP.country_code_by_addr(flow.dstaddr):
    countryData = geoCity.record_by_addr(flow.dstaddr)

    currentFlow['_source']['dst_geodata'] = []
    if countryData['longitude']:
      currentFlow['_source']['dst_geodata'].append(countryData['longitude'])
    if countryData['latitude']:
      currentFlow['_source']['dst_geodata'].append(countryData['latitude'])

    for key in countryData:
      if countryData[key]:
        keyName = "dst_" + key
        currentFlow['_source'][keyName] = countryData[key]
      
  flowData.append( currentFlow )

es = Elasticsearch([esHost], sniff_on_start=True)
es.indices.create(index=esIndex, body = esIndexSettings, ignore=400)

if len(flowData) > 0:
  helpers.bulk(es, flowData)
 
