import urllib2

def retry_interrupted(func):
    while True:
        try:
            return func()
        except urllib2.URLError, e:
            # urllib2 doesn't properly set the error number
            if str(e).find("[Errno 4] Interrupted system call") == -1: # not an interrupted system call, fail hard
                raise
        except IOError, e:
            if e.errno != 4: # not an interrupted system call, fail hard
                raise
            
