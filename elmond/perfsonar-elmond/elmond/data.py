from .util import *
from werkzeug.exceptions import BadRequest, NotImplemented
from .filters import build_time_filter
import re

DEFAULT_RESULT_LIMIT=1000
MAX_RESULT_LIMIT=10000
DEFAULT_SUMMARY_WINDOW_ROLLUP_NAME = {
    "300": "5m",
    "3600": "1h",
    "86400": "1d",
}
DATA_FIELD_MAP = {
    "failures/base": "result.error",
    "histogram-owdelay/base": "result.latency.histogram",
    "histogram-owdelay/statistics": "result.latency",
    "histogram-ttl/base": "result.ttl.histogram",
    "histogram-ttl/statistics": "result.ttl",
    "histogram-rtt/base": "result.rtt.histogram",
    "histogram-rtt/statistics": "result.rtt",
    "packet-count-lost/aggregations": "result.value",
    "packet-count-lost/base": "result.packets.lost",
    "packet-count-lost-bidir/aggregations": "result.value",
    "packet-count-lost-bidir/base": "result.packets.lost",
    "packet-count-sent/aggregations": "result.value",
    "packet-count-sent/base": "result.packets.sent",
    "packet-duplicates/base": "result.packets.duplicated",
    "packet-duplicates-bidir/base": "result.packets.duplicated",
    "packet-loss-rate/aggregations": "result.value",
    "packet-loss-rate/base": "result.packets.loss",
    "packet-loss-rate-bidir/aggregations": "result.value",
    "packet-loss-rate-bidir/base": "result.packets.loss",
    "packet-reorders/base": "result.packets.reordered",
    "packet-reorders-bidir/base": "result.packets.reordered",
    "packet-retransmits/base": "result.retransmits",
    "packet-retransmits-subintervals/base": "result.intervals.json",
    "packet-trace/base": "result.json",
    "packet-trace-multi/base": "result.json",
    "path-mtu/base": "result.mtu",
    "streams-packet-retransmits/base": "result.streams.json",
    "streams-packet-retransmits-subintervals/base": "result.intervals.json",
    "streams-throughput/base": "result.streams.json",
    "streams-throughput-subintervals/base": "result.intervals.json",
    "throughput/averages": "result.throughput",
    "throughput/base": "result.throughput",
    "throughput-subintervals/base": "result.intervals.json",
    "time-error-estimates/base": "result.max_clock_error",
    "pscheduler-run-href/base": "pscheduler.run_href"
}
CONVERSION_FACTOR_MAP = {
    "histogram-rtt": 1000 #convert rtt to ms
}

log = logging.getLogger('elmond')
    
def _build_esmond_histogram(elastic_histo, conversion_factor=1):
    values = elastic_histo.get("values", [])
    counts = elastic_histo.get("counts", [])
    #make sure same length
    num_buckets = len(values)
    if  num_buckets != len(counts):
        return None
    #build new type
    esmond_histo = {}
    for i in range(num_buckets):
        try:
            esmond_histo[str(values[i]*conversion_factor)] = int(counts[i])
        except ValueError as e:
            return None
    
    return esmond_histo

def _parse_compound_key(event_type):
    #Extract the field we want from streams, intervals and stream intervals
    event_type = re.sub(r'^streams-', "", event_type)
    event_type = re.sub(r'-subintervals$', "", event_type)
    key = DATA_FIELD_MAP.get("{0}/base".format(event_type), None)
    if key is None:
        return None
    else:
        #kinda a hack, but works
        key = re.sub("_", "-", key)
    
    return key
        
def _extract_result_field(key, result):
    key_parts = key.split('.')
    #pop off result at beginning
    key_parts.pop(0)
    curr_field = result
    for key_part in key_parts:
        #pull out the field
        try:
            curr_field = curr_field.get(key_part, None)
        except:
            #handle error because of unexpected object structure
            log.error("Error while extracting field {0}.".format(key_part))
            return None
        #if didn't find field, then return None
        if curr_field is None:
            return None
    
    return curr_field

def _extract_result_stats(key, result, is_rollup=False, conversion_factor=1):
    stats = {}
    if is_rollup:
        stat_fields = ["maximum", "mean", "median", "minimum", "mode", "percentile-25", "percentile-75", "percentile-95", "standard-deviation", "variance"]
        for sf in stat_fields:
            #note that date_histo isn't really needed and is popped-off by _extract_result_field
            stats[sf] = _extract_result_field("date_histo.{0}_{1}.value".format(key, sf), result)
            if sf == "mode":
                stats[sf] = [ stats[sf] ]
    else:
        field = _extract_result_field(key, result)
        if field is None:
            return None
        stats = {
            "maximum": field.get("max", None),
            "mean": field.get("mean", None),
            "median": field.get("median", None),
            "minimum": field.get("min", None),
            "mode": field.get("mode", None),
            "percentile-25": field.get("p_25", None),
            "percentile-75": field.get("p_75", None),
            "percentile-95": field.get("p_95", None),
            "standard-deviation": field.get("stddev", None),
            "variance": field.get("variance", None)
        }
    
    #do any conversion as needed
    for stat in stats:
        if stats[stat] is not None:
            if stat == "mode":
                try:
                    stats[stat] = [float(m)*conversion_factor for m in stats[stat]]
                except:
                    continue
            else:
                stats[stat] = float(stats[stat])*conversion_factor
        
    return stats

