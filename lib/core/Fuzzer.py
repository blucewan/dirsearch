import threading
import logging
import signal
from config import *
from lib.connection import *
from .FuzzerDictionary import *
from .NotFoundTester import *

class Fuzzer:
    def __init__(self, requester, dictionary, output, threads=1, recursive=False, excludeInternalServerError=False):
        self.requester = requester
        self.dictionary = dictionary
        self.output = output
        self.excludeInternalServerError = excludeInternalServerError
        self.threads = []
        self.threadsCount = threads
        self.running = False
        self.directories = []
        self.testers = {}
        self.recursive = recursive
        # Setting up testers
        self.testersSetup()
        # Setting up threads  
        self.threadsSetup()
  

    def testersSetup(self):
        if len(self.testers) != 0: self.testers = []
        self.testers['/'] = NotFoundTester(self.requester, "%s/" % (NOT_FOUND_PATH))
        for extension in self.dictionary.getExtensions():
            self.testers[extension] = NotFoundTester(self.requester, "%s.%s" % (NOT_FOUND_PATH, extension))
        

    def threadsSetup(self):
        if len(self.threads) != 0: self.threads = []
        for thread in range(self.threadsCount):
            newThread = threading.Thread(target=self.thread_proc)
            newThread.daemon = True
            self.threads.append(newThread)


    # Get Tester by extension  
    def getTester(self, path):
        for extension in self.testers.keys():
            if path.endswith(extension): return self.testers[extension]
        #By default, returns folder tester
        return self.testers['/']


    def start(self):
        self.dictionary.reset()
        self.runningThreadsCount = len(self.threads)
        self.isRunningCondition = threading.Condition()
        self.finishedCondition = threading.Condition()
        self.runningThreadsCountCondition = threading.Condition()
        self.stoppedByUser = False
        self.running = True
        for thread in self.threads:
            thread.start()


    def wait(self):
        while self.running: continue
        for thread in self.threads:
            while thread.is_alive(): continue

        return


    def testPath(self, path):
        response = self.requester.request(path)
        if self.getTester(path).test(response):
            return 0 if response.status == 404 else response.status

        return 0


    def addDirectory(self, path):
        if not self.recursive: return False
        if path.endswith("/"):
            self.directories.append(path)
            return True
        return False


    def thread_proc(self):
        try:
            while self.running:
                path = self.dictionary.getNextPath()
                if(path == None):
                    self.running = False
                    break
                status = self.testPath(path)
                if status != 0:
                    self.output.printStatusReport(path, status)
                self.output.printLastPathEntry(path)
            self.finishedCondition.acquire()
            self.runningThreadsCountCondition.acquire()
            self.runningThreadsCount = self.runningThreadsCount - 1
            self.runningThreadsCountCondition.release()
            self.finishedCondition.notify()
            self.finishedCondition.release()
        except KeyboardInterrupt, SystemExit:
            self.running = False
            return
        except RequestException as e:
            self.output.printError("Unexpected error:\n{0}".format(e.args[0]['message']))
            pass