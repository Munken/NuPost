import urllib
import urllib2

import time

import os

import colorama
from colorama import init, Fore, Back, Style
colorama.init(autoreset=True);

log_file = os.path.dirname(__file__) + "/../nutaq.log"

MERGE_SUFFIX = "MERGE/Merge.tml"
TAPE_SUFFIX = "TapeService/TapeService.tml"


class MergeState:
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"


class TapeState:
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"


class NuPost:
    def __init__(self, host, port):
        self._port = port
        self._host = host
        self._m_state = MergeState.STOPPED
        self._t_state = TapeState.STOPPED

        self._t_state, self._run = self.get_tape_state()
        self._m_state = self.get_merge_transfer_state()

    def go(self, prefix, run_num = None):
        if self._t_state != TapeState.STOPPED:
            raise RuntimeError("Cannot GO if TapeServer is not STOPPED")

        if not prefix.endswith("_"):
            prefix += "_"

        if run_num is not None:
            self.set_run_num(run_num)

        self.set_file(prefix)

        if self._m_state == MergeState.STOPPED:
            self.toggle_merge()

        self.send_go(prefix)

        state = None
        run = -1

        for i in range(100):
            time.sleep(0.1)
            state, run = self.get_tape_state()
            if state == TapeState.RUNNING: break

        if state != TapeState.RUNNING:
            raise RuntimeError("Tape have not switched to running state")

        rate = None
        for i in range(100):
            time.sleep(0.1)
            rate = self.get_tape_rate()
            if rate["kbytes"] > 10: break

        if rate["kbytes"] <= 10:
            raise RuntimeError("No data is being written to disc")

        self._t_state = TapeState.RUNNING
        print Fore.GREEN + "%s, %s - Opened file %s%d" % (self.get_local_date(), self.get_local_time(), prefix, run)
	f=open(log_file,'a')
        s=str("%s, %s - Opened file %s%d\n" % (self.get_local_date(), self.get_local_time(), prefix, run))
	f.write(s)
        f.close()

    def stop(self):
        if self._t_state != TapeState.RUNNING:
            raise RuntimeError("Cannot STOP if TapeServer is not RUNNING")

        if self._m_state == MergeState.RUNNING:
            self.toggle_merge()

        success = False
        state = None
        run = -1
        for j in range(10):
            # Attempt to stop NUTAQ
            self.send_stop()

            # Check whether we stopped
            for i in range(100):
                time.sleep(0.1)
                state, run = self.get_tape_state()
                if state == TapeState.STOPPED: break

            if state != TapeState.STOPPED:
                print "Tape has not switched to stopped state! Retrying"
                continue
            elif run != self._run+1:
                # print "Run# has not incremented. Retrying"
                continue
            else:
                sucess = True

        if not sucess:
            print "Stopping TapeServer failed 10 times. Something is broken..."
        else:
            print Fore.RED + "%s, %s - Closed file with %d kB" % (self.get_local_date(), self.get_local_time(), self.get_tape_rate()['kbytes'])
            f=open(log_file,'a')
	    s=str("%s, %s - Closed file with %d kB\n" % (self.get_local_date(), self.get_local_time(), self.get_tape_rate()['kbytes']))
 	    f.write(s)
	    f.close()
	    self._run = run
            self._t_state = TapeState.STOPPED

    def status(self):
        t_state, run = self.get_tape_state()
        m_state = self.get_merge_transfer_state()
       	rate = self.get_tape_rate()
	
	if t_state == TapeState.RUNNING:

            print Fore.GREEN + "TS state:              %s" % t_state
            print Fore.GREEN + "Merge transfer state:  %s" % m_state
            print Fore.GREEN + "Run#:		       %d" % run
            print Fore.GREEN + "Writen: 	       %d kB (%d blocks)" % (rate['kbytes'], rate['block'])


	else:

            print Fore.RED +  "TS state:	      %s" % t_state
            print Fore.RED +  "Merge transfer state:  %s" % m_state
            print Fore.RED +  "Run#:		      %d" % run
            print Fore.RED +  "Writen:  	      %d kB (%d blocks)" % (rate['kbytes'], rate['block'])
	    

    def toggle_merge(self):
        url = self._build_merge_url()
        values = dict(Widget="XFER")
        data = urllib.urlencode(values)
        req = urllib2.Request(url, data)
        rsp = urllib2.urlopen(req)
        rsp.read()

        target = MergeState.RUNNING if self._m_state == MergeState.STOPPED else MergeState.STOPPED

        state = None
        for i in range(100):
            time.sleep(0.1)
            state = self.get_merge_transfer_state()
            if state == target: break

        if state != target:
            raise RuntimeError("Merge transfer state stuck in %s should be %s" % (state, target))

        self._m_state = state

        return rsp.read()

    def set_file(self, prefix):
        url = "http://%s:%d/%s" % (self._host, self._port, TAPE_SUFFIX)
        data = "Widget=RUNNAME+%s&DEVNAMES=%%2Fdev%%2Ffile%%2F0&VOLN=IS605&FILEN=T113&RUNNAME=G&RUNNUM=114&BLOCKS=0&KBYTES=0&RATE=0&PERCENT=0&SERVERSTATE=0" % prefix
        req = urllib2.Request(url, data)
        rsp = urllib2.urlopen(req)
        return rsp.read()

    def send_go(self, prefix):
        n = 110
        filename = "%s%s" % (prefix, n)

        url = "http://%s:%d/%s" % (self._host, self._port, TAPE_SUFFIX)
        data = "Widget=SERVERSTATE+1&DEVNAMES=%%2Fdev%%2Ffile%%2F0&VOLN=IS605&FILEN=%s&RUNNAME=%s&RUNNUM=%s&BLOCKS=0&KBYTES=0&RATE=0&PERCENT=0&SERVERSTATE=1" \
               % (filename, prefix, n)
        req = urllib2.Request(url, data)
        rsp = urllib2.urlopen(req)
        return rsp.read()

    def send_stop(self):
        url = "http://%s:%d/%s" % (self._host, self._port, TAPE_SUFFIX)
        data = 'Widget=SERVERSTATE+0&DEVNAMES=%2Fdev%2Ffile%2F0&VOLN=IS605&FILEN=R86&RUNNAME=R&RUNNUM=87&BLOCKS=0&KBYTES=0&RATE=0&PERCENT=0&SERVERSTATE=1'
        req = urllib2.Request(url, data)
        rsp = urllib2.urlopen(req)
        return rsp.read()

    def _build_url(self):
        return "http://%s:%d" % (self._host, self._port)

    def get_merge_transfer_state(self):
        response = urllib2.urlopen(self._build_merge_url())
        html = response.read()

        return MergeState.STOPPED if "no xfer" in html else MergeState.RUNNING

    def _build_merge_url(self):
        return "http://%s:%d/%s" % (self._host, self._port, MERGE_SUFFIX)

    def get_tape_state(self):
        try:
            res = self._send_soap(build_soap_command("InquireAcqStatus"))
            split = res['result'].split()

            state = TapeState.RUNNING if int(split[1]) == 2 else TapeState.STOPPED
            run = int(split[-1])

            return state, run
        except urllib2.HTTPError, error:
            contents = error.read()
            print contents
            raise
    
    def get_local_date(self):
         from time import strftime, localtime
         return str(strftime("%a, %d %b %Y", localtime())) 
         
    def get_local_time(self):
         from time import strftime, localtime
         return str(strftime("%X", localtime()))

    def get_tape_rate(self):
        try:
            res = self._send_soap(build_stream_state_soap())
            split = res['result'].split()

            blocks = int(split[2])
            kbytes = int(split[3])
            avg = int(split[3])

            return dict(block=blocks, kbytes=kbytes, avg=avg)
        except urllib2.HTTPError, error:
            contents = error.read()
            print contents
            raise

    def set_run_num(self, n):
        try:
            res = self._send_soap(build_set_num_soap(n))

            if "result" not in res or res["result"] != "0 OK":
                raise RuntimeError("Setting run number failed")

            state, run = self.get_tape_state()
            if n != run:
                raise RuntimeError("Run number not changed to %n. Currently %d", n, run)

            print "Run number successfully changed to %d" % n

        except urllib2.HTTPError, error:
            contents = error.read()
            print contents
            raise

    def _send_soap(self, soap):
        try:
            headers = {
               'Accept-Encoding': 'identity',
               'Content-Type': 'application/xml; charset=utf-8',
               'SOAPAction': '""'
            }
            req = urllib2.Request("%s/TapeServer" % self._build_url(), soap, headers)
            response = urllib2.urlopen(req)
            res = parse_soap(response.read())
            return res
        except urllib2.HTTPError, error:
            contents = error.read()
            print contents
            raise