def _extract_result_subinterval(key, interval_obj):
    start = interval_obj.get("start", None)
    end = interval_obj.get("end", None)
    if start is None or end is None:
        return None
    duration = end - start
    val = _extract_result_field(key, interval_obj)
    if val is None:
        return None
    
    return { "start": start, "duration": duration, "val": val }
    
def _extract_result_subintervals(key, result, event_type, streams=False):
    #extract interval field
    intervals = _extract_result_field(key, result)
    if intervals is None:
        return None
    #figure out which key we are looking for by taking advantage of structure of
    # subinterval event type name
    interval_key = _parse_compound_key(event_type)
    if interval_key is None:
        return None
    
    esmond_intervals = []
    stream_intervals = {}
    for interval in intervals:
        if not streams and interval.get("summary", None):
            esmond_interval = _extract_result_subinterval(interval_key, interval["summary"])
            if esmond_interval:
                esmond_intervals.append(esmond_interval)
        elif streams and interval.get("streams", None):
            #organize interval info by stream
            for stream in interval["streams"]:
                stream_id = stream['stream-id']
                if not stream_id:
                    continue
                esmond_si = _extract_result_subinterval(interval_key, stream)
                if not esmond_si:
                    continue
                if stream_id not in stream_intervals:
                    stream_intervals[stream_id] = []
                stream_intervals[stream_id].append(esmond_si)

    #if streams now make a sorted array of arrays
    if streams:
        for id in sorted(stream_intervals):
            esmond_intervals.append(stream_intervals[id])
    
    return esmond_intervals

def _extract_result_streams(key, result, event_type):
    #extract streams field
    streams = _extract_result_field(key, result)
    if streams is None:
        return None
    #figure out field we want in the stream
    stream_key = _parse_compound_key(event_type)
    log.debug("stream_key={0}".format(stream_key))
    if stream_key is None:
        return None
    #parse streams
    vals = []
    log.debug("streams={0}".format(streams))
    for stream in streams:
        vals.append(_extract_result_field(stream_key, stream))

    return vals

def _extract_packet_trace(key, result, event_type):
    paths = _extract_result_field(key, result)
    packet_trace_multi = []
    packet_trace = None
    mtu = None  # current mtu
    for path in paths:
        formatted_path = []
        for (hop_num, hop) in enumerate(path):
            formatted_hop = {}
            formatted_hop['ttl'] = hop_num + 1
            formatted_hop['query'] = 1 #trace test doesn't support multiple  queries
            #determine success
            if hop.get("error", None):
                formatted_hop['success'] = 0
                formatted_hop['error-message'] = hop["error"]
            else:
                formatted_hop['success'] = 1
            #figure out what other info we have
            if hop.get("ip", None): 
                formatted_hop['ip'] = hop['ip']
            if hop.get("hostname", None): 
                formatted_hop['hostname'] = hop['hostname']
            if hop.get("as", None): 
                formatted_hop['as'] = hop['as']
            if ("rtt" in hop) and (hop["rtt"] is not None): 
                formatted_hop['rtt'] = iso8601_to_seconds(hop['rtt'])*1000 #convert to ms
            if ("mtu" in hop) and (hop["mtu"] is not None): 
                formatted_hop['mtu'] = hop["mtu"]
                mtu = hop["mtu"]
            elif mtu is not None:
                formatted_hop['mtu'] = mtu
            formatted_path.append(formatted_hop)
        #append formatted path to list of paths
        packet_trace_multi.append(formatted_path)
        #add first path as packet-trace path - need this for backward compatibility
        if not packet_trace:
            packet_trace = formatted_path
    
    #return correct packet trace
    if event_type.endswith('multi'):
        return packet_trace_multi
    
    return packet_trace

