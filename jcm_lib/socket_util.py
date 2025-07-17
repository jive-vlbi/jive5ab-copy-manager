import urllib.request, urllib.error, urllib.parse

def retry_interrupted(func):
    while True:
        try:
            return func()
        except urllib.error.URLError as e:
            # urllib2 doesn't properly set the error number
            if str(e).find("[Errno 4] Interrupted system call") == -1: # not an interrupted system call, fail hard
                raise
        except IOError as e:
            if e.errno != 4: # not an interrupted system call, fail hard
                raise
            
