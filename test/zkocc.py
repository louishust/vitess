#!/usr/bin/python

from optparse import OptionParser
import os
import socket
from subprocess import check_call, Popen, CalledProcessError, PIPE
import tempfile
import time
import datetime

from zk import zkocc

import utils

vttop = os.environ['VTTOP']
vtroot = os.environ['VTROOT']
hostname = socket.gethostname()

def setup():
  utils.prog_compile(['zkocc',
                      'zkclient2',
                      ])
  utils.zk_setup()

def teardown():
  if utils.options.skip_teardown:
    return
  utils.zk_teardown()
  utils.kill_sub_processes()
  utils.remove_tmp_files()

def _populate_zk():
  utils.zk_wipe()

  utils.run(vtroot+'/bin/zk touch -p /zk/test_nj/zkocc1')
  utils.run(vtroot+'/bin/zk touch -p /zk/test_nj/zkocc2')
  fd = tempfile.NamedTemporaryFile(dir=utils.tmp_root, delete=False)
  filename1 = fd.name
  fd.write("Test data 1")
  fd.close()
  utils.run(vtroot+'/bin/zk cp '+filename1+' /zk/test_nj/zkocc1/data1')

  fd = tempfile.NamedTemporaryFile(dir=utils.tmp_root, delete=False)
  filename2 = fd.name
  fd.write("Test data 2")
  fd.close()
  utils.run(vtroot+'/bin/zk cp '+filename2+' /zk/test_nj/zkocc1/data2')

  fd = tempfile.NamedTemporaryFile(dir=utils.tmp_root, delete=False)
  filename3 = fd.name
  fd.write("Test data 3")
  fd.close()
  utils.run(vtroot+'/bin/zk cp '+filename3+' /zk/test_nj/zkocc1/data3')

def _check_zk_output(cmd, expected):
  # directly for sanity
  out, err = utils.run(vtroot+'/bin/zk ' + cmd, trap_output=True)
  if out != expected:
    raise utils.TestError('unexpected direct zk output: ', cmd, "is", out, "but expected", expected)

  # using zkocc
  out, err = utils.run(vtroot+'/bin/zk --zk.zkocc-addr=localhost:14850 ' + cmd, trap_output=True)
  if out != expected:
    raise utils.TestError('unexpected zk zkocc output: ', cmd, "is", out, "but expected", expected)

  if utils.options.verbose:
    print "Matched:", out

def _format_time(timeFromBson):
  (tz, val) = timeFromBson
  t = datetime.datetime.fromtimestamp(val/1000)
  return t.strftime("%Y-%m-%d %H:%M:%S")