def _build_result_agg(event_type, summary_type):
    agg = None
    agg_field = DATA_FIELD_MAP.get("{0}/base".format(event_type), None)
    if summary_type == "aggregations" and event_type.startswith("packet-loss-rate"):
        #packet loss rate aggregation total lost and sent then divide
        agg = {
            "result_lost": {
                "sum": {
                    "field": DATA_FIELD_MAP["packet-count-lost/base"]
                }
            },
            "result_sent": {
                "sum": {
                    "field": DATA_FIELD_MAP["packet-count-sent/base"]
                }
            },
            "result": {
                "bucket_script": {
                    "buckets_path": {
                        "lost": "result_lost",
                        "sent": "result_sent"
                    },
                    "script": "params.lost / params.sent"
                }

            }
        }
    elif summary_type == "aggregations":
        agg = {
            "result": {
                "sum": {
                    "field": agg_field
                }
            }
        }
    elif summary_type == "averages":
        agg = {
            "result": {
                "avg": {
                    "field": agg_field
                }
            }
        }
    elif summary_type == "statistics":
        agg_field = DATA_FIELD_MAP.get("{0}/statistics".format(event_type), None)
        agg = {
            "result_maximum": {
                "max": {
                    "field": "{0}.max".format(agg_field)
                }
            },
            "result_minimum": {
                "min": {
                    "field": "{0}.min".format(agg_field)
                }
            },
            "result_mean": {
                "avg": {
                    "field": "{0}.mean".format(agg_field)
                }
            },
            "result_median": {
                "avg": {
                    "field": "{0}.median".format(agg_field)
                }
            },
            "result_mode": {
                "avg": {
                    "field": "{0}.mode".format(agg_field)
                }
            },
            "result_percentile-25": {
                "avg": {
                    "field": "{0}.p_25".format(agg_field)
                }
            },
            "result_percentile-75": {
                "avg": {
                    "field": "{0}.p_75".format(agg_field)
                }
            },
            "result_percentile-95": {
                "avg": {
                    "field": "{0}.p_95".format(agg_field)
                }
            },
            "result_standard-deviation": {
                "avg": {
                    "field": "{0}.stddev".format(agg_field)
                }
            },
            "result_variance": {
                "avg": {
                    "field": "{0}.variance".format(agg_field)
                }
            }
        }
    
    return agg