def build_soap_command(command):
    return '<SOAP-ENV:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:ns0="urn:TapeServer" SOAP-ENV:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><SOAP-ENV:Body><ns0:%s></ns0:%s></SOAP-ENV:Body></SOAP-ENV:Envelope>' % (command, command)


def build_stream_state_soap():
    return build_int_soap("InquireStreamState", "stream", 1)


def build_set_num_soap(n):
    return build_int_soap("SetRunNumber", "n", n)


def build_int_soap(command, argument, n):
    return '<?xml version="1.0" encoding="UTF-8"?><SOAP-ENV:Envelope xmlns:xsi="http://www.w3.org/1999/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:xsd="http://www.w3.org/1999/XMLSchema" SOAP-ENV:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><SOAP-ENV:Body><ns:%s xmlns:ns="urn:TapeServer"><%s xsi:type="xsd:int">%d</%s></ns:%s></SOAP-ENV:Body></SOAP-ENV:Envelope>' % \
            (command, argument, n, argument, command)


def parse_soap(xml):
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml)
    ns = {'SOAP-ENV': 'http://schemas.xmlsoap.org/soap/envelope/',
          'ns': 'urn:DataAcquisitionControlServer'}

    d = dict()

    for t in root.find("./SOAP-ENV:Body/*", ns):
        d[t.tag] = t.text

    return d