def run_test_zkocc():
  _populate_zk()

  # preload the test_nj cell
  vtocc_14850 = utils.run_bg(vtroot+'/bin/zkocc -port=14850 -connect-timeout=2s -cache-refresh-interval=1s test_nj')
  time.sleep(1)
  zkocc_client = zkocc.ZkOccConnection("localhost:14850", 30)
  zkocc_client.dial()

  # get test
  out, err = utils.run(vtroot+'/bin/zkclient2 -server localhost:14850 /zk/test_nj/zkocc1/data1', trap_output=True)
  if err != "/zk/test_nj/zkocc1/data1 = Test data 1 (NumChildren=0, Version=0, Cached=false, Stale=false)\n":
    raise utils.TestError('unexpected get output: ', err)
  zkNode = zkocc_client.get("/zk/test_nj/zkocc1/data1")
  if (zkNode['Data'] != "Test data 1" or \
      zkNode['Stat']['NumChildren'] != 0 or \
      zkNode['Stat']['Version'] != 0 or \
      zkNode['Cached'] != True or \
      zkNode['Stale'] != False):
    raise utils.TestError('unexpected zkocc_client.get output: ', zkNode)

  # getv test
  out, err = utils.run(vtroot+'/bin/zkclient2 -server localhost:14850 /zk/test_nj/zkocc1/data1 /zk/test_nj/zkocc1/data2 /zk/test_nj/zkocc1/data3', trap_output=True)
  if err != """[0] /zk/test_nj/zkocc1/data1 = Test data 1 (NumChildren=0, Version=0, Cached=true, Stale=false)
[1] /zk/test_nj/zkocc1/data2 = Test data 2 (NumChildren=0, Version=0, Cached=false, Stale=false)
[2] /zk/test_nj/zkocc1/data3 = Test data 3 (NumChildren=0, Version=0, Cached=false, Stale=false)
""":
    raise utils.TestError('unexpected getV output: ', err)
  zkNodes = zkocc_client.getv(["/zk/test_nj/zkocc1/data1", "/zk/test_nj/zkocc1/data2", "/zk/test_nj/zkocc1/data3"])
  if (zkNodes['Nodes'][0]['Data'] != "Test data 1" or \
      zkNodes['Nodes'][0]['Stat']['NumChildren'] != 0 or \
      zkNodes['Nodes'][0]['Stat']['Version'] != 0 or \
      zkNodes['Nodes'][0]['Cached'] != True or \
      zkNodes['Nodes'][0]['Stale'] != False or \
      zkNodes['Nodes'][1]['Data'] != "Test data 2" or \
      zkNodes['Nodes'][1]['Stat']['NumChildren'] != 0 or \
      zkNodes['Nodes'][1]['Stat']['Version'] != 0 or \
      zkNodes['Nodes'][1]['Cached'] != True or \
      zkNodes['Nodes'][1]['Stale'] != False or \
      zkNodes['Nodes'][2]['Data'] != "Test data 3" or \
      zkNodes['Nodes'][2]['Stat']['NumChildren'] != 0 or \
      zkNodes['Nodes'][2]['Stat']['Version'] != 0 or \
      zkNodes['Nodes'][2]['Cached'] != True or \
      zkNodes['Nodes'][2]['Stale'] != False):
    raise utils.TestError('unexpected zkocc_client.getv output: ', zkNodes)

  # children test
  out, err = utils.run(vtroot+'/bin/zkclient2 -server localhost:14850 -mode children /zk/test_nj', trap_output=True)
  if err != """Path = /zk/test_nj
Child[0] = zkocc1
Child[1] = zkocc2
NumChildren = 2
CVersion = 4
Cached = false
Stale = false
""":
    raise utils.TestError('unexpected children output: ', err)

  # zk command tests
  _check_zk_output("cat /zk/test_nj/zkocc1/data1", "Test data 1")
  _check_zk_output("ls -l /zk/test_nj/zkocc1", """total: 3
-rw-rw-rw- zk zk       11  %s data1
-rw-rw-rw- zk zk       11  %s data2
-rw-rw-rw- zk zk       11  %s data3
""" % (_format_time(zkNodes['Nodes'][0]['Stat']['MTime']),
       _format_time(zkNodes['Nodes'][1]['Stat']['MTime']),
       _format_time(zkNodes['Nodes'][2]['Stat']['MTime'])))

  # start a background process to query the same value over and over again
  # while we kill the zk server and restart it
  outfd = tempfile.NamedTemporaryFile(dir=utils.tmp_root, delete=False)
  filename = outfd.name
  querier = utils.run_bg('/bin/bash -c "while true ; do '+vtroot+'/bin/zkclient2 -server localhost:14850 /zk/test_nj/zkocc1/data1 ; sleep 0.1 ; done"', stderr=outfd.file)
  outfd.close()
  time.sleep(1)

  # kill zk server, sleep a bit, restart zk server, sleep a bit
  utils.run(vtroot+'/bin/zkctl -zk.cfg 1@'+hostname+':3801:3802:3803 shutdown')
  time.sleep(3)
  utils.run(vtroot+'/bin/zkctl -zk.cfg 1@'+hostname+':3801:3802:3803 start')
  time.sleep(3)

  utils.kill_sub_process(querier)

  print "Checking", filename
  fd = open(filename, "r")
  state = 0
  for line in fd:
    if line == "/zk/test_nj/zkocc1/data1 = Test data 1 (NumChildren=0, Version=0, Cached=true, Stale=false)\n":
      stale = False
    elif line == "/zk/test_nj/zkocc1/data1 = Test data 1 (NumChildren=0, Version=0, Cached=true, Stale=true)\n":
      stale = True
    else:
      raise utils.TestError('unexpected line: ', line)
    if state == 0:
      if stale:
        state = 1
    elif state == 1:
      if not stale:
        state = 2
    else:
      if stale:
        raise utils.TestError('unexpected stale state')
  if state != 2:
    raise utils.TestError('unexpected ended stale state')
  fd.close()

  utils.kill_sub_process(vtocc_14850)

def run_test_zkocc_qps():
  _populate_zk()

  # preload the test_nj cell
  vtocc_14850 = utils.run_bg(vtroot+'/bin/zkocc -port=14850 test_nj')
  qpser = utils.run_bg(vtroot+'/bin/zkclient2 -server localhost:14850 -mode qps /zk/test_nj/zkocc1/data1 /zk/test_nj/zkocc1/data2')
  time.sleep(10)
  utils.kill_sub_process(qpser)
  utils.kill_sub_process(vtocc_14850)

def run_all():
  run_test_zkocc()
  run_test_zkocc_qps()

def main():
  parser = OptionParser()
  parser.add_option('-v', '--verbose', action='store_true')
  parser.add_option('-d', '--debug', action='store_true')
  parser.add_option('--skip-teardown', action='store_true')
  (utils.options, args) = parser.parse_args()

  if not args:
    args = ['run_all']

  try:
    if args[0] != 'teardown':
      setup()
      if args[0] != 'setup':
        for arg in args:
          globals()[arg]()
          print "GREAT SUCCESS"
  except KeyboardInterrupt:
    pass
  except utils.Break:
    utils.options.skip_teardown = True
  finally:
    teardown()


if __name__ == '__main__':
  main()