class EsmondData:

    def __init__(self, es):
        self.es = es
    
    def fetch(self, metadata_key, event_type, summary_type, summary_window, q={}):
        log.debug("{0} {1}".format(summary_type, summary_window))
        #convert summary window to int
        try:
            summary_window = int(summary_window)
        except ValueError as e:
            raise BadRequest("Summary window must be an int")
        
        #determine whether we are hitting normal or rollup index
        #hit * because event types can belong to multiple test types
        #probably a may efficient way to do this
        is_rollup=False
        raw_type = False
        dfm_key = None
        index_name="pscheduler_*"
        time_field = "pscheduler.start_time"
        checksum_field = "pscheduler.test_checksum"
        if summary_window > 0:
            is_rollup=True

        #handle limit and offset
        result_size = DEFAULT_RESULT_LIMIT
        result_offset = 0
        if q.get(LIMIT_FILTER, None):
            try:
                result_size = int(q[LIMIT_FILTER])
            except ValueError:
                raise BadRequest("{0} parameter must be an integer".format(LIMIT_FILTER))
        if q.get(OFFSET_FILTER, None):
            try:
                result_offset = int(q[OFFSET_FILTER])
            except ValueError:
                raise BadRequest("{0} parameter must be an integer".format(OFFSET_FILTER))
        if result_size > MAX_RESULT_LIMIT:
            raise BadRequest("{0} parameter cannot exceed {1}".format(LIMIT_FILTER, MAX_RESULT_LIMIT))

        #data query
        dsl = {
            "query": {
              "bool": {
                "filter": [
                  {
                    "term": {
                      checksum_field: metadata_key
                    }
                  }
                ]
              }
            }
        }
        #Add rollup and non-rollup specific filters
        if is_rollup:
            #make sure we are getting the right window
            sw_map = app.config.get('ELMOND', {}).get('SUMMARY_WINDOW_ROLLUP_NAMES', None)
            if not sw_map:
                sw_map = DEFAULT_SUMMARY_WINDOW_ROLLUP_NAME
            sw=str(summary_window)
            if sw not in sw_map:
                raise BadRequest("{0} is not a supported summary_window".format(sw))
            result_agg = _build_result_agg(event_type, summary_type)
            if result_agg is None:
                raise BadRequest("Unable to build aggregation for {0}/{1}".format(event_type, summary_type))
            dsl["size"] = 0
            dsl["_source"] = False
            dsl["aggs"] = {
                "date_histo": {
                    "date_histogram": {
                        "field": time_field,
                        "min_doc_count": 1, 
                        "fixed_interval": sw_map[sw]
                    },
                    "aggs": result_agg
                }
            }
        else:
            #set filters used in raw data queries
            dsl["size"] = result_size
            dsl["from"] = result_offset
            dsl["_source"] = [ time_field ]
            dsl["sort"] = [
              {
                time_field: {
                  "order": "asc"
                }
              }
            ]
            #optimization: filter based on whether we want succeeded or not
            succeeded_filter_val = (event_type != 'failures')
            dsl["query"]["bool"]["filter"].append({ "term": { "result.succeeded": succeeded_filter_val } })
            #limit fields returned
            dfm_key = "{0}/{1}".format(event_type, summary_type)
            raw_type = True
            if dfm_key in DATA_FIELD_MAP:
                raw_type = False
                if isinstance(DATA_FIELD_MAP[dfm_key], list):
                    dsl["_source"].extend(DATA_FIELD_MAP[dfm_key])
                else:
                    dsl["_source"].append(DATA_FIELD_MAP[dfm_key])
            elif event_type == "pscheduler-raw":
                dsl["_source"].append("result.*")
            else:
                raise BadRequest("Unrecognized event type {0}".format(event_type))
        
        #handle time filters
        time_filter = build_time_filter(q, time_field=time_field)
        if time_filter:
            dsl["query"]["bool"]["filter"].append(time_filter)
            
        #exec query
        log.info("index_name={} event_type={} dsl={}".format(index_name, event_type, dsl))
        res = self.es.search(index=index_name, body=dsl)
        #handle results
        hits = []
        if is_rollup:
            hits = res.get("aggregations", {}).get("date_histo", {}).get("buckets", [])
        else:
            hits = res.get("hits", {}).get("hits", [])
        #parse results
        data = []
        for hit in hits:
            #get timestamp
            result={}
            psched_result = {}
            if is_rollup:
                #already a timestamp
                ts = hit.get("key", None)
                if ts:
                    ts = int(int(ts)/1000)
                result = hit
            else:
                #date string we have to convert
                ts = datestr_to_timestamp(hit.get("_source", {}).get("pscheduler", {}).get("start_time", None))
                result = hit.get("_source", {}).get("result", None)
                psched_result = hit.get("_source", {}).get("pscheduler", None)
            if not ts or (event_type.startswith("pscheduler-run-href") and not psched_result) or (not event_type.startswith("pscheduler-run-href") and not result):
                continue
            datum = { "ts": ts }
            #get value - event type specific. 
            # Note: right now it either spits out an empty string or just gives raw results for unsupported event types
            if raw_type:
                datum["val"] = result
            elif event_type.startswith("histogram-") and summary_type == "statistics":
                conversion_factor = CONVERSION_FACTOR_MAP.get(event_type, 1)
                result_stat_key = "result"
                if dfm_key is not None and dfm_key in DATA_FIELD_MAP:
                    result_stat_key = DATA_FIELD_MAP[dfm_key]
                datum["val"] = _extract_result_stats(result_stat_key, result, is_rollup=is_rollup, conversion_factor=conversion_factor)
            elif event_type.startswith("histogram-"):
                conversion_factor = CONVERSION_FACTOR_MAP.get(event_type, 1)
                hist = _extract_result_field(DATA_FIELD_MAP[dfm_key], result)
                if not hist:
                    continue
                datum["val"] = _build_esmond_histogram(hist, conversion_factor=conversion_factor)
            elif event_type.startswith("streams") and event_type.endswith("subintervals"):
                datum["val"] = _extract_result_subintervals(DATA_FIELD_MAP[dfm_key], result, event_type, streams=True)
            elif event_type.startswith("streams"):
                datum["val"] = _extract_result_streams(DATA_FIELD_MAP[dfm_key], result, event_type)
            elif event_type.endswith("subintervals"):
                datum["val"] = _extract_result_subintervals(DATA_FIELD_MAP[dfm_key], result, event_type)
            elif event_type.startswith("packet-trace"):
                datum["val"] = _extract_packet_trace(DATA_FIELD_MAP[dfm_key], result, event_type)
            elif event_type == 'failures':
                err_msg =  _extract_result_field(DATA_FIELD_MAP[dfm_key], result)
                if err_msg is None:
                    continue
                datum["val"] = { "error": err_msg }
            elif is_rollup:
                #rollups of single values
                datum["val"] = result.get("result", {}).get("value", None)
            elif event_type.startswith("pscheduler-run-href"):
                #special case where JSON is not in result, but in pscheduler section
                datum["val"] = _extract_result_field(DATA_FIELD_MAP[dfm_key], psched_result)
            else:
                #extract from the map
                datum["val"] = _extract_result_field(DATA_FIELD_MAP[dfm_key], result)
            
            #if we didn't find anything continue - esmond never ha s a null point (i think)
            if datum["val"] is None:
                continue
            
            #add to list of data
            data.append(datum)    

        return data

